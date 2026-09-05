"""Allowlisted local network diagnostics via subprocess (no shell)."""

from __future__ import annotations

import ipaddress
import os
import re
import shutil
import socket
import subprocess
from typing import Literal

CommandName = Literal["ping", "nslookup", "whois"]

ALLOWED_COMMANDS = frozenset({"ping", "nslookup", "whois"})
MAX_TARGET_LEN = 253
UNSAFE = re.compile(r"[^A-Za-z0-9._:\-]")
HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(?:\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$"
)
WHOIS_HOST_RE = re.compile(r"^whois\.[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def validate_target(raw: str) -> str:
    target = (raw or "").strip().rstrip(".")
    if target.startswith("[") and target.endswith("]"):
        target = target[1:-1]
    if not target or len(target) > MAX_TARGET_LEN:
        raise ValueError("Target must be a domain or IP address")
    if target.startswith("-"):
        raise ValueError("Target cannot start with '-'")
    if UNSAFE.search(target):
        raise ValueError("Target contains characters that are not allowed")

    try:
        ipaddress.ip_address(target)
        return target
    except ValueError:
        pass

    if not HOSTNAME_RE.match(target):
        raise ValueError("Target must be a valid hostname or IP address")
    return target


def build_argv(command: str, target: str) -> list[str]:
    if command == "ping":
        count_flag = "-n" if os.name == "nt" else "-c"
        return ["ping", count_flag, "4", target]
    if command == "nslookup":
        return ["nslookup", target]
    if command == "whois":
        return ["whois", target]
    raise ValueError("Command must be ping, nslookup, or whois")


def _run_subprocess(argv: list[str], timeout: int) -> tuple[str, str, int]:
    completed = subprocess.run(
        argv,
        shell=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return completed.stdout or "", completed.stderr or "", int(completed.returncode)


def _whois_query(server: str, query: str, timeout: float = 8.0) -> str:
    if not WHOIS_HOST_RE.match(server) and server != "whois.iana.org":
        raise ValueError("Refusing unexpected WHOIS server")
    with socket.create_connection((server, 43), timeout=timeout) as sock:
        sock.sendall(f"{query}\r\n".encode("ascii", errors="ignore"))
        chunks: list[bytes] = []
        while True:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)
            if sum(len(part) for part in chunks) > 200_000:
                break
    return b"".join(chunks).decode("utf-8", errors="replace")


def _whois_fallback(target: str) -> tuple[str, str, int]:
    referral = None
    try:
        bootstrap = _whois_query("whois.iana.org", target)
    except OSError as exc:
        return "", f"whois is not installed and the IANA lookup failed: {exc}", 1

    for line in bootstrap.splitlines():
        if line.lower().startswith("refer:"):
            referral = line.split(":", 1)[1].strip()
            break
        if line.lower().startswith("whois:"):
            referral = line.split(":", 1)[1].strip()
            break

    body = bootstrap
    if referral and WHOIS_HOST_RE.match(referral):
        try:
            referred = _whois_query(referral, target)
            if referred.strip():
                body = referred
        except OSError:
            pass

    note = (
        "whois executable was not found on PATH; "
        "used a direct TCP/43 lookup instead.\n\n"
    )
    return note + body, "", 0


def run_diagnostic(command: str, target: str) -> dict:
    if command not in ALLOWED_COMMANDS:
        raise ValueError("Command must be ping, nslookup, or whois")

    clean = validate_target(target)
    argv = build_argv(command, clean)
    timeout = 20 if command == "ping" else 15

    if command == "whois" and shutil.which("whois") is None:
        stdout, stderr, code = _whois_fallback(clean)
        return {
            "command": command,
            "target": clean,
            "argv": argv,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": code,
        }

    try:
        stdout, stderr, code = _run_subprocess(argv, timeout)
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"{command} timed out after {timeout}s") from None
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"{command} is not available on this system") from exc

    return {
        "command": command,
        "target": clean,
        "argv": argv,
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": code,
    }
