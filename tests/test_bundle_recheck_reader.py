"""Saved-page reader contract, using synthetic Aztek pages only."""
import asyncio
from copy import deepcopy

import pytest
from playwright.async_api import async_playwright

from web.aztek_locator import AztekLocatorError
from web.bundle_recheck import SessionExpiredError, read_saved_bundle, recheck_saved_bundle

_TIER = '''<div><label>Tier *</label><button type="button" role="combobox">Common</button>
<select><option value="0" selected>Common</option></select></div>'''


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('distinguish', ['tier', 'rate', 'both', 'zero_rate'])
def test_recheck_same_properties_match_known_tier_rate_without_order_bias(
        monkeypatch, reverse, distinguish):
    source = [dict(kind='123', option='0', duration='9', qty='1',
                   tier='Common', rate='40', source_row=7),
              dict(kind='123', option='0', duration='9', qty='1',
                   tier='Rare', rate='60', source_row=8)]
    if distinguish == 'tier':
        source[1]['rate'] = '40'
    elif distinguish == 'rate':
        source[1]['tier'] = 'Common'
    elif distinguish == 'zero_rate':
        source[0]['rate'], source[1]['rate'] = '0', '100'
    reference = dict(game='CabalM TH', items=source, rewards=[])
    submitted = dict(game='CabalM TH', type='RANDOM', rewards=[], items=[
        dict(id='91', qty='1', tier=source[0]['tier'], rate=source[0]['rate']),
        dict(id='92', qty='1', tier=source[1]['tier'], rate=source[1]['rate'])])
    actual_items = [dict(source[0], id='91'), dict(source[1], id='92')]
    # Equivalent numeric rates are not differences, including zero.
    actual_items[0]['rate'] += '.0'
    actual = dict(items=actual_items[::-1] if reverse else actual_items,
                  rewards=[], complete=True, unsupported=[])
    before = deepcopy((reference, submitted, actual))
    async def saved(*_):
        return actual
    monkeypatch.setattr('web.bundle_recheck.read_saved_bundle', saved)
    checked = asyncio.run(recheck_saved_bundle(
        None, 'https://aztek.test/combo/cabalm/shop/bundles/42', reference, submitted))
    assert checked['outcome'] == 'passed'
    assert checked['incomplete'] is False
    assert [(row['source_row'], row['actual']['id'], row['different'])
            for row in checked['rows']] == [(7, '91', []), (8, '92', [])]
    assert (reference, submitted, actual) == before


@pytest.mark.parametrize('change,outcome', [
    ('all_unreadable', 'failed'), ('second_unreadable', 'failed'),
    ('proven_mismatch_and_unreadable', 'mismatch'), ('complete_missing', 'mismatch'),
])
def test_recheck_omitted_unreadable_occurrence_does_not_invent_mismatch(
        monkeypatch, change, outcome):
    reference = dict(game='CabalM TH', rewards=[], items=[
        dict(kind='123', option='0', duration='9', qty='1', tier='Common'),
        dict(kind='456', option='0', duration='9', qty='1', tier='Common')])
    submitted = dict(game='CabalM TH', type='FIXED', rewards=[], items=[
        dict(id='91', qty='1', tier='Common'), dict(id='92', qty='1', tier='Common')])
    actual = dict(items=[dict(reference['items'][0], id='91')], rewards=[],
                  complete=False, unsupported=[1])
    if change == 'all_unreadable':
        actual['items'] = []
    elif change == 'proven_mismatch_and_unreadable':
        actual['items'][0]['tier'] = 'Rare'
    elif change == 'complete_missing':
        actual.update(complete=True, unsupported=[])
    async def saved(*_):
        return actual
    monkeypatch.setattr('web.bundle_recheck.read_saved_bundle', saved)
    checked = asyncio.run(recheck_saved_bundle(
        None, 'https://aztek.test/combo/cabalm/shop/bundles/42', reference, submitted))
    assert checked['outcome'] == outcome
    assert checked['incomplete'] is (change != 'complete_missing')
    if outcome == 'failed':
        assert checked['differences'] == []
        assert any(row['different'] == ['unreadable_item'] for row in checked['rows'])
    else:
        assert checked['differences']

