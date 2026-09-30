"""Saved-page reader contract, using synthetic Aztek pages only."""
import asyncio

import pytest
from playwright.async_api import async_playwright

from web.bundle_recheck import SessionExpiredError, read_saved_bundle, recheck_saved_bundle


@pytest.mark.parametrize('reward_kind,reward_value', [
    ('CREDIT', 'Alz'), ('DEBIT', 'Point'), ('MILEAGE', 'Mileage'),
    ('PLAYER_EXP', 'Player Experience - PC'),
])
@pytest.mark.parametrize('change,outcome,incomplete', [
    ('none', 'passed', False), ('wrong_tier', 'mismatch', False),
    ('wrong_rate', 'mismatch', False), ('wrong_reward_qty', 'mismatch', False),
    ('missing_reward', 'mismatch', False), ('unknown_source', 'partial', True),
    ('mismatch_and_unreadable', 'mismatch', True),
    ('unreadable_only', 'failed', True), ('no_reference', 'partial', True),
])
def test_mixed_rewards_compare_saved_rows(monkeypatch, change, outcome, incomplete,
                                          reward_kind, reward_value):
    async def scenario():
        actual = {'items': [dict(id='91', qty='2', kind='123', option='0',
                                 duration='9', tier='Common', rate='60')],
                  'rewards': [dict(type=reward_kind, value=reward_value,
                                   qty='6', tier='Common', rate='40')],
                  'complete': True, 'unsupported': []}
        reference = {'game': 'Cabal PC', 'items': [
            dict(kind='123', option='0', duration='9', qty='2', tier='Common', rate='60')],
            'rewards': [dict(type=reward_kind, value=reward_value,
                             qty='6', tier='Common', rate='40')]}
        submitted = {'game': 'Cabal PC', 'type': 'RANDOM',
                     'items': [dict(id='91', qty='2', tier='Common', rate='60')],
                     'rewards': [dict(type=reward_kind, value=reward_value,
                                      qty='6', tier='Common', rate='40')]}
        if change == 'wrong_tier':
            actual['rewards'][0]['tier'] = 'Rare'
        elif change == 'wrong_rate':
            actual['items'][0]['rate'] = '59'
        elif change == 'wrong_reward_qty':
            actual['rewards'][0]['qty'] = '5'
        elif change == 'missing_reward':
            actual['rewards'].clear()
        elif change == 'unknown_source':
            reference['items'][0]['kind'] = None
        elif change == 'mismatch_and_unreadable':
            actual['rewards'][0]['tier'] = 'Rare'
            actual['complete'] = False
        elif change == 'unreadable_only':
            actual['complete'] = False
        elif change == 'no_reference':
            reference = None
        async def saved(*_):
            return actual
        monkeypatch.setattr('web.bundle_recheck.read_saved_bundle', saved)
        checked = await recheck_saved_bundle(None, 'https://aztek.test/combo/cabalpc/shop/bundles/42',
                                             reference, submitted)
        assert checked['outcome'] == outcome
        assert checked['incomplete'] is incomplete
        assert len(checked['rows']) >= 2 or change in ('missing_reward', 'no_reference')
        assert checked['coverage']['saved_rows'] == (
            '1/2' if change == 'missing_reward' else '2/0' if change == 'no_reference' else '2/2')
    asyncio.run(scenario())


