"""Create or update a Mobilizon group and upload a default image for its events.

Not part of the scraping application: run it by hand whenever a venue/group needs
to exist on the Mobilizon instance, then paste the printed IDs into the group
package JSON (``publisherInfo.mobilizon.groupID`` / ``defaultImageID``).

Usage:
    uv run python scripts/mobilizon_group.py "Cafe 9" \\
        --group-image images/cafe9.png \\
        --event-image https://example.com/cafe9-default.jpg

Credentials are read like ``MobilizonUploader`` does: ``MOBILIZON_ENDPOINT``
plus ``MOBILIZON_EMAIL``/``MOBILIZON_PASSWORD`` or ``MOBILIZON_LOGIN_FILE``.
They can also be passed with --endpoint/--email/--password.

Output (stdout), e.g.: {"groupID": 15, "defaultImageID": "a192d1e5-..."}

With --dry-run nothing is created, updated or uploaded: the script logs in,
looks the group up, validates both images and prints what would change
(create vs update, field diffs, warnings) instead of the IDs.

With --search, NAME is a search term instead: the groups the bot belongs to
whose name or username matches are listed with their groupIDs, e.g.
    uv run python scripts/mobilizon_group.py "cafe" --search
    {"search": "cafe", "groups": [{"groupID": 15, "name": "Cafe 9",
      "preferredUsername": "cafe_9", "role": "ADMINISTRATOR"}]}
Only ADMINISTRATOR groups can be used in a group package. A defaultImageID is
not linked to the group in Mobilizon, so search can't show it.

The group is matched by its display name among the groups the logged-in
identity administers. If found it is renamed/re-avatared in place, otherwise a
new group is created. A fresh default event image is uploaded on every run.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx2
import validators
from calendar_event_engine.publishers.mobilizon.api import TIMEOUT_SECONDS, MobilizonAPI
from gql import gql
from gql.transport.exceptions import TransportError, TransportQueryError

REPO_ROOT = Path(__file__).resolve().parent.parent

UPLOAD_MEDIA = """
mutation UploadMedia($file: Upload!, $name: String!, $alt: String, $actorId: ID) {
  uploadMedia(file: $file, name: $name, alt: $alt, actorId: $actorId) { uuid }
}
"""

# Group avatars can't reference an already uploaded media (mediaUuid is
# rejected), so the file is sent inline in the same multipart request.
CREATE_GROUP = """
mutation CreateGroup($name: String!, $preferredUsername: String!, $summary: String,
                     $avatar: MediaInput) {
  createGroup(name: $name, preferredUsername: $preferredUsername, summary: $summary,
              avatar: $avatar) { id }
}
"""

UPDATE_GROUP = """
mutation UpdateGroup($id: ID!, $name: String, $summary: String, $avatar: MediaInput) {
  updateGroup(id: $id, name: $name, summary: $summary, avatar: $avatar) { id }
}
"""

GROUP_DETAILS = gql(
    """
