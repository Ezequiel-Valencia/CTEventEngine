import datetime
import re
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from calendar_event_engine.publishers.mobilizon.types import EventParameters
from calendar_event_engine.types.generics import GenericAddress, GenericEvent

from ct_event_engine.Websites.group_packages.common import (
    EASTERN,
    VenueScraper,
    clean,
    fetch_soup,
    localize,
    og_meta,
    parse_clock,
    text_of,
)

_FULL_DATE = re.compile(r"([A-Z][a-z]+) (\d{1,2}), (\d{4})")


class BeineckeScraper(VenueScraper):
    """
    https://beinecke.library.yale.edu/calendar (redirects to "Plan Your Visit"),
    which lists the library's upcoming events and tours. Details come from each
    event's page on library.yale.edu.
    """

    name = "Beinecke Rare Book & Manuscript Library"
    url = "https://beinecke.library.yale.edu/calendar"
    address = GenericAddress(
        latitude=41.3115974,
        longitude=-72.9273243,
        locality="New Haven",
        postalCode="06511",
        street="121 Wall St",
        region="CT",
        description="Beinecke Rare Book & Manuscript Library",
    )
    category = EventParameters.Categories.arts
    tags = ["museum", "library", "Yale"]

    def scrape(self) -> list[GenericEvent]:
        details: dict[str, tuple[str, str | None]] = {}
        events = []
        for row in fetch_soup(self.url).select(".views-row"):
            link = row.select_one("h3 a[href]")
            if link is None:
                continue
            event_url = urljoin(self.url, str(link["href"]))
            begins = self.row_start(row, event_url)
            if begins is None:
                continue
            page = event_url.split("?", 1)[0]
            if page not in details:
                details[page] = _event_details(fetch_soup(page))
            description, picture = details[page]
            events.append(
                self.new_event(
                    title=link.get_text(strip=True),
                    begins_on=begins,
                    description=description,
                    online_address=event_url,
                    picture=picture,
                )
            )
        return events

    @staticmethod
    def row_start(row: Tag, event_url: str) -> datetime.datetime | None:
        # Recurring tours link to one occurrence, given in UTC.
        occurrence = parse_qs(urlparse(event_url).query).get("occurrence")
        if occurrence:
            return (
                datetime.datetime.fromisoformat(occurrence[0])
                .replace(tzinfo=datetime.timezone.utc)
                .astimezone(EASTERN)
            )
        match = _FULL_DATE.search(text_of(row, ".views-field-field-event-time"))
        if match is None:
            return None
        day = datetime.datetime.strptime(match.group(0), "%B %d, %Y").date()
        clock = parse_clock(text_of(row, ".views-field-field-event-time-1"))
        return localize(datetime.datetime.combine(day, clock or datetime.time(0, 0)))


def _event_details(soup: BeautifulSoup) -> tuple[str, str | None]:
    description = text_of(soup, ".event-info__description") or clean(
        og_meta(soup, "description")
    )
    return description, og_meta(soup, "image")
