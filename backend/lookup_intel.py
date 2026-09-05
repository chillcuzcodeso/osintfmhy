"""Public paste-and-go lookups: IP, phone, Discord, wallet, file metadata."""

from __future__ import annotations

import ipaddress
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from urllib.parse import urlparse

import aiohttp
import phonenumbers
from phonenumbers import carrier, geocoder, timezone as pn_timezone
from PIL import Image, UnidentifiedImageError
from PIL.ExifTags import GPSTAGS, TAGS

try:
    from PIL.ExifTags import IFD
except ImportError:  # Pillow < 9.4
    IFD = None
from pypdf import PdfReader

from scam_brief import USER_AGENT, _get_json, _public_ip, resolve_public_ips

DISCORD_EPOCH_MS = 1_420_070_400_000
MAX_UPLOAD_BYTES = 8 * 1024 * 1024

SNOWFLAKE_RE = re.compile(r"\b(\d{17,20})\b")
INVITE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:discord\.gg|discord(?:app)?\.com/invite)/([A-Za-z0-9-]+)",
    re.I,
)
INVITE_CODE_RE = re.compile(r"^[A-Za-z0-9-]{2,32}$")
BTC_RE = re.compile(r"\b(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{25,62}\b")
ETH_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
TRON_RE = re.compile(r"\bT[1-9A-HJ-NP-Za-km-z]{33}\b")

PHONE_TYPES = {
    phonenumbers.PhoneNumberType.FIXED_LINE: "landline",
    phonenumbers.PhoneNumberType.MOBILE: "mobile",
    phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "landline or mobile",
    phonenumbers.PhoneNumberType.TOLL_FREE: "toll-free",
    phonenumbers.PhoneNumberType.PREMIUM_RATE: "premium",
    phonenumbers.PhoneNumberType.SHARED_COST: "shared cost",
    phonenumbers.PhoneNumberType.VOIP: "voip",
    phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "personal",
    phonenumbers.PhoneNumberType.PAGER: "pager",
    phonenumbers.PhoneNumberType.UAN: "uan",
    phonenumbers.PhoneNumberType.VOICEMAIL: "voicemail",
    phonenumbers.PhoneNumberType.UNKNOWN: "unknown",
}


def _session() -> aiohttp.ClientSession:
    timeout = aiohttp.ClientTimeout(total=14, sock_connect=5)
    return aiohttp.ClientSession(
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )


def _scope_for_ip(value: str) -> str | None:
    try:
        addr = ipaddress.ip_address(value)
    except ValueError:
        return None
    if addr.is_loopback:
        return "loopback"
    if addr.is_link_local:
        return "link-local"
    if addr.is_multicast:
        return "multicast"
    if addr.is_reserved or addr.is_unspecified:
        return "reserved"
    if addr.is_private:
        return "private"
    return "public"


def _ptr_name(ip: str) -> str:
    return ipaddress.ip_address(ip).reverse_pointer


async def _ptr(session: aiohttp.ClientSession, ip: str) -> str | None:
    data = await _get_json(
        session,
        "https://cloudflare-dns.com/dns-query",
        params={"name": _ptr_name(ip), "type": "PTR"},
        headers={"Accept": "application/dns-json"},
    )
    answers = (data or {}).get("Answer") or []
    for item in answers:
        name = str(item.get("data") or "").rstrip(".")
        if name:
            return name
    return None


def lookup_phone(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text or len(text) > 32:
        raise ValueError("Paste a phone number, including country code if you have it")

    parsed = None
    used_region = None
    for region in (None, "AU", "US", "GB"):
        try:
            candidate = phonenumbers.parse(text, region)
        except phonenumbers.NumberParseException:
            continue
        if phonenumbers.is_possible_number(candidate):
            parsed = candidate
            used_region = region
            if phonenumbers.is_valid_number(candidate):
                break

    if parsed is None:
        raise ValueError("Could not parse that as a phone number")

    ntype = phonenumbers.number_type(parsed)
    region_code = phonenumbers.region_code_for_number(parsed)
    return {
        "input": text,
        "e164": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164),
        "international": phonenumbers.format_number(
            parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
        ),
        "valid": phonenumbers.is_valid_number(parsed),
        "possible": phonenumbers.is_possible_number(parsed),
        "country": region_code,
        "country_code": parsed.country_code,
        "region": geocoder.description_for_number(parsed, "en") or None,
        "timezones": list(pn_timezone.time_zones_for_number(parsed)),
        "carrier": carrier.name_for_number(parsed, "en") or None,
        "line_type": PHONE_TYPES.get(ntype, "unknown"),
        "parsed_with_region": used_region,
        "note": (
            "Numbering-plan data only: country, area, original carrier, and line type. "
            "This is not the subscriber's name or current address."
        ),
    }