@pytest.mark.parametrize('change,outcome', [
    ('none', 'passed'), ('wrong_id', 'mismatch'), ('wrong_kind', 'mismatch'),
    ('wrong_qty', 'mismatch'), ('wrong_submitted_qty', 'mismatch'),
    ('missing', 'mismatch'), ('extra', 'mismatch'),
    ('merged', 'mismatch'), ('no_reference', 'partial'), ('missing_option', 'partial'),
    ('partial_wrong_kind', 'mismatch'),
    ('wrong_game', 'mismatch'), ('missing_game', 'partial'),
    ('wrong_detail_id', 'failed'),
    ('wrong_bundle_id', 'failed'),
])
def test_saved_reader_expands_rows_and_reads_fresh_item_details(change, outcome):
    async def scenario():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            context = await browser.new_context()
            visited = []

            async def serve(route):
                path = route.request.url
                visited.append(path)
                if path.endswith('/bundles/42'):
                    displayed_bundle_id = '43' if change == 'wrong_bundle_id' else '42'
                    body = f'''<h1>แก้ไข Bundle</h1><p>ID: {displayed_bundle_id}</p>
                    <div>รายการไอเท็ม ( 2 )</div>
                    <button onclick="document.querySelectorAll('[hidden]').forEach(e=>e.hidden=false)">ขยายทั้งหมด</button>'''
                    for index in range(2):
                        body += f'''<div><div><button aria-label="ขยาย" aria-expanded="false">ITEM stale cached attributes</button></div>
                        <div hidden><div><label>Item ID</label><p>91</p></div>
                        <label>จำนวน (Quantity)</label><input name="items.{index}.quantity" value="{index + 1}"></div></div>'''
                elif path.endswith('/items/91'):
                    displayed_id = '92' if change == 'wrong_detail_id' else '91'
                    body = f'''<h1>แก้ไข Item</h1><p>ID: {displayed_id}</p>
                    <input id="item-game-item-id" value="123">
                    <input id="item-option" value="0">
                    <input id="duration-index" value="9">'''
                else:
                    raise AssertionError(path)
                await route.fulfill(content_type='text/html; charset=utf-8', body=body)

            await context.route('**/*', serve)
            page = await context.new_page()
            if change in ('wrong_detail_id', 'wrong_bundle_id'):
                with pytest.raises(ValueError, match='Item ID' if change == 'wrong_detail_id' else 'Bundle ID'):
                    await read_saved_bundle(page, 'https://aztek.test/combo/cabalpc/shop/bundles/42')
                await browser.close()
                return
            result = await read_saved_bundle(page, 'https://aztek.test/combo/cabalpc/shop/bundles/42')
            assert result == {'items': [
                {'id': '91', 'qty': '1', 'kind': '123', 'option': '0', 'duration': '9'},
                {'id': '91', 'qty': '2', 'kind': '123', 'option': '0', 'duration': '9'},
            ], 'rewards': [], 'complete': True, 'unsupported': []}
            assert any(url.endswith('/items/91') for url in visited)
            reference = {'game': 'Cabal PC', 'items': [
                    {'kind': '123', 'option': '0', 'duration': '9', 'qty': '2'},
                    {'kind': '123', 'option': '0', 'duration': '9', 'qty': '1'},
                ]}
            submitted = {'game': 'Cabal PC', 'items': [{'id': '91', 'qty': '1'}, {'id': '91', 'qty': '2'}]}
            if change == 'wrong_id':
                submitted['items'][0]['id'] = '92'
            elif change == 'wrong_kind':
                reference['items'][0]['kind'] = '999'
            elif change == 'wrong_qty':
                reference['items'][0]['qty'] = '3'
            elif change == 'wrong_submitted_qty':
                submitted['items'][0]['qty'] = '9'
            elif change == 'missing':
                reference['items'].append(dict(reference['items'][0]))
            elif change == 'extra':
                reference['items'].pop()
            elif change == 'merged':
                reference['items'] = [dict(reference['items'][0], qty='3')]
            elif change == 'no_reference':
                reference = None
            elif change == 'missing_option':
                reference['items'][0]['option'] = None
            elif change == 'partial_wrong_kind':
                reference['items'][0]['option'] = None
                reference['items'][0]['kind'] = '999'
            elif change == 'wrong_game':
                reference['game'] = 'CabalM TH'
            elif change == 'missing_game':
                reference.pop('game')
            checked = await recheck_saved_bundle(page,
                'https://aztek.test/combo/cabalpc/shop/bundles/42', reference, submitted)
            assert checked['outcome'] == outcome
            if change == 'wrong_kind':
                assert checked['rows'][0]['original']['kind'] == '999'
                assert checked['rows'][0]['actual']['kind'] == '123'
                assert checked['rows'][0]['different'] == ['kind']
            if change == 'wrong_id':
                assert any('id' in row['different'] for row in checked['rows'])
            if change == 'wrong_submitted_qty':
                assert any('submitted_qty' in row['different'] for row in checked['rows'])
            if change == 'missing_option':
                assert checked['coverage']['properties'] == '7/8'
            await browser.close()

    asyncio.run(scenario())


