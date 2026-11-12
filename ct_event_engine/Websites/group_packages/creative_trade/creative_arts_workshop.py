import datetime
import re

from bs4 import Tag
from calendar_event_engine.publishers.mobilizon.types import EventParameters
from calendar_event_engine.types.generics import GenericAddress, GenericEvent

from ct_event_engine.Websites.group_packages.common import (
    VenueScraper,
    attr_of,
    fetch_soup,
    parse_clock,
    text_of,
)
from ct_event_engine.logger import create_logger_from_designated_logger

logger = create_logger_from_designated_logger(__name__)

_MONTH_DAY = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])")


class CreativeArtsWorkshopScraper(VenueScraper):
    """
    https://creativeartsworkshop.org/courses/ — WordPress "course" posts. The
    listing is sorted by start date; each course page lists its sessions as
    "Workshop: Saturday, 3:30-5:30 pm, 11/14". A multi-week course becomes one
    event on its first day.
    """

    name = "Creative Arts Workshop"
    url = "https://creativeartsworkshop.org/courses/"
    max_pages = 3
    default_start_time = datetime.time(9, 0)
    address = GenericAddress(
        latitude=41.3111296,
        longitude=-72.9213818,
        locality="New Haven",
        postalCode="06510",
        street="80 Audubon St",
        region="CT",
        description="Creative Arts Workshop",
    )
    category = EventParameters.Categories.crafts
    tags = ["art", "class"]

    def scrape(self) -> list[GenericEvent]:
        events: list[GenericEvent] = []
        for page in range(1, self.max_pages + 1):
            page_url = self.url if page == 1 else f"{self.url}page/{page}/"
            soup = fetch_soup(page_url)
            articles = soup.select("article.course")
            for article in articles:
                events.extend(self.course_events(article))
            if not soup.select_one(f'a[href$="/courses/page/{page + 1}/"]'):
                break
        return events

    def course_events(self, article: Tag) -> list[GenericEvent]:
        course_url = attr_of(article, "a.entry-title-link", "href")
        title = text_of(article, "a.entry-title-link")
        if course_url is None or not title:
            return []
        description = text_of(article, ".entry-content p")
        description = description.split("School Policies", 1)[0].strip()
        instructor = text_of(article, ".instructor")
        if instructor:
            description = f"Instructor: {instructor}\n\n{description}"
        picture = attr_of(article, "img", "src")

        events = []
        for session in fetch_soup(course_url).select(".session"):
            begins = self.session_start(session)
            if begins is None:
                continue
            events.append(
                self.new_event(
                    title=title,
                    begins_on=begins,
                    description=f"{description}\n\n{text_of(session)}\n\nRegister: {course_url}",
                    online_address=course_url,
                    picture=picture,
                )
            )
        return events

    def session_start(self, session: Tag) -> datetime.datetime | None:
        text = text_of(session).removeprefix(text_of(session, "strong")).strip()
        # "Saturday, 3:30–5:30 pm, 11/14" / "Tuesdays, 6–9 pm, 11/17–12/8"
        date = _MONTH_DAY.search(text)
        if date is None:
            logger.debug(f"No session date in {text!r}")
            return None
        return self.upcoming(
            int(date.group(1)), int(date.group(2)), parse_clock(text[: date.start()])
        )
