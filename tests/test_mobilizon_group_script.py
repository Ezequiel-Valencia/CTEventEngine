"""Tests for scripts/mobilizon_group.py.

The integration tests start a real Mobilizon instance (plus its PostGIS
database) with testcontainers, so they need a working Docker daemon and are
skipped otherwise. Startup takes ~20-30s and is shared by the whole module.
"""

import functools
import http.server
import json
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx2
import pytest
from calendar_event_engine.publishers.mobilizon.api import MobilizonAPI
from calendar_event_engine.publishers.mobilizon.types import (
    EventParameters,
    MobilizonEvent,
)
from gql import gql

from scripts.mobilizon_group import (
    GroupManager,
    load_image,
    main,
    plan_group,
    sync_group,
    username_from_name,
)

MOBILIZON_IMAGE = "kaihuri/mobilizon:5.2.0"
POSTGIS_IMAGE = "postgis/postgis:16-3.4-alpine"
MOBILIZON_PORT = 4000

FIXTURES = Path(__file__).parent / "fixtures"
# Repository-relative paths, as a user would pass them to the script.
GROUP_AVATAR = "tests/fixtures/group_avatar.png"
EVENT_IMAGE = "tests/fixtures/event_default.png"

DB_USER = DB_PASSWORD = DB_NAME = "mobilizon"
BOT_EMAIL = "bot@example.com"
BOT_PASSWORD = "Password123!"


def _docker_available() -> bool:
    import docker

    try:
        docker.from_env().ping()
        return True
    except docker.errors.DockerException:
        return False


# --------------------------------------------------------------------------- #
# Unit tests (no Docker)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Cafe 9", "cafe_9"),
        ("The Space Ballroom!", "the_space_ballroom"),
        ("  New-Haven  Museum ", "new_haven_museum"),
    ],
)
def test_username_from_name(name, expected):
    assert username_from_name(name) == expected


def test_username_from_name_rejects_empty():
    with pytest.raises(ValueError):
        username_from_name("!!!")


def test_load_image_from_repo_relative_path():
    image = load_image(GROUP_AVATAR)
    assert image.filename == "group_avatar.png"
    assert image.content_type == "image/png"
    assert image.content == (FIXTURES / "group_avatar.png").read_bytes()


def test_load_image_missing_file():
    with pytest.raises(FileNotFoundError):
        load_image("tests/fixtures/does_not_exist.png")


def test_load_image_rejects_non_image(tmp_path):
    text_file = tmp_path / "notes.txt"
    text_file.write_text("not an image")
    with pytest.raises(ValueError):
        load_image(str(text_file))


# --------------------------------------------------------------------------- #
# Integration tests against a real Mobilizon
# --------------------------------------------------------------------------- #

integration = pytest.mark.skipif(
    not _docker_available(), reason="Docker is required for Mobilizon integration tests"
)


def _wait_for_mobilizon(endpoint: str, timeout: float = 240) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            response = httpx2.post(
                endpoint, json={"query": "{ config { name } }"}, timeout=5
            )
            if response.status_code == 200 and "data" in response.json():
                return
        except (httpx2.HTTPError, ValueError):
            pass  # Not up yet (connection refused / not JSON); keep polling.
        time.sleep(2)
    raise TimeoutError("Mobilizon did not become ready in time")


