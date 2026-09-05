"""
Fetch FMHY wiki markdown, parse tools into SQLite, and ping link health.

Official source (raw markdown, not the rendered GitHub wiki):
  https://github.com/fmhy/edit  →  docs/*.md
  https://raw.githubusercontent.com/fmhy/edit/main/docs/<page>.md

Adblock content lives in privacy.md (there is no ADBLOCK.md upstream).
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from pathlib import Path

import aiohttp
import requests
from bs4 import BeautifulSoup

from database import (
    catalog_stats,
    clear_catalog,
    find_duplicate_links,
    get_connection,
    init_db,
    insert_tool,
    iter_unique_urls,
    update_link_status,
    upsert_category,
)

FMHY_API_DOCS = "https://api.github.com/repos/fmhy/edit/contents/docs"
FMHY_RAW_BASE = "https://raw.githubusercontent.com/fmhy/edit/main/docs"
USER_AGENT = "UnifiedIntelligencePortal/0.1 (local catalog ingest; link-health-check)"

SKIP_FILES = {
    "index.md",
    "posts.md",
    "feedback.md",
    "sandbox.md",
    "startpage.md",
}

# Fallback if the GitHub API is rate-limited.
FALLBACK_WIKI_FILES = [
    "ai.md",
    "audio.md",
    "beginners-guide.md",
    "developer-tools.md",
    "downloading.md",
    "educational.md",
    "file-tools.md",
    "gaming.md",
    "gaming-tools.md",
    "image-tools.md",
    "internet-tools.md",
    "linux-macos.md",
    "misc.md",
    "mobile.md",
    "non-english.md",
    "privacy.md",
    "reading.md",
    "social-media-tools.md",
    "storage.md",
    "system-tools.md",
    "text-tools.md",
    "torrenting.md",
    "unsafe.md",
    "video.md",
    "video-tools.md",
]

HEADER_RE = re.compile(r"^(#{1,3})\s+(?:[►▷]\s*)?(.+?)\s*$")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)(?:\s+\"[^\"]*\")?\)")
SKIP_URL_RE = re.compile(r"reddit\.com/r/FREEMEDIAHECKYEAH/wiki", re.I)
METADATA_NAMES = {
    "2",
    "3",
    "4",
    "5",
    "cli",
    "discord",
    "github",
    "gitlab",
    "guide",
    "host format",
    "note",
    "reddit",
    "source code",
    "subreddit",
    "telegram",
    "twitter",
    "video",
    "warning",
    "whitelist note",
    "x",
}

INVISIBLE = dict.fromkeys(map(ord, "\u2060\u200b\u200c\u200d\ufeff"), None)


def clean_text(value: str) -> str:
    value = value.translate(INVISIBLE)
    value = re.sub(r"[⭐🌐↪️◄►▷*]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" \t-–—/|,")


def is_metadata_name(name: str) -> bool:
    return clean_text(name).lower() in METADATA_NAMES


def is_skippable_url(url: str) -> bool:
    return not url.startswith(("http://", "https://")) or bool(SKIP_URL_RE.search(url))


def default_category_name(source_file: str) -> str:
    stem = Path(source_file).stem.replace("-", " ")
    return stem.title()


def extract_links(line: str) -> list[tuple[str, str]]:
    """Pull tool name/URL pairs from markdown and HTML anchors."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(name: str, url: str) -> None:
        name = clean_text(name)
        url = url.strip()
        if not name or is_metadata_name(name) or is_skippable_url(url):
            return
        if url in seen:
            return
        seen.add(url)
        found.append((name, url))

    for name, url in MD_LINK_RE.findall(line):
        add(name, url)

    remainder = MD_LINK_RE.sub("", line)
    if "<a" in remainder.lower():
        soup = BeautifulSoup(remainder, "html.parser")
        for anchor in soup.find_all("a", href=True):
            add(anchor.get_text(" ", strip=True), anchor["href"])

    return found


