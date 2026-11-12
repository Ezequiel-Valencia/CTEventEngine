from urllib.parse import urljoin

from bs4 import BeautifulSoup
from calendar_event_engine.publishers.mobilizon.types import EventParameters
from calendar_event_engine.types.generics import GenericAddress

from ct_event_engine.Websites.group_packages.common import text_of
from ct_event_engine.Websites.group_packages.platforms import (
    DetailPagesJsonLdScraper,
)


class SchwarzmanCenterScraper(DetailPagesJsonLdScraper):
    """
    https://schwarzman.yale.edu/events/upcoming — the listing has no JSON-LD,
    but every event page it links to does. The text comes from the page body,
    since the JSON-LD has no description.
    """

    name = "Yale Schwarzman Center"
    url = "https://schwarzman.yale.edu/events/upcoming"
    address = GenericAddress(
        latitude=41.3115959,
        longitude=-72.9255828,
        locality="New Haven",
        postalCode="06511",
        street="168 Grove St",
        region="CT",
        description="Yale Schwarzman Center",
    )
    category = EventParameters.Categories.performing_visual_arts
    tags = ["Yale", "performance"]

    def event_links(self, listing: BeautifulSoup) -> dict[str, str]:
        # The card's subheading names the room/building within the center.
        return {
            urljoin(self.url, str(card["href"])): text_of(
                card, ".event-card__subheading"
            )
            for card in listing.select("a.event-card[href]")
        }

    def describe(self, page: BeautifulSoup, context: str) -> str:
        paragraphs = [
            text_of(p)
            for p in page.select(".paragraph--type--text p, .event-meta__details p")
        ]
        text = "\n\n".join(p for p in paragraphs if p)
        return f"Location: {context}\n\n{text}" if context else text
