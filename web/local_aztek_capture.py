"""Visible Local-only Chromium flow for capturing complete Aztek SSO state."""
from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

from playwright.async_api import async_playwright

from web import browser_launch, search_runner
from web.aztek_sessions import validate_storage_state
from web.browser_gate import BrowserOperationGate
from web.settings import Settings


_AZTEK_INIT_URL = 'https://aztek-tools-v2.combo-interactive.com/init'


class LocalCaptureError(RuntimeError):
    """Base class for expected manual-capture failures."""


class LocalCaptureClosed(LocalCaptureError):
    """The operator closed Chromium before authentication completed."""


class LocalCaptureTimeout(LocalCaptureError):
    """The operator did not complete authentication before the deadline."""


class LocalCaptureLoginRequired(LocalCaptureError):
    """The final verification navigation still reached a login page."""


class LocalAztekCaptureService:
    """Open isolated Chromium, wait for manual login, and export full state."""

    def __init__(
        self,
        settings: Settings,
        browser_gate: BrowserOperationGate,
        *,
        playwright_factory=async_playwright,
        timeout_seconds: float = 300,
        settle_milliseconds: int = 1500,
        poll_milliseconds: int = 500,
    ) -> None:
        self.settings = settings
        self.browser_gate = browser_gate
        self.playwright_factory = playwright_factory
        self.timeout_seconds = max(0.0, float(timeout_seconds))
        self.settle_milliseconds = max(0, int(settle_milliseconds))
        self.poll_milliseconds = max(0, int(poll_milliseconds))
        self.target_url = _AZTEK_INIT_URL

    async def capture(self, seed_state: dict | None = None) -> dict:
        """Return validated state only after the same context passes a probe."""
        browser = None
        context = None
        async with self.browser_gate.slot():
            async with self.playwright_factory() as playwright:
                try:
                    browser = await playwright.chromium.launch(
                        **browser_launch.launch_kwargs(True))
                    context_options = (
                        {'storage_state': seed_state}
                        if seed_state is not None else {}
                    )
                    context = await browser.new_context(
                        **browser_launch.context_kwargs(
                            True, **context_options))
                    page = await context.new_page()
                    await page.goto(
                        self.target_url,
                        wait_until='domcontentloaded',
                        timeout=30000,
                    )
                    await self._wait_for_authenticated_app(
                        page,
                        allow_initial_authenticated=seed_state is not None,
                    )

                    # A second navigation proves that SSO survives a fresh app
                    # request rather than accepting a transient pre-redirect URL.
                    await page.goto(
                        self.target_url,
                        wait_until='domcontentloaded',
                        timeout=30000,
                    )
                    await page.wait_for_timeout(self.settle_milliseconds)
                    if page.is_closed():
                        raise LocalCaptureClosed()
                    if not await self._is_authenticated_app(page):
                        raise LocalCaptureLoginRequired()

                    storage_state = await context.storage_state()
                    validate_storage_state(storage_state, self.settings)
                    return storage_state
                finally:
                    if context is not None:
                        await context.close()
                    if browser is not None:
                        await browser.close()

    async def _wait_for_authenticated_app(
        self,
        page,
        *,
        allow_initial_authenticated: bool = False,
    ) -> None:
        deadline = asyncio.get_running_loop().time() + self.timeout_seconds
        saw_login_page = False
        if allow_initial_authenticated:
            await page.wait_for_timeout(self.settle_milliseconds)
        while True:
            if page.is_closed():
                raise LocalCaptureClosed()
            if await search_runner.is_login_page(page):
                saw_login_page = True
            elif (
                (allow_initial_authenticated or saw_login_page)
                and await self._is_authenticated_app(page)
            ):
                return
            if asyncio.get_running_loop().time() >= deadline:
                raise LocalCaptureTimeout()
            await page.wait_for_timeout(self.poll_milliseconds)

    async def _is_authenticated_app(self, page) -> bool:
        parts = urlsplit(str(getattr(page, 'url', '') or ''))
        host = (parts.hostname or '').lower()
        if parts.scheme != 'https':
            return False
        if not (
            host == 'aztek-tools.combo-interactive.com'
            or host == 'aztek-tools-v2.combo-interactive.com'
        ):
            return False
        path = parts.path or '/'
        if path != '/combo' and not path.startswith('/combo/'):
            return False
        return not await search_runner.is_login_page(page)
