"""
Run a group package's kernel (``events/group_packages/<package>.json``) through
the engine's own scraper for its calendar type, offline: the package JSON is
read from the repo and each calendar ID is answered with a saved page.

Used for sites that need no custom scraper because a built-in calendar type
(e.g. JSON_LD) handles them; the test checks the JSON entry really works.
"""

import contextlib
import os
from pathlib import Path
from unittest import mock

from calendar_event_engine.parser import package
from calendar_event_engine.scrapers import common as engine_common
from calendar_event_engine.scrapers.json_ld.scraper import JSONLDScraper
from calendar_event_engine.scrapers.rss.scraper import RSSScraper
from calendar_event_engine.types.generics import GenericEvent
from calendar_event_engine.types.submission import ScraperTypes

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGES_DIR = REPO_ROOT / "events" / "group_packages"

_SCRAPERS = {ScraperTypes.JSON_LD: JSONLDScraper, ScraperTypes.RSS: RSSScraper}


class _Response:
    def __init__(self, path: Path):
        self.text = path.read_text()

    def json(self):
        import json

        return json.loads(self.text)

    def raise_for_status(self) -> None:
        pass


class _NeverCached:
    def entry_already_in_cache(self, *_, **__) -> bool:
        return False


def scrape_kernel(
    package_name: str, group_name: str, pages: dict[str, Path]
) -> list[GenericEvent]:
    """
    Events the engine would publish for `group_name`. `pages` maps each of its
    calendar IDs to a saved response. Every date is kept (TEST=True), and
    addresses aren't geocoded, so no request leaves the machine.
    """
    package_path = PACKAGES_DIR / f"{package_name}.json"

    def fake_fetch(url, **_):
        if url == str(package_path):
            return _Response(package_path)
        if url not in pages:
            raise AssertionError(f"No saved page for {url}")
        return _Response(pages[url])

    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.dict(os.environ, {"TEST": "True"}))
        stack.enter_context(
            mock.patch.object(package.httpx2, "get", side_effect=fake_fetch)
        )
        stack.enter_context(
            mock.patch.object(engine_common.httpx2, "get", side_effect=fake_fetch)
        )
        stack.enter_context(
            mock.patch.object(
                engine_common,
                "find_geolocation_from_address",
                side_effect=lambda address, default, title: (address, ""),
            )
        )
        group_package = package.get_group_package(str(package_path))
        for scraper_type, kernels in group_package.scraper_type_and_kernels.items():
            for kernel in kernels:
                if kernel.group_name != group_name:
                    continue
                scraper = _SCRAPERS[scraper_type](_NeverCached())  # type: ignore[arg-type]
                groups = scraper.retrieve_from_source(kernel)
                return [event for group in groups for event in group.events]
    raise AssertionError(f"No kernel {group_name!r} in {package_path}")
