"""Unified Intelligence Portal API — reads portal.db and triggers wiki ingest."""

from __future__ import annotations

import asyncio
import json
import os
import re
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from database import get_connection, init_db
from osint_scanner import (
    iter_username_scan,
    normalize_handle,
    platform_catalog,
    scan_username,
)
from scraper import ingest_wiki
from terminal_diag import run_diagnostic

LIKE_ESCAPE_RE = re.compile(r"([\\%_])")
TOKEN_SPLIT_RE = re.compile(r"\s+")

_scrape_lock = threading.Lock()
_scrape_state: dict[str, Any] = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "error": None,
    "result": None,
}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Unified Intelligence Portal",
    version="0.1.0",
    lifespan=lifespan,
)

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

_cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https://.*\.(vercel\.app|trycloudflare\.com)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_tool(row, *, category_name: str | None = None) -> dict[str, Any]:
    payload = {
        "id": row["id"],
        "name": row["name"],
        "url": row["url"],
        "description": row["description"] or "",
        "category_id": row["category_id"],
        "source_file": row["source_file"],
        "status_code": row["status_code"],
        "is_alive": row["is_alive"],
        "last_checked": row["last_checked"],
    }
    if category_name is not None:
        payload["category"] = category_name
    return payload


def _escape_like(token: str) -> str:
    return LIKE_ESCAPE_RE.sub(r"\\\1", token)


def _score_match(name: str, category: str, description: str, tokens: list[str]) -> int:
    """Rank LIKE hits in memory: name > category > description."""
    name_l = name.casefold()
    category_l = category.casefold()
    description_l = description.casefold()
    joined = " ".join(tokens).casefold()
    score = 0

    if name_l == joined:
        score += 120
    elif name_l.startswith(joined):
        score += 90

    for token in tokens:
        token_l = token.casefold()
        if token_l in name_l:
            score += 50
            if name_l.startswith(token_l):
                score += 20
        if token_l in category_l:
            score += 30
        if token_l in description_l:
            score += 15
    return score


def _fetch_tools_grouped() -> dict[str, Any]:
    init_db()
    with get_connection() as conn:
        categories = conn.execute(
            """
            SELECT id, name, slug, parent_id, source_file, header_level
            FROM categories
            ORDER BY source_file, header_level, name COLLATE NOCASE
            """
        ).fetchall()
        tools = conn.execute(
            """
            SELECT id, name, url, description, category_id, source_file,
                   status_code, is_alive, last_checked
            FROM tools
            ORDER BY name COLLATE NOCASE
            """
        ).fetchall()

    parent_names = {row["id"]: row["name"] for row in categories}
    tools_by_category: dict[int, list[dict[str, Any]]] = {}
    for tool in tools:
        tools_by_category.setdefault(tool["category_id"], []).append(_row_to_tool(tool))

    grouped = []
    for category in categories:
        items = tools_by_category.get(category["id"])
        if not items:
            continue
        grouped.append(
            {
                "id": category["id"],
                "name": category["name"],
                "slug": category["slug"],
                "parent_id": category["parent_id"],
                "parent_name": parent_names.get(category["parent_id"]),
                "source_file": category["source_file"],
                "header_level": category["header_level"],
                "tool_count": len(items),
                "tools": items,
            }
        )

    return {
        "count": len(tools),
        "category_count": len(grouped),
        "categories": grouped,
    }


def _search_catalog(query: str, limit: int) -> dict[str, Any]:
    init_db()
    tokens = [token for token in TOKEN_SPLIT_RE.split(query.strip()) if token]
    if not tokens:
        return {"query": query, "count": 0, "results": []}

    clauses: list[str] = []
    params: list[str] = []
    for token in tokens:
        pattern = f"%{_escape_like(token)}%"
        clauses.append(
            """
            (
                tools.name LIKE ? ESCAPE '\\'
                OR IFNULL(tools.description, '') LIKE ? ESCAPE '\\'
                OR categories.name LIKE ? ESCAPE '\\'
            )
            """
        )
        params.extend([pattern, pattern, pattern])

    sql = f"""
        SELECT
            tools.id, tools.name, tools.url, tools.description,
            tools.category_id, tools.source_file, tools.status_code,
            tools.is_alive, tools.last_checked,
            categories.name AS category_name,
            categories.slug AS category_slug,
            categories.header_level AS header_level,
            parent.name AS parent_name
        FROM tools
        JOIN categories ON categories.id = tools.category_id
        LEFT JOIN categories AS parent ON parent.id = categories.parent_id
        WHERE {" AND ".join(clauses)}
    """

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    ranked: list[dict[str, Any]] = []
    for row in rows:
        payload = _row_to_tool(row, category_name=row["category_name"])
        payload["category_slug"] = row["category_slug"]
        payload["parent_name"] = row["parent_name"]
        payload["header_level"] = row["header_level"]
        payload["score"] = _score_match(
            row["name"],
            row["category_name"],
            row["description"] or "",
            tokens,
        )
        ranked.append(payload)

    ranked.sort(key=lambda item: (-item["score"], item["name"].casefold()))
    return {"query": query, "count": len(ranked), "results": ranked[:limit]}


