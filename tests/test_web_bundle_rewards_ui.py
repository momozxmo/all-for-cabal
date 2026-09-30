"""Added rewards must expose their identity, not just their reward kind."""
import pytest
from playwright.sync_api import sync_playwright, expect

from test_web_product_ui import _route_live_game_tools


@pytest.mark.parametrize('width', [360, 768, 1280, 1600])
@pytest.mark.parametrize('bundle_type', ['FIXED', 'RANDOM'])
def test_currency_names_remain_readable_with_working_controls(width, bundle_type):
    names = ['Alz - สกุลเงินสำหรับกิจกรรม ' + 'VeryLongCurrencyCode' * 8,
             'Force Gem', 'Rank 5 - Player Experience']
    kinds = ['CREDIT', 'DEBIT', 'PLAYER_EXP']
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': width, 'height': 900},
                                      reduced_motion='reduce')
        _route_live_game_tools(context)
        context.route('https://**', lambda route: route.abort())
        context.route('**/api/reward-options', lambda route: route.fulfill(json={
            'reward_options': dict(zip(kinds, [[name] for name in names])), 'logs': []}))
        page = context.new_page()
        page.goto('http://tool.test/bundles', wait_until='domcontentloaded')
        page.wait_for_function("document.querySelectorAll('#game option').length === 3")
        page.click('#btnQueueNew')
        page.select_option('#bundleType', bundle_type)
        page.click('#btnRewardFetch')
        expect(page.locator('#runMsg')).to_contain_text('โหลดตัวเลือก reward แล้ว')

        for kind, name in zip(kinds, names):
            page.select_option('#rewardKind', kind)
            page.locator('#rewardValue').focus()
            page.locator('#rewardValue').press('ArrowDown')
            page.locator('#rewardValue').press('Enter')
            expect(page.locator('#rewardValue')).to_have_value(name)
            page.locator('#btnRewardAdd').focus()
            page.locator('#btnRewardAdd').press('Enter')

        rows = page.locator('#rewardList .rwrow')
        expect(rows).to_have_count(3)
        for index, name in enumerate(names):
            row, label = rows.nth(index), rows.nth(index).locator('.v')
            expect(label).to_have_text(name)
            assert label.is_visible(), f'{name} has been squeezed out of the row'
            assert label.bounding_box()['width'] > 50
            assert label.evaluate('e => e.scrollWidth <= e.clientWidth')
            bounds = row.bounding_box()
            assert bounds['x'] >= 0
            assert bounds['x'] + bounds['width'] <= width
            for control in row.locator('input,select,button').all():
                expect(control).to_be_visible()
                box = control.bounding_box()
                assert box['width'] >= 44
                assert box['x'] >= bounds['x']
                assert box['x'] + box['width'] <= bounds['x'] + bounds['width']

        quantity = rows.nth(0).get_by_label('จำนวน Reward')
        quantity.fill('7')
        rows.nth(0).get_by_label('Rarity Reward').select_option('Epic')
        if bundle_type == 'RANDOM':
            rate = rows.nth(0).get_by_label('เรท Reward')
            rate.fill('0')
            assert rate.evaluate('e => e.checkValidity()')
        rewards = page.evaluate('jobFrom(state.queue[0]).rewards')
        assert [reward['value'] for reward in rewards] == names
        assert rewards[0]['qty'] == '7'
        assert rewards[0]['tier'] == 'Epic'
        if bundle_type == 'RANDOM':
            assert rewards[0]['rate'] == '0'
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')

        for remaining in (2, 1, 0):
            remove = rows.nth(0).get_by_role('button', name='✕', exact=True)
            remove.focus()
            expect(remove).to_be_focused()
            assert remove.evaluate('e => getComputedStyle(e).outlineStyle !== "none"')
            remove.press('Enter')
            expect(rows).to_have_count(remaining)
        assert page.evaluate('jobFrom(state.queue[0]).rewards') == []
        browser.close()
