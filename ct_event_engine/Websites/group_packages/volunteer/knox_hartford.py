from calendar_event_engine.publishers.mobilizon.types import EventParameters
from calendar_event_engine.types.generics import GenericAddress

from ct_event_engine.Websites.group_packages.platforms import TribeEventsScraper


class KnoxHartfordScraper(TribeEventsScraper):
    """https://knoxhartford.org/volunteer/ — The Events Calendar (WordPress)."""

    name = "KNOX Hartford"
    url = "https://knoxhartford.org"
    address = GenericAddress(
        latitude=41.758933,
        longitude=-72.6966939,
        locality="Hartford",
        postalCode="06106",
        street="75 Laurel St",
        region="CT",
        description="KNOX Headquarters",
    )
    category = EventParameters.Categories.causes
    tags = ["volunteer", "gardening"]
