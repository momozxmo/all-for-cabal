from pathlib import Path

from playwright.sync_api import sync_playwright, expect

from test_web_bundle_import import workbook_bytes
from test_web_product_ui import _route_live_game_tools

STATIC = Path(__file__).resolve().parents[1] / 'web' / 'static'


def test_select_sheet_preview_then_append_once_and_preserve_existing_queue(client):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        _route_live_game_tools(context)
        context.route('**/static/bundle_import.js', lambda route: route.fulfill(
            content_type='application/javascript',
            body=(STATIC / 'bundle_import.js').read_text(encoding='utf-8')
            if (STATIC / 'bundle_import.js').exists() else ''))

        def import_route(route):
            response = client.post('/api/bundles/import',
                content=route.request.post_data_buffer,
                headers={'content-type': route.request.headers['content-type']})
            route.fulfill(status=response.status_code, json=response.json())

        context.route('**/api/bundles/import', import_route)
        page = context.new_page()
        page.goto('http://tool.test/bundles')
        page.wait_for_function("document.querySelectorAll('#game option').length === 3")
        page.click('#btnQueueNew')
        page.fill('#bundleName', 'Existing')
        page.locator('#bundleName').dispatch_event('input')
        payload = workbook_bytes([
            ('wrong', [['Other', 999, 1]], False),
            ('เลือก แท็บนี้', [['Pack A', 11, 2, 'Rare', '<img src=x onerror=alert(1)>'],
                             ['Pack B', 11, 4]], False)])
        expect(page.locator('#bundleImportFile')).to_have_count(1)
        page.set_input_files('#bundleImportFile', {
            'name': 'bundle.xlsx', 'mimeType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'buffer': payload})
        page.click('#btnBundleImportRead')
        expect(page.locator('#bundleImportSheet option')).to_have_count(2)
        page.select_option('#bundleImportSheet', label='เลือก แท็บนี้')
        page.click('#btnBundleImportPreview')
        expect(page.locator('#bundleImportPreview')).to_contain_text('Pack A')
        expect(page.locator('#bundleImportPreview')).to_contain_text('Pack B')
        expect(page.locator('#bundleImportPreview')).to_contain_text('<img src=x onerror=alert(1)>')
        expect(page.locator('#bundleImportPreview img')).to_have_count(0)
        assert len(page.evaluate("JSON.parse(localStorage.getItem('afc.bundleQueue'))")) == 1
        page.click('#btnBundleImportAdd')
        expect(page.locator('#queueCount')).to_have_text('3')
        expect(page.locator('#btnBundleImportAdd')).to_be_disabled()
        queue = page.evaluate("JSON.parse(localStorage.getItem('afc.bundleQueue'))")
        assert [b['name'] for b in queue] == ['Existing', 'Pack A', 'Pack B']
        assert [b['items'][0]['qty'] for b in queue[1:]] == ['2', '4']
        assert [b['items'][0]['id'] for b in queue[1:]] == ['11', '11']
        page.reload()
        expect(page.locator('#queueCount')).to_have_text('3')

        # A valid preview cannot survive switching to an invalid sheet/file/game.
        page.set_input_files('#bundleImportFile', {
            'name': 'invalid.xlsx', 'mimeType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'buffer': workbook_bytes([
                ('Valid', [['Next', 22, 1]], False),
                ('Invalid', [['Bad', '', 1]], False)])})
        page.click('#btnBundleImportRead')
        expect(page.locator('#bundleImportSheet option')).to_have_count(2)
        page.click('#btnBundleImportPreview')
        expect(page.locator('#btnBundleImportAdd')).to_be_enabled()
        page.select_option('#bundleImportSheet', label='Invalid')
        expect(page.locator('#btnBundleImportAdd')).to_be_disabled()
        page.click('#btnBundleImportPreview')
        expect(page.locator('#bundleImportMsg')).to_contain_text('Item ID')
        expect(page.locator('#btnBundleImportAdd')).to_be_disabled()
        page.select_option('#bundleImportSheet', label='Valid')
        page.click('#btnBundleImportPreview')
        page.select_option('#game', 'CabalPC TH')
        expect(page.locator('#btnBundleImportAdd')).to_be_disabled()
        page.click('#btnBundleImportPreview')

        # A full browser store must leave the existing queue untouched.
        page.evaluate("""() => {
          window.originalSetItem = Storage.prototype.setItem;
          Storage.prototype.setItem = function(key, value) {
            if(key === 'afc.bundleQueue') throw new DOMException('Full', 'QuotaExceededError');
            return window.originalSetItem.call(this, key, value);
          };
        }""")
        page.click('#btnBundleImportAdd')
        expect(page.locator('#bundleImportMsg')).to_contain_text('พื้นที่บันทึก')
        expect(page.locator('#queueCount')).to_have_text('3')
        page.evaluate('() => { Storage.prototype.setItem = window.originalSetItem; }')
        page.click('#btnBundleImportAdd')
        expect(page.locator('#queueCount')).to_have_text('4')

        # The existing run workflow identifies completed bundles by name.
        # Import must show a unique name before adding, never discard another bundle.
        page.set_input_files('#bundleImportFile', {
            'name': 'collision.xlsx', 'mimeType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'buffer': workbook_bytes([('Names', [['Existing', 44, 1]], False),
                                      ('Same name', [['Existing', 55, 1]], False)])})
        page.click('#btnBundleImportRead')
        expect(page.locator('#bundleImportSheet option')).to_have_count(2)
        page.click('#btnBundleImportPreview')
        expect(page.locator('#bundleImportPreview')).to_contain_text('Existing (2)')
        # Queue edits during preview must not reintroduce duplicate names.
        page.click('#btnQueueNew')
        page.fill('#bundleName', 'Existing (2)')
        page.locator('#bundleName').dispatch_event('input')
        page.click('#btnBundleImportAdd')
        expect(page.locator('#queueCount')).to_have_text('5')
        expect(page.locator('#btnBundleImportAdd')).to_be_disabled()
        page.click('#btnBundleImportPreview')
        expect(page.locator('#bundleImportPreview')).to_contain_text('Existing (3)')
        page.click('#btnBundleImportAdd')
        expect(page.locator('#queueCount')).to_have_text('6')
        page.select_option('#bundleImportSheet', label='Same name')
        page.click('#btnBundleImportPreview')
        expect(page.locator('#bundleImportPreview')).to_contain_text('Existing (4)')
        page.click('#btnBundleImportAdd')
        expect(page.locator('#queueCount')).to_have_text('7')
        browser.close()
