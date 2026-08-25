from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from web.browser_gate import BrowserOperationGate
from web.local_aztek_capture import (
    LocalAztekCaptureService,
    LocalCaptureClosed,
    LocalCaptureLoginRequired,
    LocalCaptureTimeout,
)


LOGIN_URL = 'https://dex.combo-interactive.com/auth/ldap/login?back=1'
AZTEK_INIT_URL = 'https://aztek-tools-v2.combo-interactive.com/init'
AZTEK_OAUTH_CALLBACK_URL = (
    'https://aztek-tools-v2.combo-interactive.com/oauth/callback?code=hidden')
AZTEK_DASHBOARD_URL = (
    'https://aztek-tools-v2.combo-interactive.com/combo/dashboard')
AZTEK_ITEMS_URL = (
    'https://aztek-tools-v2.combo-interactive.com/combo/cabal/items')


def complete_storage_state():
    return {
        'cookies': [{
            'name': 'sso',
            'value': 'http-only-cookie-value',
            'domain': '.combo-interactive.com',
            'path': '/',
            'httpOnly': True,
            'secure': True,
            'sameSite': 'Lax',
        }],
        'origins': [{
            'origin': 'https://aztek-tools-v2.combo-interactive.com',
            'localStorage': [{'name': 'locale', 'value': 'th'}],
        }],
    }


class FakePage:
    def __init__(self, goto_urls, wait_urls=(), *, closed=False):
        self._goto_urls = list(goto_urls)
        self._wait_urls = list(wait_urls)
        self._closed = closed
        self.url = ''
        self.requested_urls = []

    async def goto(self, url, **_kwargs):
        self.requested_urls.append(url)
        if self._goto_urls:
            self.url = self._goto_urls.pop(0)

    async def wait_for_timeout(self, _milliseconds):
        if self._wait_urls:
            self.url = self._wait_urls.pop(0)
        await asyncio.sleep(0)

    def is_closed(self):
        return self._closed

    async def evaluate(self, _script):
        return False


class OAuthCallbackThenDashboardPage(FakePage):
    """Model the live callback that must finish before probing /init again."""

    def __init__(self):
        super().__init__([])
        self._goto_count = 0
        self._reached_dashboard = False

    async def goto(self, url, **_kwargs):
        self.requested_urls.append(url)
        self._goto_count += 1
        if self._goto_count == 1:
            self.url = LOGIN_URL
        elif self._reached_dashboard:
            self.url = AZTEK_DASHBOARD_URL
        else:
            self.url = LOGIN_URL

    async def wait_for_timeout(self, _milliseconds):
        if self._goto_count == 1:
            if self.url == LOGIN_URL:
                self.url = AZTEK_OAUTH_CALLBACK_URL
            elif self.url == AZTEK_OAUTH_CALLBACK_URL:
                self.url = AZTEK_DASHBOARD_URL
                self._reached_dashboard = True
        await asyncio.sleep(0)


class FakeContext:
    def __init__(self, page, state):
        self.page = page
        self.state = state
        self.closed = False

    async def new_page(self):
        return self.page

    async def storage_state(self):
        return self.state

    async def close(self):
        self.closed = True


class FakeBrowser:
    def __init__(self, context):
        self.context = context
        self.closed = False
        self.new_context_calls = []

    async def new_context(self, **kwargs):
        self.new_context_calls.append(kwargs)
        return self.context

    async def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self, browser):
        self.browser = browser

    async def launch(self, **_kwargs):
        return self.browser


class FakePlaywright:
    def __init__(self, page, state=None):
        self.context = FakeContext(page, state or complete_storage_state())
        self.browser = FakeBrowser(self.context)
        self.chromium = FakeChromium(self.browser)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


def local_settings(test_settings):
    return replace(
        test_settings,
        app_env='local-desktop',
        local_desktop_mode=True,
        local_runtime_dir='C:/AFC',
        local_launcher_secret='x' * 48,
    )


def run_capture(test_settings, fake, *, timeout=300, seed_state=None):
    service = LocalAztekCaptureService(
        local_settings(test_settings),
        BrowserOperationGate(1),
        playwright_factory=lambda: fake,
        timeout_seconds=timeout,
        settle_milliseconds=0,
        poll_milliseconds=0,
    )
    capture = service.capture() if seed_state is None else service.capture(seed_state)
    return asyncio.run(capture)


