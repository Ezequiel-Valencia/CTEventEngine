import unittest

from tests.group_packages import scraper_test_case


class TestSpaceBallroom(scraper_test_case.ScraperTestCase):
    module = "music.space_ballroom"

    def test_event_is_read_from_eventbrite(self):
        show = self.event("Tune-Yards", "2026-11-16T20:00:00-05:00")
        self.assertEqual(
            show.online_address.split("/e/", 1)[0], "https://www.eventbrite.com"
        )
        self.assertTrue(show.picture.startswith("https://img.evbuc.com/"))
        self.assertIn("with Rituals of Mine", show.description)

    def test_description_is_the_overview_not_the_summary(self):
        # The JSON-LD summary of this one is a lone invisible character.
        moved = self.event(
            "MOVED TO DISTRICT MUSIC HALL: High Vis", "2026-11-14T20:00:00-05:00"
        )
        self.assertIn("MOVED to District Music Hall", moved.description)


if __name__ == "__main__":
    unittest.main()
