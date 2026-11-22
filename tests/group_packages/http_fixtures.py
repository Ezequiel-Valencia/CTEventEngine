"""
Record and replay the HTTP responses a custom scraper makes, so its tests run
offline against a fixed snapshot of the site.

Each scraper's snapshot lives in ``<group>/fixtures/<scraper_module>/``: one
file per response plus ``manifest.json``, which maps request URLs to files and
stores the time of the recording (used as the scraper's "now" in tests).

Re-record a scraper when its site changes, e.g.:
    uv run python -m tests.group_packages.http_fixtures music.webster
"""

import argparse
import contextlib
import datetime
import importlib
import inspect
import json
import os
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from unittest import mock

import requests
from bs4 import BeautifulSoup, Comment

from ct_event_engine.Websites.group_packages import common
from ct_event_engine.Websites.group_packages.common import EASTERN, VenueScraper

GROUP_PACKAGES_DIR = Path(__file__).resolve().parent
PACKAGE = "ct_event_engine.Websites.group_packages"
FAKE_GROUP_ID = 1


def fixture_dir(module: str) -> Path:
    """`module` is relative to the group_packages package, e.g. "music.webster"."""
    group, name = module.split(".")
    return GROUP_PACKAGES_DIR / group / "fixtures" / name


def _request_url(url: str, params: dict | None) -> str:
    prepared = requests.Request("GET", url, params=params).prepare().url
    assert prepared is not None
    return prepared


def _slim_html(text: str) -> str:
    """Drop what the scrapers never read (scripts, styles, svgs) to keep fixtures small."""
    soup = BeautifulSoup(text, "html.parser")
    for tag in soup(["style", "svg", "noscript", "iframe", "link"]):
        tag.decompose()
    for script in soup.find_all("script"):
        if script.get("type") != "application/ld+json":
            script.decompose()
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    return re.sub(r"\n\s*\n+", "\n", str(soup))


class _FakeResponse:
    def __init__(self, url: str, body: bytes, status_code: int = 200):
        self.url = url
        self.content = body
        self.status_code = status_code

    @property
    def text(self) -> str:
        return self.content.decode("utf-8")

    def json(self):
        return json.loads(self.content)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} for {self.url}")


@contextlib.contextmanager
def replay(module: str) -> Iterator[datetime.datetime]:
    """Serve recorded responses; yields the time the snapshot was taken."""
    directory = fixture_dir(module)
    manifest = json.loads((directory / "manifest.json").read_text())

    def fake_get(url, params=None, **_):
        key = _request_url(url, params)
        if key not in manifest["responses"]:
            raise AssertionError(f"No recorded response for {key}")
        body = (directory / manifest["responses"][key]).read_bytes()
        return _FakeResponse(key, body)

    # TEST=True turns off the engine's own date filter (used by scrapers that
    # call its parsers), which would otherwise compare against the real date.
    with (
        mock.patch.object(common.requests, "get", side_effect=fake_get),
        mock.patch.dict(os.environ, {"TEST": "True"}),
    ):
        yield datetime.datetime.fromisoformat(manifest["recorded_at"])


def scraper_class(module: str) -> type[VenueScraper]:
    loaded = importlib.import_module(f"{PACKAGE}.{module}")
    classes = [
        value
        for value in vars(loaded).values()
        if inspect.isclass(value)
        and issubclass(value, VenueScraper)
        and value.__module__ == loaded.__name__
    ]
    assert len(classes) == 1, f"Expected one scraper in {module}, found {classes}"
    return classes[0]


def record(module: str) -> int:
    """Run the scraper against the live site and save every response."""
    directory = fixture_dir(module)
    directory.mkdir(parents=True, exist_ok=True)
    for old in directory.iterdir():
        old.unlink()
    now = datetime.datetime.now(EASTERN).replace(microsecond=0)
    responses: dict[str, str] = {}
    real_get = requests.get

    def recording_get(url, params=None, **kwargs):
        response = real_get(url, params=params, **kwargs)
        key = _request_url(url, params)
        content_type = response.headers.get("Content-Type", "")
        if "json" in content_type:
            extension, body = "json", response.content
        elif "xml" in content_type or "rss" in content_type:
            extension, body = "xml", response.content
        else:
            extension = "html"
            body = _slim_html(response.text).encode("utf-8")
        name = f"{len(responses):03d}.{extension}"
        (directory / name).write_bytes(body)
        responses[key] = name
        return _FakeResponse(key, body, response.status_code)

    with (
        mock.patch.object(common.requests, "get", side_effect=recording_get),
        mock.patch.dict(os.environ, {"TEST": "True"}),
    ):
        scraper = scraper_class(module)(FAKE_GROUP_ID, now=now)
        events = scraper.retrieve_from_source(None)[0].events

    manifest = {"recorded_at": now.isoformat(), "responses": responses}
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return len(events)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("modules", nargs="+", help='e.g. "music.webster"')
    for module_name in parser.parse_args().modules:
        print(f"{module_name}: {record(module_name)} events", file=sys.stderr)
