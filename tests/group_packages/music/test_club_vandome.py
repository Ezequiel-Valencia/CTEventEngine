import unittest

from tests.group_packages import scraper_test_case


class TestClubVandome(scraper_test_case.ScraperTestCase):
    module = "music.club_vandome"

    def test_event_start_prefers_run_time_over_class_time(self):
        # "Salsa class starts at 9:10pm ... Event runs from 9pm to 2am"
        self.event(
            "Friday, November 13th. Bachata Lovers Event", "2026-11-13T21:00:00-05:00"
        )


if __name__ == "__main__":
    unittest.main()
