import datetime
import unittest

from calendar_event_engine.types.generics import GenericEvent

from tests.group_packages.http_fixtures import FAKE_GROUP_ID, replay, scraper_class


class ScraperTestCase(unittest.TestCase):
    """
    Runs a custom scraper against its recorded fixtures (see http_fixtures.py)
    and checks every event is publishable. Subclasses set `module` and add
    checks for specific events in the snapshot — update those after
    re-recording the fixtures.
    """

    module: str = ""
    # Some sources legitimately have nothing upcoming at recording time.
    expect_events: bool = True

    @classmethod
    def setUpClass(cls):
        if cls is ScraperTestCase:
            raise unittest.SkipTest("Base class")
        cls.events, cls.now = cls.scrape()

    @classmethod
    def scrape(
        cls, now: datetime.datetime | None = None
    ) -> tuple[list[GenericEvent], datetime.datetime]:
        with replay(cls.module) as recorded_at:
            reference = now or recorded_at
            scraper = scraper_class(cls.module)(FAKE_GROUP_ID, now=reference)
            groups = scraper.retrieve_from_source(None)
        assert len(groups) == 1
        return groups[0].events, reference

    def event(self, title: str, begins_on: str) -> GenericEvent:
        for event in self.events:
            if event.title == title and event.begins_on == begins_on:
                return event
        found = "\n".join(f"{e.begins_on} {e.title}" for e in self.events)
        self.fail(f"No event {title!r} at {begins_on}. Scraped:\n{found}")

    def titles(self) -> set[str]:
        return {event.title for event in self.events}

    def test_events_are_publishable(self):
        if self.expect_events:
            self.assertGreater(len(self.events), 0)
        scraper = scraper_class(self.module)
        horizon = self.now + datetime.timedelta(days=scraper.days_ahead)
        for event in self.events:
            with self.subTest(event=event.title):
                self.assertTrue(event.title.strip())
                self.assertTrue(event.description)
                begins = datetime.datetime.fromisoformat(event.begins_on)
                self.assertIsNotNone(begins.tzinfo, "begins_on needs an offset")
                self.assertTrue(self.now <= begins <= horizon)
                if event.ends_on:
                    self.assertGreaterEqual(
                        datetime.datetime.fromisoformat(event.ends_on), begins
                    )
                self.assertIsNotNone(event.physical_address)
                self.assertTrue((event.online_address or "").startswith("http"))
                mobilizon = event.publisher_specific_info["mobilizon"]
                self.assertEqual(mobilizon["groupID"], FAKE_GROUP_ID)
                self.assertEqual(mobilizon["defaultCategory"], scraper.category.name)

    def test_no_duplicates(self):
        keys = [(event.title, event.begins_on) for event in self.events]
        self.assertEqual(len(keys), len(set(keys)))
