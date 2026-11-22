import json
import os
import unittest
from pathlib import Path
from unittest import mock

from calendar_event_engine import Runner
from calendar_event_engine.db.db_cache import SQLiteDB
from calendar_event_engine.parser import package as package_parser
from calendar_event_engine.types.custom_scraper import CustomScraperJob
from calendar_event_engine.types.generics import GenericEvent
from calendar_event_engine.types.submission import (
    AllEventsFromAGroup,
    GroupEventsKernel,
    ScraperTypes,
)
from calendar_event_engine.types.submission_handlers import RunnerSubmission

from ct_event_engine import sites
from ct_event_engine.sites import Site, build_publishers, route_event, site_of

PACKAGES_DIR = Path(__file__).resolve().parent.parent / "events" / "group_packages"


def event(title: str, group_id: int | None = 1) -> GenericEvent:
    return GenericEvent(
        publisher_specific_info={"mobilizon": {"groupID": group_id}},
        title=title,
        begins_on="2026-11-21T20:00:00-05:00",
        # Text never matters: only the source's tag does.
        description="Kids welcome! All ages, family friendly.",
    )


def kernel(name: str, source_info: dict) -> GroupEventsKernel:
    return GroupEventsKernel(
        GenericEvent(publisher_specific_info={}, title="", begins_on=""),
        name,
        [f"https://{name}.example"],
        ScraperTypes.CUSTOM,
        "",
        source_info=source_info,
    )


class TestRouteEvent(unittest.TestCase):
    def test_follows_the_source_tag(self):
        self.assertEqual(
            route_event(event("Tour"), kernel("m", {"family_friendly": True})),
            "ctgrassroots",
        )
        self.assertEqual(
            route_event(event("Show"), kernel("c", {"family_friendly": False})),
            "underground",
        )

    def test_untagged_sources_and_groupless_events_are_skipped(self):
        for info in ({}, {"family_friendly": "true"}, {"family_friendly": None}):
            with self.subTest(info=info):
                self.assertIsNone(route_event(event("A"), kernel("x", info)))
        self.assertIsNone(
            route_event(
                event("B", group_id=None), kernel("y", {"family_friendly": False})
            )
        )


class TestBuildPublishers(unittest.TestCase):
    def setUp(self):
        self.cache = SQLiteDB(test_mode=True)
        self.addCleanup(self.cache.close)

    def test_one_publisher_per_site_with_its_endpoint(self):
        env = {
            "MOBILIZON_ENDPOINT": "https://ctgrassroots.org/api",
            "UNDERGROUND_MOBILIZON_ENDPOINT": "https://underground.ctgrassroots.org/api",
        }
        with mock.patch.dict(os.environ, env):
            publishers = build_publishers(False, self.cache)
        self.assertEqual(
            {name: p.endpoint for name, p in publishers.items()},  # type: ignore[attr-defined]
            {
                "ctgrassroots": "https://ctgrassroots.org/api",
                "underground": "https://underground.ctgrassroots.org/api",
            },
        )

    def test_no_underground_publisher_without_its_endpoint(self):
        # Otherwise its uploader would fall back to MOBILIZON_ENDPOINT.
        env = {"MOBILIZON_ENDPOINT": "https://ctgrassroots.org/api"}
        with mock.patch.dict(os.environ, env, clear=True):
            publishers = build_publishers(False, self.cache)
        self.assertEqual(list(publishers), ["ctgrassroots"])

    def test_test_mode_has_both(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                set(build_publishers(True, self.cache)), {s.value for s in Site}
            )


class _FakeScraper:
    def __init__(self, group: AllEventsFromAGroup):
        self.group = group

    def connect_to_source(self) -> None:
        pass

    def close_connection_to_source(self) -> None:
        pass

    def retrieve_from_source(self, _kernel):
        return [self.group]


class TestEngineRouting(unittest.TestCase):
    """The engine's own runner, with this repo's publishers and router."""

    def run_engine(self, env: dict, *groups: AllEventsFromAGroup) -> dict:
        cache = SQLiteDB(test_mode=True)
        self.addCleanup(cache.close)
        with mock.patch.dict(os.environ, env, clear=True):
            publishers = build_publishers(False, cache)
        uploaded: dict[str, list[str]] = {}
        for name, publisher in publishers.items():
            publisher.connect = mock.Mock()  # type: ignore[method-assign]
            publisher.close = mock.Mock()  # type: ignore[method-assign]
            publisher.upload = mock.Mock(  # type: ignore[method-assign]
                side_effect=lambda batch, name=name: uploaded.setdefault(
                    name, []
                ).extend(e.title for g in batch for e in g.events)
            )
        jobs = [
            CustomScraperJob(g.event_kernel.group_name, "", _FakeScraper(g))  # type: ignore[arg-type]
            for g in groups
        ]
        Runner._runner(
            RunnerSubmission(cache, {}, True, {}),
            custom_scrapers=jobs,
            publishers=publishers,
            route_event=sites.route_event,
        )
        return uploaded

    def group(self, name, info, *events) -> AllEventsFromAGroup:
        return AllEventsFromAGroup(list(events), kernel(name, info), name)

    def test_each_source_reaches_only_its_site(self):
        env = {
            "MOBILIZON_ENDPOINT": "https://ctgrassroots.org/api",
            "UNDERGROUND_MOBILIZON_ENDPOINT": "https://underground.ctgrassroots.org/api",
        }
        uploaded = self.run_engine(
            env,
            self.group("museum", {"family_friendly": True}, event("Tour")),
            self.group("club", {"family_friendly": False}, event("Club Night")),
            self.group("untagged", {}, event("Lost")),
        )
        self.assertEqual(
            uploaded, {"ctgrassroots": ["Tour"], "underground": ["Club Night"]}
        )

    def test_underground_events_never_reach_ctgrassroots(self):
        env = {"MOBILIZON_ENDPOINT": "https://ctgrassroots.org/api"}
        uploaded = self.run_engine(
            env,
            self.group("museum", {"family_friendly": True}, event("Tour")),
            self.group("club", {"family_friendly": False}, event("Club Night")),
        )
        self.assertEqual(uploaded, {"ctgrassroots": ["Tour"]})


class _Response:
    def __init__(self, path: Path):
        self.text = path.read_text()

    def json(self):
        return json.loads(self.text)

    def raise_for_status(self) -> None:
        pass


class TestGroupPackages(unittest.TestCase):
    def test_every_entry_is_tagged_at_the_source(self):
        for path in sorted(PACKAGES_DIR.glob("*.json")):
            entries = json.loads(path.read_text()).get("groupKernels", {})
            for name, entry in entries.items():
                with self.subTest(package=path.stem, entry=name):
                    self.assertIsInstance(entry.get("family_friendly"), bool)
                    self.assertNotIn("family_friendly", entry["publisherInfo"])

    def test_engine_keeps_the_tag_on_each_kernel(self):
        path = PACKAGES_DIR / "misc.json"
        with mock.patch.object(
            package_parser.httpx2, "get", return_value=_Response(path)
        ):
            group_package = package_parser.get_group_package(str(path))
        found = {
            k.group_name: site_of(k)
            for kernels in group_package.scraper_type_and_kernels.values()
            for k in kernels
        }
        entries = json.loads(path.read_text())["groupKernels"]
        expected = {
            name: Site.CTGRASSROOTS if entry["family_friendly"] else Site.UNDERGROUND
            for name, entry in entries.items()
        }
        self.assertEqual(found, expected)


if __name__ == "__main__":
    unittest.main()