def decode_snowflake(value: str) -> dict[str, Any] | None:
    if not value.isdigit() or not (17 <= len(value) <= 20):
        return None
    snowflake = int(value)
    created_ms = (snowflake >> 22) + DISCORD_EPOCH_MS
    created = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    plausible = datetime(2015, 1, 1, tzinfo=timezone.utc) <= created <= now
    return {
        "id": value,
        "created_utc": created.isoformat(),
        "created_unix_ms": created_ms,
        "plausible": plausible,
        "could_be": ["user", "channel", "guild", "message", "invite"],
        "note": "A snowflake only encodes created-time. It does not name the account.",
    }


def _invite_code(raw: str) -> str | None:
    text = raw.strip()
    match = INVITE_RE.search(text)
    if match:
        return match.group(1)
    if INVITE_CODE_RE.match(text) and not text.isdigit():
        return text
    path = urlparse(text if "://" in text else f"https://{text}").path
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[0].lower() == "invite":
        return parts[1]
    return None


async def _discord_invite(session: aiohttp.ClientSession, code: str) -> dict[str, Any]:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; UIP/0.1; +https://github.com/chillcuzcodeso/osintfmhy)",
        "Accept": "application/json",
    }
    async with session.get(
        f"https://discord.com/api/v10/invites/{code}",
        params={"with_counts": "true", "with_expiration": "true"},
        headers=headers,
    ) as response:
        status = response.status
        try:
            data = await response.json(content_type=None)
        except Exception:
            data = None
    if status == 404 or not isinstance(data, dict) or data.get("code") == 10006:
        return {"code": code, "found": False, "error": "Invite not found or expired"}
    if status >= 400:
        return {"code": code, "found": False, "error": f"Discord API HTTP {status}"}

    guild = data.get("guild") if isinstance(data.get("guild"), dict) else {}
    channel = data.get("channel") if isinstance(data.get("channel"), dict) else {}
    inviter = data.get("inviter") if isinstance(data.get("inviter"), dict) else {}
    return {
        "code": data.get("code") or code,
        "found": True,
        "guild": guild.get("name"),
        "guild_id": guild.get("id"),
        "description": guild.get("description"),
        "nsfw": bool(guild.get("nsfw")),
        "vanity": guild.get("vanity_url_code"),
        "members": data.get("approximate_member_count"),
        "online": data.get("approximate_presence_count"),
        "expires_at": data.get("expires_at"),
        "channel": channel.get("name"),
        "inviter": inviter.get("username"),
        "inviter_id": inviter.get("id"),
        "url": f"https://discord.gg/{data.get('code') or code}",
    }


