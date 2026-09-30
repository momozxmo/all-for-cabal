"""Real API/runner, with all Aztek traffic fulfilled by synthetic pages."""
from types import SimpleNamespace

import pytest
from playwright.async_api import async_playwright

from web import bundle_runner
from test_web_validation import _connect_aztek, GAME


@pytest.mark.parametrize('mode,created,outcome', [
    ('correct', 2, 'passed'), ('wrong', 1, 'mismatch'), ('no_id', 1, 'failed'),
    ('unreadable', 1, 'failed'),
    ('dropped', 0, 'pending'),
])
def test_create_checkpoint_recheck_and_queue_gate(client, monkeypatch, mode, created, outcome):
    _connect_aztek(client)
    writes = []

    async def serve(route):
        url = route.request.url
        if route.request.method == 'POST':
            writes.append(url)
            if mode == 'dropped':
                await route.abort()
                return
            await route.fulfill(json={} if mode == 'no_id' else {'id': 42})
            return
        if url.endswith('/create'):
            body = '''<input id="bundle-name"><select><option>FIXED</option></select>
            <button role="switch" aria-checked="true">ส่งทันที</button>
            <input placeholder="ค้นหา Item"><div>ID: 91 <button>เพิ่ม</button></div>
            <div><input name="items.0.quantity" value="1"><select><option>Common</option></select></div>
            <button onclick="document.getElementById('confirm').hidden=false">สร้าง Bundle</button>
            <div id="confirm" role="dialog" hidden><button onclick="fetch('/api/bundles',{method:'POST'});this.parentElement.hidden=true">ยืนยัน</button></div>'''
        elif url.endswith('/bundles/42'):
            body = '''<h1>แก้ไข Bundle</h1><p>ID: 42</p><div>รายการไอเท็ม ( 1 )</div>
            <button>ขยายทั้งหมด</button><div><div><button aria-label="ย่อ" aria-expanded="true">ITEM</button></div>
            <div><div><label>Item ID</label><p>91</p></div><input name="items.0.quantity" value="1">
            <select><option selected>Common</option></select></div></div>'''
            if mode == 'unreadable':
                body = body.replace('value="1"', 'value="unreadable"')
        elif url.endswith('/items/91'):
            kind = '999' if mode == 'wrong' else '123'
            body = f'''<h1>แก้ไข Item</h1><p>ID: 91</p><input id="item-game-item-id" value="{kind}">
            <input id="item-option" value="0"><input id="duration-index" value="9">'''
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
    if mode == 'dropped':
        assert result['results'][0]['creation_uncertain'] is True
    assert len(writes) == (1 if mode == 'dropped' else created)
    # The checkpoint, not a fabricated fake-runner call, protects the replay.
    assert client.post('/api/bundles/run', json=payload).status_code == 409
    assert len(writes) == (1 if mode == 'dropped' else created)