def _saved_page(content, bundle_type='FIXED'):
    # The verified saved page keeps its record heading/ID outside the form;
    # picker-result IDs belong inside it. Preserve the supplied wrong-ID cases.
    heading_and_id, end_id, cards = content.partition('</p>')
    assert content.lstrip().startswith('<h1>แก้ไข Bundle</h1><p>ID: ') and end_id
    return f'''<main>{heading_and_id}{end_id}<form><input id="bundle-name" value="Saved">
    <div><label>ประเภท Bundle *</label><button type="button" role="combobox">{bundle_type}</button>
    <select><option selected>{bundle_type}</option></select></div>{cards}</form></main>'''


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
                        body += f'''<div><div><button type="button" aria-label="ขยาย" aria-expanded="false"
                        onclick="this.setAttribute('aria-expanded','true');this.parentElement.nextElementSibling.hidden=false"><span>ITEM</span> stale cached attributes</button></div>
                        <div hidden><div><label>Item ID</label><p>91</p></div>
                        <label>จำนวน (Quantity)</label><input name="items.{index}.quantity" type="number" value="{index + 1}">{_TIER}</div></div>'''
                    body = _saved_page(body)
                elif path.endswith('/items/91'):
                    displayed_id = '92' if change == 'wrong_detail_id' else '91'
                    body = f'''<main><h1>แก้ไข Item</h1><p>ID: {displayed_id}</p>
                    <form><input id="item-name" value="Item">
                    <input id="item-game-item-id" value="123">
                    <input id="item-option" value="0">
                    <input id="duration-index" value="9"></form></main>'''
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
                {'id': '91', 'qty': '1', 'kind': '123', 'option': '0', 'duration': '9', 'tier': 'Common'},
                {'id': '91', 'qty': '2', 'kind': '123', 'option': '0', 'duration': '9', 'tier': 'Common'},
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
                content_type='text/html; charset=utf-8', body=_saved_page('''
                <h1>แก้ไข Bundle</h1><p>ID: 42</p>
                <div>รายการไอเท็ม ( 2 )</div><button>ขยายทั้งหมด</button>
                <div><div><button aria-label="ย่อ" aria-expanded="true">CREDIT</button></div></div>''')))
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
                    body = '''<main><h1>แก้ไข Item</h1><p>ID: 91</p>
                    <form><input id="item-name" value="Item">
                    <input id="item-game-item-id" value="123">
                    <input id="item-option" value="0"><input id="duration-index" value="9"></form></main>'''
                else:
                    body = f'''<h1>แก้ไข Bundle</h1><p>ID: 42</p><div>รายการไอเท็ม ( 2 )</div>
                    <button onclick="document.querySelectorAll('[hidden]').forEach(e=>e.hidden=false)">ขยายทั้งหมด</button>
                    <div><div><button type="button" aria-label="ขยาย" aria-expanded="false"
                    onclick="this.setAttribute('aria-expanded','true');this.parentElement.nextElementSibling.hidden=false"><span>ITEM</span></button></div>
                    <div hidden><div><label>Item ID</label><p>91</p></div>
                    <input name="items.0.quantity" type="number" value="2">
                    {_TIER}
                    <input id="items.0.secret_chance" name="items.0.secret_chance" type="number" value="60"></div></div>
                    <div><div><button type="button" aria-label="ขยาย" aria-expanded="false"
                    onclick="this.setAttribute('aria-expanded','true');this.parentElement.nextElementSibling.hidden=false"><p>Player Experience - PC</p><span>PLAYER_EXP</span></button></div>
                    <div hidden><div><label>ชื่อ Monarchy</label><p>Player Experience - PC</p></div>
                    <input name="items.1.quantity" type="number" value="6">
                    {_TIER}
                    <input id="items.1.secret_chance" name="items.1.secret_chance" type="number" value="40"></div></div>'''
                    body = _saved_page(body, 'RANDOM')
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
                body = ('''<main><h1>แก้ไข Item</h1><p>ID: 91</p>
                    <form><input id="item-name" value="Item">
                    <input id="item-game-item-id" value="123"><input id="item-option" value="0">
                    <input id="duration-index" value="9"></form></main>'''
                    if route.request.url.endswith('/items/91') else
                    f'''<h1>แก้ไข Bundle</h1><p>ID: 42</p><div>รายการไอเท็ม (1)</div>
                    <div><div><button type="button" aria-label="ย่อ" aria-expanded="true"><span>ITEM</span></button></div>
                    <div><div><label>Item ID</label><p>91</p></div>
                    <input name="items.0.quantity" type="number" value="1">{_TIER}</div></div>''')
                if route.request.url.endswith('/bundles/42'):
                    body = _saved_page(body)
                await route.fulfill(content_type='text/html; charset=utf-8', body=body)
            await context.route('**/*', serve)
            result = await read_saved_bundle(page, 'https://aztek.test/combo/cabalpc/shop/bundles/42')
            assert result['complete'] is True
            assert result['items'][0]['id'] == '91'
            await browser.close()
    asyncio.run(scenario())


