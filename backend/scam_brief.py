"""Scam-lure infrastructure brief from a pasted URL or message. No API keys."""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import ssl
from typing import Any
from urllib.parse import urlparse

import aiohttp

USER_AGENT = "UnifiedIntelligencePortal/0.1 (scam-infrastructure brief; public sources)"

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,24}\b", re.I)
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,18}\d")
DOMAIN_RE = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,24}\b", re.I)
BTC_RE = re.compile(r"\b(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{25,62}\b")
ETH_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
TRON_RE = re.compile(r"\bT[1-9A-HJ-NP-Za-km-z]{33}\b")

SKIP_DOMAINS = {
    "gmail.com",
    "google.com",
    "googleapis.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "icloud.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "instagram.com",
}


def _public_ip(value: str) -> bool:
    try:
        addr = ipaddress.ip_address(value)
    except ValueError:
        return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def assert_public_host(host: str) -> list[str]:
    host = host.strip("[]").lower()
    if host in {"localhost", "metadata.google.internal"}:
        raise ValueError("Refusing to contact a private or metadata host")
    try:
        ipaddress.ip_address(host)
        if not _public_ip(host):
            raise ValueError("Refusing to contact a private IP")
        return [host]
    except ValueError as exc:
        if "Refusing" in str(exc):
            raise

    infos = socket.getaddrinfo(host, None)
    ips = sorted({item[4][0] for item in infos})
    if not ips:
        raise ValueError(f"Could not resolve {host}")
    if not all(_public_ip(ip) for ip in ips):
        raise ValueError("Refusing to contact a host that resolves to a private address")
    return ips


def extract_artifacts(text: str) -> dict[str, list[str]]:
    urls = list(dict.fromkeys(URL_RE.findall(text)))[:8]
    emails = list(dict.fromkeys(e.lower() for e in EMAIL_RE.findall(text)))[:8]
    phones = list(dict.fromkeys(re.sub(r"\s+", " ", p).strip() for p in PHONE_RE.findall(text)))[:8]
    wallets = {
        "btc": list(dict.fromkeys(BTC_RE.findall(text)))[:6],
        "eth": list(dict.fromkeys(ETH_RE.findall(text)))[:6],
        "tron": list(dict.fromkeys(TRON_RE.findall(text)))[:6],
    }
    domains: list[str] = []
    for url in urls:
        host = urlparse(url).hostname
        if host:
            domains.append(host.lower())
    for match in DOMAIN_RE.findall(text):
        host = match.lower()
        if host in SKIP_DOMAINS or host.split("@")[-1] in SKIP_DOMAINS:
            continue
        if any(host.endswith(f".{skip}") for skip in SKIP_DOMAINS):
            continue
        domains.append(host)
    for email in emails:
        domains.append(email.split("@", 1)[1])
    clean_domains = []
    for host in domains:
        if host in SKIP_DOMAINS:
            continue
        if host not in clean_domains:
            clean_domains.append(host)
    return {
        "urls": urls,
        "emails": emails,
        "phones": phones,
        "wallets": wallets,
        "domains": clean_domains[:8],
    }


async def _get_json(session: aiohttp.ClientSession, url: str, **kwargs) -> Any:
    async with session.get(url, **kwargs) as response:
        if response.status >= 400:
            return None
        try:
            return await response.json(content_type=None)
        except Exception:
            return None


async def dns_records(session: aiohttp.ClientSession, host: str) -> dict[str, list[str]]:
    records: dict[str, list[str]] = {}
    for rtype in ("A", "AAAA", "MX", "NS", "TXT"):
        data = await _get_json(
            session,
            "https://cloudflare-dns.com/dns-query",
            params={"name": host, "type": rtype},
            headers={"Accept": "application/dns-json"},
        )
        answers = (data or {}).get("Answer") or []
        records[rtype] = [str(item.get("data", "")) for item in answers][:8]
    return records


