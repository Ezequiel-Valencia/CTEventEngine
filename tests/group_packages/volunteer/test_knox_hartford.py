import unittest

from tests.group_packages import scraper_test_case


class TestKnoxHartford(scraper_test_case.ScraperTestCase):
    module = "volunteer.knox_hartford"

    def test_uses_wall_clock_time_despite_wrong_site_timezone(self):
        # The site is set to America/Halifax; the event is at 5 pm in Hartford.
        self.event(
            "The Betty Bash: A 60th Anniversary Celebration!",
            "2026-11-12T17:00:00-05:00",
        )

    def test_offsite_venue_gets_its_own_address(self):
        bash = self.event(
            "The Betty Bash: A 60th Anniversary Celebration!",
            "2026-11-12T17:00:00-05:00",
        )
        self.assertEqual(bash.physical_address.street, "1 Jewell Street")
        market = self.event("KNOX Harvest Market", "2026-11-21T10:00:00-05:00")
        self.assertEqual(market.physical_address.latitude, 41.758933)


if __name__ == "__main__":
    unittest.main()
