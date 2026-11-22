import unittest
from pathlib import Path

from tests.group_packages.package_kernels import scrape_kernel

FIXTURES = Path(__file__).parent / "fixtures" / "nxthvn_json_ld"


class TestNxthvnJsonLd(unittest.TestCase):
    """NXTHVN is scraped by the engine's JSON_LD calendar type (museum.json)."""

    @classmethod
    def setUpClass(cls):
        cls.events = scrape_kernel(
            "museum",
            "NXTHVN",
            {"https://www.nxthvn.com/calendar/": FIXTURES / "calendar.html"},
        )

    def test_event(self):
        mahjong = next(e for e in self.events if e.title == "Learn Mahjong")
        self.assertEqual(mahjong.begins_on, "2026-12-03T14:00:00-05:00")
        self.assertEqual(mahjong.physical_address.street, "169 Henry St")
        self.assertTrue(mahjong.picture.startswith("https://www.nxthvn.com/"))
        self.assertEqual(
            mahjong.publisher_specific_info["mobilizon"]["defaultCategory"], "arts"
        )


if __name__ == "__main__":
    unittest.main()