async def rdap_domain(session: aiohttp.ClientSession, host: str) -> dict[str, Any]:
    data = await _get_json(session, f"https://rdap.org/domain/{host}")
    if not isinstance(data, dict):
        return {}
    events = {item.get("eventAction"): item.get("eventDate") for item in data.get("events") or [] if isinstance(item, dict)}
    nameservers = [
        (ns.get("ldhName") or ns.get("unicodeName") or "")
        for ns in data.get("nameservers") or []
        if isinstance(ns, dict)
    ]
    return {
        "handle": data.get("handle"),
        "ldh_name": data.get("ldhName"),
        "registered": events.get("registration"),
        "expires": events.get("expiration"),
        "last_changed": events.get("last changed"),
        "nameservers": [ns.lower() for ns in nameservers if ns][:8],
        "status": data.get("status") or [],
    }


async def crtsh_names(session: aiohttp.ClientSession, host: str) -> list[str]:
    data = await _get_json(session, "https://crt.sh/", params={"q": host, "output": "json"})
    if not isinstance(data, list):
        return []
    names: list[str] = []
    for row in data[:80]:
        if not isinstance(row, dict):
            continue
        for part in str(row.get("name_value") or "").split("\n"):
            name = part.strip().lower().lstrip("*.")
            if name and name not in names:
                names.append(name)
            if len(names) >= 25:
                return names
    return names


async def wayback(session: aiohttp.ClientSession, host: str) -> dict[str, Any]:
    data = await _get_json(
        session,
        "https://web.archive.org/cdx/search/cdx",
        params={"url": f"{host}/*", "output": "json", "limit": "5", "fl": "timestamp,original,statuscode"},
    )
    rows = data[1:] if isinstance(data, list) and data else []
    snapshots = []
    for row in rows[:5]:
        if isinstance(row, list) and len(row) >= 1:
            ts = row[0]
            snapshots.append(
                {
                    "timestamp": ts,
                    "url": f"https://web.archive.org/web/{ts}/{row[1] if len(row) > 1 else host}",
                }
            )
    return {
        "count_shown": len(snapshots),
        "snapshots": snapshots,
        "calendar": f"https://web.archive.org/web/*/{host}",
    }


async def ip_brief(session: aiohttp.ClientSession, ip: str) -> dict[str, Any]:
    who = await _get_json(session, f"https://ipwho.is/{ip}")
    inet = await _get_json(session, f"https://internetdb.shodan.io/{ip}")
    brief = {"ip": ip}
    if isinstance(who, dict) and who.get("success") is not False:
        brief.update(
            {
                "country": who.get("country"),
                "city": who.get("city"),
                "asn": (who.get("connection") or {}).get("asn"),
                "org": (who.get("connection") or {}).get("org"),
                "isp": (who.get("connection") or {}).get("isp"),
            }
        )
    if isinstance(inet, dict):
        brief.update(
            {
                "ports": inet.get("ports") or [],
                "hostnames": inet.get("hostnames") or [],
                "cpes": inet.get("cpes") or [],
                "vulns": inet.get("vulns") or [],
            }
        )
    return brief


async def urlhaus_host(session: aiohttp.ClientSession, host: str) -> dict[str, Any]:
    try:
        async with session.post(
            "https://urlhaus-api.abuse.ch/v1/host/",
            data={"host": host},
        ) as response:
            if response.status >= 400:
                return {"listed": False, "status_code": response.status}
            data = await response.json(content_type=None)
    except aiohttp.ClientError:
        return {"listed": False, "error": "unreachable"}
    if not isinstance(data, dict):
        return {"listed": False}
    return {
        "listed": data.get("query_status") == "ok",
        "url_count": data.get("url_count"),
        "blacklists": data.get("blacklists") or {},
    }


