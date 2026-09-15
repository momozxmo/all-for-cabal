from pathlib import Path

from playwright.sync_api import sync_playwright, expect

from test_web_product_ui import _route_live_game_tools
from test_web_bundle_bulk import TEXT

STATIC = Path(__file__).resolve().parents[1] / 'web' / 'static'


def test_paste_random_and_rewards_reaches_editable_queue(client):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        _route_live_game_tools(context)
        context.route('**/static/bundle_import.js', lambda route: route.fulfill(
            content_type='application/javascript', body=(STATIC/'bundle_import.js').read_text(encoding='utf-8')))
        def parse(route):
            response = client.post('/api/bundles/import-text', json=route.request.post_data_json)
            route.fulfill(status=response.status_code, json=response.json())
        context.route('**/api/bundles/import-text', parse)
        page = context.new_page()
        page.goto('http://tool.test/bundles')
        page.wait_for_function("document.querySelectorAll('#game option').length === 3")
        expect(page.locator('#bundlePasteText')).to_have_count(1)
        page.fill('#bundlePasteText', TEXT)
        page.click('#btnBundlePastePreview')
        expect(page.locator('#bundleImportPreview')).to_contain_text('RANDOM')
        expect(page.locator('#bundleImportPreview')).to_contain_text('100000')
        expect(page.locator('#bundleImportPreview')).to_contain_text('CREDIT: Alz')
        expect(page.locator('#queueCount')).to_have_text('0')
        page.click('#btnBundleImportAdd')
        expect(page.locator('#queueCount')).to_have_text('2')
        queue = page.evaluate("JSON.parse(localStorage.getItem('afc.bundleQueue'))")
        assert queue[0]['type'] == 'RANDOM'
        assert [i['rate'] for i in queue[0]['items']] == ['60','30','10']
        assert queue[1]['rewards'][0]['tier'] == 'Rare'
        page.select_option('#queuePick', queue[1]['key'])
        expect(page.locator('#rewardList')).to_contain_text('Alz')
        expect(page.locator('#rewardList select')).to_have_value('Rare')
        page.locator('#rewardList select').select_option('Epic')
        queue = page.evaluate("JSON.parse(localStorage.getItem('afc.bundleQueue'))")
        assert queue[1]['rewards'][0]['tier'] == 'Epic'
        page.select_option('#bundleType', 'RANDOM')
        expect(page.locator('#rewardList input[aria-label="เรท Reward"]')).to_have_count(1)
        page.select_option('#bundleType', 'FIXED')
        expect(page.locator('#rewardList input[aria-label="เรท Reward"]')).to_have_count(0)
        page.click('#btnBundlePastePreview')
        expect(page.locator('#btnBundleImportAdd')).to_be_enabled()
        page.fill('#bundlePasteText', 'bad text')
        expect(page.locator('#btnBundleImportAdd')).to_be_disabled()
        browser.close()
