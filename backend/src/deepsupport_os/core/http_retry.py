"""Shared HTTP helpers: bounded timeout + limited retries (sync + async)."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def request_with_retries(
    method: str,
    url: str,
    *,
    timeout: float = 30.0,
    retries: int = 2,
    backoff_s: float = 0.4,
    **kwargs: Any,
) -> httpx.Response:
    """GET/POST with small retry budget for transient network/5xx failures (sync)."""
    last_exc: Exception | None = None
    attempts = max(1, retries + 1)
    for i in range(attempts):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.request(method, url, **kwargs)
            if resp.status_code >= 500 and i < attempts - 1:
                time.sleep(backoff_s * (i + 1))
                continue
            return resp
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            logger.debug("http retry %s %s (%s/%s): %s", method, url, i + 1, attempts, exc)
            if i < attempts - 1:
                time.sleep(backoff_s * (i + 1))
                continue
            raise
    assert last_exc is not None
    raise last_exc


async def arequest_with_retries(
    method: str,
    url: str,
    *,
    timeout: float = 30.0,
    retries: int = 2,
    backoff_s: float = 0.4,
    **kwargs: Any,
) -> httpx.Response:
    """Async GET/POST with small retry budget — non-blocking on the event loop."""
    last_exc: Exception | None = None
    attempts = max(1, retries + 1)
    for i in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(method, url, **kwargs)
            if resp.status_code >= 500 and i < attempts - 1:
                await _sleep(backoff_s * (i + 1))
                continue
            return resp
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            logger.debug("http retry %s %s (%s/%s): %s", method, url, i + 1, attempts, exc)
            if i < attempts - 1:
                await _sleep(backoff_s * (i + 1))
                continue
            raise
    assert last_exc is not None
    raise last_exc


async def _sleep(seconds: float) -> None:
    """Wait without blocking the event loop (sync path uses asyncio.run once)."""
    await asyncio.sleep(seconds)