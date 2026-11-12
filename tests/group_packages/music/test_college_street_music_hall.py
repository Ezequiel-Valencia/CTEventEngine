import unittest

from tests.group_packages import scraper_test_case


class TestCollegeStreetMusicHall(scraper_test_case.ScraperTestCase):
    module = "music.college_street_music_hall"

    def test_show_time_is_local(self):
        # The widget writes "2026-11-15T19:30:00+00:00" for a 7:30 pm show.
        show = self.event("Big Head Todd and the Monsters", "2026-11-15T19:30:00-05:00")
        self.assertIn("Show: 7:30 pm", show.description)
        self.assertTrue(show.online_address.startswith("https://www.eventbrite.com/e/"))

    def test_invisible_characters_are_removed(self):
        for event in self.events:
            self.assertNotIn("‎", event.description)


if __name__ == "__main__":
    unittest.main()
