from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

from .config import Settings

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = {"http", "https"}
RESTRICTED_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "tiktok.com",
    "www.tiktok.com",
}


@dataclass(slots=True)
class UrlClassification:
    url: str
    domain: Optional[str]
    is_platform_restricted: bool


@dataclass(slots=True)
class UrlValidationResult:
    ok: bool
    reason: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


def classify_url(url: str) -> UrlClassification:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    is_restricted = any(host.endswith(domain) for domain in RESTRICTED_DOMAINS)
    return UrlClassification(url=url, domain=host, is_platform_restricted=is_restricted)


async def ensure_allowed_url(url: str, settings: Settings) -> UrlValidationResult:
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return UrlValidationResult(ok=False, reason="Схема ссылки не поддерживается")

    host = parsed.hostname
    if not host:
        return UrlValidationResult(ok=False, reason="Не удалось определить домен")

    if settings.allowed_domains:
        if not any(host == domain or host.endswith(f".{domain}") for domain in settings.allowed_domains):
            return UrlValidationResult(ok=False, reason="Домен не в списке разрешённых")

    if await _host_is_private(host):
        return UrlValidationResult(ok=False, reason="Домен указывает на приватный IP")

    headers = await _head_request(url)
    if headers is None:
        return UrlValidationResult(ok=False, reason="Удалённый сервер недоступен")

    content_type = headers.get("content-type")
    content_length_header = headers.get("content-length")
    accept_ranges = headers.get("accept-ranges")
    meta: Dict[str, Any] = {
        "content_type": content_type,
        "content_length": None,
        "accept_ranges": accept_ranges,
    }

    if content_length_header and content_length_header.isdigit():
        content_length = int(content_length_header)
        meta["content_length"] = content_length
        if content_length > settings.max_file_bytes:
            return UrlValidationResult(ok=False, reason="Размер файла превышает лимит")

    if accept_ranges and "bytes" not in accept_ranges.lower():
        logger.info("URL %s не поддерживает диапазоны", url)

    return UrlValidationResult(ok=True, meta=meta)


async def _head_request(url: str) -> Optional[Dict[str, str]]:
    timeout = httpx.Timeout(10.0, connect=5.0)
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        try:
            response = await client.head(url)
            if response.status_code == 405:
                response = await client.get(url, headers={"Range": "bytes=0-0"})
        except httpx.HTTPError as exc:
            logger.warning("HEAD request failed for %s: %s", url, exc)
            return None
    if response.status_code >= 400:
        return None
    return {k.lower(): v for k, v in response.headers.items()}


async def _host_is_private(host: str) -> bool:
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return True
    has_public = False
    for family, _, _, _, sockaddr in infos:
        ip_str = sockaddr[0]
        ip_obj = ipaddress.ip_address(ip_str)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved or ip_obj.is_link_local:
            continue
        has_public = True
    return not has_public


def parse_timecode(value: str) -> Optional[float]:
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)

    parts = value.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        try:
            return int(minutes) * 60 + float(seconds)
        except ValueError:
            return None
    if len(parts) == 3:
        hours, minutes, seconds = parts
        try:
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        except ValueError:
            return None
    return None

