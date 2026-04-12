"""Async HTTP base client with rate limiting and shared headers."""

from __future__ import annotations

import asyncio
import time
from urllib.parse import urlparse

import aiohttp


# Scryfall requires User-Agent + Accept.
# https://scryfall.com/docs/api — rate limits are path-specific:
_STRICT_PATHS = frozenset(
    {
        "/cards/search",
        "/cards/named",
        "/cards/random",
        "/cards/collection",
    }
)
_STRICT_INTERVAL = 0.5  # 2/second
_DEFAULT_INTERVAL = 0.1  # 10/second for all other API routes
_429_DEFAULT_BACKOFF = 30.0  # "limited for 30 seconds" after 429

_USER_AGENT = "Skryfall/0.1 (personal e-ink desk display; contact via GitHub)"
_ACCEPT = "application/json;q=0.9,*/*;q=0.8"


class BaseClient:
    """Thin async HTTP client. Subclass for specific APIs."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None
        self._last_strict: float = 0.0
        self._last_general: float = 0.0
        self._lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "User-Agent": _USER_AGENT,
                    "Accept": _ACCEPT,
                },
            )
        return self._session

    @staticmethod
    def _normalize_api_path(path: str) -> str:
        base = path.split("?", maxsplit=1)[0].rstrip("/")
        if not base.startswith("/"):
            base = "/" + base
        return base

    async def _throttle_api_path(self, path: str) -> None:
        """Enforce Scryfall per-route limits (strict vs default tier)."""
        norm = self._normalize_api_path(path)
        strict = norm in _STRICT_PATHS
        interval = _STRICT_INTERVAL if strict else _DEFAULT_INTERVAL
        async with self._lock:
            if strict:
                elapsed = time.monotonic() - self._last_strict
                if elapsed < interval:
                    await asyncio.sleep(interval - elapsed)
                self._last_strict = time.monotonic()
            else:
                elapsed = time.monotonic() - self._last_general
                if elapsed < interval:
                    await asyncio.sleep(interval - elapsed)
                self._last_general = time.monotonic()

    @staticmethod
    def _is_scryfall_cdn_url(url: str) -> bool:
        """File hosts under *.scryfall.io (not api.scryfall.com) have no API rate limits."""
        host = urlparse(url).hostname or ""
        return host.endswith("scryfall.io") and host != "api.scryfall.com"

    async def get(self, path: str, **kwargs) -> dict:
        """GET api.scryfall.com JSON. Handles 429 with backoff (do not ignore 429)."""
        await self._throttle_api_path(path)
        session = await self._get_session()
        url = f"{self.base_url}/{path.lstrip('/')}"

        async with session.get(url, **kwargs) as response:
            if response.status == 429:
                ra = response.headers.get("Retry-After")
                try:
                    delay = float(ra) if ra is not None else _429_DEFAULT_BACKOFF
                except ValueError:
                    delay = _429_DEFAULT_BACKOFF
                await asyncio.sleep(delay)
                async with session.get(url, **kwargs) as response2:
                    response2.raise_for_status()
                    return await response2.json()
            response.raise_for_status()
            return await response.json()

    async def get_binary(self, url: str) -> bytes:
        """GET binary (e.g. card image). CDN *.scryfall.io URLs are not throttled."""
        if not self._is_scryfall_cdn_url(url):
            parsed = urlparse(url)
            path = parsed.path or "/"
            if parsed.query:
                path = f"{path}?{parsed.query}"
            await self._throttle_api_path(path)

        session = await self._get_session()
        async with session.get(url) as response:
            if response.status == 429:
                ra = response.headers.get("Retry-After")
                try:
                    delay = float(ra) if ra is not None else _429_DEFAULT_BACKOFF
                except ValueError:
                    delay = _429_DEFAULT_BACKOFF
                await asyncio.sleep(delay)
                async with session.get(url) as response2:
                    response2.raise_for_status()
                    return await response2.read()
            response.raise_for_status()
            return await response.read()

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