def test_saved_reader_rejects_missing_cards_instead_of_reporting_complete():
    async def scenario():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()
            await page.route('**/*', lambda route: route.fulfill(
                content_type='text/html; charset=utf-8', body='''
                <h1>แก้ไข Bundle</h1><p>ID: 42</p>
                <div>รายการไอเท็ม ( 2 )</div><button>ขยายทั้งหมด</button>
                <div><div><button aria-label="ย่อ" aria-expanded="true">CREDIT</button></div></div>'''))
            with pytest.raises(ValueError, match='จำนวนแถว'):
                await read_saved_bundle(page, 'https://aztek.test/combo/cabalpc/shop/bundles/42')
            await browser.close()

    asyncio.run(scenario())


def test_saved_reader_reads_reward_tier_and_random_rate_from_saved_cards():
    async def scenario():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            context = await browser.new_context()
            async def serve(route):
                if route.request.url.endswith('/items/91'):
                    body = '''<h1>แก้ไข Item</h1><p>ID: 91</p>
                    <input id="item-game-item-id" value="123">
                    <input id="item-option" value="0"><input id="duration-index" value="9">'''
                else:
                    body = '''<h1>แก้ไข Bundle</h1><p>ID: 42</p><div>รายการไอเท็ม ( 2 )</div>
                    <button onclick="document.querySelectorAll('[hidden]').forEach(e=>e.hidden=false)">ขยายทั้งหมด</button>
                    <div><div><button aria-label="ขยาย" aria-expanded="false"><span>ITEM</span></button></div>
                    <div hidden><div><label>Item ID</label><p>91</p></div>
                    <input name="items.0.quantity" value="2">
                    <select><option selected>Common</option></select>
                    <input name="items.0.secret_chance" value="60"></div></div>
                    <div><div><button aria-label="ขยาย" aria-expanded="false"><p>Player Experience - PC</p><span>PLAYER_EXP</span></button></div>
                    <div hidden><input name="items.1.quantity" value="6">
                    <select><option selected>Common</option></select>
                    <input name="items.1.secret_chance" value="40"></div></div>'''
                await route.fulfill(content_type='text/html; charset=utf-8', body=body)
            await context.route('**/*', serve)
            page = await context.new_page()
            result = await read_saved_bundle(page, 'https://aztek.test/combo/cabalpc/shop/bundles/42')
            assert result['items'][0]['tier'] == 'Common'
            assert result['items'][0]['rate'] == '60'
            assert result['rewards'] == [dict(type='PLAYER_EXP', value='Player Experience - PC',
                                               qty='6', tier='Common', rate='40')]
            assert result['complete']
            await browser.close()
    asyncio.run(scenario())


def test_single_saved_card_does_not_require_expand_all_button():
    async def scenario():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()
            async def serve(route):
                body = ('''<h1>แก้ไข Item</h1><p>ID: 91</p>
                    <input id="item-game-item-id" value="123"><input id="item-option" value="0">
                    <input id="duration-index" value="9">'''
                    if route.request.url.endswith('/items/91') else
                    '''<h1>แก้ไข Bundle</h1><p>ID: 42</p><div>รายการไอเท็ม (1)</div>
                    <div><div><button aria-label="ย่อ" aria-expanded="true">ITEM</button></div>
                    <div><div><label>Item ID</label><p>91</p></div>
                    <input name="items.0.quantity" value="1"></div></div>''')
                await route.fulfill(content_type='text/html; charset=utf-8', body=body)
            await context.route('**/*', serve)
            result = await read_saved_bundle(page, 'https://aztek.test/combo/cabalpc/shop/bundles/42')
            assert result['complete'] is True
            assert result['items'][0]['id'] == '91'
            await browser.close()
    asyncio.run(scenario())


