import unittest

from tests.group_packages import scraper_test_case


class TestToadsPlace(scraper_test_case.ScraperTestCase):
    module = "music.toads_place"

    def test_event(self):
        party = self.event("HYPERSONIC GLOW PARTY", "2026-11-13T21:00:00-05:00")
        self.assertIn("Advance Tickets From: $15.00", party.description)
        self.assertTrue(
            party.online_address.startswith("https://www.etix.com/ticket/p/")
        )

    def test_show_time_is_used_over_doors(self):
        show = self.event("Live Nation Presents: POUYA", "2026-11-18T19:30:00-05:00")
        self.assertIn("Show 7:30pm", show.description.replace("| ", ""))


if __name__ == "__main__":
    unittest.main()
