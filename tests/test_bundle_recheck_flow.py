"""Real API/runner, with all Aztek traffic fulfilled by synthetic pages."""
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright, expect

from web import bundle_runner
from test_web_product_ui import _route_live_game_tools
from test_web_validation import _connect_aztek, GAME


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
    endpoint = 'https://admin-api-v2.combo-interactive.com/cabalm/warehouse/bundles'

    async def serve(route):
        url = route.request.url
        if route.request.method == 'POST':
            if url != endpoint:
                await route.abort()
                raise AssertionError('Unexpected external write: ' + url)
            writes.append(url)
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
            <button type="button" onclick="fetch('https://admin-api-v2.combo-interactive.com/cabalm/warehouse/bundles',{method:'POST'});this.parentElement.hidden=true">ยืนยัน</button></div>'''
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
    payload = {'game': GAME, 'do_save': True, 'bundles': [
        {'client_key': key, 'name': key, 'items': [{'id': '91', 'qty': '1'}],
         'document_reference': reference} for key in ('first', 'later')]}
    if manual_checked:
        payload['manual_checked'] = True
    if manual_ui:
        result, payload = _create_manually_checked_queue(client, payload)
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
    # The checkpoint, not a fabricated fake-runner call, protects the replay.
    if mode == 'incomplete':
        assert client.get('/api/bundles/rechecks').json()['rows'] == []
    else:
        assert client.post('/api/bundles/run', json=payload).status_code == 409
    assert len(writes) == (1 if mode in ('dropped', 'save_failure') else created)
