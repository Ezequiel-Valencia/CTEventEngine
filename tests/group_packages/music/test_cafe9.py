import unittest

from tests.group_packages import scraper_test_case


class TestCafe9(scraper_test_case.ScraperTestCase):
    module = "music.cafe9"

    def test_event(self):
        jam = self.event(
            "Saturday Jazz Jam ft. Gary Grippo - Saturday 11/14/2026 - 4:00 PM EDT",
            "2026-11-14T16:00:00-05:00",
        )
        self.assertIn("Saturday Afternoon Jazz Jam", jam.description)
        self.assertTrue(jam.online_address.startswith("https://cafenine.com/products/"))
        self.assertTrue(jam.picture.startswith("https://speedy.uenicdn.com/"))


if __name__ == "__main__":
    unittest.main()
