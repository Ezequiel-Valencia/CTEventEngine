import datetime
import unittest

from bs4 import BeautifulSoup

from ct_event_engine.Websites.group_packages.common import (
    EASTERN,
    attr_of,
    clean,
    html_to_text,
    infer_year,
    og_meta,
    parse_clock,
    text_of,
    upcoming_datetime,
)


class TestParseClock(unittest.TestCase):
    def test_formats(self):
        cases = {
            "7:30 pm": datetime.time(19, 30),
            "7pm": datetime.time(19, 0),
            "9:30–11 am": datetime.time(9, 30),
            "3–4:15 pm": datetime.time(15, 0),
            "2-4 p.m.": datetime.time(14, 0),
            "12pm–1:30pm": datetime.time(12, 0),
            "Doors: 9 pm // Show: 9:30 pm": datetime.time(21, 0),
            "noon": datetime.time(12, 0),
            "Saturday, 3:30–5:30 pm, 11/14": datetime.time(15, 30),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_clock(text), expected)

    def test_numbers_that_are_not_times(self):
        for text in ("Nov 13", "Call (203) 789-2066", "11/14", ""):
            with self.subTest(text=text):
                self.assertIsNone(parse_clock(text))


class TestInferYear(unittest.TestCase):
    today = datetime.date(2026, 11, 12)

    def test_upcoming_this_year(self):
        self.assertEqual(infer_year(11, 13, self.today), 2026)
        self.assertEqual(infer_year(12, 31, self.today), 2026)

    def test_recently_passed_stays_this_year(self):
        self.assertEqual(infer_year(11, 1, self.today), 2026)

    def test_early_months_are_next_year(self):
        self.assertEqual(infer_year(2, 20, self.today), 2027)


class TestText(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(clean("  a&amp;b‎ \n c "), "a&b c")

    def test_html_to_text_keeps_paragraphs(self):
        self.assertEqual(
            html_to_text("<p>One<br>two</p><p>Three</p>"), "One\ntwo\nThree"
        )


class TestUpcomingDatetime(unittest.TestCase):
    today = datetime.date(2026, 11, 12)
    default = datetime.time(20, 0)

    def test_clock_and_inferred_year(self):
        self.assertEqual(
            upcoming_datetime(2, 20, datetime.time(9, 30), self.today, self.default),
            EASTERN.localize(datetime.datetime(2027, 2, 20, 9, 30)),
        )

    def test_default_time(self):
        self.assertEqual(
            upcoming_datetime(11, 13, None, self.today, self.default),
            EASTERN.localize(datetime.datetime(2026, 11, 13, 20, 0)),
        )

    def test_impossible_day(self):
        self.assertIsNone(upcoming_datetime(11, 31, None, self.today, self.default))


class TestSoupHelpers(unittest.TestCase):
    soup = BeautifulSoup(
        '<meta property="og:image" content="https://x.org/a.png">'
        '<div class="card"><h3> A &amp;  B </h3><img src="/b.png"><img alt="no src"></div>',
        "html.parser",
    )

    def test_text_of(self):
        self.assertEqual(text_of(self.soup, ".card h3"), "A & B")
        self.assertEqual(text_of(self.soup, ".missing"), "")
        self.assertEqual(text_of(None), "")

    def test_attr_of(self):
        self.assertEqual(attr_of(self.soup, "img", "src"), "/b.png")
        self.assertEqual(
            attr_of(self.soup, "img", "src", base="https://x.org/e/"),
            "https://x.org/b.png",
        )
        self.assertIsNone(attr_of(self.soup, "img[alt]", "src"))
        self.assertIsNone(attr_of(None, "img", "src"))

    def test_og_meta(self):
        self.assertEqual(og_meta(self.soup, "image"), "https://x.org/a.png")
        self.assertIsNone(og_meta(self.soup, "description"))


if __name__ == "__main__":
    unittest.main()
