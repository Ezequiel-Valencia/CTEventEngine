import datetime
from urllib.parse import urljoin

from calendar_event_engine.publishers.mobilizon.types import EventParameters
from calendar_event_engine.types.generics import GenericAddress, GenericEvent

from ct_event_engine.logger import create_logger_from_designated_logger
from ct_event_engine.Websites.group_packages.common import (
    VenueScraper,
    attr_of,
    fetch_soup,
    first_image_from_srcset,
    localize,
    text_of,
)

logger = create_logger_from_designated_logger(__name__)

# "Friday, November 13, 2026 at 8:00 PM EST", sometimes with a "." after the day.
_START_FORMATS = ["%A, %B %d, %Y at %I:%M %p", "%A. %B %d, %Y at %I:%M %p"]


class Cafe9Scraper(VenueScraper):
    """
    https://cafenine.com — Material UI cards on the home page, each linking to
    a product page whose first paragraph is the start time.
    """

    name = "Cafe 9"
    url = "https://cafenine.com"
    address = GenericAddress(
        latitude=41.30377450753123,
        longitude=-72.9238838019238,
        locality="New Haven",
        postalCode="06510",
        street="250 State St",
        region="CT",
        description="Cafe 9",
    )
    category = EventParameters.Categories.music
    tags = ["nightlife", "music","bar"]

    def scrape(self) -> list[GenericEvent]:
        events = []
        for card in fetch_soup(self.url).select(".MuiPaper-root-25, .MuiCard-root-24"):
            divs = card.find_all("div", recursive=False)
            href = attr_of(divs[1], "a", "href") if len(divs) > 1 else None
            if href is None:
                continue
            event = self.event_page(urljoin(self.url, href))
            if event is not None:
                events.append(event)
        return events

    def event_page(self, page_url: str) -> GenericEvent | None:
        details = fetch_soup(page_url).select_one("#product_details .MuiGrid-root")
        blocks = details.select("div") if details else []
        paragraphs = blocks[-3].select("p") if len(blocks) >= 3 else []
        if details is None or not paragraphs:
            logger.warning(f"Unexpected Cafe 9 page layout: {page_url}")
            return None
        # Drop the trailing timezone ("EST") before parsing.
        begins = _parse_start(paragraphs[0].get_text(strip=True).rsplit(" ", 1)[0])
        if begins is None:
            logger.warning(f"Could not read the start time on {page_url}")
            return None
        srcset = attr_of(details, "img", "srcset")
        return self.new_event(
            title=text_of(details, "h2"),
            begins_on=begins,
            description="\n".join(p.get_text() for p in paragraphs),
            online_address=page_url,
            picture=first_image_from_srcset(srcset) if srcset else None,
        )


def _parse_start(text: str) -> datetime.datetime | None:
    for start_format in _START_FORMATS:
        try:
            return localize(datetime.datetime.strptime(text, start_format))
        except ValueError:
            continue
    return None