def line_description(line: str) -> str:
    stripped = MD_LINK_RE.sub("", line)
    if "<a" in stripped.lower():
        stripped = BeautifulSoup(stripped, "html.parser").get_text(" ", strip=True)
    stripped = re.sub(r"^\s*[-*]\s*", "", stripped)
    if " - " in stripped:
        stripped = stripped.split(" - ", 1)[1]
    return clean_text(stripped)


def parse_markdown(text: str, source_file: str) -> list[dict]:
    """
    Walk FMHY markdown and emit tool dicts.

    H1 (►), H2, and H3 headers become categories / subcategories.
    """
    tools: list[dict] = []
    page_category = clean_text(default_category_name(source_file))
    current_h1 = page_category
    current_h2 = ""
    current_h3 = ""

    def active_category() -> tuple[str, str | None, int]:
        if current_h3:
            parent = current_h2 or current_h1 or page_category
            return current_h3, parent, 3
        if current_h2:
            parent = current_h1 if current_h1 != page_category else None
            level = 2
            if parent:
                return current_h2, parent, level
            return current_h2, None, level
        return current_h1 or page_category, None, 1

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line == "***":
            continue
        if "Back to Wiki Index" in line:
            continue

        header = HEADER_RE.match(line)
        if header:
            level = len(header.group(1))
            title = clean_text(header.group(2))
            if not title:
                continue
            if level == 1:
                current_h1 = title
                current_h2 = ""
                current_h3 = ""
            elif level == 2:
                current_h2 = title
                current_h3 = ""
            else:
                current_h3 = title
            continue

        links = extract_links(line)
        if not links:
            continue

        description = line_description(line)
        category_name, parent_name, header_level = active_category()
        for name, url in links:
            tools.append(
                {
                    "name": name,
                    "url": url,
                    "description": description,
                    "category": category_name,
                    "parent_category": parent_name,
                    "header_level": header_level,
                    "source_file": source_file,
                }
            )
    return tools


def fetch_wiki_files() -> list[str]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    try:
        response = requests.get(FMHY_API_DOCS, headers=headers, timeout=30)
        response.raise_for_status()
        files = [
            item["name"]
            for item in response.json()
            if item.get("type") == "file"
            and str(item.get("name", "")).endswith(".md")
            and item["name"] not in SKIP_FILES
        ]
        if files:
            return files
    except requests.RequestException as exc:
        print(f"GitHub API listing failed ({exc}); using fallback file list.", file=sys.stderr)
    return list(FALLBACK_WIKI_FILES)


def fetch_markdown(filename: str) -> str:
    url = f"{FMHY_RAW_BASE}/{filename}"
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/plain"},
        timeout=45,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def ingest_wiki(fresh: bool = False) -> dict[str, int]:
    init_db()
    files = fetch_wiki_files()
    inserted = 0
    duplicates = 0

    with get_connection() as conn:
        if fresh:
            clear_catalog(conn)

        for filename in files:
            print(f"Fetching {filename} …")
            try:
                markdown = fetch_markdown(filename)
            except requests.RequestException as exc:
                print(f"  skipped ({exc})", file=sys.stderr)
                continue

            parsed = parse_markdown(markdown, filename)
            for item in parsed:
                parent_id = None
                if item["parent_category"]:
                    parent_id = upsert_category(
                        conn,
                        item["parent_category"],
                        filename,
                        max(item["header_level"] - 1, 1),
                    )
                category_id = upsert_category(
                    conn,
                    item["category"],
                    filename,
                    item["header_level"],
                    parent_id,
                )
                result = insert_tool(
                    conn,
                    item["name"],
                    item["url"],
                    item["description"],
                    category_id,
                    filename,
                )
                if result == "inserted":
                    inserted += 1
                else:
                    duplicates += 1
            print(f"  parsed {len(parsed)} links")

        stats = catalog_stats(conn)
        stats["inserted"] = inserted
        stats["skipped_duplicates"] = duplicates
        return stats