async def lookup_discord(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text or len(text) > 200:
        raise ValueError("Paste a Discord invite, discord.gg link, or snowflake ID")

    invite_code = _invite_code(text)
    snowflakes = list(dict.fromkeys(SNOWFLAKE_RE.findall(text)))[:4]
    if text.isdigit() and 17 <= len(text) <= 20 and text not in snowflakes:
        snowflakes.insert(0, text)

    if not invite_code and not snowflakes:
        raise ValueError("Need a discord.gg invite or a 17–20 digit Discord ID")

    decoded = [row for row in (decode_snowflake(sid) for sid in snowflakes) if row]
    invite = None
    if invite_code:
        async with _session() as session:
            invite = await _discord_invite(session, invite_code)
            inviter_id = invite.get("inviter_id")
            if inviter_id and inviter_id not in snowflakes:
                extra = decode_snowflake(str(inviter_id))
                if extra:
                    extra["role"] = "inviter"
                    decoded.append(extra)
            guild_id = invite.get("guild_id")
            if guild_id and guild_id not in snowflakes:
                extra = decode_snowflake(str(guild_id))
                if extra:
                    extra["role"] = "guild"
                    decoded.append(extra)

    return {
        "input": text,
        "invite": invite,
        "snowflakes": decoded,
    }


async def lookup_ip(raw: str) -> dict[str, Any]:
    text = (raw or "").strip().split()[0].strip("[]")
    if not text or len(text) > 253:
        raise ValueError("Paste a public IPv4/IPv6 address or hostname")

    try:
        ipaddress.ip_address(text)
        target = text
        resolved: list[str] = []
        hostname = None
    except ValueError:
        hostname = text.rstrip(".")
        async with _session() as session:
            resolved = await resolve_public_ips(session, hostname)
        target = resolved[0]

    scope = _scope_for_ip(target)
    if scope != "public":
        return {
            "input": text,
            "ip": target,
            "public": False,
            "scope": scope or "invalid",
            "hostname": hostname,
            "note": "This address is not on the public internet, so there is no city / ISP geolocation.",
        }

    async with _session() as session:
        who, ipapi, inet, ptr = await _gather_ip(session, target)

    geo: dict[str, Any] = {"ip": target, "public": True, "scope": "public", "hostname": hostname}
    if resolved:
        geo["resolved_ips"] = resolved
    if isinstance(who, dict) and who.get("success") is not False:
        conn = who.get("connection") or {}
        tz = who.get("timezone") or {}
        geo.update(
            {
                "type": who.get("type"),
                "continent": who.get("continent"),
                "country": who.get("country"),
                "country_code": who.get("country_code"),
                "region": who.get("region"),
                "city": who.get("city"),
                "postal": who.get("postal"),
                "latitude": who.get("latitude"),
                "longitude": who.get("longitude"),
                "timezone": tz.get("id"),
                "utc_offset": tz.get("utc"),
                "asn": conn.get("asn"),
                "org": conn.get("org"),
                "isp": conn.get("isp"),
                "domain": conn.get("domain"),
            }
        )
    if isinstance(ipapi, dict) and ipapi.get("status") == "success":
        geo.setdefault("country", ipapi.get("country"))
        geo.setdefault("region", ipapi.get("regionName"))
        geo.setdefault("city", ipapi.get("city"))
        geo.setdefault("latitude", ipapi.get("lat"))
        geo.setdefault("longitude", ipapi.get("lon"))
        geo.setdefault("timezone", ipapi.get("timezone"))
        geo.setdefault("isp", ipapi.get("isp"))
        geo.setdefault("org", ipapi.get("org"))
        if not geo.get("asn") and ipapi.get("as"):
            geo["asn"] = str(ipapi.get("as")).split()[0].lstrip("AS")
            geo["as_name"] = ipapi.get("asname")
        geo["mobile"] = bool(ipapi.get("mobile"))
        geo["proxy"] = bool(ipapi.get("proxy"))
        geo["hosting"] = bool(ipapi.get("hosting"))
        if ipapi.get("reverse"):
            geo["reverse_ipapi"] = ipapi.get("reverse")
    if isinstance(inet, dict):
        geo["ports"] = inet.get("ports") or []
        geo["hostnames"] = inet.get("hostnames") or []
        geo["cpes"] = inet.get("cpes") or []
        geo["vulns"] = inet.get("vulns") or []
    geo["ptr"] = ptr
    geo["map"] = None
    lat, lon = geo.get("latitude"), geo.get("longitude")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        pad = 0.08
        geo["map"] = {
            "osm": f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=10/{lat}/{lon}",
            "embed": (
                "https://www.openstreetmap.org/export/embed.html"
                f"?bbox={lon - pad},{lat - pad},{lon + pad},{lat + pad}"
                f"&layer=mapnik&marker={lat},{lon}"
            ),
        }
    geo["note"] = "City / region / ISP only. This is not a street address."
    geo["input"] = text
    return geo


async def _gather_ip(session: aiohttp.ClientSession, ip: str) -> tuple[Any, Any, Any, str | None]:
    import asyncio

    return await asyncio.gather(
        _get_json(session, f"https://ipwho.is/{ip}"),
        _get_json(
            session,
            f"http://ip-api.com/json/{ip}",
            params={
                "fields": "status,message,country,regionName,city,lat,lon,timezone,isp,org,as,asname,mobile,proxy,hosting,reverse,query"
            },
        ),
        _get_json(session, f"https://internetdb.shodan.io/{ip}"),
        _ptr(session, ip),
    )


def detect_wallet(raw: str) -> tuple[str, str] | None:
    text = (raw or "").strip()
    for chain, regex in (("eth", ETH_RE), ("btc", BTC_RE), ("tron", TRON_RE)):
        match = regex.search(text)
        if match:
            return chain, match.group(0)
    return None


def _sats(value: Any) -> float | None:
    try:
        return int(value) / 100_000_000
    except (TypeError, ValueError):
        return None


async def lookup_wallet(raw: str) -> dict[str, Any]:
    found = detect_wallet(raw)
    if not found:
        raise ValueError("Paste a BTC, ETH (0x…), or TRON (T…) address")
    chain, address = found
    async with _session() as session:
        if chain == "btc":
            body = await _btc(session, address)
        elif chain == "eth":
            body = await _eth(session, address)
        else:
            body = await _tron(session, address)
    body["input"] = raw.strip()
    return body


async def _btc(session: aiohttp.ClientSession, address: str) -> dict[str, Any]:
    data = await _get_json(session, f"https://blockstream.info/api/address/{address}")
    txs = await _get_json(session, f"https://blockstream.info/api/address/{address}/txs")
    if not isinstance(data, dict) or data.get("error"):
        return {
            "chain": "btc",
            "address": address,
            "found": False,
            "error": (data or {}).get("error") if isinstance(data, dict) else "No data",
            "explorer": f"https://mempool.space/address/{address}",
        }
    chain_stats = data.get("chain_stats") or {}
    latest = None
    if isinstance(txs, list) and txs:
        first = txs[0] if isinstance(txs[0], dict) else {}
        status = first.get("status") or {}
        latest = {
            "txid": first.get("txid"),
            "block_time": status.get("block_time"),
            "confirmed": bool(status.get("confirmed")),
        }
    funded = _sats(chain_stats.get("funded_txo_sum"))
    spent = _sats(chain_stats.get("spent_txo_sum"))
    return {
        "chain": "btc",
        "address": address,
        "found": True,
        "balance": None if funded is None or spent is None else round(funded - spent, 8),
        "unit": "BTC",
        "received": funded,
        "sent": spent,
        "tx_count": chain_stats.get("tx_count"),
        "latest_tx": latest,
        "explorer": f"https://mempool.space/address/{address}",
    }


async def _eth(session: aiohttp.ClientSession, address: str) -> dict[str, Any]:
    data = await _get_json(session, f"https://eth.blockscout.com/api/v2/addresses/{address}")
    counters = await _get_json(
        session, f"https://eth.blockscout.com/api/v2/addresses/{address}/counters"
    )
    if not isinstance(data, dict) or data.get("message") == "Not found":
        return {
            "chain": "eth",
            "address": address,
            "found": False,
            "error": "Address not found on Blockscout",
            "explorer": f"https://etherscan.io/address/{address}",
        }
    wei = data.get("coin_balance")
    try:
        balance = int(wei) / 1e18 if wei is not None else None
    except (TypeError, ValueError):
        balance = None
    return {
        "chain": "eth",
        "address": address,
        "found": True,
        "balance": None if balance is None else round(balance, 8),
        "unit": "ETH",
        "is_contract": bool(data.get("is_contract")),
        "ens": data.get("ens_domain_name"),
        "tx_count": (counters or {}).get("transactions_count") if isinstance(counters, dict) else None,
        "creation_tx": data.get("creation_tx_hash"),
        "explorer": f"https://etherscan.io/address/{address}",
    }


async def _tron(session: aiohttp.ClientSession, address: str) -> dict[str, Any]:
    data = await _get_json(session, f"https://api.trongrid.io/v1/accounts/{address}")
    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        return {
            "chain": "tron",
            "address": address,
            "found": False,
            "error": "Address not found on TronGrid",
            "explorer": f"https://tronscan.org/#/address/{address}",
        }
    row = rows[0] if isinstance(rows[0], dict) else {}
    sun = row.get("balance")
    try:
        balance = int(sun) / 1_000_000 if sun is not None else 0.0
    except (TypeError, ValueError):
        balance = None
    created = row.get("create_time")
    latest = row.get("latest_opration_time") or row.get("latest_operation_time")
    return {
        "chain": "tron",
        "address": address,
        "found": True,
        "balance": None if balance is None else round(balance, 6),
        "unit": "TRX",
        "created_unix_ms": created,
        "last_active_unix_ms": latest,
        "explorer": f"https://tronscan.org/#/address/{address}",
    }


def _ratio(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, tuple) and len(value) == 2 and value[1]:
        return float(value[0]) / float(value[1])
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _gps_decimal(gps: dict[str, Any]) -> tuple[float, float] | None:
    lat = gps.get("GPSLatitude")
    lat_ref = gps.get("GPSLatitudeRef")
    lon = gps.get("GPSLongitude")
    lon_ref = gps.get("GPSLongitudeRef")
    if not lat or not lon or not lat_ref or not lon_ref:
        return None
    try:
        lat_d = sum(
            (_ratio(part) or 0.0) / div
            for part, div in zip(lat, (1, 60, 3600))
        )
        lon_d = sum(
            (_ratio(part) or 0.0) / div
            for part, div in zip(lon, (1, 60, 3600))
        )
    except (TypeError, ValueError):
        return None
    if str(lat_ref).upper().startswith("S"):
        lat_d = -lat_d
    if str(lon_ref).upper().startswith("W"):
        lon_d = -lon_d
    return lat_d, lon_d


def _decode_exif_value(value: Any) -> Any:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace").strip("\x00").strip()
        except Exception:
            return value.hex()
    if isinstance(value, (list, tuple)) and len(value) <= 8:
        return [_decode_exif_value(item) for item in value]
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)


