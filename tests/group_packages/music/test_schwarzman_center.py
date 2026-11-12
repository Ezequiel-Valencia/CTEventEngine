import unittest

from tests.group_packages import scraper_test_case


class TestSchwarzmanCenter(scraper_test_case.ScraperTestCase):
    module = "music.schwarzman_center"

    def test_event(self):
        session = self.event(
            "Schwarzman Session - Accessibility as a Core Value from Ideation to Opening Night with DJ Kurs",
            "2026-11-18T12:00:00-05:00",
        )
        self.assertTrue(
            session.description.startswith("Location: Humanities Quadrangle")
        )
        self.assertEqual(
            session.online_address,
            "https://schwarzman.yale.edu/events/schwarzman-session-accessibility-core-value-ideation-opening-night-dj-kurs",
        )
        self.assertTrue(session.picture.startswith("https://schwarzman.yale.edu/"))
        self.assertEqual(session.physical_address.street, "168 Grove St")

    def test_window_matches_the_engine(self):
        # Nov 30 is past the engine's 7 day window from the Nov 12 snapshot.
        self.assertNotIn("Karim Sulayman & Tom Poster", self.titles())


if __name__ == "__main__":
    unittest.main()
