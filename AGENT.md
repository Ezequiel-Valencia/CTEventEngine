# CTEventEngine — Agent Guide

## Purpose

This repository scrapes social event information from venue/event websites in Connecticut and publishes them to Mobilizon — to one of two sites (separate Mobilizon instances):

- **ctgrassroots.org** — family friendly events
- **underground.ctgrassroots.org** — events for adults and nightlife

See "ctgrassroots vs underground" below; every source has a `family_friendly` tag.

Each scraper targets a specific website and extracts:

- **Title** — event name
- **Description** — event details
- **Location** — physical address and coordinates
- **Flyer image URL** — promotional image for the event

---

## Project Structure

```
ct_event_engine/
├── runner.py              # Entry point; registers scrapers and starts the engine
├── logger.py              # Logger factory
└── Websites/
    └── group_packages/    # Every custom scraper (see "Group Package Scrapers")
tests/
└── group_packages/        # Offline tests replaying recorded responses
```

---

## How to Add a New Scraper

### 1. Create a new file in `ct_event_engine/Websites/`

Name it after the venue or site (e.g., `toadshaven.py`).

**If the URL of the website to scrape has not been provided, stop and ask for it before proceeding.**

### 2. Implement the `Scraper` abstract class

```python
from calendar_event_engine.scrapers.abc_scraper import Scraper
from calendar_event_engine.types.generics import GenericEvent, GenericAddress
from calendar_event_engine.types.submission import GroupEventsKernel, ScraperTypes, AllEventsFromAGroup

class MyVenueScraper(Scraper):
    url = "https://myvenue.com"

    group_kernel = GroupEventsKernel(
        GenericEvent(publisher_specific_info={}, title="", begins_on=""),
        "My Venue", [url], ScraperTypes.CUSTOM, "",
    )

    def connect_to_source(self):
        pass  # stub unless connection setup is needed

    def close_connection_to_source(self) -> None:
        pass  # stub unless cleanup is needed

    def get_source_type(self):
        pass  # stub

    def retrieve_from_source(self, event_kernel) -> list[AllEventsFromAGroup]:
        # Scrape the site and return a list of AllEventsFromAGroup
        events: list[GenericEvent] = []
        # ... scraping logic ...
        return [AllEventsFromAGroup(events, MyVenueScraper.group_kernel, MyVenueScraper.url)]
```

### 3. Populate `GenericEvent` fields

```python
event = GenericEvent(publisher_specific_info={}, title="", begins_on="")
event.title = "Event Name"
event.description = "Event description text"
event.picture = "https://myvenue.com/path/to/flyer.jpg"  # flyer image URL
event.begins_on = pytz.timezone("America/New_York").localize(parsed_datetime).isoformat()
event.online_address = "https://myvenue.com/event-page"
event.physical_address = GenericAddress(
    latitude=41.30377450753123,
    longitude=-72.9238838019238,
    locality="New Haven",
    postalCode="06510",
    street="123 Example St",
    region="CT"
)
# Optional: Mobilizon-specific metadata
event.publisher_specific_info = {
    "mobilizon": {
        "defaultCategory": EventParameters.Categories.music.value.lower(),
        "defaultTags": ["bar"],
        "groupID": 14  # Mobilizon group ID for this venue
    }
}
```

### 4. Register the scraper in `runner.py`

```python
from ct_event_engine.Websites.myvenue import MyVenueScraper

custom_scrapers = {
    MobilizonUploader(env_test_mode, cache_db): [
        CustomScraperJob("Cafe 9", "Music venue", Cafe9Scraper(group_id=14)),
        CustomScraperJob("My Venue", "Category description", MyVenueScraper()),  # add here
    ]
}
```

`CustomScraperJob` takes three positional arguments:
1. Venue name (string)
2. Venue category/description (string)
3. Instance of the scraper class

---

## Group Package Scrapers

For a site listed under `need_to_parse` in `events/group_packages/<package>.json`,
first try a built-in calendar type and add it as a group kernel in that JSON:
`ICAL`, `GOOGLE_CAL`, `RSS` (only feeds with `ev:startdate`/`xCal:dtstart`; a
plain `pubDate` isn't an event date) or `JSON_LD` (a page whose
`<script type="application/ld+json">` lists the events). Sea Tea Improv and
NXTHVN are `JSON_LD` kernels; `tests/group_packages/package_kernels.py` runs a
kernel through the engine offline so its test checks the JSON entry works.

Only when none fits, write a custom scraper in the matching subfolder, with
tests in the same layout. Reuse the engine's parsers where part of a site fits
one (e.g. `schwarzman_center.py` reads detail pages with the JSON-LD parser):

```
ct_event_engine/Websites/group_packages/
├── common.py        # VenueScraper base class + date/time/text helpers
├── platforms.py     # Shared platforms (Tribe, Squarespace, Wild Apricot, rhp-events,
│                    #   Carbonhouse, detail pages with JSON-LD, Eventbrite links)
└── <package>/<site>.py
tests/group_packages/
├── http_fixtures.py         # Records/replays a scraper's HTTP responses
├── package_kernels.py       # Runs a group package kernel through the engine
├── scraper_test_case.py     # Shared checks every scraper test inherits
└── <package>/test_<site>.py, <package>/fixtures/<site>/
```

A `VenueScraper` subclass sets `name`, `url`, `address`, `category`, `tags` and
implements `scrape()`; the base class keeps events within `days_ahead` (31 days)
and fills the Mobilizon metadata.

