import unittest

from tests.group_packages import scraper_test_case


class TestCanalDock(scraper_test_case.ScraperTestCase):
    module = "adventure_games.canal_dock"

    def test_event(self):
        session = self.event(
            "LEAP Intro to Sculling - Boys Thursday Session",
            "2026-11-12T16:00:00-05:00",
        )
        self.assertEqual(
            session.online_address, "https://www.canaldock.org/event-6869064"
        )
        self.assertIn("sculling", session.description)

    def test_date_suffix_is_removed_from_titles(self):
        for title in self.titles():
            self.assertNotRegex(title, r"\(\d+/\d+/\d{4}\)")


if __name__ == "__main__":
    unittest.main()
