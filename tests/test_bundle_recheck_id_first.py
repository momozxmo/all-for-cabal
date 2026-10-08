"""Public saved-reader contract; every request stays on synthetic pages."""
import asyncio

import pytest
from playwright.async_api import async_playwright

from web.aztek_locator import AztekLocatorError
from web.bundle_recheck import read_saved_bundle


def saved_card(index='0', qty='2'):
    return f'''<div><div><button type="button" aria-label="ย่อ" aria-expanded="true">
    <p>Item 91</p><span>ITEM</span></button></div>
    <div><label>Item ID</label><p>91</p></div>
    <input name="items.{index}.quantity" type="number" value="{qty}">
    <div><label>Tier *</label><button type="button" role="combobox">Common</button>
    <select><option value="0" selected>Common</option></select></div></div>'''


def saved_bundle(cards, count=1, bundle_type='FIXED'):
    return f'''<main><h1>แก้ไข Bundle</h1><p>ID: 42</p>
    <form><input id="bundle-name" value="Saved">
    <div><label>ประเภท Bundle *</label><button type="button" role="combobox">{bundle_type}</button>
    <select><option selected>{bundle_type}</option></select></div>
    <div>รายการไอเท็ม ({count})</div>{cards}</form></main>'''


ITEM_DETAIL = '''<main><h1>แก้ไข Item</h1><p>ID: 91</p>
<form><input id="item-name" value="Item"><input id="item-game-item-id" value="123">
<input id="item-option" value="0"><input id="duration-index" value="9"></form></main>'''
SAVED_URL = 'https://aztek.test/combo/cabalpc/shop/bundles/42'


def test_saved_reader_ignores_cards_and_counts_outside_verified_form():
    async def scenario():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            context = await browser.new_context()
            requests = []

            async def serve(route):
                requests.append((route.request.method, route.request.url))
                assert route.request.method == 'GET'
                if route.request.url == SAVED_URL:
                    body = '<aside>รายการไอเท็ม (1)' + saved_card('99', '999') + '</aside>'
                    body += saved_bundle(saved_card())
                elif route.request.url == 'https://aztek.test/combo/cabalpc/shop/items/91':
                    body = ITEM_DETAIL
                else:
                    await route.abort()
                    raise AssertionError(route.request.url)
                await route.fulfill(content_type='text/html; charset=utf-8', body=body)

            await context.route('**/*', serve)
            page = await context.new_page()
            actual = await read_saved_bundle(page, SAVED_URL)
            assert actual == {'items': [dict(id='91', qty='2', kind='123', option='0',
                                            duration='9', tier='Common')],
                              'rewards': [], 'complete': True, 'unsupported': []}
            assert requests == [('GET', SAVED_URL),
                                ('GET', 'https://aztek.test/combo/cabalpc/shop/items/91')]
            await browser.close()
    asyncio.run(scenario())


async def read_fixture(body, *, mutate_on_detail=None):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        async def serve(route):
            assert route.request.method == 'GET'
            if route.request.url == SAVED_URL:
                content = body
            elif route.request.url == 'https://aztek.test/combo/cabalpc/shop/items/91':
                if mutate_on_detail:
                    await page.evaluate(mutate_on_detail)
                content = ITEM_DETAIL
            else:
                await route.abort()
                raise AssertionError(route.request.url)
            await route.fulfill(content_type='text/html; charset=utf-8', body=content)
        await context.route('**/*', serve)
        try:
            return await read_saved_bundle(page, SAVED_URL)
        finally:
            await browser.close()


def test_saved_reader_ignores_item_picker_ids_that_mount_during_detail_read():
    body = saved_bundle(saved_card()).replace(
        '<h1>แก้ไข Bundle</h1><p>ID: 42</p>',
        '<div><h1>แก้ไข Bundle</h1><p><span>ID: <span>42</span></span></p></div>')
    actual = asyncio.run(read_fixture(body, mutate_on_detail='''() => {
        document.querySelector('form').insertAdjacentHTML('beforeend',
            '<div role="tabpanel"><div><span>ID: 224529</span></div></div>');
    }'''))
    assert actual == {'items': [dict(id='91', qty='2', kind='123', option='0',
                                    duration='9', tier='Common')],
                      'rewards': [], 'complete': True, 'unsupported': []}


@pytest.mark.parametrize('picker_id', ['224529', '42'])
def test_saved_reader_ignores_item_picker_ids_already_present(picker_id):
    body = saved_bundle(saved_card()).replace('</form>',
        f'<div role="tabpanel"><span>ID: {picker_id}</span></div></form>')
    actual = asyncio.run(read_fixture(body))
    assert actual == {'items': [dict(id='91', qty='2', kind='123', option='0',
                                    duration='9', tier='Common')],
                      'rewards': [], 'complete': True, 'unsupported': []}


def test_item_picker_id_cannot_replace_missing_bundle_header_identity():
    body = saved_bundle(saved_card()).replace('<p>ID: 42</p>', '')
    body = body.replace('</form>', '<div role="tabpanel"><span>ID: 42</span></div></form>')
    with pytest.raises(ValueError, match='Bundle ID'):
        asyncio.run(read_fixture(body))


