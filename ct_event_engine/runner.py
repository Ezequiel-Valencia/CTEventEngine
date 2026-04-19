import logging
import os

from calendar_event_engine.Runner import start_event_engine
from calendar_event_engine.db.db_cache import SQLiteDB
from calendar_event_engine.publishers.mobilizon.uploader import MobilizonUploader
from calendar_event_engine.types.custom_scraper import CustomScraperJob
from slack_sdk.webhook import WebhookClient

from ct_event_engine.Websites.cafe9 import Cafe9Scraper
from ct_event_engine.Websites.space_ballroom import SpaceBallroomScraper

logger = logging.Logger(__name__)

if __name__ == "__main__":
    env_webhook = None if os.environ.get("SLACK_WEBHOOK") is None else WebhookClient(os.environ.get("SLACK_WEBHOOK"))
    env_test_mode = False if "TEST_MODE" not in os.environ else True
    submission_json_path = os.getenv("RUNNER_SUBMISSION_JSON_PATH")
    logger.info("Got Env Variables")
    cache_db = SQLiteDB(env_test_mode)
    logger.info("Connect to DB")
    custom_scrapers = {
        MobilizonUploader(env_test_mode, cache_db) : [
            CustomScraperJob("Cafe 9", "Music venue", Cafe9Scraper()),
            CustomScraperJob("Space Ballroom", "Music venue", SpaceBallroomScraper()),
        ]
    }
    logger.info("Engine starting.")
    start_event_engine(submission_json_path, cache_db, env_webhook, custom_scrapers, env_test_mode)


