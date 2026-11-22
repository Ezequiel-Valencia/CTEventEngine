"""
Scrapers for website platforms that several venues share. A venue built on one
of them only needs to subclass and fill in its name, url and address.

- ``TribeEventsScraper``: WordPress + The Events Calendar (REST API)
- ``SquarespaceEventsScraper``: Squarespace event collections (``?format=json``)
- ``WildApricotScraper``: Wild Apricot event lists (RSS)
- ``RhpEventsScraper``: WordPress + Rockhouse Partners' rhp-events plugin
- ``CarbonhouseEventsScraper``: Carbonhouse venue sites (``/events/all``)
- ``DetailPagesJsonLdScraper``: a listing linking to pages with Event JSON-LD
- ``EventbriteLinksScraper``: a page linking out to Eventbrite event pages
"""

import datetime
import re
import xml.etree.ElementTree as ElementTree
from abc import abstractmethod
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from calendar_event_engine.scrapers.common import SCRAPE_WINDOW
from calendar_event_engine.scrapers.json_ld.scraper import parse_page
from calendar_event_engine.types.generics import GenericAddress, GenericEvent

from ct_event_engine.logger import create_logger_from_designated_logger
from ct_event_engine.Websites.group_packages.common import (
    EASTERN,
    CardListingScraper,
    VenueScraper,
    attr_of,
    clean,
    fetch,
    fetch_soup,
    html_to_text,
    localize,
    month_number,
    parse_clock,
    text_of,
)

logger = create_logger_from_designated_logger(__name__)


class TribeEventsScraper(VenueScraper):
    """
    WordPress sites running The Events Calendar (``/wp-json/tribe/events/v1``).

    Use the JSON_LD calendar type instead when the site's timezone setting is
    right (as NXTHVN's is): its listing pages carry the events as JSON-LD. A
    wrong setting (KNOX Hartford's is America/Halifax) puts the wrong offset
    on every JSON-LD date, while the REST API also gives the wall clock time.
    The iCal export can't be used either: it has no STATUS, which the ICAL
    scraper requires to be CONFIRMED.
    """

    per_page: int = 50

    @property
    def api_url(self) -> str:
        return f"{self.url.rstrip('/')}/wp-json/tribe/events/v1/events"

    def scrape(self) -> list[GenericEvent]:
        horizon = self.now + datetime.timedelta(days=self.days_ahead)
        params = {
            "per_page": self.per_page,
            "start_date": self.now.strftime("%Y-%m-%d %H:%M:%S"),
            "end_date": horizon.strftime("%Y-%m-%d %H:%M:%S"),
        }
        data = fetch(self.api_url, params=params).json()
        return [self.to_event(item) for item in data.get("events", [])]

    def to_event(self, item: dict) -> GenericEvent:
        # The wall clock dates are what the organizer typed in. The site's
        # timezone setting can be wrong (KNOX Hartford's is America/Halifax),
        # which shifts the UTC dates, but every venue here is in Connecticut.
        begins = _local(item["start_date"])
        ends = _local(item["end_date"]) if item.get("end_date") else None
        if item.get("all_day"):
            ends = None
        image = item.get("image") or {}
        return self.new_event(
            title=item.get("title", ""),
            begins_on=begins,
            ends_on=ends,
            description=html_to_text(item.get("description")),
            online_address=item.get("url"),
            picture=image.get("url") if isinstance(image, dict) else None,
            physical_address=self.venue_address(item.get("venue")),
        )

    def venue_address(self, venue) -> GenericAddress | None:
        """The venue's address when it differs from the organization's own."""
        if not isinstance(venue, dict) or not venue.get("address"):
            return None
        street = clean(venue.get("address"))
        if (
            self.address
            and self.address.street
            and _same_street(street, self.address.street)
        ):
            return None
        return GenericAddress(
            street=street,
            locality=clean(venue.get("city")) or None,
            postalCode=clean(venue.get("zip")) or None,
            region="CT",
            description=clean(venue.get("venue")),
        )


def _local(value: str) -> datetime.datetime:
    return EASTERN.localize(datetime.datetime.fromisoformat(value))


def _same_street(first: str, second: str) -> bool:
    def normalize(street: str) -> str:
        return (
            street.lower()
            .replace("street", "st")
            .replace("avenue", "ave")
            .replace(".", "")
        )

    return normalize(first) == normalize(second)


