"""Real API/runner, with all Aztek traffic fulfilled by synthetic pages."""
from types import SimpleNamespace
from urllib.parse import urlsplit
from io import BytesIO
import datetime as dt

import pytest
from openpyxl import Workbook
from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright, expect

from web import bundle_runner
from test_web_bundle_import import workbook_bytes
from test_web_product_ui import _route_live_game_tools, PRODUCTS
from test_web_finder_id_first import DETAIL_HTML, LIST_HTML, routed_browser
from test_web_search_auth import _drain
from test_web_validation import _connect_aztek, GAME


def _import_and_search_plan(client, monkeypatch, *, shop=False):
    if shop:
        # Inject only the clock input; the original Shop metadata parser still reads the workbook.
        import item_finder
        original_meta = item_finder._shop_product_meta

        def fixed_clock_meta(header_rows, sheet_title, group, now=None):
            return original_meta(header_rows, sheet_title, group, now=now or dt.datetime(
                2026, 10, 17, 12, tzinfo=dt.timezone(dt.timedelta(hours=7))))

        monkeypatch.setattr(item_finder, '_shop_product_meta', fixed_clock_meta)
    book = Workbook()
    book.remove(book.active)
    for name, kind, amount in [('First', 123, 2), ('Later', 123, 3), ('Unchecked', 777, 1)]:
        sheet = book.create_sheet(name)
        rows = ([['Product Name', name + ' Pack'],
                 ['Category', 'Highlight', 'End Date', dt.date(2027, 9, 28),
                  'End Time', dt.time(23, 59, 59)], ['Limit', 'No limit'],
                 ['ItemKind', 'ItemOption', 'DurationIndex', 'Item Name', 'Amt'],
                 [kind, 0, 9, 'Item', amount]] if shop else
                [['Event Name', 'Plan Event'], ['Reward: ' + name],
                 ['ItemKind', 'ItemOption', 'DurationIndex', 'Display Name', 'Amt'],
                 [kind, 0, 9, 'Item', amount]])
        for row in rows:
            sheet.append(row)
    stream = BytesIO()
    book.save(stream)
    book.close()
    imported = client.post('/api/import-plan', data={'mode': 'shop' if shop else 'event'},
        files={'file': ('plan.xlsx', stream.getvalue())})
    assert imported.status_code == 200, imported.text
    pending = imported.json()
    assert [sheet['name'] for sheet in pending['sheets']] == ['First', 'Later', 'Unchecked']
    applied = client.post('/api/import-plan/apply', json={
        'pending_id': pending['pending_id'],
        'selected_sheets': ['First', 'Later'] if shop else ['First', 'Later', 'Unchecked']})
    assert applied.status_code == 200, applied.text
    html = LIST_HTML.replace('12345', '123')
    if not shop:
        html = html.replace('</tbody>',
            '<tr><td>99</td><td>Unchecked</td><td>777</td><td>0</td><td>9</td></tr></tbody>')
    detail = None
    if shop:
        assert [sheet['product_count'] for sheet in pending['sheets']] == [1, 1, 1]
        detail = DETAIL_HTML.replace('12345', '123').replace('</form>', '''
          <img alt="Preview" id="fixture-preview" width="40" height="40">
          <script>document.getElementById('fixture-preview').src=URL.createObjectURL(new Blob(
            ['<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"><rect width="40" height="40"/></svg>'],
            {type:'image/svg+xml'}));</script></form>''')
    traffic, unexpected = routed_browser(monkeypatch, html, detail=detail,
        context_options={'service_workers': 'block'} if shop else None)
    workspace_id = pending['workspace_id']
    with client.websocket_connect('/ws/search') as ws:
        ws.send_json({'workspace_id': workspace_id, 'game': GAME, 'web_mode': 'any'})
        messages = _drain(ws)
    assert not [m for m in messages if m.get('type') == 'error'], (messages, traffic, unexpected)
    results = client.get('/api/workspaces/' + workspace_id).json()['results']
    assert [row['aztek_id'] for row in results] == (['91', '91'] if shop else ['91', '91', '99'])
    if shop:
        products = client.get(f'/api/workspaces/{workspace_id}/products').json()['products']
        assert [p['name_th'] for p in products] == ['First Pack', 'Later Pack']
        assert [p['bundle_ids'] for p in products] == [[], []]
        assert [p['start_at'] for p in products] == ['2026-10-17 00:00:00'] * 2
        assert [p['end_at'] for p in products] == ['2027-09-28 23:59:59'] * 2
    assert unexpected == []
    assert traffic and all(method == 'GET' for method, _url in traffic)
    return workspace_id