@pytest.fixture(scope="module")
def mobilizon_endpoint():
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.network import Network

    with Network() as network:
        db = (
            DockerContainer(POSTGIS_IMAGE)
            .with_network(network)
            .with_network_aliases("db")
            .with_env("POSTGRES_USER", DB_USER)
            .with_env("POSTGRES_PASSWORD", DB_PASSWORD)
            .with_env("POSTGRES_DB", DB_NAME)
        )
        app = (
            DockerContainer(MOBILIZON_IMAGE)
            .with_network(network)
            .with_exposed_ports(MOBILIZON_PORT)
            .with_envs(
                MOBILIZON_DATABASE_HOST="db",
                MOBILIZON_DATABASE_USERNAME=DB_USER,
                MOBILIZON_DATABASE_PASSWORD=DB_PASSWORD,
                MOBILIZON_DATABASE_DBNAME=DB_NAME,
                MOBILIZON_INSTANCE_HOST="localhost",
                MOBILIZON_INSTANCE_PORT=str(MOBILIZON_PORT),
                MOBILIZON_INSTANCE_SECRET_KEY_BASE=uuid.uuid4().hex * 2,
                MOBILIZON_INSTANCE_SECRET_KEY=uuid.uuid4().hex * 2,
            )
        )
        with db, app:
            host = app.get_container_host_ip()
            port = app.get_exposed_port(MOBILIZON_PORT)
            endpoint = f"http://{host}:{port}/api"
            _wait_for_mobilizon(endpoint)

            result = app.exec(
                [
                    "/bin/mobilizon_ctl",
                    "users.new",
                    BOT_EMAIL,
                    "--password",
                    BOT_PASSWORD,
                    "--admin",
                    "--profile-username",
                    "eventbot",
                    "--profile-display-name",
                    "EventBot",
                ]
            )
            assert result.exit_code == 0, result.output.decode()
            yield endpoint


@pytest.fixture(scope="module")
def api(mobilizon_endpoint):
    client = MobilizonAPI(mobilizon_endpoint, BOT_EMAIL, BOT_PASSWORD)
    yield client
    client.logout()


@pytest.fixture(scope="module")
def image_server():
    """Serves tests/fixtures over HTTP so URL sources can be tested offline."""
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(FIXTURES)
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _group(api: MobilizonAPI, username: str) -> dict:
    query = gql(
        """
        query ($u: String!) {
          group(preferredUsername: $u) { id name preferredUsername summary avatar { url } }
        }
        """
    )
    return api._execute(query, {"u": username})["group"]


def _media(api: MobilizonAPI, media_uuid: str) -> dict:
    query = gql("query ($u: UUID!) { media(uuid: $u) { uuid contentType size } }")
    return api._execute(query, {"u": media_uuid})["media"]


def _admin_group_ids(api: MobilizonAPI, name: str) -> list[int]:
    elements = api.get_groups(name=name, limit=50)["loggedUser"]["memberships"][
        "elements"
    ]
    return [
        int(m["parent"]["id"])
        for m in elements
        if m["role"] == "ADMINISTRATOR" and m["parent"]["name"] == name
    ]


def _assert_package_ids(result: dict) -> None:
    assert set(result) == {"groupID", "defaultImageID"}
    assert isinstance(result["groupID"], int)
    uuid.UUID(result["defaultImageID"])  # raises if not a UUID


@integration
def test_creates_group_from_repo_files(api):
    result = sync_group(
        api, "Cafe Nine", GROUP_AVATAR, EVENT_IMAGE, summary="Music venue"
    )
    _assert_package_ids(result)

    group = _group(api, "cafe_nine")
    assert int(group["id"]) == result["groupID"]
    assert group["name"] == "Cafe Nine"
    assert "Music venue" in group["summary"]
    assert group["avatar"] is not None and group["avatar"]["url"]

    media = _media(api, result["defaultImageID"])
    assert media["contentType"] == "image/png"
    assert media["size"] == (FIXTURES / "event_default.png").stat().st_size


@integration
def test_rerun_updates_existing_group_instead_of_duplicating(api):
    first = sync_group(api, "Space Ballroom", GROUP_AVATAR, EVENT_IMAGE)
    avatar_before = _group(api, "space_ballroom")["avatar"]["url"]

    # Swap the images around so the avatar content actually changes.
    second = sync_group(api, "Space Ballroom", EVENT_IMAGE, GROUP_AVATAR)
    _assert_package_ids(second)

    assert second["groupID"] == first["groupID"]
    assert _admin_group_ids(api, "Space Ballroom") == [first["groupID"]]
    assert _group(api, "space_ballroom")["avatar"]["url"] != avatar_before
    assert second["defaultImageID"] != first["defaultImageID"]
    assert _media(api, second["defaultImageID"])["size"] == (
        (FIXTURES / "group_avatar.png").stat().st_size
    )