class SquarespaceEventsScraper(VenueScraper):
    """
    Squarespace event collections, read through ``<collection>?format=json``.
    ``collections`` are paths relative to ``url``.
    """

    collections: list[str] = []

    def scrape(self) -> list[GenericEvent]:
        events: list[GenericEvent] = []
        for collection in self.collections:
            collection_url = f"{self.url.rstrip('/')}/{collection.strip('/')}"
            data = fetch(collection_url, params={"format": "json"}).json()
            events.extend(self.to_event(item) for item in data.get("upcoming", []))
        return events

    def to_event(self, item: dict) -> GenericEvent:
        return self.new_event(
            title=item.get("title", ""),
            begins_on=_from_epoch_ms(item["startDate"]),
            ends_on=_from_epoch_ms(item["endDate"]) if item.get("endDate") else None,
            description=html_to_text(item.get("body") or item.get("excerpt")),
            online_address=f"{self.url.rstrip('/')}{item.get('fullUrl', '')}",
            picture=item.get("assetUrl"),
        )


def _from_epoch_ms(value: int) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(value / 1000, EASTERN).replace(microsecond=0)


class WildApricotScraper(VenueScraper):
    """
    Wild Apricot event lists. ``url`` is the list page; its ``/RSS`` feed has
    every upcoming session, with the start time as the item's pubDate.
    """

    # Wild Apricot appends the session date to titles: "Open Rowing (11/12/2026)"
    _DATE_SUFFIX = re.compile(r"\s*\(\d{1,2}/\d{1,2}/\d{4}\)\s*$")

    @property
    def rss_url(self) -> str:
        return f"{self.url.rstrip('/')}/RSS"

    def scrape(self) -> list[GenericEvent]:
        root = ElementTree.fromstring(fetch(self.rss_url).content)
        events = []
        for item in root.iter("item"):
            published = item.findtext("pubDate")
            if not published:
                continue
            events.append(
                self.new_event(
                    title=self._DATE_SUFFIX.sub("", item.findtext("title") or ""),
                    begins_on=parsedate_to_datetime(published).astimezone(EASTERN),
                    description=html_to_text(item.findtext("description")),
                    online_address=item.findtext("link"),
                )
            )
        return events


class RhpEventsScraper(CardListingScraper):
    """
    WordPress sites running Rockhouse Partners' rhp-events plugin (common with
    Etix ticketing). Dates have no year ("Fri, Nov 13") and times read
    "Doors: 9 pm // Show: 9:30 pm".
    """

    card_selector = ".rhpSingleEvent"
    default_start_time = datetime.time(20, 0)

    _DATE = re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})\b")
    _SHOW_TIME = re.compile(r"show\s*:?\s*(.+)$", re.I)

    def card_event(self, card: Tag) -> GenericEvent | None:
        title = text_of(card, ".rhp-event__title--list")
        match = self._DATE.search(text_of(card, ".singleEventDate"))
        month = month_number(match.group(1)) if match else None
        if not title or match is None or month is None:
            return None
        time_text = text_of(card, ".rhp-event__time-text--list")
        show = self._SHOW_TIME.search(time_text)
        begins = self.upcoming(
            month,
            int(match.group(2)),
            parse_clock(show.group(1) if show else time_text),
        )
        if begins is None:
            return None
        description = [
            text_of(card, ".rhp-event__subheader--list"),
            time_text,
            text_of(card, ".rhp-event__age-restriction--list"),
            text_of(card, ".rhpVenueContent"),
        ]
        return self.new_event(
            title=title,
            begins_on=begins,
            description="\n".join(line for line in description if line),
            online_address=attr_of(card, "a.url", "href") or self.url,
            picture=attr_of(card, "img.eventListImage", "src"),
        )


