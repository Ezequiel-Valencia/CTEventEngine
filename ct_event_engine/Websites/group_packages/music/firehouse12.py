from calendar_event_engine.publishers.mobilizon.types import EventParameters
from calendar_event_engine.types.generics import GenericAddress

from ct_event_engine.Websites.group_packages.platforms import (
    SquarespaceEventsScraper,
)


class Firehouse12Scraper(SquarespaceEventsScraper):
    """https://firehouse12.com/ — Squarespace event collections."""

    name = "Firehouse 12"
    url = "https://firehouse12.com"
    collections = ["jazz-series", "special-events"]
    address = GenericAddress(
        latitude=41.3038119,
        longitude=-72.9242964,
        locality="New Haven",
        postalCode="06510",
        street="45 Crown St",
        region="CT",
        description="Firehouse 12",
    )
    category = EventParameters.Categories.music
    tags = ["jazz", "concert", "music"]