def _create_queue_and_check_consumers(client, payload, workspace_id=None, consumer_drafts=None, *, shop=False):
    """Real Bundle APIs/runner; only the legacy/Event Product drafts are fixtures."""
    responses, requests = [], []
    group_keys = ['first', 'later']
    if workspace_id:
        preview = client.post(f'/api/workspaces/{workspace_id}/bundles',
                              json={'selected_indexes': [0, 1]}).json()
        group_keys = [bundle['group_key'] for bundle in preview['bundles']]
        assert len(group_keys) == 2
    products = {'workspace_id': workspace_id or 'pipeline-workspace', 'game': GAME, 'products': [
        {'source_group_key': key, 'name_th': key, 'name_en': key,
         'bundle_ids': [], 'prices': [], 'price_candidates': []}
        for key in group_keys]}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(service_workers='block')
        context.route('**/*', lambda route: route.abort())
        _route_live_game_tools(context, workspace=None if shop else products)
        context.route('http://tool.test/products?*', lambda route: route.fulfill(
            content_type='text/html; charset=utf-8', body=PRODUCTS.read_text(encoding='utf-8')))

        def forward(route):
            request = route.request
            response = client.request(request.method, urlsplit(request.url).path,
                content=request.post_data_buffer,
                headers={'content-type': 'application/json'})
            if request.url.endswith('/run'):
                requests.append(request.post_data_json)
                responses.append(response.json())
            route.fulfill(status=response.status_code, json=response.json())

        context.route('http://tool.test/api/bundles/**', forward)
        if workspace_id:
            context.route(f'http://tool.test/api/workspaces/{workspace_id}', forward)
            context.route(f'http://tool.test/api/workspaces/{workspace_id}/bundles', forward)
            if shop:
                context.route(f'http://tool.test/api/workspaces/{workspace_id}/products', forward)
        page = context.new_page()
        page.goto('http://tool.test/bundles')
        page.wait_for_function("document.querySelectorAll('#game option').length === 3")
        # The legacy case seeds queue input; the pipeline case uses Finder UI.
        if workspace_id:
            page.evaluate("id => localStorage.setItem('afc.workspaceId', id)", workspace_id)
            page.goto('http://tool.test/')
            expect(page.locator('#resultsTable input.pick')).to_have_count(2 if shop else 3)
            page.locator('#resultsTable input.pick').nth(0).check()
            page.locator('#resultsTable input.pick').nth(1).check()
            page.locator('#btnBundleOpen').click()
            page.wait_for_url('http://tool.test/bundles')
        else:
            page.evaluate("""payload => sessionStorage.setItem('afc.bundleHandoff', JSON.stringify({
          game:payload.game, workspace_id:'pipeline-workspace', mode:'event',
          bundles:payload.bundles.map(b => ({...b, group:b.client_key, group_key:b.client_key})),
          event_drafts:[{name_th:'Plan Event',name_en:'Plan Event',rewards:[
            {group_key:'first',name_th:'First'},{group_key:'later',name_th:'Later'}]}]
            }))""", payload)
            page.reload()
        expect(page.locator('#queueCount')).to_have_text('2')
        if workspace_id:
            queue = page.evaluate("JSON.parse(localStorage.getItem('afc.bundleQueue'))")
            assert [[i['id'] for i in bundle['items']] for bundle in queue] == [['91'], ['91']]
            assert [bundle['items'][0]['qty'] for bundle in queue] == ['2', '3']
            assert [(bundle['document_reference']['items'][0]['filename'],
                     bundle['document_reference']['items'][0]['sheet'],
                     bundle['document_reference']['items'][0]['source_row'])
                    for bundle in queue] == [('plan.xlsx', 'First', 5 if shop else 4),
                                            ('plan.xlsx', 'Later', 5 if shop else 4)]
        page.on('dialog', lambda dialog: dialog.accept())
        page.click('#btnCreateAll')
        if workspace_id:
            # Excel omitted Tier: preserving unknown must pause, not fake a pass.
            expect(page.locator('#queueCount')).to_have_text('1', timeout=30000)
            expect(page.locator('#handoff')).to_be_hidden()
            expect(page.locator('#btnCreateAll')).to_be_disabled()
            page.locator('#btnContinueQueue').click()
            page.locator('#btnCreateAll').click()
        expect(page.locator('#queueCount')).to_have_text('0', timeout=30000)
        expected_outcome = 'partial' if workspace_id else 'passed'
        if workspace_id:
            page.reload()
            expect(page.locator('#queueCount')).to_have_text('0')
            expect(page.locator('#handoff')).to_be_hidden()
            for _ in range(2):
                detail = page.locator('#bundleResults details.submitted-reference').filter(
                    has=page.locator('button', has_text='ยืนยันส่งต่อ')).first
                detail.locator(':scope > summary').click()
                detail.get_by_role('button', name='ยืนยันส่งต่อ', exact=False).click()
        expect(page.locator('#handoff')).to_be_visible()
        assert len(responses) == (2 if workspace_id else 1)
        actual_results = [r for response in responses for r in response['results']]
        assert [r['bundle_id'] for r in actual_results] == ['42', '43']
        assert [r['recheck']['outcome'] for r in actual_results] == [expected_outcome] * 2
        targets = [
            ('/itemcodes', '#btnToItemCode', 'afc.itemcodeQueue'),
            ('/events', '#btnToEvent', 'afc.eventQueue'),
            ('/products', '#btnToProduct', 'afc.productQueue.v1'),
        ]
        for target, button, storage in (targets[-1:] if shop else targets):
            if target != '/itemcodes':
                page.goto('http://tool.test/bundles')
                expect(page.locator('#handoff')).to_be_visible()
            page.click(button)
            page.wait_for_url(lambda url: url.startswith('http://tool.test' + target))
            try:
                page.wait_for_function("""key => {
                  const rows=JSON.parse(localStorage.getItem(key)||'[]');
                  return rows.length && rows.every(row => key==='afc.productQueue.v1'
                    ? row.bundle_ids?.length : row.rewards?.every(r=>r.bundle_id));
                }""", arg=storage, timeout=10000)
            except Exception as exc:
                actual = page.evaluate("key => ({drafts:JSON.parse(localStorage.getItem(key)||'[]'),made:JSON.parse(localStorage.getItem('afc.bundleMade')||'[]')})", storage)
                raise AssertionError(f'{target} did not receive the Bundle IDs: {actual}') from exc
            drafts = page.evaluate("key => JSON.parse(localStorage.getItem(key))", storage)
            if consumer_drafts is not None:
                consumer_drafts[target] = drafts
            ids = [identity for draft in drafts for identity in (
                draft['bundle_ids'] if target == '/products'
                else [reward['bundle_id'] for reward in draft['rewards']])]
            assert ids == ['42', '43']
            expect(page.locator('#game')).to_have_value(GAME)
            if target == '/products':
                assert [draft['primary_bundle_id'] for draft in drafts] == ['42', '43']
                if shop:
                    assert [draft['name_th'] for draft in drafts] == ['First Pack', 'Later Pack']
                    assert [draft['source_sheet'] for draft in drafts] == ['First', 'Later']
                    assert [draft['start_at'] for draft in drafts] == ['2026-10-17 00:00:00'] * 2
                    assert [draft['end_at'] for draft in drafts] == ['2027-09-28 23:59:59'] * 2
            saved = page.evaluate("JSON.parse(localStorage.getItem('afc.bundleResults'))")
            assert [r['recheck']['outcome'] for r in saved] == [expected_outcome] * 2
            if workspace_id:
                assert [(r['document_reference']['items'][0]['filename'],
                         r['document_reference']['items'][0]['sheet'],
                         r['document_reference']['items'][0]['qty']) for r in saved] == [
                    ('plan.xlsx', 'First', '2'), ('plan.xlsx', 'Later', '3')]
            else:
                assert all(r['document_reference']['filename'] == 'source.xlsx' for r in saved)
        browser.close()
    return {'created': sum(r['created'] for r in responses), 'results': actual_results}, requests[0]


