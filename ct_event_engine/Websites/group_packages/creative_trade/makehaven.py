import datetime

from bs4 import Tag
from calendar_event_engine.publishers.mobilizon.types import EventParameters
from calendar_event_engine.types.generics import GenericAddress, GenericEvent

from ct_event_engine.Websites.group_packages.common import (
    EASTERN,
    CardListingScraper,
    attr_of,
    text_of,
)


class MakeHavenScraper(CardListingScraper):
    """
    https://www.makehaven.org/events — Drupal + CiviCRM event cards, each with
    an ISO datetime. (CiviCRM's iCal feed has no STATUS, so the ICAL calendar
    type would skip every event.)
    """

    name = "MakeHaven"
    url = "https://www.makehaven.org/events"
    card_selector = ".card"
    address = GenericAddress(
        latitude=41.3047239,
        longitude=-72.9238511,
        locality="New Haven",
        postalCode="06510",
        street="770 Chapel St",
        region="CT",
        description="MakeHaven",
    )
    category = EventParameters.Categories.crafts
    tags = ["makerspace", "workshop"]

    def card_event(self, card: Tag) -> GenericEvent | None:
        title = text_of(card, ".card-title a")
        link = attr_of(card, ".card-title a", "href", base=self.url)
        when = attr_of(card, "time.datetime[datetime]", "datetime")
        if not title or link is None or when is None:
            return None
        begins = datetime.datetime.fromisoformat(when.replace("Z", "+00:00"))
        details = [
            text_of(card, selector)
            for selector in (".experience-level", ".event-card-price", ".summary")
        ]
        return self.new_event(
            title=title,
            begins_on=begins.astimezone(EASTERN),
            description="\n\n".join(d for d in details if d),
            online_address=link,
            picture=attr_of(card, "img", "src", base=self.url),
        )
