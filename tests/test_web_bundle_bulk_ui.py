from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, expect

from test_web_product_ui import _route_live_game_tools
from test_web_bundle_bulk import TEXT

STATIC = Path(__file__).resolve().parents[1] / 'web' / 'static'


@pytest.mark.parametrize('width', [1280, 390])
def test_zero_item_and_currency_rates_survive_preview_queue_and_job(client, width):
    """Real parser and UI must retain zero, including reward input validity."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': width, 'height': 900})
        _route_live_game_tools(context)
        context.route('https://**', lambda route: route.abort())

        def parse(route):
            response = client.post('/api/bundles/import-text', json=route.request.post_data_json)
            route.fulfill(status=response.status_code, json=response.json())

        context.route('**/api/bundles/import-text', parse)
        page = context.new_page()
        page.goto('http://tool.test/bundles', wait_until='domcontentloaded')
        page.wait_for_function("document.querySelectorAll('#game option').length === 3")
        page.fill('#bundlePasteText', 'Pack\tRANDOM\n11\t1\tCommon\t0\n'
                                    '12\t1\tRare\t100\nCREDIT: Alz\t1\tCommon\t0')
        page.locator('#btnBundlePastePreview').focus()
        page.locator('#btnBundlePastePreview').press('Enter')
        expect(page.locator('#bundleImportPreview')).to_be_visible()
        rows = page.locator('#bundleImportPreview tbody tr')
        expect(rows.nth(0).locator('td').last).to_have_text('0')
        expect(rows.nth(2).locator('td').last).to_have_text('0')
        page.click('#btnBundleImportAdd')
        expect(page.locator('#queueCount')).to_have_text('1')
        reward_rate = page.locator('#rewardList input[aria-label="เรท Reward"]')
        expect(reward_rate).to_have_value('0')
        assert reward_rate.evaluate('el => el.checkValidity()')
        # Numeric zero in restored drafts must survive, too.
        page.evaluate("""() => {
            state.queue[0].items[0].rate = 0;
            state.queue[0].rewards[0].rate = 0;
            renderItems(); renderRewards();
        }""")
        expect(page.locator('#itemsTable tbody tr').nth(0).locator('input[step="0.001"]')).to_have_value('0')
        expect(reward_rate).to_have_value('0')
        job = page.evaluate('jobFrom(state.queue[0])')
        assert [item['rate'] for item in job['items']] == ['0', '100']
        assert job['rewards'][0]['rate'] == 0
        assert page.evaluate('rateGap(jobFrom(state.queue[0]))') is False
        from web.app import _clean_items, _clean_rewards
        assert _clean_items(job['items'])[0]['rate'] == '0'
        assert _clean_rewards(job['rewards'])[0]['rate'] == '0'
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        browser.close()


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


@pytest.mark.parametrize('width', [1280, 390])
def test_clear_pasted_bundle_draft_preserves_existing_queue(client, width):
    """Clear must invalidate the preview, not just erase the visible text."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': width, 'height': 900})
        _route_live_game_tools(context)
        context.route('https://**', lambda route: route.abort())

        def parse(route):
            response = client.post('/api/bundles/import-text',
                                   json=route.request.post_data_json)
            route.fulfill(status=response.status_code, json=response.json())

        context.route('**/api/bundles/import-text', parse)
        page = context.new_page()
        page.goto('http://tool.test/bundles', wait_until='domcontentloaded')
        page.wait_for_function("document.querySelectorAll('#game option').length === 3")
        page.click('#btnQueueNew')
        page.fill('#bundleName', 'Keep this Bundle')
        queue_before = page.evaluate("localStorage.getItem('afc.bundleQueue')")
        page.fill('#bundlePasteText', TEXT)
        page.click('#btnBundlePastePreview')
        expect(page.locator('#bundleImportPreview')).to_be_visible()
        expect(page.locator('#btnBundleImportAdd')).to_be_enabled()

        clear = page.get_by_role('button', name='Clear ข้อมูล', exact=True)
        expect(clear).to_have_count(1)
        bounds = clear.bounding_box()
        assert bounds['x'] >= 0
        assert bounds['x'] + bounds['width'] <= width
        clear.focus()
        clear.press('Enter')

        expect(page.locator('#bundlePasteText')).to_have_value('')
        expect(page.locator('#bundlePasteText')).to_be_focused()
        expect(page.locator('#bundleImportPreview')).to_be_hidden()
        expect(page.locator('#bundleImportPreview')).to_be_empty()
        expect(page.locator('#bundleImportMsg')).to_be_hidden()
        expect(page.locator('#btnBundleImportAdd')).to_be_disabled()
        expect(page.locator('#queueCount')).to_have_text('1')
        expect(page.locator('#bundleName')).to_have_value('Keep this Bundle')
        assert page.evaluate("localStorage.getItem('afc.bundleQueue')") == queue_before
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        browser.close()


def test_clear_discards_a_paste_preview_response_that_arrives_late(client):
    """An in-flight response must not restore data the user already cleared."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        _route_live_game_tools(context)
        context.route('https://**', lambda route: route.abort())
        pending = []
        context.route('**/api/bundles/import-text', lambda route: pending.append(route))
        page = context.new_page()
        page.goto('http://tool.test/bundles', wait_until='domcontentloaded')
        page.wait_for_function("document.querySelectorAll('#game option').length === 3")
        page.fill('#bundlePasteText', TEXT)
        with page.expect_request('**/api/bundles/import-text'):
            page.click('#btnBundlePastePreview')
        expect(page.locator('#btnBundlePastePreview')).to_be_disabled()
        page.get_by_role('button', name='Clear ข้อมูล', exact=True).click()
        expect(page.locator('#bundlePasteText')).to_have_value('')
        expect(page.locator('#btnBundlePastePreview')).to_be_enabled()

        response = client.post('/api/bundles/import-text', json={'text': TEXT})
        with page.expect_response('**/api/bundles/import-text') as completed:
            pending[0].fulfill(status=response.status_code, json=response.json())
        completed.value.finished()
        page.evaluate('() => new Promise(resolve => requestAnimationFrame(resolve))')

        expect(page.locator('#bundlePasteText')).to_have_value('')
        expect(page.locator('#bundleImportPreview')).to_be_hidden()
        expect(page.locator('#bundleImportMsg')).to_be_hidden()
        expect(page.locator('#btnBundleImportAdd')).to_be_disabled()
        expect(page.locator('#queueCount')).to_have_text('0')
        browser.close()
