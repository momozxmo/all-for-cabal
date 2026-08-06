"""Application-wide concurrency gate for Playwright browser operations."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager


class BrowserOperationGate:
    """Bound the number of browser jobs shared by every web workflow."""

    def __init__(self, limit: int = 1) -> None:
        self._semaphore = asyncio.Semaphore(max(1, int(limit)))

    @asynccontextmanager
    async def slot(self):
        async with self._semaphore:
            yield
