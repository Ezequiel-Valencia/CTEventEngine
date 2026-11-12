from calendar_event_engine.publishers.mobilizon.types import EventParameters
from calendar_event_engine.types.generics import GenericAddress

from ct_event_engine.Websites.group_packages.platforms import (
    CarbonhouseEventsScraper,
)


class ShubertScraper(CarbonhouseEventsScraper):
    """https://www.shubert.com/events/all — a Carbonhouse site."""

    name = "Shubert Theatre"
    url = "https://www.shubert.com/events/all"
    address = GenericAddress(
        latitude=41.3063682,
        longitude=-72.9288353,
        locality="New Haven",
        postalCode="06510",
        street="247 College St",
        region="CT",
        description="Shubert Theatre",
    )
    category = EventParameters.Categories.theatre
    tags = ["theatre", "Broadway"]