def _create_manually_checked_queue(client, payload):
    """Click the actual page; all Bundle requests reach the real API/runner."""
    requests, responses = [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(service_workers='block')
        context.route('**/*', lambda route: route.abort())
        _route_live_game_tools(context)
        page = context.new_page()

        def forward(route):
            request = route.request
            if request.method == 'POST':
                requests.append(request.post_data_json)
                # Re-entry while the request is outstanding must be disabled.
                for button in ('btnCreateAllChecked', 'btnCreateAll', 'btnCreateOne'):
                    assert page.locator('#' + button).is_disabled()
                    page.locator('#' + button).evaluate('(button) => button.click()')
            response = client.request(request.method, urlsplit(request.url).path,
                content=request.post_data_buffer,
                headers={'content-type': 'application/json'})
            if request.method == 'POST':
                responses.append(response.json())
            route.fulfill(status=response.status_code, json=response.json())

        context.route('http://tool.test/api/bundles/**', forward)
        page.goto('http://tool.test/bundles')
        page.wait_for_function("document.querySelectorAll('#game option').length === 3")
        queue = [dict(bundle, key=bundle['client_key'], type='FIXED', rewards=[])
                 for bundle in payload['bundles']]
        page.evaluate("rows => localStorage.setItem('afc.bundleQueue',JSON.stringify(rows))", queue)
        page.reload()
        checked = page.get_by_role('button', name='ตรวจเองครบแล้ว — สร้างทุกบันเดิลต่อเนื่อง', exact=False)
        expect(checked).to_be_visible(timeout=2000)
        dismiss = lambda dialog: dialog.dismiss()
        page.on('dialog', dismiss)
        checked.click()
        assert requests == []
        expect(page.locator('#queueCount')).to_have_text('2')
        page.remove_listener('dialog', dismiss)
        page.on('dialog', lambda dialog: dialog.accept())
        checked.click()
        expect(page.locator('#queueCount')).to_have_text('0', timeout=45000)
        expect(checked).to_be_disabled()
        expect(page.locator('#handoff')).to_be_hidden()
        page.reload()
        expect(page.locator('#queueCount')).to_have_text('0')
        expect(page.locator('#handoff')).to_be_hidden()
        rows = page.evaluate("JSON.parse(localStorage.getItem('afc.bundleResults'))")
        assert [row['recheck']['outcome'] for row in rows] == ['mismatch', 'mismatch']
        assert all(not row.get('handoff_override') for row in rows)
        assert len(requests) == 1
        assert requests[0]['manual_checked'] is True
        browser.close()
    return responses[0], requests[0]


@pytest.mark.parametrize('mode,created,outcome', [
    ('correct', 2, 'passed'), ('wrong', 1, 'mismatch'), ('no_id', 1, 'failed'),
    ('unreadable', 1, 'failed'),
    ('detail_missing', 1, 'failed'), ('detail_duplicate', 1, 'failed'),
    ('detail_wrong_type', 1, 'failed'),
    ('card_duplicate_qty', 1, 'failed'), ('card_duplicate_tier', 1, 'failed'),
    ('card_submit_expander', 1, 'failed'),
    ('imported_edited_qty', 1, 'mismatch'),
    ('finder_pipeline', 2, 'partial'),
    ('shop_pipeline', 2, 'partial'),
    ('dropped', 0, 'pending'),
    ('manual_wrong', 2, 'mismatch'),
    ('manual_ui_wrong', 2, 'mismatch'),
    ('manual_no_id', 1, 'failed'),
    ('manual_dropped', 0, 'pending'),
    ('manual_incomplete', 0, None),
    ('manual_save_failure', 0, 'pending'),
    ('manual_unreadable', 2, 'failed'),
])
def test_create_checkpoint_recheck_and_queue_gate(client, monkeypatch, mode, created, outcome):
    manual_checked = mode.startswith('manual_')
    mode = mode.removeprefix('manual_')
    manual_ui = mode.startswith('ui_')
    mode = mode.removeprefix('ui_')
    _connect_aztek(client)
    writes = []
    sent_quantities = []
    endpoint = 'https://admin-api-v2.combo-interactive.com/cabalm/warehouse/bundles'

    async def serve(route):
        url = route.request.url
        if route.request.method == 'POST':
            if url != endpoint:
                await route.abort()
                raise AssertionError('Unexpected external write: ' + url)
            writes.append(url)
            sent_quantities.append(route.request.post_data_json['qty'])
            if mode == 'dropped':
                await route.abort()
                return
            await route.fulfill(status=500 if mode == 'save_failure' else 200,
                                json={} if mode == 'no_id' else {'id': 41 + len(writes)},
                                headers={'access-control-allow-origin': '*'})
            return
        if url.endswith('/create'):
            body = '''<main><form onsubmit="event.preventDefault()"><input id="bundle-name">
            <div><label>ประเภท Bundle *</label><button type="button" role="combobox">FIXED</button>
            <select><option>FIXED</option></select></div>
            <button id="immediately-send" type="button" role="switch" aria-checked="true">ส่งทันที</button>
            <div role="tablist"><button type="button" role="tab" aria-selected="true">Item</button></div>
            <div role="tabpanel" data-state="active"><input placeholder="ค้นหาชื่อ Item...">
            <div><span>ID: 91</span><button type="button">เพิ่ม</button></div></div>
            <div><div><button type="button" aria-label="ย่อ" aria-expanded="true"><span>ITEM</span></button></div>
            <div><label>Item ID</label><p>91</p></div>
            <input name="items.0.quantity" type="number" value="1">
            <button type="button" role="combobox">Common</button><select><option>Common</option></select></div>
            <button type="submit" onclick="document.getElementById('confirm').hidden=false">สร้าง Bundle</button></form></main>
            <div id="confirm" role="alertdialog" data-state="open" hidden
            aria-labelledby="confirm-heading" aria-describedby="confirm-description">
            <h2 id="confirm-heading">ยืนยันการสร้าง</h2><p id="confirm-description">ต้องการสร้าง Bundle ใช่หรือไม่?</p>
            <button type="button" onclick="fetch('https://admin-api-v2.combo-interactive.com/cabalm/warehouse/bundles',{method:'POST',body:JSON.stringify({qty:document.getElementsByName('items.0.quantity')[0].value})});this.parentElement.hidden=true">ยืนยัน</button></div>'''
            if mode == 'incomplete':
                body = body.replace('<input id="bundle-name">', '<textarea id="bundle-name"></textarea>')
        elif url.endswith(('/bundles/42', '/bundles/43')):
            body = '''<main><h1>แก้ไข Bundle</h1><p>ID: 42</p><form><input id="bundle-name" value="Saved">
            <div><label>ประเภท Bundle *</label><button type="button" role="combobox">FIXED</button>
            <select><option selected>FIXED</option></select></div><div>รายการไอเท็ม ( 1 )</div>
            <button type="button">ขยายทั้งหมด</button><div><div><button type="button" aria-label="ย่อ" aria-expanded="true"><span>ITEM</span></button></div>
            <div><div><label>Item ID</label><p>91</p></div><input name="items.0.quantity" type="number" value="1">
            <div><label>Tier *</label><button type="button" role="combobox">Common</button>
            <select><option selected>Common</option></select></div></div></div></form></main>'''
            if mode == 'unreadable':
                body = body.replace('value="1"', 'value="unreadable"')
            elif mode == 'card_duplicate_qty':
                body = body.replace('<input name="items.0.quantity" type="number" value="1">',
                    '<input name="items.0.quantity" type="number" value="1">' * 2)
            elif mode == 'card_duplicate_tier':
                body = body.replace('<option selected>Common</option></select>',
                    '<option selected>Common</option></select><select><option>Legend</option></select>')
            elif mode == 'card_submit_expander':
                body = body.replace('type="button" aria-label=', 'type="submit" aria-label=')
            elif mode == 'imported_edited_qty':
                body = body.replace('value="1"', 'value="3"')
            elif mode in ('finder_pipeline', 'shop_pipeline'):
                body = body.replace('value="1"', 'value="2"' if url.endswith('/42') else 'value="3"')
            if url.endswith('/bundles/43'):
                body = body.replace('ID: 42', 'ID: 43')
        elif url.endswith('/items/91'):
            kind = '999' if mode == 'wrong' else '123'
            duration = '<input id="duration-index" value="9">'
            if mode == 'detail_missing':
                duration = '<input name="duration-index" value="9">'
            elif mode == 'detail_duplicate':
                duration += duration
            elif mode == 'detail_wrong_type':
                duration = '<textarea id="duration-index">9</textarea>'
            body = f'''<main><h1>แก้ไข Item</h1><p>ID: 91</p>
            <form><input id="item-name" value="Item"><input id="item-game-item-id" value="{kind}">
            <input id="item-option" value="0">{duration}</form></main>'''
        else:
            raise AssertionError('Unexpected external request: ' + url)
        await route.fulfill(content_type='text/html; charset=utf-8', body=body)

    async def start():
        driver = await async_playwright().start()

        async def launch(**_kwargs):
            browser = await driver.chromium.launch(headless=True)

            async def new_context(**kwargs):
                context = await browser.new_context(**{**kwargs, 'service_workers': 'block'})
                await context.route('**/*', serve)
                return context
            return SimpleNamespace(new_context=new_context, close=browser.close)
        return SimpleNamespace(chromium=SimpleNamespace(launch=launch), stop=driver.stop)

    monkeypatch.setattr(bundle_runner, 'async_playwright', lambda: SimpleNamespace(start=start))
    reference = {'game': GAME, 'filename': 'source.xlsx', 'items': [
        {'kind': '123', 'option': '0', 'duration': '9', 'qty': '1', 'tier': 'Common'}]}
    quantity = '1'
    if mode == 'imported_edited_qty':
        imported = client.post('/api/bundles/import', files={'file': (
            'original.xlsx', workbook_bytes([
                ('Original', [['Pack', '91', 2, 'Common', 'Item']], False)]))})
        assert imported.status_code == 200, imported.text
        reference = imported.json()['sheets'][0]['bundles'][0]['document_reference']
        reference['game'] = GAME
        # An operator edits Qty; the document remains the independent baseline.
        quantity = '3'
    payload = {'game': GAME, 'do_save': True, 'bundles': [
        {'client_key': key, 'name': key, 'items': [{'id': '91', 'qty': quantity}],
         'document_reference': reference} for key in ('first', 'later')]}
    if manual_checked:
        payload['manual_checked'] = True
    if manual_ui:
        result, payload = _create_manually_checked_queue(client, payload)
    elif mode in ('finder_pipeline', 'shop_pipeline'):
        shop = mode == 'shop_pipeline'
        workspace_id = _import_and_search_plan(client, monkeypatch, shop=shop)
        consumer_drafts = {}
        result, payload = _create_queue_and_check_consumers(
            client, payload, workspace_id, consumer_drafts, shop=shop)
    elif mode == 'correct':
        result, payload = _create_queue_and_check_consumers(client, payload)
    else:
        response = client.post('/api/bundles/run', json=payload)
        assert response.status_code == 200, response.text
        result = response.json()
    assert result['created'] == created, result
    assert result['results'][0].get('recheck', {}).get('outcome') == outcome, result
    assert result['results'][0]['saved'] is (mode not in ('dropped', 'incomplete', 'save_failure'))
    if manual_checked and created == 2:
        assert [row['bundle_id'] for row in result['results']] == ['42', '43']
        assert all(row['continued'] is True for row in result['results'])
        history = client.get('/api/bundles/rechecks').json()['rows']
        assert len(history) == 2
        assert all(row['result']['recheck']['outcome'] == outcome for row in history)
        assert all(row['history'][-1]['outcome'] == outcome for row in history)
    elif manual_checked:
        assert len(result['results']) == 1
        assert not result['results'][0].get('continued')
    if mode.startswith(('detail_', 'card_')):
        assert str(result['results'][0]['bundle_id']) == '42'
        assert result['results'][0]['recheck']['incomplete'] is True
        history = client.get('/api/bundles/rechecks').json()['rows']
        assert len(history) == 1
        assert str(history[0]['bundle_id']) == '42'
        assert history[0]['history'][0]['outcome'] == 'failed'
        assert history[0]['submitted_values']['document_reference'] == reference
    if mode == 'dropped':
        assert result['results'][0]['creation_uncertain'] is True
    assert len(writes) == (1 if mode in ('dropped', 'save_failure') else created)
    assert sent_quantities == (['2', '3'] if mode in ('finder_pipeline', 'shop_pipeline') else [quantity] * len(writes))
    if mode == 'imported_edited_qty':
        history = client.get('/api/bundles/rechecks').json()['rows']
        assert len(history) == 1
        job = history[0]
        assert job['submitted_values']['items'][0]['qty'] == '3'
        for snapshot in [job['submitted_values']['document_reference'],
                         job['history'][0]['document_reference']]:
            assert (snapshot['filename'], snapshot['sheet']) == ('original.xlsx', 'Original')
            assert (snapshot['items'][0]['source_row'], snapshot['items'][0]['qty']) == (2, '2')
        row = result['results'][0]['recheck']['rows'][0]
        assert (row['original']['qty'], row['submitted']['qty'], row['actual']['qty']) == ('2', '3', '3')
        assert 'qty' in row['different']
        retry = client.post(f"/api/bundles/rechecks/{job['id']}/retry", json={'bundle_id': '42'})
        assert retry.status_code == 200, retry.text
        assert retry.json()['recheck']['outcome'] == 'mismatch'
        reread = client.get('/api/bundles/rechecks').json()['rows'][0]
        assert len(reread['history']) == 2
        assert reread['history'][1]['document_reference'] == reference
        assert sent_quantities == ['3']  # Read-only retry sends no create request.
    # The checkpoint, not a fabricated fake-runner call, protects the replay.
    if mode == 'incomplete':
        assert client.get('/api/bundles/rechecks').json()['rows'] == []
    else:
        assert client.post('/api/bundles/run', json=payload).status_code == 409
    assert len(writes) == (1 if mode in ('dropped', 'save_failure') else created)
    if mode in ('finder_pipeline', 'shop_pipeline'):
        from consumer_create_pipeline_support import create_consumers_from_drafts, create_products_from_drafts
        before = {str(row['bundle_id']): row
                  for row in client.get('/api/bundles/rechecks').json()['rows']}
        assert set(before) == {'42', '43'}
        for row in before.values():
            assert row['result']['recheck']['outcome'] == row['history'][-1]['outcome'] == 'partial'
        if mode == 'shop_pipeline':
            assert set(consumer_drafts) == {'/products'}
            create_products_from_drafts(client, monkeypatch, consumer_drafts['/products'],
                                        preserve_source_fields=True)
        else:
            create_consumers_from_drafts(client, monkeypatch, consumer_drafts)
        assert len(writes) == 2  # Consumers use existing IDs; never rebuild Bundles.
        after = {str(row['bundle_id']): row
                 for row in client.get('/api/bundles/rechecks').json()['rows']}
        assert after == before  # Current result, full history and source provenance stay unchanged.