def _image_meta(data: bytes) -> dict[str, Any]:
    image = Image.open(BytesIO(data))
    image.load()
    tags: dict[str, Any] = {}
    gps_tags: dict[str, Any] = {}
    try:
        exif = image.getexif()
    except Exception:
        exif = None
    if exif:
        for key, value in exif.items():
            name = TAGS.get(key, str(key))
            if name in {"MakerNote", "UserComment", "PrintImageMatching"}:
                continue
            tags[name] = _decode_exif_value(value)
        try:
            gps_ifd = exif.get_ifd(IFD.GPSInfo) if IFD is not None and hasattr(exif, "get_ifd") else {}
        except Exception:
            gps_ifd = {}
        for key, value in (gps_ifd or {}).items():
            gps_tags[GPSTAGS.get(key, str(key))] = _decode_exif_value(value)

    coords = _gps_decimal(gps_tags) if gps_tags else None
    return {
        "kind": "image",
        "format": image.format,
        "width": image.width,
        "height": image.height,
        "mode": image.mode,
        "camera_make": tags.get("Make"),
        "camera_model": tags.get("Model"),
        "software": tags.get("Software"),
        "taken_at": tags.get("DateTimeOriginal") or tags.get("DateTime"),
        "artist": tags.get("Artist"),
        "copyright": tags.get("Copyright"),
        "gps": {"latitude": coords[0], "longitude": coords[1]} if coords else None,
        "map": (
            {
                "osm": f"https://www.openstreetmap.org/?mlat={coords[0]}&mlon={coords[1]}#map=15/{coords[0]}/{coords[1]}",
            }
            if coords
            else None
        ),
        "exif": {k: tags[k] for k in ("DateTime", "DateTimeOriginal", "Make", "Model", "Software", "Orientation", "LensModel", "HostComputer") if k in tags},
    }