@pytest.mark.parametrize('mutation', [
    '''() => {document.querySelector('main > p').textContent='ID: 43'}''',
    '''() => {document.querySelector('main').insertAdjacentHTML('afterbegin','<p>ID: 43</p>')}''',
    '''() => {document.querySelector('main > p').hidden=true}''',
    '''() => {document.querySelector('main > p').remove()}''',
    '''() => {document.querySelector('form').append(document.querySelector('main > p'))}''',
    '''() => {history.replaceState(null, '', '/combo/cabalpc/shop/bundles/43')}''',
])
def test_bundle_header_identity_changing_during_detail_read_still_stops(mutation):
    body = saved_bundle(saved_card()).replace('</form>',
        '<div role="tabpanel"><span>ID: 42</span></div></form>')
    with pytest.raises(ValueError, match='Bundle ID'):
        asyncio.run(read_fixture(body, mutate_on_detail=mutation))


def test_random_readback_uses_current_row_id_not_name_or_display_chance():
    first = saved_card('7').replace('</select></div></div>', '''</select></div>
    <input id="items.7.secret_chance" name="changed-name" type="number" value="0">
    <input id="items.7.chance" name="items.7.secret_chance" type="number" value="50"></div>''')
    second = saved_card('3', '4').replace('</select></div></div>', '''</select></div>
    <input id="items.3.secret_chance" type="number" value="100">
    <input name="items.3.secret_chance" type="number" value="50"></div>''')
    actual = asyncio.run(read_fixture(saved_bundle(first + second, 2, 'RANDOM')))
    assert actual == {'items': [
        dict(id='91', qty='2', kind='123', option='0', duration='9', tier='Common', rate='0'),
        dict(id='91', qty='4', kind='123', option='0', duration='9', tier='Common', rate='100')],
        'rewards': [], 'complete': True, 'unsupported': []}


@pytest.mark.parametrize('defect', ['missing', 'duplicate', 'wrong_type', 'hidden'])
def test_random_draw_id_contract_failure_cannot_fall_back(defect):
    draw = '<input id="items.7.secret_chance" type="number" value="0">'
    if defect == 'missing':
        draw = ''
    elif defect == 'duplicate':
        draw += draw
    elif defect == 'wrong_type':
        draw = '<textarea id="items.7.secret_chance">0</textarea>'
    else:
        draw = draw.replace('type="number"', 'type="number" hidden')
    card = saved_card('7').replace('</select></div></div>', '</select></div>' + draw +
        '<input name="items.7.secret_chance" type="number" value="0"></div>')
    body = '<input id="items.7.secret_chance" type="number" value="0">'
    body += saved_bundle(card, bundle_type='RANDOM')
    with pytest.raises(AztekLocatorError, match='เรทสุ่ม'):
        asyncio.run(read_fixture(body))


@pytest.mark.parametrize('defect', ['duplicate_tier', 'missing_tier', 'hidden_tier', 'multiple_tier',
                                  'duplicate_identity', 'duplicate_badge', 'submit_expander'])
def test_saved_card_ambiguity_never_reports_complete(defect):
    card = saved_card()
    if defect == 'duplicate_tier':
        card = card.replace('</select>', '</select><select><option>Legend</option></select>')
    elif defect == 'missing_tier':
        card = card.replace('<select><option value="0" selected>Common</option></select>', '')
    elif defect == 'hidden_tier':
        card = card.replace('role="combobox"', 'role="combobox" hidden')
    elif defect == 'multiple_tier':
        card = card.replace('<select>', '<select multiple>')
    elif defect == 'duplicate_identity':
        card = card.replace('<p>91</p>', '<p>91</p><p>92</p>')
    elif defect == 'duplicate_badge':
        card = card.replace('<span>ITEM</span>', '<span>ITEM</span><span>WALLET</span>')
    else:
        card = card.replace('type="button" aria-label=', 'type="submit" aria-label=')
    with pytest.raises(AztekLocatorError):
        asyncio.run(read_fixture(saved_bundle(card)))


def test_saved_reader_expands_only_safe_current_card_and_waits_for_mount():
    card = saved_card().replace('aria-label="ย่อ" aria-expanded="true"',
        '''aria-label="ขยาย" aria-expanded="false" onclick="this.setAttribute('aria-expanded','true');
        setTimeout(()=>this.parentElement.nextElementSibling.hidden=false,650)"''')
    card = card.replace('<div><label>Item ID', '<div hidden><div><label>Item ID')
    card = card.replace('</select></div></div>', '</select></div></div></div>')
    body = saved_bundle(card)
    actual = asyncio.run(read_fixture(body))
    assert actual['items'] == [dict(id='91', qty='2', kind='123', option='0',
                                   duration='9', tier='Common')]
    assert actual['complete'] is True