async def _probe_url(session: aiohttp.ClientSession, url: str) -> int:
    try:
        async with session.head(url, allow_redirects=True) as response:
            if response.status < 400:
                return response.status
            if response.status not in {403, 405, 501}:
                return response.status
        async with session.get(url, allow_redirects=True) as response:
            return response.status
    except aiohttp.ClientError:
        return 0
    except asyncio.TimeoutError:
        return 0


async def ping_links(
    concurrency: int = 12,
    limit: int | None = None,
) -> dict[str, int]:
    init_db()
    with get_connection() as conn:
        urls = iter_unique_urls(conn)
    if limit:
        urls = urls[:limit]

    timeout = aiohttp.ClientTimeout(total=15, connect=8)
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    connector = aiohttp.TCPConnector(limit=concurrency)
    sem = asyncio.Semaphore(concurrency)
    alive = 0
    dead = 0

    async def checked(session: aiohttp.ClientSession, url: str) -> tuple[str, int]:
        async with sem:
            status = await _probe_url(session, url)
            return url, status

    async with aiohttp.ClientSession(
        timeout=timeout,
        headers=headers,
        connector=connector,
    ) as session:
        tasks = [checked(session, url) for url in urls]
        with get_connection() as conn:
            for coro in asyncio.as_completed(tasks):
                url, status = await coro
                update_link_status(conn, url, status)
                if status == 200:
                    alive += 1
                    mark = "200"
                else:
                    dead += 1
                    mark = str(status) if status else "dead"
                print(f"[{mark}] {url}")
            conn.commit()

    return {"checked": len(urls), "alive": alive, "dead": dead}


def run_ping_loop(interval: int, concurrency: int, limit: int | None) -> None:
    print(f"Link checker running every {interval}s. Ctrl+C to stop.")
    while True:
        started = time.time()
        stats = asyncio.run(ping_links(concurrency=concurrency, limit=limit))
        print(
            f"Ping pass complete: {stats['alive']} HTTP 200, "
            f"{stats['dead']} dead, {stats['checked']} unique URLs."
        )
        elapsed = time.time() - started
        sleep_for = max(0, interval - elapsed)
        if sleep_for:
            time.sleep(sleep_for)


def print_duplicates() -> None:
    init_db()
    with get_connection() as conn:
        rows = find_duplicate_links(conn)
    if not rows:
        print("No duplicate links found.")
        return
    print(f"{len(rows)} URLs appear in more than one row:")
    for row in rows:
        print(f"  {row['occurrences']}×  {row['url']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FMHY wiki ingest and link checker")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Wipe categories/tools before ingesting",
    )
    parser.add_argument(
        "--ping",
        action="store_true",
        help="Ping stored URLs and record HTTP 200 vs dead",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Keep pinging on an interval (background checker)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Seconds between ping passes when --loop is set (default 3600)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=12,
        help="Parallel ping requests",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Ping only the first N unique URLs (sanity checks)",
    )
    parser.add_argument(
        "--duplicates",
        action="store_true",
        help="Print URLs stored more than once and exit",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.duplicates:
        print_duplicates()
        return
    if args.ping:
        if args.loop:
            run_ping_loop(args.interval, args.concurrency, args.limit)
        else:
            stats = asyncio.run(ping_links(args.concurrency, args.limit))
            print(
                f"Checked {stats['checked']} URLs: "
                f"{stats['alive']} HTTP 200, {stats['dead']} dead."
            )
        return

    stats = ingest_wiki(fresh=args.fresh)
    print(
        "Ingest complete: "
        f"{stats['inserted']} new tools, "
        f"{stats['skipped_duplicates']} duplicate skips, "
        f"{stats['categories']} categories, "
        f"{stats['unique_links']} unique URLs "
        f"({stats['duplicate_urls']} URLs in multiple categories)."
    )


if __name__ == "__main__":
    main()