def _pdf_meta(data: bytes) -> dict[str, Any]:
    reader = PdfReader(BytesIO(data))
    info = reader.metadata or {}
    fields = {}
    for key in ("/Title", "/Author", "/Subject", "/Creator", "/Producer", "/CreationDate", "/ModDate"):
        value = info.get(key)
        if value:
            fields[key.lstrip("/")] = str(value)
    return {
        "kind": "pdf",
        "pages": len(reader.pages),
        "encrypted": bool(reader.is_encrypted),
        "title": fields.get("Title"),
        "author": fields.get("Author"),
        "subject": fields.get("Subject"),
        "creator": fields.get("Creator"),
        "producer": fields.get("Producer"),
        "created": fields.get("CreationDate"),
        "modified": fields.get("ModDate"),
    }


def inspect_file_meta(data: bytes, filename: str, content_type: str | None) -> dict[str, Any]:
    if not data:
        raise ValueError("Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("File too large (8 MB max)")
    if data[4:8] == b"ftyp" and b"heic" in data[4:16].lower():
        raise ValueError("HEIC is not supported — export a JPEG first")

    base = {
        "filename": filename,
        "size_bytes": len(data),
        "content_type": content_type,
        "note": "Parsed in memory and discarded. No file is stored.",
    }
    if data.startswith(b"%PDF"):
        return {**base, **_pdf_meta(data)}
    try:
        return {**base, **_image_meta(data)}
    except UnidentifiedImageError as exc:
        raise ValueError("Use a JPEG, PNG, WebP, TIFF, or PDF") from exc
    except Exception as exc:
        if data.startswith(b"%PDF"):
            raise
        raise ValueError(f"Could not read file metadata: {exc}") from exc
