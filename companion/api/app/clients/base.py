"""Async HTTP base client with rate limiting and shared headers."""

import asyncio
import time

import aiohttp


# Scryfall asks for a descriptive User-Agent and 50-100ms between requests
_USER_AGENT = "Skryfall/0.1 (personal e-ink desk display; contact via GitHub)"
_MIN_INTERVAL = 0.1  # 100ms between requests


class BaseClient:
    """Thin async HTTP client. Subclass for specific APIs."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None
        self._last_request: float = 0.0

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": _USER_AGENT},
            )
        return self._session

    async def _throttle(self) -> None:
        """Enforce minimum interval between requests."""
        elapsed = time.monotonic() - self._last_request
        if elapsed < _MIN_INTERVAL:
            await asyncio.sleep(_MIN_INTERVAL - elapsed)
        self._last_request = time.monotonic()

    async def get(self, path: str, **kwargs) -> dict:
        """GET request. Returns parsed JSON or raises on non-2xx."""
        await self._throttle()
        session = await self._get_session()
        url = f"{self.base_url}/{path.lstrip('/')}"

        async with session.get(url, **kwargs) as response:
            response.raise_for_status()
            return await response.json()

    async def get_binary(self, url: str) -> bytes:
        """GET a raw binary response (e.g. image). Accepts full URL."""
        await self._throttle()
        session = await self._get_session()

        async with session.get(url) as response:
            response.raise_for_status()
            return await response.read()

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
