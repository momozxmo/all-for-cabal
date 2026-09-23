"""Saved-page reader contract, using synthetic Aztek pages only."""
import asyncio

import pytest
from playwright.async_api import async_playwright

from web.bundle_recheck import read_saved_bundle, recheck_saved_bundle


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
            ], 'complete': True, 'unsupported': []}
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
