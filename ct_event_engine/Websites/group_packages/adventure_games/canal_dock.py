from calendar_event_engine.publishers.mobilizon.types import EventParameters
from calendar_event_engine.types.generics import GenericAddress

from ct_event_engine.Websites.group_packages.platforms import WildApricotScraper


class CanalDockScraper(WildApricotScraper):
    """
    https://www.canaldock.org/all-events — New Haven Community Boating
    (formerly Canal Dock Boathouse) on Wild Apricot.
    """

    name = "New Haven Community Boating"
    url = "https://www.canaldock.org/all-events"
    address = GenericAddress(
        latitude=41.2958705,
        longitude=-72.9156192,
        locality="New Haven",
        postalCode="06511",
        street="475 Long Wharf Dr",
        region="CT",
        description="New Haven Community Boating",
    )
    category = EventParameters.Categories.outdoors_adventure
    tags = ["boating", "rowing", "sailing"]