@integration
def test_custom_username_and_existing_group_found_by_username(api):
    first = sync_group(api, "Old Name", GROUP_AVATAR, EVENT_IMAGE, username="renamed")
    second = sync_group(api, "New Name", GROUP_AVATAR, EVENT_IMAGE, username="renamed")
    assert second["groupID"] == first["groupID"]
    assert _group(api, "renamed")["name"] == "New Name"


@integration
def test_images_from_urls(api, image_server):
    result = sync_group(
        api,
        "URL Venue",
        f"{image_server}/group_avatar.png",
        f"{image_server}/event_default.png",
    )
    _assert_package_ids(result)
    assert _group(api, "url_venue")["avatar"]["url"]
    assert _media(api, result["defaultImageID"])["contentType"] == "image/png"


@integration
def test_returned_ids_work_for_creating_group_events(api):
    """The IDs are only useful if the event uploader can use them as-is."""
    result = sync_group(api, "Package Venue", GROUP_AVATAR, EVENT_IMAGE)

    event = MobilizonEvent(
        attributedToId=result["groupID"],
        title="Default picture event",
        description="Created from group package IDs",
        beginsOn=(datetime.now(UTC) + timedelta(days=7)).isoformat(),
        picture=EventParameters.MediaInput(mediaUuid=result["defaultImageID"]),
    )
    created = api.create_event(event)

    query = gql(
        "query ($u: UUID!) { event(uuid: $u) { attributedTo { id } picture { uuid } } }"
    )
    fetched = api._execute(query, {"u": created["uuid"]})["event"]
    assert int(fetched["attributedTo"]["id"]) == result["groupID"]
    assert fetched["picture"]["uuid"] == result["defaultImageID"]


@integration
def _use_shared_session(api, endpoint, monkeypatch):
    """Make main() use the module's logged-in client (Mobilizon rate-limits
    logins). Credentials still come from the environment, as in real use."""
    monkeypatch.setenv("MOBILIZON_ENDPOINT", endpoint)
    monkeypatch.setenv("MOBILIZON_EMAIL", BOT_EMAIL)
    monkeypatch.setenv("MOBILIZON_PASSWORD", BOT_PASSWORD)

    def fake_client(endpoint_arg, email, password):
        assert (endpoint_arg, email, password) == (endpoint, BOT_EMAIL, BOT_PASSWORD)
        return api

    monkeypatch.setattr("scripts.mobilizon_group.MobilizonAPI", fake_client)
    monkeypatch.setattr(api, "logout", lambda: None)


def test_cli_prints_package_json(api, mobilizon_endpoint, monkeypatch, capsys):
    _use_shared_session(api, mobilizon_endpoint, monkeypatch)

    exit_code = main(
        [
            "CLI Venue",
            "--group-image",
            GROUP_AVATAR,
            "--event-image",
            EVENT_IMAGE,
        ]
    )
    assert exit_code == 0
    result = json.loads(capsys.readouterr().out)
    _assert_package_ids(result)
    assert int(_group(api, "cli_venue")["id"]) == result["groupID"]


@integration
def test_dry_run_for_new_group_creates_nothing(api):
    plan = plan_group(
        api, "Dry Run Venue", GROUP_AVATAR, EVENT_IMAGE, summary="Not real yet"
    )

    assert plan["dryRun"] is True
    assert plan["action"] == "create"
    assert plan["groupID"] is None
    assert plan["preferredUsername"] == "dry_run_venue"
    assert plan["changes"]["name"] == {"from": None, "to": "Dry Run Venue"}
    assert plan["changes"]["summary"] == {"from": None, "to": "Not real yet"}
    assert plan["groupImage"]["contentType"] == "image/png"
    assert (
        plan["defaultImage"]["size"] == (FIXTURES / "event_default.png").stat().st_size
    )
    assert plan["warnings"] == []

    assert GroupManager(api).get_group("dry_run_venue") is None
    assert _admin_group_ids(api, "Dry Run Venue") == []