@pytest.mark.parametrize('field', ['item-game-item-id', 'item-option', 'duration-index'])
@pytest.mark.parametrize('defect', ['missing', 'duplicate', 'wrong_type', 'hidden'])
def test_saved_item_contract_failure_cannot_use_a_misleading_fallback(field, defect):
    """A page-wide/name-based read must not turn a broken ID into a pass."""
    async def scenario():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            context = await browser.new_context()

            async def serve(route):
                assert route.request.method == 'GET'
                if route.request.url.endswith('/bundles/42'):
                    body = f'''<h1>แก้ไข Bundle</h1><p>ID: 42</p><div>รายการไอเท็ม (1)</div>
                    <div><div><button type="button" aria-label="ย่อ" aria-expanded="true"><span>ITEM</span></button></div>
                    <div><label>Item ID</label><p>91</p><input name="items.0.quantity" type="number" value="1">{_TIER}</div></div>'''
                    body = _saved_page(body)
                else:
                    values = {'item-game-item-id': '123', 'item-option': '0', 'duration-index': '9'}
                    controls = ''
                    for identifier, value in values.items():
                        control = f'<input id="{identifier}" value="{value}">'
                        if identifier == field:
                            if defect == 'missing':
                                control = f'<input name="{identifier}" value="{value}">'
                            elif defect == 'duplicate':
                                control += control
                            elif defect == 'wrong_type':
                                control = f'<textarea id="{identifier}">{value}</textarea>'
                            else:
                                control = f'<input id="{identifier}" value="{value}" hidden>'
                        controls += control
                    # A correct-looking ID outside the verified form is not evidence.
                    body = f'''<input id="{field}" value="{values[field]}">
                    <main><h1>แก้ไข Item</h1><p>ID: 91</p>
                    <form><input id="item-name" value="Item">{controls}</form></main>'''
                await route.fulfill(content_type='text/html; charset=utf-8', body=body)

            await context.route('**/*', serve)
            page = await context.new_page()
            with pytest.raises(AztekLocatorError):
                await read_saved_bundle(page, 'https://aztek.test/combo/cabalpc/shop/bundles/42')
            await browser.close()
    asyncio.run(scenario())


@pytest.mark.parametrize('mode', ['outside_decoys', 'delayed_values', 'wrong_identity',
                                  'delayed_identity', 'hidden_identity', 'identity_disappears'])
