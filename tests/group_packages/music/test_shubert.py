import unittest

from tests.group_packages import scraper_test_case


class TestShubert(scraper_test_case.ScraperTestCase):
    """The fixture is trimmed to two productions: Grease and Riverdance 30."""

    module = "music.shubert"

    def test_each_performance_is_an_event(self):
        self.assertEqual(
            [e.begins_on for e in self.events if e.title == "Grease"],
            [
                "2026-11-13T19:00:00-05:00",
                "2026-11-14T14:00:00-05:00",
                "2026-11-14T19:00:00-05:00",
            ],
        )
        grease = self.events[0]
        self.assertIn("Sacred Heart Academy presents", grease.description)
        self.assertIn("GREASE is the word", grease.description)

    def test_run_starting_after_the_window_is_not_fetched(self):
        # Riverdance opens in January; its detail page isn't in the fixtures,
        # so fetching it would fail the test.
        self.assertNotIn("Riverdance 30", self.titles())


if __name__ == "__main__":
    unittest.main()