@integration
def test_dry_run_for_existing_group_reports_diff_without_changing_it(api):
    created = sync_group(
        api, "Dry Existing", GROUP_AVATAR, EVENT_IMAGE, summary="Old summary"
    )
    before = _group(api, "dry_existing")

    plan = plan_group(
        api,
        "Dry Existing Renamed",
        EVENT_IMAGE,
        EVENT_IMAGE,
        username="dry_existing",
        summary="New summary",
    )

    assert plan["action"] == "update"
    assert plan["groupID"] == created["groupID"]
    assert plan["changes"]["name"] == {
        "from": "Dry Existing",
        "to": "Dry Existing Renamed",
    }
    assert plan["changes"]["summary"] == {"from": "Old summary", "to": "New summary"}
    assert plan["changes"]["avatar"]["from"] == before["avatar"]["url"]

    assert _group(api, "dry_existing") == before


@integration
def test_dry_run_with_no_field_changes_only_lists_avatar(api):
    sync_group(api, "Dry Same", GROUP_AVATAR, EVENT_IMAGE, summary="Same")
    plan = plan_group(api, "Dry Same", GROUP_AVATAR, EVENT_IMAGE, summary="Same")
    assert plan["action"] == "update"
    assert set(plan["changes"]) == {"avatar"}


@integration
def test_dry_run_still_validates_images(api):
    with pytest.raises(FileNotFoundError):
        plan_group(api, "Dry Bad Image", "tests/fixtures/missing.png", EVENT_IMAGE)


@integration
def test_cli_dry_run_prints_plan_and_creates_nothing(
    api, mobilizon_endpoint, monkeypatch, capsys
):
    _use_shared_session(api, mobilizon_endpoint, monkeypatch)

    exit_code = main(
        [
            "CLI Dry Venue",
            "--group-image",
            GROUP_AVATAR,
            "--event-image",
            EVENT_IMAGE,
            "--dry-run",
        ]
    )
    assert exit_code == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["dryRun"] is True
    assert plan["action"] == "create"
    assert GroupManager(api).get_group("cli_dry_venue") is None


@integration
def test_search_lists_matching_groups_with_ids(api):
    first = sync_group(api, "Search Hall One", GROUP_AVATAR, EVENT_IMAGE)
    second = sync_group(api, "Search Hall Two", GROUP_AVATAR, EVENT_IMAGE)
    sync_group(api, "Unrelated Venue", GROUP_AVATAR, EVENT_IMAGE)

    results = GroupManager(api).search_groups("Search Hall")

    assert results == [
        {
            "groupID": first["groupID"],
            "name": "Search Hall One",
            "preferredUsername": "search_hall_one",
            "role": "ADMINISTRATOR",
        },
        {
            "groupID": second["groupID"],
            "name": "Search Hall Two",
            "preferredUsername": "search_hall_two",
            "role": "ADMINISTRATOR",
        },
    ]


@integration
def test_search_matches_username(api):
    created = sync_group(
        api, "Display Only", GROUP_AVATAR, EVENT_IMAGE, username="hidden_handle"
    )
    ids = [g["groupID"] for g in GroupManager(api).search_groups("hidden_handle")]
    assert ids == [created["groupID"]]


@integration
def test_search_with_no_matches(api):
    assert GroupManager(api).search_groups("zzz no such group") == []


@integration
def test_cli_search_prints_ids_without_images(
    api, mobilizon_endpoint, monkeypatch, capsys
):
    created = sync_group(api, "CLI Search Venue", GROUP_AVATAR, EVENT_IMAGE)
    _use_shared_session(api, mobilizon_endpoint, monkeypatch)

    assert main(["CLI Search", "--search"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["search"] == "CLI Search"
    assert [g["groupID"] for g in output["groups"]] == [created["groupID"]]


def test_cli_requires_images_unless_searching(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["Some Venue"])
    assert exc.value.code == 2
    assert "--group-image and --event-image are required" in capsys.readouterr().err


def test_cli_search_and_dry_run_are_exclusive():
    with pytest.raises(SystemExit) as exc:
        main(["Some Venue", "--search", "--dry-run"])
    assert exc.value.code == 2
