import datetime
import json

import pytz
import requests
from bs4 import BeautifulSoup
from calendar_event_engine.types.generics import GenericEvent

from ct_event_engine.logger import create_logger_from_designated_logger

logger = create_logger_from_designated_logger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
}


def get_eventbrite_event(eventbrite_url: str) -> GenericEvent | None:
    """
    Fetch and parse an Eventbrite event page, returning a partially-populated GenericEvent.

    Populates: title, description, picture, begins_on, online_address.
    The caller is responsible for setting physical_address and publisher_specific_info.

    Returns None if the page cannot be fetched or a title cannot be extracted.
    """
    try:
        response = requests.get(eventbrite_url, headers=HEADERS)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch Eventbrite page {eventbrite_url}: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    event = GenericEvent.default()
    event.online_address = eventbrite_url

    # Try JSON-LD structured data first — most reliable for title, date, image, description
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                data = next((d for d in data if d.get('@type') == 'Event'), {})
            if data.get('@type') != 'Event':
                continue

            event.title = data.get('name', '')
            event.description = data.get('description', '')
            event.picture = data.get('image', '')

            start_date = data.get('startDate')
            if start_date:
                dt = datetime.datetime.fromisoformat(start_date)
                if dt.tzinfo is None:
                    dt = pytz.timezone("America/New_York").localize(dt)
                event.begins_on = dt.isoformat()

            if event.title:
                return event
        except (json.JSONDecodeError, ValueError):
            continue

    # Fall back to Open Graph meta tags
    og_title = soup.find('meta', property='og:title')
    og_desc = soup.find('meta', property='og:description')
    og_image = soup.find('meta', property='og:image')

    if og_title:
        event.title = og_title.get('content', '')
    if og_desc:
        event.description = og_desc.get('content', '')
    if og_image:
        event.picture = og_image.get('content', '')

    # Try to extract date from a <time> element
    time_el = soup.find('time', attrs={'datetime': True})
    if time_el:
        try:
            dt = datetime.datetime.fromisoformat(time_el['datetime'])
            if dt.tzinfo is None:
                dt = pytz.timezone("America/New_York").localize(dt)
            event.begins_on = dt.isoformat()
        except ValueError:
            pass

    if not event.title:
        logger.warning(f"Could not extract title from {eventbrite_url}")
        return None

    return event
