"""
The two websites events are published to, each its own Mobilizon instance.
Every source is tagged with a ``family_friendly`` boolean, and all of its
events go to one site:

- ``true``: ctgrassroots.org (``MOBILIZON_ENDPOINT``)
- ``false``: underground.ctgrassroots.org (``UNDERGROUND_MOBILIZON_ENDPOINT``),
  events for adults and nightlife

The tag belongs to the source and is static: nothing in an event's text
changes where it goes.

- A custom scraper (``VenueScraper``) sets the class attribute
  ``family_friendly``.
- A group package entry sets it next to its other settings::

      "Sea Tea Improv": {"family_friendly": false, "calendarIDs": [...], ...}

The engine keeps the tag in the kernel's ``source_info`` and calls
``route_event`` for every event to pick its publisher. A source's ``groupID``
and ``defaultImageID`` (in ``publisherInfo``) are the ones on its site.
"""

import os
from enum import Enum

from calendar_event_engine.db.db_cache import SQLiteDB
from calendar_event_engine.publishers.abc_publisher import Publisher
from calendar_event_engine.publishers.mobilizon.uploader import MobilizonUploader
from calendar_event_engine.types.generics import GenericEvent
from calendar_event_engine.types.submission import GroupEventsKernel

from ct_event_engine.logger import create_logger_from_designated_logger

logger = create_logger_from_designated_logger(__name__)

FAMILY_FRIENDLY_KEY = "family_friendly"


class Site(Enum):
    """Each value is the name of the site's publisher in ``publishers``."""

    CTGRASSROOTS = "ctgrassroots"
    UNDERGROUND = "underground"


ENDPOINT_ENV = {
    Site.CTGRASSROOTS: "MOBILIZON_ENDPOINT",
    Site.UNDERGROUND: "UNDERGROUND_MOBILIZON_ENDPOINT",
}


def site_of(kernel: GroupEventsKernel) -> Site | None:
    """The source's site, or None when it has no boolean ``family_friendly``."""
    family_friendly = kernel.source_info.get(FAMILY_FRIENDLY_KEY)
    if not isinstance(family_friendly, bool):
        return None
    return Site.CTGRASSROOTS if family_friendly else Site.UNDERGROUND


def route_event(event: GenericEvent, kernel: GroupEventsKernel) -> str | None:
    """The engine's ``EventRouter``: the publisher name of the event's site."""
    site = site_of(kernel)
    if site is None:
        logger.error(
            f"{kernel.group_name}: skipping {event.title!r}, the source has no "
            "family_friendly tag (true or false)."
        )
        return None
    metadata = (event.publisher_specific_info or {}).get("mobilizon") or {}
    if metadata.get("groupID") is None:
        logger.warning(
            f"{kernel.group_name}: skipping {event.title!r}, no groupID on "
            f"{site.value} yet."
        )
        return None
    return site.value


def build_publishers(test_mode: bool, cache_db: SQLiteDB) -> dict[str, Publisher]:
    """
    One uploader per site, all with the same login. A site whose endpoint is
    unset gets no publisher (the engine then skips its events): an uploader
    without an endpoint would fall back to MOBILIZON_ENDPOINT, i.e. publish
    underground events on the family site.
    """
    publishers: dict[str, Publisher] = {}
    for site, env in ENDPOINT_ENV.items():
        endpoint = os.environ.get(env)
        if not endpoint and not test_mode:
            logger.warning(f"{env} is not set: nothing is published to {site.value}.")
            continue
        # The cache records each event's site under this name (the engine also
        # passes it when routing), so an event is updated on the site it was
        # published to.
        publishers[site.value] = MobilizonUploader(
            test_mode, cache_db, endpoint=endpoint, site_name=site.value
        )
    return publishers
