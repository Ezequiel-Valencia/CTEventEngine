import datetime

from bs4 import Tag
from calendar_event_engine.publishers.mobilizon.types import EventParameters
from calendar_event_engine.types.generics import GenericAddress, GenericEvent

from ct_event_engine.Websites.group_packages.common import (
    CardListingScraper,
    attr_of,
    localize,
    text_of,
)


class CollegeStreetMusicHallScraper(CardListingScraper):
    """
    https://collegestreetmusichall.com/ — an Eventbrite widget (``sg__event``
    cards) on the home page.
    """

    name = "College Street Music Hall"
    url = "https://collegestreetmusichall.com/"
    card_selector = "article.sg__event"
    address = GenericAddress(
        latitude=41.3066953,
        longitude=-72.9295768,
        locality="New Haven",
        postalCode="06510",
        street="238 College St",
        region="CT",
        description="College Street Music Hall",
    )
    category = EventParameters.Categories.music
    tags = ["concert", "music"]

    def card_event(self, card: Tag) -> GenericEvent | None:
        title = text_of(card, ".sg__title a")
        when = attr_of(card, "time[datetime]", "datetime")
        if not title or when is None:
            return None
        # The widget labels the venue's local show time as UTC
        # ("2026-11-15T19:30:00+00:00" for a 7:30 pm show).
        begins = datetime.datetime.fromisoformat(when).replace(tzinfo=None)
        details = [
            text_of(card, selector)
            for selector in (".sg__summary", ".sg__door-time", ".sg__age-resriction")
        ]
        return self.new_event(
            title=title,
            begins_on=localize(begins),
            description="\n".join(line for line in details if line),
            online_address=attr_of(card, "a.book-now__link", "href") or self.url,
            picture=attr_of(card, ".sg__hero img", "src"),
        )
