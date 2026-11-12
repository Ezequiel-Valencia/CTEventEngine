from calendar_event_engine.publishers.mobilizon.types import EventParameters
from calendar_event_engine.types.generics import GenericAddress

from ct_event_engine.Websites.group_packages.platforms import RhpEventsScraper


class WebsterScraper(RhpEventsScraper):
    """https://thewebsterct.com/events/ — Rockhouse Partners rhp-events plugin."""

    name = "The Webster"
    url = "https://thewebsterct.com/events/"
    address = GenericAddress(
        latitude=41.7444223,
        longitude=-72.6832131,
        locality="Hartford",
        postalCode="06114",
        street="31 Webster St",
        region="CT",
        description="The Webster Theater",
    )
    category = EventParameters.Categories.music
    tags = ["concert", "music"]
