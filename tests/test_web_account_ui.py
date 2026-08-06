from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = ROOT / 'web' / 'static' / 'account.html'


def account_page(browser, *, local_mode):
    page = browser.new_page()
    state = {'capture_seen': False, 'capture_requests': 0,
             'status_requests': 0}

    def fulfill(route):
        url = route.request.url
        if url == 'http://tool.test/account':
            route.fulfill(
                body=ACCOUNT.read_text(encoding='utf-8'),
                content_type='text/html')
        elif url.endswith('/api/auth/me'):
            route.fulfill(json={
                'username': 'local.owner' if local_mode else 'operator',
                'role': 'admin', 'local_mode': local_mode,
            })
        elif url.endswith('/api/aztek/status'):
            state['status_requests'] += 1
            active = state['capture_seen']
            route.fulfill(json={
                'connected': active,
                'status': 'active' if active else 'disconnected',
                'account_label': 'Local Chromium' if active else None,
                'updated_at': '2026-08-06T12:00:00' if active else None,
                'last_validated_at': None,
            })
        elif url.endswith('/api/aztek/local-capture'):
            state['capture_requests'] += 1
            state['capture_seen'] = True
            route.fulfill(json={
                'status': 'connected', 'account_label': 'Local Chromium'})
        else:
            route.fulfill(status=404, body='not found')

    page.route('**/*', fulfill)
    page.goto('http://tool.test/account', wait_until='domcontentloaded')
    page.wait_for_function(
        "document.getElementById('aztekStatusText').textContent "
        "!== 'กำลังโหลด…'")
    return page, state


def test_local_mode_shows_direct_capture_and_hides_bookmark_pairing():
    """Showing both methods locally would send users back to broken pairing."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page, _state = account_page(browser, local_mode=True)

        assert page.locator('#localCaptureButton').is_visible()
        assert not page.locator('#bookmarklet').is_visible()
        assert not page.locator('#createPairingButton').is_visible()
        assert not page.locator('#openAztekLink').is_visible()
        assert page.locator('#disconnectAztekButton').is_visible()
        browser.close()


def test_local_capture_button_visibly_waits_while_browser_login_is_pending():
    """Without pending feedback a five-minute manual login looks frozen."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page, _state = account_page(browser, local_mode=True)
        page.evaluate("""() => {
          const realFetch = window.fetch.bind(window);
          window.__localCaptureRequests = 0;
          window.fetch = (url, options) => {
            if (String(url).endsWith('/api/aztek/local-capture')) {
              window.__localCaptureRequests += 1;
              return new Promise(() => {});
            }
            return realFetch(url, options);
          };
        }""")

        page.locator('#localCaptureButton').click()
        page.wait_for_function(
            "document.getElementById('localCaptureButton').disabled")

        assert page.evaluate('window.__localCaptureRequests') == 1
        assert 'Chromium' in page.locator('#aztekMessage').inner_text()
        page.close()
        browser.close()


def test_successful_local_capture_refreshes_visible_connection_status():
    """A stored session is not useful if the page still says disconnected."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page, state = account_page(browser, local_mode=True)

        page.locator('#localCaptureButton').click()
        page.wait_for_function(
            "document.getElementById('aztekStatusText').textContent "
            "=== 'เชื่อมแล้ว'")

        assert state['capture_requests'] == 1
        assert state['status_requests'] >= 2
        assert page.locator('#aztekAccountLabel').inner_text() == 'Local Chromium'
        assert 'สำเร็จ' in page.locator('#aztekMessage').inner_text()
        browser.close()


def test_hosted_mode_keeps_pairing_and_hides_local_capture():
    """A hosted server must never offer to open Chromium on the server."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page, state = account_page(browser, local_mode=False)

        assert not page.locator('#localCaptureButton').is_visible()
        assert page.locator('#bookmarklet').is_visible()
        assert page.locator('#createPairingButton').is_visible()
        assert page.locator('#openAztekLink').is_visible()
        assert state['capture_requests'] == 0
        browser.close()