async def resolve_public_ips(session: aiohttp.ClientSession, host: str) -> list[str]:
    host = host.strip("[]").lower()
    try:
        ipaddress.ip_address(host)
        if not _public_ip(host):
            raise ValueError("Refusing to contact a private IP")
        return [host]
    except ValueError as exc:
        if "Refusing" in str(exc):
            raise

    records = await dns_records(session, host)
    ips = [ip for ip in records.get("A", []) + records.get("AAAA", []) if _public_ip(ip)]
    if not ips:
        try:
            return assert_public_host(host)
        except (ValueError, socket.gaierror) as exc:
            raise ValueError(f"Could not resolve {host}: {exc}") from exc
    return ips


def tls_cert(host: str, ip: str | None = None) -> dict[str, Any]:
    try:
        target = ip or host
        if ip and not _public_ip(ip):
            raise ValueError("Refusing to contact a private IP")
        if not ip:
            assert_public_host(host)
        ctx = ssl.create_default_context()
        with socket.create_connection((target, 443), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
    except (OSError, ValueError, ssl.SSLError) as exc:
        return {"error": str(exc)}
    sans = []
    for kind, value in cert.get("subjectAltName") or []:
        if kind == "DNS":
            sans.append(value)
    subject = dict(x[0] for x in (cert.get("subject") or ()) if x)
    issuer = dict(x[0] for x in (cert.get("issuer") or ()) if x)
    return {
        "subject": subject.get("commonName"),
        "issuer": issuer.get("commonName") or issuer.get("organizationName"),
        "not_before": cert.get("notBefore"),
        "not_after": cert.get("notAfter"),
        "sans": sans[:15],
    }


def explorer_links(wallets: dict[str, list[str]]) -> list[dict[str, str]]:
    links = []
    for addr in wallets.get("btc") or []:
        links.append({"chain": "btc", "address": addr, "url": f"https://www.blockchain.com/explorer/search?search={addr}"})
    for addr in wallets.get("eth") or []:
        links.append({"chain": "eth", "address": addr, "url": f"https://etherscan.io/address/{addr}"})
    for addr in wallets.get("tron") or []:
        links.append({"chain": "tron", "address": addr, "url": f"https://tronscan.org/#/address/{addr}"})
    return links


async def build_scam_brief(text: str) -> dict[str, Any]:
    artifacts = extract_artifacts(text)
    host = artifacts["domains"][0] if artifacts["domains"] else None
    timeout = aiohttp.ClientTimeout(total=18, sock_connect=6)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    domain_report: dict[str, Any] | None = None

    if host:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            try:
                ips = await resolve_public_ips(session, host)
            except ValueError as exc:
                domain_report = {"host": host, "error": str(exc)}
            else:
                dns, rdap, certs, archive, listed, *ip_rows = await asyncio.gather(
                    dns_records(session, host),
                    rdap_domain(session, host),
                    crtsh_names(session, host),
                    wayback(session, host),
                    urlhaus_host(session, host),
                    *[ip_brief(session, ip) for ip in ips[:2]],
                )
                domain_report = {
                    "host": host,
                    "ips": ips,
                    "dns": dns,
                    "rdap": rdap,
                    "tls": tls_cert(host, ips[0] if ips else None),
                    "certificates": certs,
                    "wayback": archive,
                    "urlhaus": listed,
                    "ip": ip_rows,
                    "links": {
                        "crtsh": f"https://crt.sh/?q={host}",
                        "wayback": f"https://web.archive.org/web/*/{host}",
                        "urlscan": f"https://urlscan.io/search/#domain:{host}",
                        "whois": f"https://lookup.icann.org/en/lookup?name={host}",
                    },
                }

    return {
        "artifacts": artifacts,
        "primary_host": host,
        "domain": domain_report,
        "wallets": explorer_links(artifacts["wallets"]),
        "reports": [
            {"name": "IC3", "url": "https://www.ic3.gov/Home/FileComplaint"},
            {"name": "FTC ReportFraud", "url": "https://reportfraud.ftc.gov/"},
            {"name": "Scamwatch (AU)", "url": "https://www.scamwatch.gov.au/report-a-scam"},
        ],
    }