class CarbonhouseEventsScraper(VenueScraper):
    """
    Carbonhouse venue sites (``/events/all``). The listing gives each
    production's run; its detail page lists every performance with an "Add to
    Calendar" link titled "November 13 2026 at 7:00 PM". Each performance is
    an event.
    """

    _FIRST_DATE = re.compile(r"([A-Za-z]{3,9})\s*/?\s*(\d{1,2})")
    _YEAR = re.compile(r"\b(\d{4})\b")
    _SHOWING = re.compile(r"Add to Calendar for (.+ \d{4} at \d{1,2}:\d{2} [AP]M)")

    def scrape(self) -> list[GenericEvent]:
        horizon = self.now.date() + datetime.timedelta(days=self.days_ahead)
        events: list[GenericEvent] = []
        for item in fetch_soup(self.url).select(".eventItem"):
            opening = self.run_start(item)
            if opening is not None and opening > horizon:
                continue  # The run hasn't started within the window
            detail_url = attr_of(item, ".title a", "href", base=self.url)
            if detail_url is None:
                continue
            events.extend(self.performances(item, detail_url))
        return events

    def performances(self, item: Tag, detail_url: str) -> list[GenericEvent]:
        detail = fetch_soup(detail_url)
        body = detail.select_one(".event_description")
        description_parts = [
            text_of(item, ".presented-by"),
            text_of(item, ".info > .location"),
            "\n\n".join(text_of(p) for p in body.find_all("p")) if body else "",
        ]
        description = "\n\n".join(part for part in description_parts if part)
        title = text_of(item, ".title")
        picture = attr_of(item, ".thumb img", "src", base=self.url)

        events = []
        for calendar_link in detail.select(".event_showings a.ical[title]"):
            match = self._SHOWING.search(str(calendar_link["title"]))
            if match is None:
                continue
            begins = datetime.datetime.strptime(match.group(1), "%B %d %Y at %I:%M %p")
            events.append(
                self.new_event(
                    title=title,
                    begins_on=localize(begins),
                    description=description,
                    online_address=detail_url,
                    picture=picture,
                )
            )
        return events

    @classmethod
    def run_start(cls, item: Tag) -> datetime.date | None:
        """First day of the run from "Nov / 13 - 14, 2026"."""
        text = text_of(item, ".date")
        first, year = cls._FIRST_DATE.search(text), cls._YEAR.search(text)
        month = month_number(first.group(1)) if first else None
        if first is None or year is None or month is None:
            return None
        try:
            return datetime.date(int(year.group(1)), month, int(first.group(2)))
        except ValueError:
            return None


class DetailPagesJsonLdScraper(VenueScraper):
    """
    A listing page (``url``) linking to one page per event, each carrying
    schema.org/Event JSON-LD that the engine's JSON_LD parser reads. Use the
    JSON_LD calendar type instead when the listing itself has the JSON-LD.
    """

    # The engine's parser keeps only events within its own scrape window.
    days_ahead = SCRAPE_WINDOW.days

    @abstractmethod
    def event_links(self, listing: BeautifulSoup) -> dict[str, str]:
        """{absolute event page url: context for ``describe``}, in listing order."""

    def describe(self, page: BeautifulSoup, context: str) -> str | None:
        """Description to use instead of the JSON-LD one; None keeps it."""
        return None

    def scrape(self) -> list[GenericEvent]:
        events: list[GenericEvent] = []
        for event_url, context in self.event_links(fetch_soup(self.url)).items():
            page_html = fetch(event_url).text
            template = GenericEvent(publisher_specific_info={}, title="", begins_on="")
            parsed = parse_page(page_html, template, page_url=event_url)
            if not parsed:
                continue
            description = self.describe(
                BeautifulSoup(page_html, "html.parser"), context
            )
            for event in parsed:
                event.online_address = event_url
                if description is not None:
                    event.description = description
                events.append(event)
        return events


class EventbriteLinksScraper(DetailPagesJsonLdScraper):
    """
    A venue page that links out to Eventbrite event pages ("eventbrite.com/e/…"),
    each read through its JSON-LD. ``link_scope`` narrows the links to part of
    the page; ``max_links`` bounds the number of Eventbrite pages fetched.
    """

    link_scope: str = "body"
    max_links: int = 25

    # Eventbrite's CSS module class names carry a build hash, so match a part.
    _OVERVIEW = '[class*="Overview-module"][class*="summaryWrapper"]'

    def describe(self, page: BeautifulSoup, context: str) -> str | None:
        """The "Overview" text; the JSON-LD only has the one line summary."""
        overview = page.select_one(self._OVERVIEW)
        if overview is None:
            return None
        blocks = [text_of(block) for block in overview.select("p, li")]
        text = "\n\n".join(b for b in blocks if b) or text_of(overview)
        return text or None

    def event_links(self, listing: BeautifulSoup) -> dict[str, str]:
        links: dict[str, str] = {}
        for anchor in listing.select(f"{self.link_scope} a[href*='eventbrite.']"):
            href = urljoin(self.url, str(anchor["href"])).split("?", 1)[0]
            if "/e/" in href:
                links.setdefault(href, "")
            if len(links) >= self.max_links:
                break
        return links
