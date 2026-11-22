import logging
import os

from calendar_event_engine.db.db_cache import SQLiteDB
from calendar_event_engine.Runner import start_event_engine
from calendar_event_engine.types.custom_scraper import CustomScraperJob
from slack_sdk.webhook import WebhookClient

from ct_event_engine import sites
from ct_event_engine.Websites.group_packages.adventure_games.canal_dock import (
    CanalDockScraper,
)
from ct_event_engine.Websites.group_packages.creative_trade.creative_arts_workshop import (
    CreativeArtsWorkshopScraper,
)
from ct_event_engine.Websites.group_packages.creative_trade.makehaven import (
    MakeHavenScraper,
)
from ct_event_engine.Websites.group_packages.museum.beinecke import BeineckeScraper
from ct_event_engine.Websites.group_packages.music.cafe9 import Cafe9Scraper
from ct_event_engine.Websites.group_packages.music.club_vandome import (
    ClubVandomeScraper,
)
from ct_event_engine.Websites.group_packages.music.college_street_music_hall import (
    CollegeStreetMusicHallScraper,
)
from ct_event_engine.Websites.group_packages.music.firehouse12 import (
    Firehouse12Scraper,
)
from ct_event_engine.Websites.group_packages.music.schwarzman_center import (
    SchwarzmanCenterScraper,
)
from ct_event_engine.Websites.group_packages.music.shubert import ShubertScraper
from ct_event_engine.Websites.group_packages.music.space_ballroom import (
    SpaceBallroomScraper,
)
from ct_event_engine.Websites.group_packages.music.toads_place import (
    ToadsPlaceScraper,
)
from ct_event_engine.Websites.group_packages.music.webster import WebsterScraper
from ct_event_engine.Websites.group_packages.volunteer.knox_hartford import (
    KnoxHartfordScraper,
)

logger = logging.Logger(__name__)

if __name__ == "__main__":
    env_webhook_key = os.environ.get("SLACK_WEBHOOK")
    env_webhook = None if env_webhook_key is None else WebhookClient(env_webhook_key)
    env_test_mode = False if "TEST_MODE" not in os.environ else True
    submission_json_path = os.getenv("RUNNER_SUBMISSION_JSON_PATH")
    if submission_json_path is None:
        raise ValueError(
            "A JSON file is needed to start the scraping process, please set the ENV variable RUNNER_SUBMISSION_JSON_PATH"
        )
    logger.info("Got Env Variables")
    cache_db = SQLiteDB(env_test_mode)
    logger.info("Connect to DB")
    custom_scrapers: list[CustomScraperJob] = [
        # Each scraper's events go to ctgrassroots.org when its class has
        # `family_friendly = True`, else underground.ctgrassroots.org. group_id and
        # default_image_id are the IDs on that site, from
        # scripts/mobilizon_groups/<site>/<package>.json. Without a group_id
        # nothing is published.
        # adventure_games
        CustomScraperJob(
            "New Haven Community Boating",
            "Community boathouse",
            CanalDockScraper(
                group_id=28,
                default_image_id="ee475112-b9b5-45d6-8fe2-ac4dce1cab7f",
            ),
        ),
        # creative_trade
        CustomScraperJob(
            "Creative Arts Workshop",
            "Art school",
            CreativeArtsWorkshopScraper(
                group_id=29,
                default_image_id="b28ad99f-bf27-4ba5-a4ad-b2a65ce48ebc",
            ),
        ),
        CustomScraperJob(
            "MakeHaven",
            "Makerspace",
            MakeHavenScraper(
                group_id=30,
                default_image_id="cd8e8d67-04ad-471a-a275-2458acb704f6",
            ),
        ),
        # museum
        CustomScraperJob(
            "Beinecke Rare Book & Manuscript Library",
            "Library and museum",
            BeineckeScraper(
                group_id=31,
                default_image_id="70f59467-3830-4d35-b1ba-44588f2f675b",
            ),
        ),
        # music
        CustomScraperJob(
            "Shubert Theatre",
            "Theatre",
            ShubertScraper(
                group_id=35,
                default_image_id="4254dd38-6f09-47a4-8f35-7d07cb91c080",
            ),
        ),
        CustomScraperJob(
            "Yale Schwarzman Center",
            "Performing arts center",
            SchwarzmanCenterScraper(
                group_id=38,
                default_image_id="6f3e2b71-2475-4984-b3dc-c1ba490b0414",
            ),
        ),
        # music, family_friendly = False: IDs on underground.ctgrassroots.org,
        # from scripts/mobilizon_groups/underground/music.json.
        CustomScraperJob(
            "Cafe 9",
            "Music venue",
            Cafe9Scraper(
                group_id=5,
                default_image_id="e56e9c4a-61a4-49f7-b8d8-293ab16a6b11",
            ),
        ),
        CustomScraperJob(
            "Club Vandome",
            "Nightclub",
            ClubVandomeScraper(
                group_id=6,
                default_image_id="4e48795c-1772-460a-89a5-517c186125d2",
            ),
        ),
        CustomScraperJob(
            "College Street Music Hall",
            "Music venue",
            CollegeStreetMusicHallScraper(
                group_id=7,
                default_image_id="98b4b01d-5442-4809-a6c9-28f555a8a5c8",
            ),
        ),
        CustomScraperJob(
            "Firehouse 12",
            "Music venue",
            Firehouse12Scraper(
                group_id=8,
                default_image_id="e02e4a0e-34bb-423d-b2f6-35fb65075dc7",
            ),
        ),
        CustomScraperJob(
            "Space Ballroom",
            "Music venue",
            SpaceBallroomScraper(
                group_id=12,
                default_image_id="4eb09e39-6405-4d92-8bfe-859515f8e109",
            ),
        ),
        CustomScraperJob(
            "The Webster",
            "Music venue",
            WebsterScraper(
                group_id=9,
                default_image_id="15ce8ce7-9d09-4e75-9ed4-338ff0be3f38",
            ),
        ),
        CustomScraperJob(
            "Toad's Place",
            "Music venue",
            ToadsPlaceScraper(
                group_id=10,
                default_image_id="2f840dc5-9fd5-4f6d-9abf-caa68c8c4fca",
            ),
        ),
        # volunteer
        CustomScraperJob(
            "KNOX Hartford",
            "Volunteer organization",
            KnoxHartfordScraper(
                group_id=39,
                default_image_id="34722d25-c3dd-453b-94a5-3c80566bae32",
            ),
        ),
    ]
    logger.info("Engine starting.")
    start_event_engine(
        submission_json_path,
        cache_db,
        env_webhook,
        custom_scrapers,
        env_test_mode,
        # Every event, scraped here or from the group packages, goes to the
        # publisher of its source's site (ct_event_engine/sites.py).
        publishers=sites.build_publishers(env_test_mode, cache_db),
        route_event=sites.route_event,
    )
