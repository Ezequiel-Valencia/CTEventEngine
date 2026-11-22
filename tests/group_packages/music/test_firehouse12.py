import unittest

from tests.group_packages import scraper_test_case


class TestFirehouse12(scraper_test_case.ScraperTestCase):
    module = "music.firehouse12"

    def test_event(self):
        show = self.event(
            "Wadada Leo Smith & Sylvie Courvoisier", "2026-11-13T20:30:00-05:00"
        )
        self.assertEqual(
            show.online_address, "https://firehouse12.com/jazz-series/2026/11/13"
        )
        self.assertIn("trumpet", show.description)
        self.assertTrue(show.picture.startswith("https://images.squarespace-cdn.com/"))

    def test_past_and_far_off_listings_are_left_out(self):
        self.assertNotIn("Fall 2026 Season Pass", self.titles())  # Began in September
        self.assertNotIn("Dirty Projectors (solo)", self.titles())  # April 2027


if __name__ == "__main__":
    unittest.main()
