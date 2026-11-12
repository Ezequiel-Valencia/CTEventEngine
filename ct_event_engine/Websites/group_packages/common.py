"""
Shared building blocks for the custom scrapers that live in the group package
subfolders (one subfolder per ``events/group_packages/<package>.json``).

A concrete scraper subclasses ``VenueScraper`` and only implements ``scrape``;
the base class takes care of the date window, the Mobilizon metadata and the
default venue address.
"""

import datetime
import html
import re
from abc import abstractmethod
from urllib.parse import urljoin

import pytz
import requests
from bs4 import BeautifulSoup, Tag
from calendar_event_engine.publishers.mobilizon.types import EventParameters
from calendar_event_engine.scrapers.abc_scraper import Scraper
from calendar_event_engine.types.generics import GenericAddress, GenericEvent
from calendar_event_engine.types.submission import (
    AllEventsFromAGroup,
    GroupEventsKernel,
    ScraperTypes,
)

from ct_event_engine.logger import create_logger_from_designated_logger

logger = create_logger_from_designated_logger(__name__)

EASTERN = pytz.timezone("America/New_York")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}
REQUEST_TIMEOUT_SECONDS = 30
MONTHS = {
    name: number
    for number in range(1, 13)
    for name in (
        datetime.date(2000, number, 1).strftime("%B").lower(),
        datetime.date(2000, number, 1).strftime("%b").lower(),
    )
}
MONTHS["sept"] = 9

# "7", "7:30", "7pm", "7:30 p.m." ... The meridiem is optional so that ranges
# such as "9:30–11 am" can borrow it from the end of the range.
_CLOCK = re.compile(r"(?<![\d:])(\d{1,2})(?::(\d{2}))?\s*(?:([ap])\.?\s*m\b\.?)?", re.I)
_NOON = re.compile(r"\bnoon\b", re.I)
# Zero width spaces/joiners, direction marks and the BOM.
_INVISIBLE = re.compile("[​-‏⁠﻿]")


