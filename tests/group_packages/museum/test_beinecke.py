import unittest

from tests.group_packages import scraper_test_case


class TestBeinecke(scraper_test_case.ScraperTestCase):
    module = "museum.beinecke"

    def test_tour_occurrence_is_converted_from_utc(self):
        tour = self.event("Beinecke Library Tour", "2026-11-13T13:30:00-05:00")
        self.assertIn("introductory tour", tour.description)

    def test_dated_event(self):
        orientation = self.event(
            "Learning to Use Yale Special Collections: A New User Orientation for the New Haven Community",
            "2026-11-14T09:30:00-05:00",
        )
        self.assertTrue(orientation.picture.startswith("https://library.yale.edu/"))


if __name__ == "__main__":
    unittest.main()
