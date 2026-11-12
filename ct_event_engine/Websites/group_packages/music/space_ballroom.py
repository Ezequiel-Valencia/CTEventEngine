from calendar_event_engine.publishers.mobilizon.types import EventParameters
from calendar_event_engine.types.generics import GenericAddress

from ct_event_engine.Websites.group_packages.platforms import EventbriteLinksScraper


class SpaceBallroomScraper(EventbriteLinksScraper):
    """
    https://spaceballroom.com — an Eventbrite feed widget (``section.wfea``)
    whose articles link to each show's Eventbrite page.
    """

    name = "Space Ballroom"
    url = "https://spaceballroom.com"
    link_scope = "section.wfea article"
    max_links = 10
    address = GenericAddress(
        latitude=41.3718,
        longitude=-72.9246,
        locality="Hamden",
        postalCode="06514",
        street="295 Treadwell St",
        region="CT",
        description="Space Ballroom",
    )
    category = EventParameters.Categories.music
    tags = ["concert", "music"]