def test_capture_returns_complete_http_only_state_after_live_app_check(
        test_settings):
    """Using document.cookie would drop the HttpOnly cookie from this result."""
    page = FakePage(
        [LOGIN_URL, AZTEK_ITEMS_URL],
        wait_urls=[AZTEK_ITEMS_URL],
    )
    fake = FakePlaywright(page)

    state = run_capture(test_settings, fake)

    assert state == complete_storage_state()
    assert state['cookies'][0]['httpOnly'] is True
    assert fake.context.closed is True
    assert fake.browser.closed is True


def test_capture_discards_external_login_artifacts_before_validation(
        test_settings):
    """Identity-provider state must not invalidate a valid Aztek session."""
    page = FakePage(
        [LOGIN_URL, AZTEK_ITEMS_URL],
        wait_urls=[AZTEK_ITEMS_URL],
    )
    captured = complete_storage_state()
    captured['cookies'].append({
        'name': 'external-login',
        'value': 'irrelevant-provider-value',
        'domain': '.identity-provider.example',
        'path': '/',
        'httpOnly': True,
        'secure': True,
        'sameSite': 'Lax',
    })
    captured['origins'].append({
        'origin': 'https://identity-provider.example',
        'localStorage': [{'name': 'temporary-login', 'value': 'irrelevant'}],
    })
    fake = FakePlaywright(page, captured)

    result = run_capture(test_settings, fake)

    assert result == complete_storage_state()


def test_capture_waits_through_transient_aztek_page_and_ipa_login(
        test_settings):
    """The pre-SSO Aztek shell must not close Chromium when IPA appears."""
    page = FakePage(
        [AZTEK_ITEMS_URL, AZTEK_ITEMS_URL],
        wait_urls=[LOGIN_URL, AZTEK_ITEMS_URL],
    )
    fake = FakePlaywright(page)

    state = run_capture(test_settings, fake)

    assert state == complete_storage_state()
    assert fake.context.closed is True
    assert fake.browser.closed is True


def test_capture_waits_for_oauth_callback_to_reach_dashboard(test_settings):
    page = OAuthCallbackThenDashboardPage()
    state = complete_storage_state()
    fake = FakePlaywright(page, state)

    result = run_capture(test_settings, fake, seed_state=state)

    assert result == state
    assert page.requested_urls == [AZTEK_INIT_URL, AZTEK_INIT_URL]
    assert page._reached_dashboard is True


def test_capture_uses_game_neutral_init_for_login_and_probe(test_settings):
    page = FakePage(
        [LOGIN_URL, AZTEK_DASHBOARD_URL],
        wait_urls=[AZTEK_DASHBOARD_URL],
    )
    fake = FakePlaywright(page)

    run_capture(test_settings, fake)

    assert page.requested_urls == [AZTEK_INIT_URL, AZTEK_INIT_URL]


def test_seeded_authenticated_context_skips_login_page(test_settings):
    page = FakePage([AZTEK_DASHBOARD_URL, AZTEK_DASHBOARD_URL])
    state = complete_storage_state()
    fake = FakePlaywright(page, state)

    result = run_capture(test_settings, fake, seed_state=state)

    assert result == state
    assert fake.browser.new_context_calls == [{
        'no_viewport': True,
        'storage_state': state,
    }]


def test_expired_seed_waits_for_login_in_the_same_browser(test_settings):
    page = FakePage(
        [AZTEK_INIT_URL, AZTEK_DASHBOARD_URL],
        wait_urls=[LOGIN_URL, AZTEK_DASHBOARD_URL],
    )
    state = complete_storage_state()
    fake = FakePlaywright(page, state)

    result = run_capture(test_settings, fake, seed_state=state)

    assert result == state
    assert page.requested_urls == [AZTEK_INIT_URL, AZTEK_INIT_URL]


def test_capture_reports_closed_window_and_cleans_up(test_settings):
    page = FakePage([LOGIN_URL], closed=True)
    fake = FakePlaywright(page)

    with pytest.raises(LocalCaptureClosed):
        run_capture(test_settings, fake)

    assert fake.context.closed is True
    assert fake.browser.closed is True


def test_capture_times_out_without_persisting_a_login_page(test_settings):
    page = FakePage([LOGIN_URL])
    fake = FakePlaywright(page)

    with pytest.raises(LocalCaptureTimeout):
        run_capture(test_settings, fake, timeout=0)

    assert fake.context.closed is True
    assert fake.browser.closed is True


def test_capture_rejects_final_navigation_that_returns_to_login(test_settings):
    page = FakePage(
        [LOGIN_URL, LOGIN_URL],
        wait_urls=[AZTEK_ITEMS_URL],
    )
    fake = FakePlaywright(page)

    with pytest.raises(LocalCaptureLoginRequired):
        run_capture(test_settings, fake)

    assert fake.context.closed is True
    assert fake.browser.closed is True
