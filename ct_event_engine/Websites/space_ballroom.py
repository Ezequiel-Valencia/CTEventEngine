import requests
from bs4 import BeautifulSoup
from calendar_event_engine.publishers.mobilizon.types import EventParameters
from calendar_event_engine.scrapers.abc_scraper import Scraper
from calendar_event_engine.types.generics import GenericEvent, GenericAddress
from calendar_event_engine.types.submission import GroupEventsKernel, ScraperTypes, AllEventsFromAGroup

from ct_event_engine.Websites.utils import get_eventbrite_event
from ct_event_engine.logger import create_logger_from_designated_logger

logger = create_logger_from_designated_logger(__name__)

MAX_ARTICLES = 10


class SpaceBallroomScraper(Scraper):
    url = "https://spaceballroom.com"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }
    group_kernel = GroupEventsKernel(None, "Space Ballroom", [url], ScraperTypes.CUSTOM, "")

    def connect_to_source(self):
        pass

    def close_connection_to_source(self) -> None:
        pass

    def get_source_type(self):
        pass

    def retrieve_from_source(self, event_kernel) -> list[AllEventsFromAGroup]:
        logger.info("Getting Events From Space Ballroom")
        response = requests.get(SpaceBallroomScraper.url, headers=SpaceBallroomScraper.headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        events: list[GenericEvent] = []

        wfea_section = soup.select_one('section.wfea')
        if not wfea_section:
            logger.warning("Could not find .wfea section on Space Ballroom homepage")
            return [AllEventsFromAGroup(events, SpaceBallroomScraper.group_kernel, SpaceBallroomScraper.url)]

        articles = wfea_section.find_all('article')[:MAX_ARTICLES]
        logger.info(f"Found {len(articles)} articles to process")

        for article in articles:
            eventbrite_url = self._find_eventbrite_link(article)
            if not eventbrite_url:
                logger.debug("No Eventbrite link found in article, skipping")
                continue

            event = get_eventbrite_event(eventbrite_url)
            if not event:
                continue

            event.physical_address = GenericAddress(
                geom="-72.9246;41.3718",
                locality="Hamden",
                postalCode="06514",
                street="295 Treadwell St",
                region="CT"
            )
            event.publisher_specific_info = {
                "mobilizon": {
                    "defaultCategory": EventParameters.Categories.music.value.lower(),
                    "defaultTags": ["concert", "music"],
                    "groupID": 0  # TODO: set to the Mobilizon group ID for Space Ballroom
                }
            }
            events.append(event)

        return [AllEventsFromAGroup(events, SpaceBallroomScraper.group_kernel, SpaceBallroomScraper.url)]

    def _find_eventbrite_link(self, article) -> str | None:
        for a_tag in article.find_all('a', href=True):
            href = a_tag['href']
            text = a_tag.get_text(strip=True).upper()
            if 'eventbrite' in href.lower() or text == 'TICKETS':
                return href
        return None
