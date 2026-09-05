"""Parallel public-profile probes for a username handle."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote

import aiohttp

logger = logging.getLogger(__name__)

HANDLE_RE = re.compile(r"^[A-Za-z0-9._-]{1,39}$")
USER_AGENT = (
    "UnifiedIntelligencePortal/0.1 "
    "(local OSINT username probe; +http://127.0.0.1:8000)"
)

PLATFORMS: list[dict[str, str]] = [
    {"id": "github", "name": "GitHub", "url": "https://github.com/{handle}"},
    {"id": "gitlab", "name": "GitLab", "url": "https://gitlab.com/{handle}"},
    {"id": "bitbucket", "name": "Bitbucket", "url": "https://bitbucket.org/{handle}/"},
    {"id": "reddit", "name": "Reddit", "url": "https://www.reddit.com/user/{handle}"},
    {"id": "x", "name": "X / Twitter", "url": "https://x.com/{handle}"},
    {"id": "instagram", "name": "Instagram", "url": "https://www.instagram.com/{handle}/"},
    {"id": "pinterest", "name": "Pinterest", "url": "https://www.pinterest.com/{handle}/"},
    {"id": "youtube", "name": "YouTube", "url": "https://www.youtube.com/@{handle}"},
    {"id": "tiktok", "name": "TikTok", "url": "https://www.tiktok.com/@{handle}"},
    {"id": "twitch", "name": "Twitch", "url": "https://www.twitch.tv/{handle}"},
    {"id": "steam", "name": "Steam", "url": "https://steamcommunity.com/id/{handle}"},
    {"id": "medium", "name": "Medium", "url": "https://medium.com/@{handle}"},
    {"id": "devto", "name": "Dev.to", "url": "https://dev.to/{handle}"},
    {"id": "hackernews", "name": "Hacker News", "url": "https://news.ycombinator.com/user?id={handle}"},
    {"id": "keybase", "name": "Keybase", "url": "https://keybase.io/{handle}"},
    {"id": "soundcloud", "name": "SoundCloud", "url": "https://soundcloud.com/{handle}"},
    {"id": "telegram", "name": "Telegram", "url": "https://t.me/{handle}"},
    {"id": "flickr", "name": "Flickr", "url": "https://www.flickr.com/people/{handle}/"},
    {"id": "tumblr", "name": "Tumblr", "url": "https://{handle}.tumblr.com"},
    {"id": "vimeo", "name": "Vimeo", "url": "https://vimeo.com/{handle}"},
]


def normalize_handle(raw: str) -> str:
    handle = (raw or "").strip().lstrip("@")
    if handle.startswith("http://") or handle.startswith("https://") or "/" in handle:
        raise ValueError("Handle must be a username, not a URL or path")
    if not HANDLE_RE.match(handle):
        raise ValueError("Handle must be 1–39 characters: letters, digits, dot, underscore, hyphen")
    return handle


def platform_url(template: str, handle: str) -> str:
    safe = quote(handle, safe="._-")
    return template.format(handle=safe)


def platform_catalog() -> list[dict[str, str]]:
    return [{"id": p["id"], "name": p["name"]} for p in PLATFORMS]


def _classify(status_code: int | None) -> tuple[bool, str]:
    if status_code == 200:
        return True, "found"
    if status_code in {404, 410}:
        return False, "absent"
    return False, "uncertain"


async def _probe(
    session: aiohttp.ClientSession,
    platform: dict[str, str],
    handle: str,
) -> dict[str, Any]:
    url = platform_url(platform["url"], handle)
    status_code: int | None = None
    error = None
    try:
        async with session.get(url, allow_redirects=True) as response:
            status_code = response.status
            await response.release()
    except asyncio.TimeoutError:
        error = "timeout"
        status_code = 0
    except aiohttp.ClientError as exc:
        error = exc.__class__.__name__
        status_code = 0

    exists, state = _classify(status_code)
    if exists:
        logger.info("Account exists: %s on %s (%s)", handle, platform["name"], url)

    return {
        "id": platform["id"],
        "platform": platform["name"],
        "url": url,
        "status_code": status_code,
        "exists": exists,
        "state": state,
        "error": error,
    }


async def iter_username_scan(handle: str) -> AsyncIterator[dict[str, Any]]:
    timeout = aiohttp.ClientTimeout(total=12, sock_connect=6)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    }
    connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=60)
    async with aiohttp.ClientSession(
        timeout=timeout,
        headers=headers,
        connector=connector,
    ) as session:
        tasks = [_probe(session, platform, handle) for platform in PLATFORMS]
        for coro in asyncio.as_completed(tasks):
            yield await coro


async def scan_username(handle: str) -> dict[str, Any]:
    results = [item async for item in iter_username_scan(handle)]
    results.sort(key=lambda row: (not row["exists"], row["platform"].casefold()))
    found = [row for row in results if row["exists"]]
    return {
        "handle": handle,
        "checked": len(results),
        "found": len(found),
        "results": results,
    }
