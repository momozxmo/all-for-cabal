from pathlib import Path

from playwright.sync_api import sync_playwright
import pytest


def test_update_popup_shows_notes_as_text_and_can_be_reopened():
    script = (Path(__file__).resolve().parents[1] / 'web/static/updates.js').read_text(encoding='utf-8')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        state = {'supported': True, 'state': 'available', 'current_version': '0.1.30',
                 'release': {'version': '0.1.31', 'notes': '<img src=x onerror=alert(1)> แก้ Import'},
                 'message': 'มีเวอร์ชันใหม่'}
        page.route('http://tool.test/**', lambda route: route.fulfill(
            json={'show': True} if route.request.url.endswith('/seen') else state)
            if '/api/' in route.request.url else route.fulfill(
                content_type='text/html', body='<html><body><h1>Tool</h1></body></html>'))
        page.goto('http://tool.test/')
        page.add_script_tag(content=script)
        dialog = page.get_by_role('dialog', name='อัปเดต All for Cabal')
        dialog.wait_for(state='visible')
        assert '0.1.31' in dialog.inner_text()
        assert 'แก้ Import' in dialog.inner_text()
        assert dialog.locator('img').count() == 0
        dialog.get_by_role('button', name='ไว้ก่อน', exact=True).click()
        assert not dialog.is_visible()
        page.get_by_role('button', name='อัปเดตโปรแกรม', exact=True).click()
        assert dialog.is_visible()
        browser.close()


@pytest.mark.parametrize('scenario', ['defer', 'retry'])
def test_operator_controls_install_after_download_and_failure(scenario):
    script = (Path(__file__).resolve().parents[1] / 'web/static/updates.js').read_text(encoding='utf-8')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        state = {'supported': True, 'state': 'available', 'current_version': '0.1.30',
                 'release': {'version': '0.1.31', 'notes': 'Update'}, 'message': ''}
        downloads, commands = [], []
        def route_request(route):
            suffix = route.request.url.rsplit('/', 1)[-1]
            if '/api/' not in route.request.url:
                return route.fulfill(content_type='text/html', body='<html><body>Tool</body></html>')
            commands.append(suffix)
            if suffix == 'download':
                state['state'] = 'downloading'
                downloads.append(route)
                return
            if suffix == 'prepare':
                state.update(state='preparing', preparation='attempt', tabs_ready=True)
            if suffix == 'install':
                state.update(state='available', preparation='', message='เตรียมติดตั้งไม่สำเร็จ')
            route.fulfill(json={'show': False} if suffix == 'seen' else state)
        page.route('http://tool.test/**', route_request)
        page.goto('http://tool.test/')
        page.add_script_tag(content=script)
        page.get_by_role('button', name='อัปเดตโปรแกรม', exact=True).click()
        dialog = page.get_by_role('dialog')
        button = dialog.get_by_role('button', name='อัปเดต', exact=True)
        button.click()
        page.wait_for_timeout(100)
        assert downloads
        if scenario == 'defer':
            dialog.get_by_role('button', name='ไว้ก่อน', exact=True).click()
        state['state'] = 'ready'
        downloads[0].fulfill(json=state)
        page.wait_for_timeout(2500)
        if scenario == 'defer':
            assert 'prepare' not in commands
            assert 'install' not in commands
        else:
            assert 'install' in commands
            assert button.is_enabled()
        browser.close()


def test_bundle_tab_preserves_draft_and_acknowledges_preparation():
    from test_web_product_ui import _route_live_game_tools
    root = Path(__file__).resolve().parents[1]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        _route_live_game_tools(context)
        context.route('**/static/updates.js', lambda route: route.fulfill(
            content_type='application/javascript', body=(root / 'web/static/updates.js').read_text(encoding='utf-8')))
        state = {'supported': True, 'state': 'available', 'current_version': '0.1.30',
                 'release': {'version': '0.1.31', 'notes': 'แก้ Import'}, 'message': ''}
        acks = []
        def update_route(route):
            if route.request.url.endswith('/tabs'):
                acks.append(route.request.post_data_json)
            route.fulfill(json={'show': False} if route.request.url.endswith('/seen') else state)
        context.route('**/api/local/update**', update_route)
        page = context.new_page()
        page.goto('http://tool.test/bundles')
        page.locator('#btnQueueNew').click()
        page.locator('#bundleName').fill('ร่างที่ต้องอยู่หลังอัปเดต')
        state.update(state='preparing', preparation='prepare-test', tabs_ready=False)
        page.wait_for_function("JSON.parse(localStorage.getItem('afc.bundleQueue') || '[]').some(x => x.name === 'ร่างที่ต้องอยู่หลังอัปเดต')")
        page.wait_for_timeout(3500)
        assert any(ack.get('prepared') == 'prepare-test' and ack.get('saved') for ack in acks)
        # A newly installed runtime makes the old page reload and restore its own draft.
        state.update(state='idle', preparation='', current_version='0.1.31', release=None)
        page.wait_for_timeout(5000)
        assert page.locator('#bundleName').input_value() == 'ร่างที่ต้องอยู่หลังอัปเดต'
        browser.close()
