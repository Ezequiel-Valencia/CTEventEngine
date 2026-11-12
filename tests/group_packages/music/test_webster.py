import unittest

from tests.group_packages import scraper_test_case


class TestWebster(scraper_test_case.ScraperTestCase):
    module = "music.webster"

    def test_event(self):
        disco = self.event("GIMME GIMME DISCO", "2026-11-13T21:30:00-05:00")
        self.assertIn("The Webster Underground", disco.description)
        self.assertIn("Ages 18 and up", disco.description)
        self.assertTrue(
            disco.picture.startswith("https://thewebsterct.com/wp-content/")
        )


if __name__ == "__main__":
    unittest.main()
