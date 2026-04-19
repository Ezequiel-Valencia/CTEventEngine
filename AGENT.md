# CTEventEngine — Agent Guide

## Purpose

This repository scrapes social event information from venue/event websites in Connecticut and publishes them to Mobilizon. Each scraper targets a specific website and extracts:

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
└── Websites/              # One file per concrete scraper implementation
    └── cafe9.py           # Scraper for cafenine.com
tests/
└── test_cafe9.py          # Integration tests for Cafe9Scraper
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

    group_kernel = GroupEventsKernel(None, "My Venue", [url], ScraperTypes.CUSTOM, "")

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
event = GenericEvent.default()
event.title = "Event Name"
event.description = "Event description text"
event.picture = "https://myvenue.com/path/to/flyer.jpg"  # flyer image URL
event.begins_on = pytz.timezone("America/New_York").localize(parsed_datetime).isoformat()
event.online_address = "https://myvenue.com/event-page"
event.physical_address = GenericAddress(
    geom="-72.9238838019238;41.30377450753123",  # lon;lat
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
        CustomScraperJob("Cafe 9", "Music venue", Cafe9Scraper()),
        CustomScraperJob("My Venue", "Category description", MyVenueScraper()),  # add here
    ]
}
```

`CustomScraperJob` takes three positional arguments:
1. Venue name (string)
2. Venue category/description (string)
3. Instance of the scraper class

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
