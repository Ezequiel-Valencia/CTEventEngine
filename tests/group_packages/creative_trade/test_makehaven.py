import unittest

from tests.group_packages import scraper_test_case


class TestMakeHaven(scraper_test_case.ScraperTestCase):
    module = "creative_trade.makehaven"

    def test_event(self):
        workshop = self.event(
            "Intro to Sewing: Get to Know Your Machine", "2026-11-12T17:30:00-05:00"
        )
        self.assertIn("$71 · Members $61", workshop.description)
        self.assertEqual(
            workshop.online_address,
            "https://www.makehaven.org/civicrm/event/info?id=996&reset=1",
        )
        self.assertTrue(workshop.picture.startswith("https://www.makehaven.org/sites/"))


if __name__ == "__main__":
    unittest.main()