query Group($preferredUsername: String!) {
  group(preferredUsername: $preferredUsername) {
    id name preferredUsername summary avatar { url }
  }
}
"""
)


@dataclass
class Image:
    filename: str
    content: bytes
    content_type: str


def load_image(source: str) -> Image:
    """Read an image from a URL, or from a file path (relative to the current
    directory, falling back to the repository root)."""
    if validators.url(source):
        with httpx2.Client(timeout=TIMEOUT_SECONDS, follow_redirects=True) as http:
            response = http.get(source)
            response.raise_for_status()
        filename = Path(httpx2.URL(source).path).name or "image"
        content_type = response.headers.get("content-type", "").split(";")[0].strip()
        content = response.content
    else:
        path = Path(source)
        if not path.is_file() and not path.is_absolute():
            path = REPO_ROOT / source
        if not path.is_file():
            raise FileNotFoundError(f"Image not found: {source}")
        filename = path.name
        content_type = mimetypes.guess_type(path.name)[0] or ""
        content = path.read_bytes()

    if not content_type.startswith("image/"):
        guessed = mimetypes.guess_type(filename)[0] or ""
        if not guessed.startswith("image/"):
            raise ValueError(
                f"{source} is not an image (content type {content_type!r})"
            )
        content_type = guessed
    return Image(filename, content, content_type)


def username_from_name(name: str) -> str:
    """Mobilizon usernames only allow lowercase letters, digits and underscores."""
    username = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")
    if not username:
        raise ValueError(
            f"Cannot derive a group username from {name!r}; pass --username"
        )
    return username


class GroupManager:
    def __init__(self, api: MobilizonAPI):
        self.api = api

    def _multipart(self, query: str, variables: dict, files: dict[str, Image]) -> dict:
        """Send a GraphQL request with file uploads (Absinthe's multipart format:
        each Upload variable holds the name of a multipart part)."""
        with httpx2.Client(timeout=TIMEOUT_SECONDS) as http:
            response = http.post(
                self.api.endpoint,
                data={"query": query, "variables": json.dumps(variables)},
                files={
                    part: (img.filename, img.content, img.content_type)
                    for part, img in files.items()
                },
                headers={**self.api._headers, "accept": "application/json"},
            )
        response.raise_for_status()
        content = response.json()
        if content.get("errors"):
            raise RuntimeError(f"Mobilizon returned errors: {content['errors']}")
        return content["data"]

    def find_group(self, name: str, username: str) -> dict | None:
        """Find a group the bot administers whose name (or username) matches.

        Mobilizon's membership search is a text filter, so search by the name
        first and then by the username (covers renaming a group via --username).
        """
        for term in (name, username):
            for membership in self._memberships(term):
                group = membership["parent"]
                if membership["role"] == "ADMINISTRATOR" and (
                    group["name"] == name or group["preferredUsername"] == username
                ):
                    return group
        return None

    def _memberships(self, term: str) -> list[dict]:
        """All of the bot's group memberships matching ``term`` (every page)."""
        found: list[dict] = []
        page = 1
        while True:
            memberships = self.api.get_groups(name=term, page=page, limit=50)[
                "loggedUser"
            ]["memberships"]
            elements = memberships["elements"]
            found.extend(m for m in elements if m.get("parent"))
            if not elements or page * 50 >= memberships["total"]:
                return found
            page += 1

    def search_groups(self, term: str) -> list[dict]:
        """Groups the bot belongs to whose name or username matches ``term``."""
        results = []
        for membership in self._memberships(term):
            group = membership["parent"]
            results.append(
                {
                    "groupID": int(group["id"]),
                    "name": group["name"],
                    "preferredUsername": group["preferredUsername"],
                    "role": membership["role"],
                }
            )
        return sorted(results, key=lambda g: g["groupID"])

    def upload_image(self, image: Image, alt: str) -> str:
        variables = {
            "file": "image",
            "name": image.filename,
            "alt": alt,
            "actorId": self.api.bot_actor.id,
        }
        data = self._multipart(UPLOAD_MEDIA, variables, {"image": image})
        return data["uploadMedia"]["uuid"]

    def upsert_group(
        self,
        name: str,
        avatar: Image,
        username: str | None = None,
        summary: str | None = None,
    ) -> int:
        username = username or username_from_name(name)
        avatar_input = {
            "media": {
                "name": avatar.filename,
                "alt": f"{name} avatar",
                "file": "avatar",
            }
        }
        variables: dict = {"name": name, "avatar": avatar_input}
        if summary is not None:
            variables["summary"] = summary

        existing = self.find_group(name, username)
        if existing is None:
            variables["preferredUsername"] = username
            data = self._multipart(CREATE_GROUP, variables, {"avatar": avatar})
            return int(data["createGroup"]["id"])

        variables["id"] = existing["id"]
        data = self._multipart(UPDATE_GROUP, variables, {"avatar": avatar})
        return int(data["updateGroup"]["id"])

    def get_group(self, username: str) -> dict | None:
        """Look up any group (not only the bot's) by username; None if missing."""
        try:
            return self.api._execute(GROUP_DETAILS, {"preferredUsername": username})[
                "group"
            ]
        except TransportQueryError as err:
            if "not found" in str(err).lower():
                return None
            raise


def _plain_text(html: str | None) -> str:
    """Mobilizon stores summaries as HTML; compare them as text."""
    return re.sub(r"<[^>]+>", "", html or "").strip()


