import unittest
from pathlib import Path

from tests.group_packages.package_kernels import scrape_kernel

FIXTURES = Path(__file__).parent / "fixtures" / "sea_tea_improv_json_ld"


class TestSeaTeaImprovJsonLd(unittest.TestCase):
    """Sea Tea is scraped by the engine's JSON_LD calendar type (misc.json)."""

    @classmethod
    def setUpClass(cls):
        cls.events = scrape_kernel(
            "misc",
            "Sea Tea Improv",
            {"https://seateaimprov.com/calendar/": FIXTURES / "calendar.html"},
        )

    def event(self, title: str):
        return next(e for e in self.events if e.title == title)

    def test_all_listed_events_are_read(self):
        self.assertEqual(len(self.events), 44)

    def test_show_is_at_the_theater(self):
        show = self.event("The Deep End: Hartford's Weekly Improv Show")
        self.assertEqual(show.begins_on, "2026-11-14T00:00:00+00:00")  # 7 pm ET
        self.assertEqual(show.physical_address.street, "15 Asylum Street")
        self.assertEqual(show.physical_address.locality, "Hartford")
        self.assertEqual(
            show.online_address, "https://seateaimprov.com/event/2003876900753/"
        )
        mobilizon = show.publisher_specific_info["mobilizon"]
        self.assertEqual(mobilizon["defaultCategory"], "comedy")

    def test_class_uses_the_studio_address_from_the_page(self):
        course = self.event("Improv 201: The Game")
        self.assertEqual(course.physical_address.description, "Sea Tea Improv Studios")


if __name__ == "__main__":
    unittest.main()