@pytest.mark.parametrize('control', ['quantity', 'tier', 'type', 'rate'])
def test_saved_reader_waits_for_independently_hydrated_controls(control):
    card = saved_card('7')
    card = card.replace('</select></div></div>', '''</select></div>
        <input id="items.7.secret_chance" type="number" value="0"></div>''')
    body = saved_bundle(card, bundle_type='RANDOM')
    if control == 'quantity':
        body = body.replace('value="2"', 'value=""')
        hydrate = "document.querySelector('[name=\"items.7.quantity\"]').value='2'"
    elif control == 'rate':
        body = body.replace('type="number" value="0"', 'type="number" value=""')
        hydrate = "document.getElementById('items.7.secret_chance').value='0'"
    elif control == 'tier':
        body = body.replace('<option value="0" selected>Common</option>', '<option selected></option>')
        hydrate = "document.querySelectorAll('select')[1].innerHTML='<option value=\"0\" selected>Common</option>'"
    else:
        body = body.replace('<option selected>RANDOM</option>', '<option selected></option>')
        hydrate = "document.querySelector('select').innerHTML='<option selected>RANDOM</option>'"
    body += '<script>setTimeout(()=>{' + hydrate + '},700)</script>'
    actual = asyncio.run(read_fixture(body))
    assert actual['items'] == [dict(id='91', qty='2', kind='123', option='0',
                                   duration='9', tier='Common', rate='0')]


@pytest.mark.parametrize('defect', ['duplicate_identity', 'hidden_identity',
                                  'hidden_expander', 'hidden_badge', 'hidden_type'])
def test_hidden_or_ambiguous_bundle_semantics_are_not_evidence(defect):
    body = saved_bundle(saved_card())
    if defect == 'duplicate_identity':
        body = body.replace('<p>ID: 42</p>', '<p>ID: 42</p><p>ID: 43</p>')
    elif defect == 'hidden_identity':
        body = body.replace('<p>ID: 42</p>', '<p hidden>ID: 42</p><p>ID: 43</p>')
    elif defect == 'hidden_expander':
        body = body.replace('aria-label="ย่อ"', 'hidden aria-label="ย่อ"')
    elif defect == 'hidden_badge':
        body = body.replace('<span>ITEM</span>', '<span hidden>ITEM</span>')
    else:
        body = body.replace('role="combobox">FIXED', 'role="combobox" style="visibility:hidden">FIXED')
    with pytest.raises((ValueError, AztekLocatorError)):
        asyncio.run(read_fixture(body))


def test_expander_changing_to_submit_while_becoming_enabled_never_submits():
    card = saved_card().replace('aria-expanded="true"', 'aria-expanded="false" disabled')
    body = saved_bundle(card)
    body += '''<script>setTimeout(()=>{const b=document.querySelector('[aria-expanded]');
        b.type='submit';b.disabled=false},650)</script>'''
    with pytest.raises(AztekLocatorError):
        asyncio.run(read_fixture(body))


def test_card_mutation_during_detail_read_stops_instead_of_returning_stale_rows():
    body = saved_bundle(saved_card())
    with pytest.raises(AztekLocatorError):
        asyncio.run(read_fixture(body, mutate_on_detail='''() => {
            document.querySelector('[name="items.0.quantity"]').value='99';
        }'''))


def test_saved_reader_waits_for_remaining_card_to_mount():
    body = saved_bundle(saved_card(), count=2)
    body += '<template id="late-card">' + saved_card('1', '4') + '</template>'
    body += '''<script>setTimeout(()=>{document.querySelector('form').append(
        document.getElementById('late-card').content.cloneNode(true))},700)</script>'''
    actual = asyncio.run(read_fixture(body))
    assert actual['items'] == [
        dict(id='91', qty='2', kind='123', option='0', duration='9', tier='Common'),
        dict(id='91', qty='4', kind='123', option='0', duration='9', tier='Common')]


def test_duplicate_current_indexes_cannot_be_used_for_two_occurrences():
    with pytest.raises(AztekLocatorError, match='เลขแถว Quantity'):
        asyncio.run(read_fixture(saved_bundle(saved_card() + saved_card('0', '4'), count=2)))


def test_unknown_reward_type_is_incomplete_not_silently_an_item():
    actual = asyncio.run(read_fixture(saved_bundle(saved_card().replace('<span>ITEM</span>', '<span>NEW_KIND</span>'))))
    assert actual == {'items': [], 'rewards': [], 'complete': False, 'unsupported': [1]}


def test_semantic_count_can_contain_nested_number_markup():
    body = saved_bundle(saved_card()).replace('รายการไอเท็ม (1)', 'รายการไอเท็ม (<span>1</span>)')
    actual = asyncio.run(read_fixture(body))
    assert actual['items'][0]['qty'] == '2'
    assert actual['complete'] is True


@pytest.mark.parametrize('mutation', [
    '''() => {document.querySelector('form').insertAdjacentHTML('beforeend','<input id="bundle-name">')}''',
    '''() => {document.getElementById('bundle-name').hidden=true}''',
    '''() => {document.getElementById('bundle-name').outerHTML='<textarea id="bundle-name">Saved</textarea>'}''',
])
def test_form_marker_contract_changing_during_detail_read_cannot_pass(mutation):
    with pytest.raises(AztekLocatorError):
        asyncio.run(read_fixture(saved_bundle(saved_card()), mutate_on_detail=mutation))