def plan_group(
    api: MobilizonAPI,
    name: str,
    group_image: str,
    event_image: str,
    username: str | None = None,
    summary: str | None = None,
) -> dict:
    """Report what ``sync_group`` would change, without changing anything.

    Only read-only queries are sent. Both images are still loaded, so a bad
    path or URL fails the dry run just like the real run.
    """
    manager = GroupManager(api)
    avatar = load_image(group_image)
    default_image = load_image(event_image)
    username = username or username_from_name(name)
    warnings: list[str] = []
    changes: dict[str, dict] = {}

    existing = manager.find_group(name, username)
    if existing is None:
        action, group_id = "create", None
        taken = manager.get_group(username)
        if taken is not None:
            warnings.append(
                f"Username '{username}' is already used by a group the bot does not "
                f"administer (id {taken['id']}); creating would fail. Pass --username."
            )
        changes["name"] = {"from": None, "to": name}
        changes["preferredUsername"] = {"from": None, "to": username}
        if summary is not None:
            changes["summary"] = {"from": None, "to": summary}
        changes["avatar"] = {"from": None, "to": group_image}
    else:
        action, group_id = "update", int(existing["id"])
        current = manager.get_group(existing["preferredUsername"]) or existing
        if current.get("name") != name:
            changes["name"] = {"from": current.get("name"), "to": name}
        if summary is not None and _plain_text(current.get("summary")) != summary:
            changes["summary"] = {
                "from": _plain_text(current.get("summary")),
                "to": summary,
            }
        if existing["preferredUsername"] != username:
            warnings.append(
                f"Matched group '{existing['preferredUsername']}' by name; its "
                f"username cannot be changed to '{username}'."
            )
        # The avatar is always re-uploaded; Mobilizon re-encodes images, so the
        # stored file can't be compared with the new one.
        current_avatar = (current.get("avatar") or {}).get("url")
        changes["avatar"] = {"from": current_avatar, "to": group_image}

    return {
        "dryRun": True,
        "action": action,
        "groupID": group_id,
        "preferredUsername": existing["preferredUsername"] if existing else username,
        "changes": changes,
        "groupImage": _describe(avatar, group_image),
        "defaultImage": {
            **_describe(default_image, event_image),
            "note": "A new media would be uploaded, giving a new defaultImageID.",
        },
        "warnings": warnings,
    }


def _describe(image: Image, source: str) -> dict:
    return {
        "source": source,
        "contentType": image.content_type,
        "size": len(image.content),
    }


def sync_group(
    api: MobilizonAPI,
    name: str,
    group_image: str,
    event_image: str,
    username: str | None = None,
    summary: str | None = None,
) -> dict:
    """Create/update the group and upload the default event image.

    :return: ``{"groupID": int, "defaultImageID": str}`` ready for a group package.
    """
    manager = GroupManager(api)
    group_id = manager.upsert_group(name, load_image(group_image), username, summary)
    image_id = manager.upload_image(load_image(event_image), f"{name} event")
    return {"groupID": group_id, "defaultImageID": image_id}


def _credentials(args: argparse.Namespace) -> tuple[str, str, str]:
    endpoint = args.endpoint or os.environ.get("MOBILIZON_ENDPOINT")
    email = args.email or os.environ.get("MOBILIZON_EMAIL")
    password = args.password or os.environ.get("MOBILIZON_PASSWORD")
    if (email is None or password is None) and "MOBILIZON_LOGIN_FILE" in os.environ:
        with open(os.environ["MOBILIZON_LOGIN_FILE"]) as f:
            secrets = json.load(f)
        email = email or secrets["email"]
        password = password or secrets["password"]
    if not endpoint or not email or not password:
        raise SystemExit(
            "Missing Mobilizon credentials: set MOBILIZON_ENDPOINT and "
            "MOBILIZON_EMAIL/MOBILIZON_PASSWORD (or MOBILIZON_LOGIN_FILE)."
        )
    return endpoint, email, password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "name",
        help="Group display name (used to find an existing group), "
        "or the search term with --search",
    )
    parser.add_argument("--group-image", help="Avatar: file path or URL")
    parser.add_argument("--event-image", help="Default event image: file path or URL")
    parser.add_argument(
        "--username", help="Group username (default: derived from name)"
    )
    parser.add_argument("--summary", help="Group description")
    parser.add_argument("--endpoint", help="GraphQL endpoint, e.g. https://host/api")
    parser.add_argument("--email")
    parser.add_argument("--password")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would change; nothing is created or uploaded",
    )
    mode.add_argument(
        "--search",
        action="store_true",
        help="List the bot's groups matching NAME with their groupIDs; no changes",
    )
    args = parser.parse_args(argv)
    if not args.search and not (args.group_image and args.event_image):
        parser.error("--group-image and --event-image are required unless --search")

    api = MobilizonAPI(*_credentials(args))
    try:
        if args.search:
            result: dict = {
                "search": args.name,
                "groups": GroupManager(api).search_groups(args.name),
            }
        else:
            result = (plan_group if args.dry_run else sync_group)(
                api,
                args.name,
                args.group_image,
                args.event_image,
                args.username,
                args.summary,
            )
    finally:
        try:
            api.logout()
        except (httpx2.HTTPError, TransportError) as err:
            # The access token expires on its own; nothing else to clean up.
            print(f"Warning: unable to log out of Mobilizon: {err}", file=sys.stderr)
    pretty = args.dry_run or args.search
    print(json.dumps(result, indent=2) if pretty else json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
