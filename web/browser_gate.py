"""Application-wide concurrency gate for Playwright browser operations."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, contextmanager
import threading


class BrowserOperationGate:
    """Bound the number of browser jobs shared by every web workflow."""

    def __init__(self, limit: int = 1) -> None:
        self._semaphore = asyncio.Semaphore(max(1, int(limit)))
        self._lock = threading.Lock()
        self._work = 0
        self._updating = False

    @contextmanager
    def work(self):
        """Reserve an entire workflow, including gaps between browser steps."""
        with self._lock:
            if self._updating:
                raise RuntimeError('กำลังเตรียมอัปเดต กรุณารอโปรแกรมเปิดกลับ')
            self._work += 1
        try:
            yield
        finally:
            with self._lock:
                self._work -= 1

    def begin_update(self) -> bool:
        with self._lock:
            if self._work or self._updating:
                return False
            self._updating = True
            return True

    def end_update(self):
        with self._lock:
            self._updating = False

    @property
    def busy(self):
        with self._lock:
            return bool(self._work)

    @asynccontextmanager
    async def slot(self):
        with self.work():
            async with self._semaphore:
                yield
