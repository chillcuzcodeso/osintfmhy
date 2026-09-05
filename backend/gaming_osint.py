"""Public gaming-profile lookups. No API keys."""

from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote

import aiohttp

USER_AGENT = "UnifiedIntelligencePortal/0.1 (public gaming profile lookup)"
HANDLE_RE = re.compile(r"^[A-Za-z0-9._-]{2,32}$")

PROFILE_PROBES = [
    {
        "id": "fortnite",
        "name": "Fortnite Tracker",
        "url": "https://fortnitetracker.com/profile/all/{handle}",
    },
    {
        "id": "xbox",
        "name": "Xbox Gamertag",
        "url": "https://xboxgamertag.com/search/{handle}",
    },
    {
        "id": "psn",
        "name": "PSNProfiles",
        "url": "https://psnprofiles.com/{handle}",
    },
    {
        "id": "faceit",
        "name": "FACEIT",
        "url": "https://www.faceit.com/en/players/{handle}",
    },
    {
        "id": "tracker_steam",
        "name": "Tracker.gg Steam",
        "url": "https://tracker.gg/search?term={handle}",
    },
]


def normalize_gamer_tag(raw: str) -> str:
    handle = (raw or "").strip().lstrip("@")
    if handle.startswith("http://") or handle.startswith("https://") or "/" in handle:
        raise ValueError("Use a gamertag, not a URL")
    if not HANDLE_RE.match(handle):
        raise ValueError("Gamertag must be 2–32 characters: letters, digits, dot, underscore, hyphen")
    return handle


def _text(parent: ET.Element | None, tag: str) -> str | None:
    if parent is None:
        return None
    node = parent.find(tag)
    if node is None or node.text is None:
        return None
    value = node.text.strip()
    return value or None


async def _json(session: aiohttp.ClientSession, url: str, **kwargs) -> tuple[int, Any]:
    async with session.get(url, **kwargs) as response:
        status = response.status
        try:
            return status, await response.json(content_type=None)
        except aiohttp.ContentTypeError:
            return status, None
        except Exception:
            return status, None


async def lookup_steam(session: aiohttp.ClientSession, handle: str) -> dict[str, Any]:
    safe = quote(handle, safe="._-")
    candidates = [f"https://steamcommunity.com/id/{safe}/?xml=1"]
    if handle.isdigit():
        candidates.insert(0, f"https://steamcommunity.com/profiles/{safe}/?xml=1")

    last_status = 0
    for url in candidates:
        try:
            async with session.get(url) as response:
                last_status = response.status
                body = await response.text()
        except aiohttp.ClientError as exc:
            return {"found": False, "error": exc.__class__.__name__, "url": url}

        if last_status != 200 or "<error>" in body.lower() and "could not be found" in body.lower():
            continue
        if "The specified profile could not be found" in body:
            continue
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            continue
        if root.find("error") is not None:
            continue
        sid = _text(root, "steamID64")
        if not sid:
            continue
        return {
            "found": True,
            "url": f"https://steamcommunity.com/profiles/{sid}",
            "steam_id64": sid,
            "persona": _text(root, "steamID"),
            "online_state": _text(root, "onlineState"),
            "privacy": _text(root, "privacyState"),
            "member_since": _text(root, "memberSince"),
            "location": _text(root, "location"),
            "vac_banned": _text(root, "vacBanned") == "1",
            "trade_ban": _text(root, "tradeBanState"),
            "status_code": last_status,
        }

    return {
        "found": False,
        "url": f"https://steamcommunity.com/id/{safe}",
        "status_code": last_status,
    }


async def lookup_minecraft(session: aiohttp.ClientSession, handle: str) -> dict[str, Any]:
    safe = quote(handle, safe="._-")
    status, data = await _json(session, f"https://api.ashcon.app/mojang/v2/user/{safe}")
    if status == 200 and isinstance(data, dict) and data.get("uuid"):
        uuid = data["uuid"]
        return {
            "found": True,
            "url": f"https://namemc.com/profile/{uuid}",
            "username": data.get("username"),
            "uuid": uuid,
            "created_at": data.get("created_at"),
            "skin_url": (data.get("textures") or {}).get("skin", {}).get("url"),
            "status_code": status,
        }

    status, data = await _json(
        session,
        f"https://api.mojang.com/users/profiles/minecraft/{safe}",
    )
    if status == 200 and isinstance(data, dict) and data.get("id"):
        uuid = data["id"]
        dashed = uuid if "-" in uuid else f"{uuid[0:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:32]}"
        return {
            "found": True,
            "url": f"https://namemc.com/profile/{dashed}",
            "username": data.get("name"),
            "uuid": dashed,
            "status_code": status,
        }
    return {"found": False, "url": f"https://namemc.com/search?q={safe}", "status_code": status}


async def lookup_roblox(session: aiohttp.ClientSession, handle: str) -> dict[str, Any]:
    try:
        async with session.post(
            "https://users.roblox.com/v1/usernames/users",
            json={"usernames": [handle], "excludeBannedUsers": False},
        ) as response:
            status = response.status
            payload = await response.json(content_type=None)
    except aiohttp.ClientError as exc:
        return {"found": False, "error": exc.__class__.__name__}

    rows = payload.get("data") if isinstance(payload, dict) else None
    if status != 200 or not rows:
        return {"found": False, "status_code": status, "url": f"https://www.roblox.com/search/users?keyword={quote(handle)}"}

    user = rows[0]
    user_id = user.get("id")
    detail = {}
    if user_id:
        _, detail = await _json(session, f"https://users.roblox.com/v1/users/{user_id}")
        if not isinstance(detail, dict):
            detail = {}
    return {
        "found": True,
        "url": f"https://www.roblox.com/users/{user_id}/profile" if user_id else None,
        "user_id": user_id,
        "username": user.get("name") or detail.get("name"),
        "display_name": user.get("displayName") or detail.get("displayName"),
        "created": detail.get("created"),
        "banned": detail.get("isBanned"),
        "description": (detail.get("description") or "")[:240],
        "status_code": status,
    }


async def probe_profile(session: aiohttp.ClientSession, spec: dict[str, str], handle: str) -> dict[str, Any]:
    url = spec["url"].format(handle=quote(handle, safe="._-"))
    try:
        async with session.get(url, allow_redirects=True) as response:
            status = response.status
            exists = status == 200
            return {
                "id": spec["id"],
                "platform": spec["name"],
                "url": str(response.url),
                "status_code": status,
                "exists": exists,
                "state": "found" if exists else "absent" if status in {404, 410} else "uncertain",
            }
    except aiohttp.ClientError:
        return {
            "id": spec["id"],
            "platform": spec["name"],
            "url": url,
            "status_code": 0,
            "exists": False,
            "state": "uncertain",
        }


async def scan_gamer(handle: str) -> dict[str, Any]:
    timeout = aiohttp.ClientTimeout(total=15, sock_connect=6)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json, text/xml, text/html"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        steam, minecraft, roblox, *probes = await asyncio.gather(
            lookup_steam(session, handle),
            lookup_minecraft(session, handle),
            lookup_roblox(session, handle),
            *[probe_profile(session, spec, handle) for spec in PROFILE_PROBES],
        )
    return {
        "handle": handle,
        "steam": steam,
        "minecraft": minecraft,
        "roblox": roblox,
        "profiles": probes,
    }