@pytest.mark.parametrize('badge,kind', [
    ('WALLET_CREDIT', 'CREDIT'), ('WALLET', 'DEBIT'),
    ('WALLET_MILEAGE', 'MILEAGE'), ('PLAYER_EXPERIENCE', 'PLAYER_EXP'),
])
def test_saved_reward_badges_match_template_types(badge, kind):
    async def scenario():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()
            await context.route('**/*', lambda route: route.fulfill(
                content_type='text/html; charset=utf-8', body=f'''
                <h1>แก้ไข Bundle</h1><p>ID: 42</p><div>รายการไอเท็ม (1)</div>
                <div><div><button aria-label="ย่อ" aria-expanded="true"><p>Pirate Coin</p><span>{badge}</span></button></div>
                <div><div><label>ชื่อ</label><p>Pirate Coin</p></div>
                <input name="items.0.quantity" value="2">
                <select><option selected>Common</option></select></div></div>'''))
            result = await read_saved_bundle(page, 'https://aztek.test/combo/cabalpc/shop/bundles/42')
            assert result['complete'] is True
            assert result['rewards'] == [dict(type=kind, value='Pirate Coin', qty='2', tier='Common')]
            await browser.close()
    asyncio.run(scenario())


def test_currency_code_not_visible_on_saved_card_is_partial_not_false_mismatch(monkeypatch):
    async def saved(*_):
        return {'items': [], 'rewards': [dict(type='DEBIT', value='Pirate Coin',
                                             qty='2', tier='Common')],
                'complete': True, 'unsupported': []}
    monkeypatch.setattr('web.bundle_recheck.read_saved_bundle', saved)
    reference = {'game': 'Cabal PC', 'items': [], 'rewards': [
        dict(type='DEBIT', value='cabalpcth-pirate-coin - Pirate Coin',
             qty='2', tier='Common')]}
    submitted = {'game': 'Cabal PC', 'items': [], 'rewards': [
        dict(type='DEBIT', value='cabalpcth-pirate-coin - Pirate Coin',
             qty='2', tier='Common')]}
    checked = asyncio.run(recheck_saved_bundle(None, 'url', reference, submitted))
    assert checked['outcome'] == 'partial'
    assert checked['incomplete'] is True
    assert checked['differences'] == []


@pytest.mark.parametrize('source_items,expected_outcome', [
    (None, 'partial'), ([], 'mismatch'),
])
def test_missing_or_explicitly_empty_item_source_cannot_pass(
        monkeypatch, source_items, expected_outcome):
    async def saved(*_):
        return {'items': [dict(id='91', qty='1', kind='123', option='0', duration='9')],
                'rewards': [dict(type='PLAYER_EXP', value='Player Experience - PC',
                                 qty='6', tier='Common')],
                'complete': True, 'unsupported': []}
    monkeypatch.setattr('web.bundle_recheck.read_saved_bundle', saved)
    reference = {'game': 'Cabal PC', 'rewards': [
        dict(type='PLAYER_EXP', value='Player Experience - PC',
             qty='6', tier='Common')]}
    if source_items is not None:
        reference['items'] = source_items
    submitted = {'game': 'Cabal PC', 'type': 'FIXED',
                 'items': [dict(id='91', qty='1')],
                 'rewards': [dict(type='PLAYER_EXP', value='Player Experience - PC',
                                  qty='6', tier='Common')]}
    checked = asyncio.run(recheck_saved_bundle(None, 'url', reference, submitted))
    assert checked['outcome'] == expected_outcome


def test_item_detail_login_redirect_stops_recheck_immediately():
    async def scenario():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            context = await browser.new_context()
            async def serve(route):
                path = route.request.url
                if path.endswith('/bundles/42'):
                    await route.fulfill(content_type='text/html; charset=utf-8', body='''
                        <h1>แก้ไข Bundle</h1><p>ID: 42</p><div>รายการไอเท็ม (1)</div>
                        <div><div><button aria-label="ย่อ" aria-expanded="true"><span>ITEM</span></button></div>
                        <div><label>Item ID</label><p>91</p>
                        <input name="items.0.quantity" value="1"></div></div>''')
                elif path.endswith('/items/91'):
                    await route.fulfill(content_type='text/html',
                                        body='<script>location.replace("/login")</script>')
                elif path.endswith('/login'):
                    await route.fulfill(content_type='text/html', body='<h1>Login</h1>')
                else:
                    raise AssertionError(path)
            await context.route('**/*', serve)
            page = await context.new_page()
            with pytest.raises(SessionExpiredError, match='หมดอายุ'):
                await read_saved_bundle(page, 'https://aztek.test/combo/cabalpc/shop/bundles/42')
            await browser.close()
    asyncio.run(scenario())