def fetch(url: str, params: dict | None = None) -> requests.Response:
    response = requests.get(
        url, headers=HEADERS, params=params, timeout=REQUEST_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    return response


def fetch_soup(url: str, params: dict | None = None) -> BeautifulSoup:
    return BeautifulSoup(fetch(url, params).text, "html.parser")


def html_to_text(markup: str | None) -> str:
    """Plain text from an HTML fragment, keeping paragraph breaks."""
    if not markup:
        return ""
    # The separator also splits text around <br>, so it needs no handling.
    text = BeautifulSoup(markup, "html.parser").get_text("\n")
    lines = [re.sub(r"[ \t\xa0]+", " ", line).strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def clean(text: str | None) -> str:
    """Collapse whitespace, drop invisible format characters, decode entities."""
    text = _INVISIBLE.sub("", html.unescape(text or ""))
    return re.sub(r"\s+", " ", text).strip()


def localize(naive: datetime.datetime) -> datetime.datetime:
    return EASTERN.localize(naive)


def parse_clock(text: str) -> datetime.time | None:
    """
    First clock time in `text`, e.g. "Doors 6:30pm | Show 7:30pm" -> 18:30,
    "9:30–11 am" -> 9:30, "noon" -> 12:00. A time without am/pm takes the next
    meridiem written after it; with none at all it is read as pm, since venues
    rarely write out evening times in full.
    """
    noon = _NOON.search(text)
    matches = list(_CLOCK.finditer(text))
    for index, match in enumerate(matches):
        if noon and noon.start() < match.start():
            break
        hour, minute, meridiem = int(match.group(1)), match.group(2), match.group(3)
        # A bare number ("3") only counts as the start of a range ("3–4:15 pm").
        starts_range = re.match(r"\s*[-–—]", text[match.end() :]) is not None
        if minute is None and meridiem is None and not starts_range:
            continue
        if not (1 <= hour <= 12 and int(minute or 0) < 60):
            continue
        if meridiem is None:
            later = (m.group(3) for m in matches[index + 1 :] if m.group(3))
            meridiem = next(later, "p")
        hour = hour % 12 + (12 if meridiem.lower() == "p" else 0)
        return datetime.time(hour, int(minute or 0))
    return datetime.time(12, 0) if noon else None


def infer_year(month: int, day: int, today: datetime.date) -> int:
    """
    Year of a date written without one ("Fri, Nov 13"). Listings only show
    upcoming events, so a date well before today belongs to next year.
    """
    year = today.year
    try:
        candidate = datetime.date(year, month, day)
    except ValueError:  # Feb 29 on a non leap year
        return year + 1
    if candidate < today - datetime.timedelta(days=60):
        return year + 1
    return year


def month_number(name: str) -> int | None:
    return MONTHS.get(name.strip(" .,/").lower())


def first_image_from_srcset(srcset: str) -> str:
    return srcset.split(",", 1)[0].strip().split(" ")[0]


def text_of(node: Tag | None, selector: str | None = None) -> str:
    """Cleaned text of `node`, or of its first match for `selector`; "" if absent."""
    if node is not None and selector is not None:
        node = node.select_one(selector)
    return clean(node.get_text(" ")) if node is not None else ""


def attr_of(
    node: Tag | None, selector: str, attribute: str, base: str | None = None
) -> str | None:
    """
    `attribute` of the first match for `selector`, resolved against `base`
    when given; None when the element or attribute is missing.
    """
    element = node.select_one(selector) if node is not None else None
    if element is None or not element.get(attribute):
        return None
    value = str(element[attribute])
    return urljoin(base, value) if base else value


def og_meta(soup: BeautifulSoup, name: str) -> str | None:
    """Content of an Open Graph tag, e.g. og_meta(soup, "image")."""
    meta = soup.find("meta", property=f"og:{name}")
    content = meta.get("content") if isinstance(meta, Tag) else None
    return str(content) if content else None


def upcoming_datetime(
    month: int,
    day: int,
    clock: datetime.time | None,
    today: datetime.date,
    default: datetime.time,
) -> datetime.datetime | None:
    """
    Local start time of a listing written without a year ("Fri, Nov 13" plus
    some time text). None when the day doesn't exist.
    """
    try:
        date = datetime.date(infer_year(month, day, today), month, day)
    except ValueError:
        return None
    return localize(datetime.datetime.combine(date, clock or default))


class VenueScraper(Scraper):
    """
    Base for a single venue/organization. Subclasses set the class attributes
    and implement ``scrape``.

    Args:
        group_id: Mobilizon group the events are published under. Create the
            group with ``scripts/mobilizon_group.py`` to get one.
        default_image_id: Optional Mobilizon media used as the event picture.
        now: Reference time for the date window; defaults to the current time.
    """

    name: str
    url: str
    address: GenericAddress | None = None
    category: EventParameters.Categories = EventParameters.Categories.default
    tags: list[str] = []
    # Events starting further out than this are left for a later run.
    days_ahead: int = 31
    # Start time for a listing whose time can't be read.
    default_start_time: datetime.time = datetime.time(19, 0)

    def __init__(
        self,
        group_id: int,
        default_image_id: str | None = None,
        now: datetime.datetime | None = None,
    ):
        self.group_id = group_id
        self.default_image_id = default_image_id
        self._now = now

    @property
    def now(self) -> datetime.datetime:
        if self._now is not None:
            return self._now
        return datetime.datetime.now(EASTERN)

    def upcoming(
        self, month: int, day: int, clock: datetime.time | None = None
    ) -> datetime.datetime | None:
        """See ``upcoming_datetime``; uses this scraper's "now" and default time."""
        return upcoming_datetime(
            month, day, clock, self.now.date(), self.default_start_time
        )

    @property
    def group_kernel(self) -> GroupEventsKernel:
        return GroupEventsKernel(
            GenericEvent(publisher_specific_info={}, title="", begins_on=""),
            self.name,
            [self.url],
            ScraperTypes.CUSTOM,
            "",
        )

    def connect_to_source(self) -> None:
        pass

    def close_connection_to_source(self) -> None:
        pass

    def get_source_type(self) -> ScraperTypes:
        return ScraperTypes.CUSTOM

    @abstractmethod
    def scrape(self) -> list[GenericEvent]:
        """Every event the source lists; filtering happens afterwards."""

    def retrieve_from_source(
        self, event_kernel: GroupEventsKernel | None = None
    ) -> list[AllEventsFromAGroup]:
        logger.info(f"Getting Events From {self.name}")
        events: list[GenericEvent] = []
        seen: set[tuple[str, str]] = set()
        for event in self.scrape():
            key = (event.title, event.begins_on)
            if key in seen or not self.in_window(event):
                continue
            seen.add(key)
            self.finalize(event)
            events.append(event)
        logger.info(f"{self.name}: {len(events)} upcoming events")
        return [AllEventsFromAGroup(events, self.group_kernel, self.url)]

    def in_window(self, event: GenericEvent) -> bool:
        if not event.title or not event.begins_on:
            return False
        begins = datetime.datetime.fromisoformat(event.begins_on)
        if begins.tzinfo is None:
            begins = localize(begins)
        horizon = self.now + datetime.timedelta(days=self.days_ahead)
        return self.now <= begins <= horizon

    def finalize(self, event: GenericEvent) -> None:
        # A date-only end (Eventbrite's JSON-LD) reads as midnight, before the start.
        if event.ends_on and datetime.datetime.fromisoformat(
            event.ends_on
        ) < datetime.datetime.fromisoformat(event.begins_on):
            event.ends_on = None
        if event.physical_address is None:
            event.physical_address = self.address
        if not event.description:
            event.description = f"{event.title} at {self.name}."
        mobilizon: dict = {
            "groupID": self.group_id,
            "defaultCategory": self.category.name,
            "defaultTags": list(self.tags),
        }
        if self.default_image_id:
            mobilizon["defaultImageID"] = self.default_image_id
        event.publisher_specific_info = {"mobilizon": mobilizon}

    @staticmethod
    def new_event(
        title: str,
        begins_on: datetime.datetime,
        description: str = "",
        ends_on: datetime.datetime | None = None,
        online_address: str | None = None,
        picture: str | None = None,
        physical_address: GenericAddress | None = None,
    ) -> GenericEvent:
        """`begins_on`/`ends_on` must be timezone aware."""
        return GenericEvent(
            publisher_specific_info={},
            title=clean(title),
            begins_on=begins_on.isoformat(),
            description=description.strip(),
            ends_on=None if ends_on is None else ends_on.isoformat(),
            online_address=online_address,
            picture=picture or None,
            physical_address=physical_address,
        )


class CardListingScraper(VenueScraper):
    """
    A single listing page (``url``) with one element per event. Subclasses set
    ``card_selector`` and turn each card into an event, or None to skip it.
    """

    card_selector: str

    def scrape(self) -> list[GenericEvent]:
        events = []
        for card in fetch_soup(self.url).select(self.card_selector):
            event = self.card_event(card)
            if event is not None:
                events.append(event)
        return events

    @abstractmethod
    def card_event(self, card: Tag) -> GenericEvent | None:
        """The event a card describes, or None when it can't be read."""
