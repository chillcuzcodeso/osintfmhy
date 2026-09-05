"""SQLite schema and helpers for the Unified Intelligence Portal catalog."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

DB_PATH = Path(os.getenv("PORTAL_DB", Path(__file__).resolve().parent / "portal.db"))

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    parent_id INTEGER REFERENCES categories(id),
    source_file TEXT NOT NULL,
    header_level INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    url_normalized TEXT NOT NULL,
    description TEXT,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    source_file TEXT,
    status_code INTEGER,
    is_alive INTEGER,
    last_checked TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(url_normalized, category_id)
);

CREATE INDEX IF NOT EXISTS idx_categories_source_slug
    ON categories(source_file, slug);
CREATE INDEX IF NOT EXISTS idx_categories_parent
    ON categories(parent_id);
CREATE INDEX IF NOT EXISTS idx_tools_category
    ON tools(category_id);
CREATE INDEX IF NOT EXISTS idx_tools_url
    ON tools(url_normalized);
CREATE INDEX IF NOT EXISTS idx_tools_alive
    ON tools(is_alive);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_url(url: str) -> str:
    """Canonicalize a URL for duplicate detection."""
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "https").lower()
    host = (parsed.hostname or "").lower()
    port = parsed.port
    if port and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    else:
        netloc = host
    path = parsed.path.rstrip("/") or ""
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | str | None = None) -> Path:
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(path) as conn:
        conn.executescript(SCHEMA)
    return path


def slugify(name: str) -> str:
    import re

    cleaned = re.sub(r"[^\w\s-]", "", name, flags=re.UNICODE)
    return re.sub(r"[-\s]+", "-", cleaned.strip().lower()) or "uncategorized"


def upsert_category(
    conn: sqlite3.Connection,
    name: str,
    source_file: str,
    header_level: int,
    parent_id: int | None = None,
) -> int:
    slug = slugify(name)
    if parent_id is None:
        row = conn.execute(
            """
            SELECT id FROM categories
            WHERE source_file = ? AND slug = ? AND parent_id IS NULL
            """,
            (source_file, slug),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT id FROM categories
            WHERE source_file = ? AND slug = ? AND parent_id = ?
            """,
            (source_file, slug, parent_id),
        ).fetchone()
    if row:
        return int(row["id"])

    cur = conn.execute(
        """
        INSERT INTO categories (name, slug, parent_id, source_file, header_level, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name, slug, parent_id, source_file, header_level, utc_now()),
    )
    return int(cur.lastrowid)


def link_exists(
    conn: sqlite3.Connection,
    url: str,
    category_id: int | None = None,
) -> bool:
    """Return True if this URL is already stored (optionally in a category)."""
    normalized = normalize_url(url)
    if category_id is None:
        row = conn.execute(
            "SELECT 1 FROM tools WHERE url_normalized = ? LIMIT 1",
            (normalized,),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT 1 FROM tools
            WHERE url_normalized = ? AND category_id = ?
            LIMIT 1
            """,
            (normalized, category_id),
        ).fetchone()
    return row is not None


def find_duplicate_links(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """URLs stored more than once (same link in multiple categories or rows)."""
    return conn.execute(
        """
        SELECT
            url_normalized,
            url,
            COUNT(*) AS occurrences,
            GROUP_CONCAT(category_id) AS category_ids
        FROM tools
        GROUP BY url_normalized
        HAVING COUNT(*) > 1
        ORDER BY occurrences DESC, url_normalized
        """
    ).fetchall()


def insert_tool(
    conn: sqlite3.Connection,
    name: str,
    url: str,
    description: str,
    category_id: int,
    source_file: str,
) -> str:
    """
    Insert a tool if the link is new for this category.

    Returns "inserted" or "duplicate".
    """
    if link_exists(conn, url, category_id):
        return "duplicate"

    conn.execute(
        """
        INSERT INTO tools (
            name, url, url_normalized, description, category_id,
            source_file, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (name, url, normalize_url(url), description, category_id, source_file, utc_now()),
    )
    return "inserted"


def update_link_status(
    conn: sqlite3.Connection,
    url: str,
    status_code: int | None,
) -> None:
    is_alive = 1 if status_code == 200 else 0
    conn.execute(
        """
        UPDATE tools
        SET status_code = ?, is_alive = ?, last_checked = ?
        WHERE url_normalized = ?
        """,
        (status_code, is_alive, utc_now(), normalize_url(url)),
    )


def iter_unique_urls(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT url FROM tools ORDER BY url"
    ).fetchall()
    return [row["url"] for row in rows]


def clear_catalog(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM tools")
    conn.execute("DELETE FROM categories")


def catalog_stats(conn: sqlite3.Connection) -> dict[str, int]:
    categories = conn.execute("SELECT COUNT(*) AS n FROM categories").fetchone()["n"]
    tools = conn.execute("SELECT COUNT(*) AS n FROM tools").fetchone()["n"]
    unique_links = conn.execute(
        "SELECT COUNT(DISTINCT url_normalized) AS n FROM tools"
    ).fetchone()["n"]
    duplicates = len(find_duplicate_links(conn))
    return {
        "categories": categories,
        "tools": tools,
        "unique_links": unique_links,
        "duplicate_urls": duplicates,
    }


if __name__ == "__main__":
    path = init_db()
    print(f"Initialized SQLite database at {path}")
