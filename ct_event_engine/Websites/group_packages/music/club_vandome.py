import datetime
import re

from bs4 import Tag
from calendar_event_engine.publishers.mobilizon.types import EventParameters
from calendar_event_engine.types.generics import GenericAddress, GenericEvent

from ct_event_engine.Websites.group_packages.common import (
    CardListingScraper,
    attr_of,
    month_number,
    parse_clock,
    text_of,
)

_CLOCK = r"(\d{1,2}(?::\d{2})?\s*[ap]\.?m)"
# Most specific first: "Event runs from 9pm to 2am" beats "Salsa class starts
# at 9:10pm" in the same post.
_STARTS = [
    re.compile(rf"\bruns\s+from\s+{_CLOCK}", re.I),
    re.compile(rf"\bdoors(?:\s+open)?\s+(?:at\s+)?{_CLOCK}", re.I),
    re.compile(rf"\b(?:starts?|begins?|open)\s+(?:from|at)\s+{_CLOCK}", re.I),
]


class ClubVandomeScraper(CardListingScraper):
    """
    http://clubvandome.com/events/ — WordPress posts of an "events" type, each
    with a "Nov 13" date badge (no year) and the times in the text.
    """

    name = "Club Vandome"
    url = "http://clubvandome.com/events/"
    card_selector = ".post-wrapper-full"
    default_start_time = datetime.time(21, 0)
    # The site only gives driving directions ("I-91 exit 2, Hamilton St").
    address = GenericAddress(
        locality="New Haven",
        street="Hamilton St",
        region="CT",
        description="Club Vandome",
    )
    category = EventParameters.Categories.party
    tags = ["nightlife", "music"]

    def card_event(self, card: Tag) -> GenericEvent | None:
        title = card.select_one("h2.title a[href]")
        badge = card.select_one("h4.post-date")
        if title is None or badge is None:
            return None
        day = text_of(badge, "span")
        month = month_number(text_of(badge).split(" ", 1)[0])
        if not day.isdigit() or month is None:
            return None

        text = text_of(card, ".post-data p")
        start = next((m for m in (p.search(text) for p in _STARTS) if m), None)
        begins = self.upcoming(
            month, int(day), parse_clock(start.group(1)) if start else None
        )
        if begins is None:
            return None
        return self.new_event(
            title=text_of(title),
            begins_on=begins,
            description=text,
            online_address=str(title["href"]),
            picture=attr_of(card, ".post-thumb-container img", "src"),
        )