Before writing `scrape()` by hand, check whether the site runs on a platform in
`platforms.py`; then the venue file only sets its name, url and address. A
venue page that links to Eventbrite events subclasses `EventbriteLinksScraper`
(see `music/space_ballroom.py`); one whose own event pages carry JSON-LD
subclasses `DetailPagesJsonLdScraper`. A single listing page with one element
per event subclasses `CardListingScraper` (set `card_selector`, implement
`card_event`). Use the helpers in `common.py` rather than repeating them:
`text_of`/`attr_of` for elements, `og_meta` for Open Graph tags, and
`self.upcoming(month, day, clock)` for dates written without a year (it falls
back to the class's `default_start_time`). It takes the Mobilizon `group_id` in its
constructor (create the group with `scripts/mobilizon_group.py`; list it in its
module's batch file `scripts/mobilizon_groups/<site>/<package>.json` and run
`--batch` on that file to create or update all of the module's groups at once;
`make ctgrassroots_groups` / `make underground_groups` run `--batch` on a
site's whole folder with a single login; `make all_groups` does both).

Scrapers return every upcoming event, published or not; don't filter against
the cache. On each run the engine (≥0.6) publishes new events, updates
published ones whose content changed and skips the rest. It recognises an event
by `source_event_id`, falling back to its title and start time, so a changed
title or time updates the event rather than duplicating it. `VenueScraper`
uses the event's own page (`online_address`) as that ID; override
`source_event_id()` when a site has a better one. Keep scraped content
deterministic: anything that changes on every fetch (cache-busting image
URLs, "posted 3 hours ago") republishes the event on every run.

Tests replay recorded responses, so they run offline. When a site changes,
re-record and update the spot checks in its test:

```bash
uv run python -m tests.group_packages.http_fixtures music.webster
```

---

## ctgrassroots vs underground

Every source is tagged with a `family_friendly` boolean
(`ct_event_engine/sites.py`), and all of its events are published to one site:
`true` → ctgrassroots.org, `false` → underground.ctgrassroots.org. The tag is
static: nothing in an event's text changes where it goes.

- **Custom scraper**: set the class attribute `family_friendly = True` or
  `False` (required).
- **Group package entry**: set it on the source itself, not in
  `publisherInfo` (it isn't publisher specific):
  `"Sea Tea Improv": {"family_friendly": false, "calendarIDs": [...], ...}`.

Use `false` for bars, nightclubs, concert venues and comedy clubs; `true` for
museums, libraries, theatres, classes, markets, volunteering.

Each site is its own Mobilizon instance with its own group and media IDs, so a
source's `groupID`/`defaultImageID` are the ones on its site. The groups'
batch files live in `scripts/mobilizon_groups/ctgrassroots/` and
`scripts/mobilizon_groups/underground/`; `make ctgrassroots_groups` /
`make underground_groups` create them (`make all_groups` does both).
The engine keeps the tag in the kernel's `source_info`. `runner.py` passes it
one `MobilizonUploader` per site and `ct_event_engine/sites.py:route_event`,
which the engine calls for every event to pick its site. An untagged source's
events, or events whose source has no `groupID` on its site yet, are skipped
and logged. Group IDs are per site: when a source changes site, replace its
`groupID`/`defaultImageID` with the ones on the new site.

---

## Key External Types

All from the `calendar-event-engine` package (sourced from git):

| Type | Import path | Purpose |
|------|-------------|---------|
| `Scraper` | `calendar_event_engine.scrapers.abc_scraper` | Abstract base class all scrapers must implement |
| `GenericEvent` | `calendar_event_engine.types.generics` | Holds all fields for a single event |
| `GenericAddress` | `calendar_event_engine.types.generics` | Physical address for an event |
| `AllEventsFromAGroup` | `calendar_event_engine.types.submission` | Wraps a list of events with group metadata |
| `GroupEventsKernel` | `calendar_event_engine.types.submission` | Metadata about the venue/source group |
| `ScraperTypes` | `calendar_event_engine.types.submission` | Enum; use `ScraperTypes.CUSTOM` for web scrapers |
| `MobilizonUploader` | `calendar_event_engine.publishers.mobilizon.uploader` | Publisher that sends events to Mobilizon |
| `CustomScraperJob` | `calendar_event_engine.types.custom_scraper` | Bundles a scraper with its name and category |
| `EventParameters` | `calendar_event_engine.publishers.mobilizon.types` | Contains the `Categories` enum for Mobilizon |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SLACK_WEBHOOK` | No | Slack webhook URL for notifications |
| `MOBILIZON_ENDPOINT` | Yes | GraphQL endpoint of ctgrassroots.org (family site) |
| `UNDERGROUND_MOBILIZON_ENDPOINT` | No | GraphQL endpoint of underground.ctgrassroots.org; unset = underground events aren't published |
| `MOBILIZON_EMAIL` / `MOBILIZON_PASSWORD` or `MOBILIZON_LOGIN_FILE` | Yes | Login, shared by both sites |
| `TEST_MODE` | No | Set to any value to enable test mode |
| `RUNNER_SUBMISSION_JSON_PATH` | Yes | Path to the submission JSON config file |
| `CACHE_DB_PATH` | Yes (Docker) | Directory for SQLite cache database |

---

## Running Locally

```bash
uv run python ct_event_engine/runner.py
```

## Running Tests

```bash
uv run pytest
```

Tests are integration tests that make real HTTP requests by default, but mocks are encouraged for each site — mock the HTTP responses so tests are fast, deterministic, and don't depend on the live site being up or having current events.

## Docker

Build and run via Docker Compose from the parent directory:

```bash
cd docker/
docker compose up
```

The container expects a `docker/docker.env` file (gitignored) with the environment variables above, and a `/app/config/` volume mount for the SQLite database.