def _run_scrape(fresh: bool) -> None:
    try:
        result = ingest_wiki(fresh=fresh)
        with _scrape_lock:
            _scrape_state["result"] = result
            _scrape_state["error"] = None
    except Exception as exc:  # noqa: BLE001 — surface any ingest failure to the API
        with _scrape_lock:
            _scrape_state["result"] = None
            _scrape_state["error"] = str(exc)
    finally:
        with _scrape_lock:
            _scrape_state["running"] = False
            _scrape_state["finished_at"] = _utc_now()


def _snapshot_scrape_state() -> dict[str, Any]:
    with _scrape_lock:
        return dict(_scrape_state)


@app.get("/")
async def root():
    index = FRONTEND_DIST / "index.html"
    if index.is_file():
        return FileResponse(index)
    return {
        "message": "Hello World",
        "service": "Unified Intelligence Portal API",
        "status": "ok",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/tools")
async def list_tools():
    """Return every tool grouped under its category."""
    return await asyncio.to_thread(_fetch_tools_grouped)


@app.get("/api/search")
async def search_tools(
    q: str = Query(..., min_length=1, max_length=200, description="Search text"),
    limit: int = Query(100, ge=1, le=500),
):
    """
    Fuzzy catalog search.

    SQLite LIKE narrows candidates across tool name, description, and category.
    An in-memory scorer then ranks name hits above category and description hits.
    """
    return await asyncio.to_thread(_search_catalog, q, limit)


@app.get("/api/osint/username")
async def osint_username(
    handle: str = Query(..., min_length=1, max_length=64, description="Account handle"),
    stream: bool = Query(False, description="Stream SSE events as each platform resolves"),
):
    """
    Probe public profile URLs for a handle across popular platforms.

    HTTP 200 is treated as an existing account. Set stream=true for live SSE updates.
    """
    try:
        normalized = normalize_handle(handle)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not stream:
        return await scan_username(normalized)

    async def event_source():
        start = {
            "handle": normalized,
            "platforms": platform_catalog(),
        }
        yield f"event: start\ndata: {json.dumps(start)}\n\n"
        found = 0
        checked = 0
        async for item in iter_username_scan(normalized):
            checked += 1
            if item["exists"]:
                found += 1
            yield f"event: result\ndata: {json.dumps(item)}\n\n"
        done = {
            "handle": normalized,
            "checked": checked,
            "found": found,
        }
        yield f"event: done\ndata: {json.dumps(done)}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class TerminalRunRequest(BaseModel):
    target: str = Field(..., min_length=1, max_length=253)
    command: Literal["ping", "nslookup", "whois"]


@app.post("/api/terminal/run")
async def terminal_run(body: TerminalRunRequest):
    """
    Run an allowlisted local diagnostic: ping, nslookup, or whois.

    The target is validated as a hostname or IP. Commands are executed with
    subprocess and shell=False — user input is never interpolated into a shell.
    """
    try:
        result = await asyncio.to_thread(run_diagnostic, body.command, body.target)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return result


@app.post("/api/scrape-update", status_code=202)
async def scrape_update(
    background_tasks: BackgroundTasks,
    fresh: bool = Query(False, description="Wipe the catalog before ingesting"),
):
    """Manually trigger scraper.py ingest against the FMHY wiki."""
    with _scrape_lock:
        if _scrape_state["running"]:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "A scrape is already running",
                    **{k: v for k, v in _scrape_state.items() if k != "running"},
                    "running": True,
                },
            )
        _scrape_state["running"] = True
        _scrape_state["started_at"] = _utc_now()
        _scrape_state["finished_at"] = None
        _scrape_state["error"] = None
        _scrape_state["result"] = None

    background_tasks.add_task(_run_scrape, fresh)
    return {
        "message": "Scrape started",
        "fresh": fresh,
        **_snapshot_scrape_state(),
    }


_assets_dir = FRONTEND_DIST / "assets"
if _assets_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    reserved = {"api", "docs", "redoc", "openapi.json", "health"}
    first = full_path.split("/", 1)[0]
    if first in reserved or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    candidate = FRONTEND_DIST / full_path
    if candidate.is_file():
        return FileResponse(candidate)
    index = FRONTEND_DIST / "index.html"
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Frontend build not found")
