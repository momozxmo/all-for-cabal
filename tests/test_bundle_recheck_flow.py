"""Real API/runner, with all Aztek traffic fulfilled by synthetic pages."""
from types import SimpleNamespace

import pytest
from playwright.async_api import async_playwright

from web import bundle_runner
from test_web_validation import _connect_aztek, GAME


@pytest.mark.parametrize('mode,created,outcome', [
    ('correct', 2, 'passed'), ('wrong', 1, 'mismatch'), ('no_id', 1, 'failed'),
    ('unreadable', 1, 'failed'),
    ('detail_missing', 1, 'failed'), ('detail_duplicate', 1, 'failed'),
    ('detail_wrong_type', 1, 'failed'),
    ('card_duplicate_qty', 1, 'failed'), ('card_duplicate_tier', 1, 'failed'),
    ('card_submit_expander', 1, 'failed'),
    ('dropped', 0, 'pending'),
])
def test_create_checkpoint_recheck_and_queue_gate(client, monkeypatch, mode, created, outcome):
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
            await route.fulfill(json={} if mode == 'no_id' else {'id': 42},
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
        elif url.endswith('/bundles/42'):
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
                context = await browser.new_context(**kwargs)
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
    response = client.post('/api/bundles/run', json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['created'] == created, result
    assert result['results'][0]['recheck']['outcome'] == outcome, result
    assert result['results'][0]['saved'] is (mode != 'dropped')
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
    assert len(writes) == (1 if mode == 'dropped' else created)
    # The checkpoint, not a fabricated fake-runner call, protects the replay.
    assert client.post('/api/bundles/run', json=payload).status_code == 409
    assert len(writes) == (1 if mode == 'dropped' else created)
