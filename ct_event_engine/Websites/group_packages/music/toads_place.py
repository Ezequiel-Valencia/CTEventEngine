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

_SHOW_TIME = re.compile(r"show\s*:?\s*(\d{1,2}(?::\d{2})?\s*[ap]\.?m)", re.I)


class ToadsPlaceScraper(CardListingScraper):
    """
    https://www.toadsplace.com/ — a Divi page builder home page with one row
    per show: a date blurb ("20" / "feb" / "sat"), a flyer, the details text
    and an Etix "GET TICKETS" button.
    """

    name = "Toad's Place"
    url = "https://www.toadsplace.com/"
    card_selector = ".et_pb_row"
    default_start_time = datetime.time(20, 0)
    address = GenericAddress(
        latitude=41.3115245,
        longitude=-72.929635,
        locality="New Haven",
        postalCode="06511",
        street="300 York St",
        region="CT",
        description="Toad's Place",
    )
    category = EventParameters.Categories.music
    tags = ["concert", "music"]

    def card_event(self, card: Tag) -> GenericEvent | None:
        day = text_of(card, ".et_pb_blurb_content .et_pb_module_header")
        month_and_weekday = card.select_one(".et_pb_blurb_description")
        details = card.select_one(".et_pb_text_inner")
        title = text_of(details, "h3")
        if not (day.isdigit() and month_and_weekday and details and title):
            return None
        months = (month_number(text_of(p)) for p in month_and_weekday.find_all("p"))
        month = next((m for m in months if m), None)
        if month is None:
            return None

        text = text_of(details)
        show = _SHOW_TIME.search(text)
        begins = self.upcoming(
            month, int(day), parse_clock(show.group(1) if show else text)
        )
        if begins is None:
            return None
        lines = [text_of(p) for p in details.find_all("p")]
        return self.new_event(
            title=title,
            begins_on=begins,
            description="\n".join(line for line in lines if line),
            online_address=attr_of(card, "a.et_pb_button", "href") or self.url,
            picture=attr_of(card, ".et_pb_image img", "src"),
        )