def test_saved_item_read_uses_ready_values_in_the_verified_form(mode):
    """Fresh form values, not external decoys or early empty hydration, win."""
    async def scenario():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            context = await browser.new_context()

            async def serve(route):
                assert route.request.method == 'GET'
                if route.request.url.endswith('/bundles/42'):
                    body = f'''<h1>แก้ไข Bundle</h1><p>ID: 42</p><div>รายการไอเท็ม (1)</div>
                    <div><div><button type="button" aria-label="ย่อ" aria-expanded="true"><span>ITEM</span></button></div>
                    <div><label>Item ID</label><p>91</p><input name="items.0.quantity" type="number" value="1">{_TIER}</div></div>'''
                    body = _saved_page(body)
                else:
                    identity = '92' if mode == 'wrong_identity' else '91'
                    body = f'''<aside><p>ID: 91</p><input id="item-game-item-id" value="999">
                    <input id="item-option" value="999"><input id="duration-index" value="999"></aside>
                    <main><h1>แก้ไข Item</h1><p>ID: {identity}</p>
                    <form><input id="item-name" value="Item">
                    <input id="item-game-item-id" value="123"><input id="item-option" value="0">
                    <input id="duration-index" value="9"></form></main>'''
                    if mode == 'delayed_values':
                        body = body.replace('value="123"', 'value=""').replace('value="0"', 'value=""').replace('value="9"', 'value=""')
                        body += '''<script>setTimeout(()=>{const f=document.querySelector('form');
                        f.querySelector('[id="item-game-item-id"]').value='123';
                        f.querySelector('[id="item-option"]').value='0';
                        f.querySelector('[id="duration-index"]').value='9'},700)</script>'''
                    elif mode == 'delayed_identity':
                        body = body.replace('<p>ID: 91</p>\n                    <form>', '<p id="record-identity"></p>\n                    <form>')
                        body += '''<script>setTimeout(()=>{document.getElementById('record-identity').textContent='ID: 91'},700)</script>'''
                    elif mode == 'hidden_identity':
                        body = body.replace('<main><h1>แก้ไข Item</h1><p>ID: 91</p>',
                                            '<main><h1>แก้ไข Item</h1><p hidden>ID: 91</p><p>ID: 92</p>')
                    elif mode == 'identity_disappears':
                        body += '''<script>setTimeout(()=>{document.querySelector('main p').hidden=true},150)</script>'''
                await route.fulfill(content_type='text/html; charset=utf-8', body=body)

            await context.route('**/*', serve)
            page = await context.new_page()
            if mode in ('wrong_identity', 'hidden_identity', 'identity_disappears'):
                with pytest.raises(ValueError, match='Item ID'):
                    await read_saved_bundle(page, 'https://aztek.test/combo/cabalpc/shop/bundles/42')
            else:
                result = await read_saved_bundle(page, 'https://aztek.test/combo/cabalpc/shop/bundles/42')
                assert result == {'items': [dict(id='91', qty='1', kind='123', option='0', duration='9', tier='Common')],
                                  'rewards': [], 'complete': True, 'unsupported': []}
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
                content_type='text/html; charset=utf-8', body=_saved_page(f'''
                <h1>แก้ไข Bundle</h1><p>ID: 42</p><div>รายการไอเท็ม (1)</div>
                <div><div><button type="button" aria-label="ย่อ" aria-expanded="true"><p>Pirate Coin</p><span>{badge}</span></button></div>
                <div><div><label>{'ชื่อ Monarchy' if badge == 'PLAYER_EXPERIENCE' else 'ชื่อ'}</label><p>Pirate Coin</p></div>
                <input name="items.0.quantity" type="number" value="2">
                {_TIER}</div></div>''')))
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
                    await route.fulfill(content_type='text/html; charset=utf-8', body=_saved_page(f'''
                        <h1>แก้ไข Bundle</h1><p>ID: 42</p><div>รายการไอเท็ม (1)</div>
                        <div><div><button type="button" aria-label="ย่อ" aria-expanded="true"><span>ITEM</span></button></div>
                        <div><label>Item ID</label><p>91</p>
                        <input name="items.0.quantity" type="number" value="1">{_TIER}</div></div>'''))
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
