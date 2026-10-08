"""Real Bundle runner against isolated synthetic Aztek traffic, never live writes."""
import asyncio
import re
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from playwright.async_api import async_playwright

from web import bundle_runner
from web.aztek_locator import AztekLocatorError
from test_web_validation import _connect_aztek, GAME


HEADER = '''<select><option>Wrong</option></select>
<input name="name" value="outside"><button role="switch" aria-checked="false">Outside</button>
<main><form onsubmit="event.preventDefault();fetch('/combo/cabalpc/shop/bundles',
{method:'POST',body:JSON.stringify({name:document.getElementById('bundle-name').value})})">
<input id="bundle-name" name="name" value="before">
<div><label>ประเภท Bundle *</label><button type="button" role="combobox">FIXED</button>
<select><option>FIXED</option><option>RANDOM</option></select></div>
<button type="button" id="immediately-send" role="switch" aria-checked="true"
onclick="this.setAttribute('aria-checked',this.getAttribute('aria-checked')==='true'?'false':'true')">Changed label</button>
<button type="submit">สร้าง Bundle</button></form></main>'''


def routed_bundle(monkeypatch, html, *, write_status=201, write_body=None, drop_write=False,
                  pages=None, write_url=None, other_responses=None):
    writes, snapshots, unexpected = [], [], []

    async def serve(route):
        request = route.request
        path = urlsplit(request.url).path
        if request.method == 'GET' and path.endswith('/shop/bundles/create'):
            await route.fulfill(content_type='text/html; charset=utf-8', body=html)
        elif request.method == 'GET' and path in (pages or {}):
            await route.fulfill(content_type='text/html; charset=utf-8', body=pages[path])
        elif request.method == 'OPTIONS' and any(key[1] == request.url for key in (other_responses or {})):
            await route.fulfill(headers={'access-control-allow-origin': '*',
                                        'access-control-allow-methods': 'GET, POST, PUT, PATCH'})
        elif ((request.method, request.url, request.frame.url) in (other_responses or {})
              or (request.method, request.url) in (other_responses or {})):
            key = (request.method, request.url, request.frame.url)
            if key not in other_responses:
                key = (request.method, request.url)
            status, body = other_responses[key]
            await route.fulfill(status=status, json=body,
                                headers={'access-control-allow-origin': '*'})
        elif request.method == 'POST' and (request.url == write_url if write_url
                                          else path.endswith('/shop/bundles')):
            writes.append(request.post_data_json)
            if drop_write:
                await route.abort()
            else:
                await route.fulfill(status=write_status, json={'id': 777} if write_body is None else write_body,
                                    headers={'access-control-allow-origin': '*'})
        else:
            unexpected.append((request.method, path))
            await route.abort()

    class RoutedPlaywright:
        async def __aenter__(self):
            self.driver = await self.start()
            return self.driver

        async def __aexit__(self, *args):
            await self.driver.stop()

        async def start(self):
            driver = await async_playwright().start()

            async def launch(**kwargs):
                kwargs['headless'] = True
                browser = await driver.chromium.launch(**kwargs)

                async def new_context(**kwargs):
                    context = await browser.new_context(**kwargs)
                    context.set_default_timeout(1000)
                    await context.route('**/*', serve)

                    async def close():
                        for page in context.pages:
                            snapshots.append(await page.evaluate('''() => [...document.querySelectorAll('input,select,button[role="switch"]')].map(e=>({id:e.id,name:e.name,value:e.value,checked:e.getAttribute('aria-checked'),isChecked:e.checked}))'''))
                        await context.close()

                    return SimpleNamespace(new_page=context.new_page, close=close)

                return SimpleNamespace(new_context=new_context, close=browser.close)

            return SimpleNamespace(chromium=SimpleNamespace(launch=launch), stop=driver.stop)

    monkeypatch.setattr(bundle_runner, 'async_playwright', RoutedPlaywright)
    return writes, snapshots, unexpected


def run_bundle(*, save=False, items=(), deliver=False, rewards=(), btype='RANDOM', game='CabalPC TH'):
    logs = []
    builder = bundle_runner.BundleBuilder(lambda message, level: logs.append((message, level)))
    result = asyncio.run(builder.run(game, 'Pack', btype, deliver, items,
                                    {'cookies': [], 'origins': []}, do_save=save, rewards=rewards))
    return result, logs


@pytest.mark.parametrize('method,decoy', [
    ('POST', 'https://admin-api-v2.combo-interactive.com/cabalm/warehouse/bundles/999/draft'),
    ('POST', 'https://aztek-tools-v2.combo-interactive.com/combo/cabalm/shop/bundles'),
    ('POST', 'https://other.example/cabalm/warehouse/bundles'),
    ('POST', 'https://admin-api-v2.combo-interactive.com/cabalpc/warehouse/bundles'),
    ('PUT', 'https://admin-api-v2.combo-interactive.com/cabalm/warehouse/bundles'),
    ('PATCH', 'https://admin-api-v2.combo-interactive.com/cabalm/warehouse/bundles'),
    ('GET', 'https://admin-api-v2.combo-interactive.com/cabalm/warehouse/bundles'),
])
def test_cabalm_create_does_not_adopt_an_unrelated_bundle_write(monkeypatch, method, decoy):
    # Actual M TH create endpoint observed from the one approved live probe.
    endpoint = 'https://admin-api-v2.combo-interactive.com/cabalm/warehouse/bundles'
    options = "method:'%s'" % method + (",body:'{}'" if method != 'GET' else '')
    script = ("event.preventDefault();fetch('%s',{%s})"
              ".then(()=>fetch('%s',{method:'POST',body:JSON.stringify("
              "{name:document.getElementById('bundle-name').value})}))") % (decoy, options, endpoint)
    html = re.sub(r'onsubmit="[^"]*"', lambda _: 'onsubmit="' + script + '"', HEADER, count=1)
    writes, _, unexpected = routed_bundle(monkeypatch, html, write_url=endpoint,
                                          other_responses={(method, decoy): (200, {'id': 999})})
    result, _ = run_bundle(save=True, game='CabalM TH')
    assert (result['saved'], result['bundle_id']) == (True, '777')
    assert writes == [{'name': 'Pack'}] and unexpected == []


@pytest.mark.parametrize('status,body,saved,bundle_id', [
    (200, {'id': 225954}, True, '225954'),
    (200, {}, True, None),
    (500, {'id': 999}, False, None),
])
def test_cabalm_create_keeps_only_its_verified_operation_result(monkeypatch, status, body, saved, bundle_id):
    endpoint = 'https://admin-api-v2.combo-interactive.com/cabalm/warehouse/bundles'
    html = HEADER.replace('/combo/cabalpc/shop/bundles', endpoint)
    writes, _, unexpected = routed_bundle(monkeypatch, html, write_url=endpoint,
                                          write_status=status, write_body=body)
    result, _ = run_bundle(save=True, game='CabalM TH')
    assert (result['saved'], result['bundle_id']) == (saved, bundle_id)
    assert writes == [{'name': 'Pack'}] and unexpected == []


def test_cabalm_missing_create_response_keeps_the_checkpoint_and_blocks_replay(client, monkeypatch):
    _connect_aztek(client)
    endpoint = 'https://admin-api-v2.combo-interactive.com/cabalm/warehouse/bundles'
    decoy = 'https://admin-api-v2.combo-interactive.com/cabalm/warehouse/bundles/999/draft'
    script = ("event.preventDefault();fetch('%s',{method:'POST',body:'{}'})"
              ".then(()=>fetch('%s',{method:'POST',body:JSON.stringify("
              "{name:document.getElementById('bundle-name').value})}))") % (decoy, endpoint)
    html = re.sub(r'onsubmit="[^"]*"', lambda _: 'onsubmit="' + script + '"', item_form(), count=1)
    writes, _, unexpected = routed_bundle(monkeypatch, html, write_url=endpoint, drop_write=True,
                                          other_responses={('POST', decoy): (200, {'id': 999})})
    payload = {'game': 'CabalM TH', 'do_save': True, 'bundles': [{
        'client_key': 'cabalm-missing-write', 'name': 'Pack',
        'items': [{'id': '91', 'qty': '1'}],
    }]}
    response = client.post('/api/bundles/run', json=payload)
    assert response.status_code == 200, response.text
    result = response.json()['results'][0]
    assert not result['saved'] and result['bundle_id'] is None
    assert result['creation_uncertain'] and result['recheck']['outcome'] == 'pending'
    assert client.post('/api/bundles/run', json=payload).status_code == 409
    assert writes == [{'name': 'Pack'}] and unexpected == []


def test_cabalm_create_ignores_another_frames_response_from_the_same_endpoint(monkeypatch):
    endpoint = 'https://admin-api-v2.combo-interactive.com/cabalm/warehouse/bundles'
    html = re.sub(r'onsubmit="[^"]*"', 'onsubmit="event.preventDefault()"', HEADER, count=1)
    html += '''<script>
document.querySelector('main form').addEventListener('submit', () => {
  window.addEventListener('message', event => {
    if(event.data === 'decoy-finished') fetch('%s', {method:'POST',
      body:JSON.stringify({name:document.getElementById('bundle-name').value})});
  }, {once:true});
  const frame=document.createElement('iframe');
  frame.srcdoc=`<script>fetch('%s',{method:'POST',body:'{}'})
    .then(()=>parent.postMessage('decoy-finished','*'))<\\/script>`;
  document.body.append(frame);
});
</script>''' % (endpoint, endpoint)
    writes, _, unexpected = routed_bundle(monkeypatch, html, write_url=endpoint,
        other_responses={('POST', endpoint, 'about:srcdoc'): (200, {'id': 999})})
    result, _ = run_bundle(save=True, game='CabalM TH')
    assert (result['saved'], result['bundle_id']) == (True, '777')
    assert writes == [{'name': 'Pack'}] and unexpected == []


def test_create_ignores_a_matching_action_outside_the_bundle_form(monkeypatch):
    html = '<button onclick="fetch(\'/wrong-bundle\',{method:\'POST\'})">สร้าง Bundle</button>' + HEADER
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(save=True)
    assert result['saved'] and result['bundle_id'] == '777'
    assert writes == [{'name': 'Pack'}] and unexpected == []


@pytest.mark.parametrize('mutation', ['duplicate', 'missing', 'wrong-type', 'wrong-role', 'hidden-duplicate'])
def test_broken_create_action_does_not_reserve_an_uncertain_creation(client, monkeypatch, mutation):
    _connect_aztek(client)
    html = item_form()
    if mutation in ('duplicate', 'hidden-duplicate'):
        hidden = ' hidden' if mutation == 'hidden-duplicate' else ''
        html = html.replace('</form>', '<button type="submit"%s>สร้าง Bundle</button></form>' % hidden)
    elif mutation == 'missing':
        html = html.replace('<button type="submit">สร้าง Bundle</button>', '')
    elif mutation == 'wrong-type':
        html = html.replace('<button type="submit">สร้าง Bundle</button>', '<button type="button">สร้าง Bundle</button>')
    else:
        html = html.replace('<button type="submit">สร้าง Bundle</button>', '<button type="submit" role="switch">สร้าง Bundle</button>')
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    payload = {'game': GAME, 'do_save': True, 'bundles': [
        {'client_key': 'bad-create', 'name': 'Pack', 'items': [{'id': '91'}]}]}
    response = client.post('/api/bundles/run', json=payload)
    assert response.status_code == 200
    result = response.json()['results'][0]
    assert not result['saved'] and result['fields_complete'] is False
    assert not result.get('creation_uncertain')
    assert client.post('/api/bundles/run', json=payload).status_code == 200
    assert writes == [] and unexpected == []


@pytest.mark.parametrize('status,body,saved,bundle_id', [
    (201, {'data': {'bundleId': 90210}}, True, '90210'),
    (200, {}, True, None),
    (500, {'id': 13}, False, None),
])
def test_create_reports_only_the_verified_write_result(monkeypatch, status, body, saved, bundle_id):
    writes, _, unexpected = routed_bundle(monkeypatch, HEADER, write_status=status, write_body=body)
    result, _ = run_bundle(save=True)
    assert (result['saved'], result['bundle_id']) == (saved, bundle_id)
    assert writes == [{'name': 'Pack'}] and unexpected == []


def test_create_preserves_the_existing_confirmation_flow(monkeypatch):
    writes, _, unexpected = routed_bundle(monkeypatch, confirmation_form())
    result, logs = run_bundle(save=True)
    assert result['saved'] and result['bundle_id'] == '777'
    assert any('ยืนยัน' in message for message, _ in logs)
    assert writes == [{'name': 'Pack'}] and unexpected == []


def confirmation_form(base=HEADER):
    # M TH live evidence: no developer IDs; Radix IDs are live ARIA relations.
    html = base.replace("onsubmit=\"event.preventDefault();fetch('/combo/cabalpc/shop/bundles',\n{method:'POST',body:JSON.stringify({name:document.getElementById('bundle-name').value})})\"",
        'onsubmit="event.preventDefault();document.getElementById(\'confirmation\').hidden=false"')
    return html + '''<div id="confirmation" role="alertdialog" data-state="open" hidden
aria-labelledby="runtime-heading" aria-describedby="runtime-description">
<h2 id="runtime-heading">ยืนยันการสร้าง</h2><p id="runtime-description">ต้องการสร้าง Bundle ใช่หรือไม่?</p>
<button type="button">ยกเลิก</button><button type="button"
onclick="fetch('/combo/cabalpc/shop/bundles',{method:'POST',body:JSON.stringify({name:document.getElementById('bundle-name').value})});this.parentElement.hidden=true">ยืนยัน</button></div>'''


def test_confirmation_ignores_a_matching_action_outside_the_bundle_dialog(monkeypatch):
    decoy = '<button type="button" onclick="fetch(\'/wrong-bundle\',{method:\'POST\'})">ยืนยัน</button>'
    writes, _, unexpected = routed_bundle(monkeypatch, decoy + confirmation_form())
    result, _ = run_bundle(save=True)
    assert result['saved'] and result['bundle_id'] == '777'
    assert writes == [{'name': 'Pack'}] and unexpected == []


def test_confirmation_stops_if_the_game_page_changes_after_create(client, monkeypatch):
    _connect_aztek(client)
    html = confirmation_form(item_form()).replace(
        "document.getElementById('confirmation').hidden=false",
        "document.getElementById('confirmation').hidden=false;history.pushState({},'', '/combo/cabalpc/shop/bundles/create')")
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    payload = {'game': GAME, 'do_save': True, 'bundles': [
        {'client_key': 'changed-page', 'name': 'Pack', 'items': [{'id': '91'}]}]}
    result = client.post('/api/bundles/run', json=payload).json()['results'][0]
    assert not result['saved'] and result['creation_uncertain'] is True
    assert client.post('/api/bundles/run', json=payload).status_code == 409
    assert writes == [] and unexpected == []


@pytest.mark.parametrize('mutation', ['duplicate-action', 'hidden-action', 'duplicate-dialog',
    'wrong-type', 'wrong-role', 'missing-aria', 'duplicate-aria', 'outside-aria',
    'other-record', 'nested-dialog', 'form-owner', 'dialog-role', 'dialog-tag'])
def test_ambiguous_confirmation_keeps_the_checkpoint_without_a_write(client, monkeypatch, mutation):
    _connect_aztek(client)
    html = confirmation_form(item_form())
    if mutation in ('duplicate-action', 'hidden-action'):
        hidden = ' hidden' if mutation == 'hidden-action' else ''
        html = html.replace('</div>', '<button type="button"%s>ยืนยัน</button></div>' % hidden)
    elif mutation == 'duplicate-dialog':
        html += html[html.index('<div id="confirmation"'):].replace(' hidden', '')
    elif mutation == 'wrong-type':
        html = html.replace('<button type="button"\nonclick="fetch', '<button type="submit"\nonclick="fetch')
    elif mutation == 'wrong-role':
        html = html.replace('<button type="button"\nonclick="fetch', '<button type="button" role="switch"\nonclick="fetch')
    elif mutation == 'missing-aria':
        html = html.replace('aria-describedby="runtime-description"', '')
    elif mutation == 'duplicate-aria':
        html += '<p id="runtime-description">ต้องการสร้าง Bundle ใช่หรือไม่?</p>'
    elif mutation == 'outside-aria':
        html = html.replace('aria-describedby="runtime-description"', 'aria-describedby="outside-description"')
        html += '<p id="outside-description">ต้องการสร้าง Bundle ใช่หรือไม่?</p>'
    elif mutation == 'other-record':
        html = html.replace('ต้องการสร้าง Bundle ใช่หรือไม่?', 'ต้องการสร้าง Product ใช่หรือไม่?')
    elif mutation == 'nested-dialog':
        html = html.replace('<h2 id="runtime-heading">', '<div role="dialog"></div><h2 id="runtime-heading">')
    elif mutation == 'dialog-role':
        html = html.replace('role="alertdialog"', 'role="region"')
    elif mutation == 'dialog-tag':
        html = html.replace('<div id="confirmation"', '<section id="confirmation"')
    else:
        html = html.replace('<button type="button"\nonclick="fetch', '<button type="button" form="other"\nonclick="fetch')
        html += '<form id="other"></form>'
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    payload = {'game': GAME, 'do_save': True, 'bundles': [
        {'client_key': 'bad-confirm', 'name': 'Pack', 'items': [{'id': '91'}]}]}
    response = client.post('/api/bundles/run', json=payload)
    assert response.status_code == 200
    result = response.json()['results'][0]
    assert not result['saved'] and result['creation_uncertain'] is True
    assert 'Bundle' in result['error'] and result['recheck']['outcome'] == 'pending'
    assert client.post('/api/bundles/run', json=payload).status_code == 409
    assert writes == [] and unexpected == []


def test_confirmation_ignores_an_unrelated_active_dialog(monkeypatch):
    other = '''<div role="alertdialog" data-state="open"><h2>ยืนยันการสร้าง</h2>
<p>ต้องการสร้าง Product ใช่หรือไม่?</p><button type="button"
onclick="fetch('/wrong-bundle',{method:'POST'})">ยืนยัน</button></div>'''
    writes, _, unexpected = routed_bundle(monkeypatch, other + confirmation_form())
    result, _ = run_bundle(save=True)
    assert result['saved'] and result['bundle_id'] == '777'
    assert writes == [{'name': 'Pack'}] and unexpected == []


def test_confirmation_waits_for_a_late_mounted_dialog(monkeypatch):
    html = confirmation_form().replace("document.getElementById('confirmation').hidden=false",
        "setTimeout(()=>document.getElementById('confirmation').hidden=false,4000)")
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(save=True)
    assert result['saved'] and result['bundle_id'] == '777'
    assert writes == [{'name': 'Pack'}] and unexpected == []


@pytest.mark.parametrize('mutation', ['type', 'role', 'aria', 'duplicate-action', 'duplicate-dialog', 'page'])
def test_confirmation_revalidates_after_waiting_for_enable(monkeypatch, mutation):
    html = confirmation_form().replace('<button type="button"\nonclick="fetch',
                                       '<button type="button" disabled\nonclick="fetch')
    change = {'type': "b.type='submit'", 'role': "b.setAttribute('role','switch')",
        'aria': "d.setAttribute('aria-describedby','missing')",
        'duplicate-action': 'b.after(b.cloneNode(true))',
        'duplicate-dialog': 'd.after(d.cloneNode(true))',
        'page': "history.pushState({},'', '/combo/cabalm/shop/bundles/create')"}[mutation]
    html = html.replace("document.getElementById('confirmation').hidden=false",
        "document.getElementById('confirmation').hidden=false;setTimeout(()=>{const d=document.getElementById('confirmation');const b=d.querySelector('button[disabled]');%s;b.disabled=false},700)" % change)
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    with pytest.raises(AztekLocatorError, match='Bundle'):
        run_bundle(save=True)
    assert writes == [] and unexpected == []


def test_a_verified_direct_write_survives_an_invalid_confirmation(monkeypatch):
    # The write races with an invalid dialog: preserve its proof, never confirm.
    popup = confirmation_form()[confirmation_form().index('<div id="confirmation"'):]
    popup = popup.replace(' hidden', '').replace('aria-describedby="runtime-description"', '')
    html = HEADER.replace("event.preventDefault();fetch", "event.preventDefault();setTimeout(()=>fetch").replace(
        "{method:'POST',body:JSON.stringify({name:document.getElementById('bundle-name').value})})\"",
        "{method:'POST',body:JSON.stringify({name:document.getElementById('bundle-name').value})}),400)\"") + popup
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(save=True)
    assert result['saved'] and result['bundle_id'] == '777'
    assert writes == [{'name': 'Pack'}] and unexpected == []


@pytest.mark.parametrize('redirect,saved,bundle_id', [
    ('/combo/cabalpc/shop/bundles/4242', True, '4242'),
    ('/combo/cabalm/shop/bundles/4242', False, None),
])
def test_lost_response_retains_only_the_original_games_redirect_id(monkeypatch, redirect, saved, bundle_id):
    html = HEADER.replace("{method:'POST',body:JSON.stringify({name:document.getElementById('bundle-name').value})})",
        "{method:'POST',body:JSON.stringify({name:document.getElementById('bundle-name').value})}).catch(()=>history.pushState({},'', %r))" % redirect)
    writes, _, unexpected = routed_bundle(monkeypatch, html, drop_write=True)
    if saved:
        result, _ = run_bundle(save=True)
        assert (result['saved'], result['bundle_id']) == (saved, bundle_id)
    else:
        with pytest.raises(AztekLocatorError, match='Bundle'):
            run_bundle(save=True)
    assert writes == [{'name': 'Pack'}] and unexpected == []


def test_disabled_create_action_keeps_the_draft_retryable(client, monkeypatch):
    _connect_aztek(client)
    html = item_form().replace('<button type="submit">สร้าง Bundle</button>', '<button type="submit" disabled>สร้าง Bundle</button>')
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    response = client.post('/api/bundles/run', json={'game':GAME,'do_save':True,'bundles':[
        {'client_key':'disabled-create','name':'Pack','items':[{'id':'91'}]}]})
    assert response.status_code == 200
    result = response.json()['results'][0]
    assert not result.get('creation_uncertain') and result['fields_complete'] is False
    assert writes == [] and unexpected == []


def test_create_rejects_a_button_owned_by_another_form(monkeypatch):
    html = '<form id="other" onsubmit="event.preventDefault();fetch(\'/wrong-bundle\',{method:\'POST\'})"></form>' + HEADER.replace(
        '<button type="submit">สร้าง Bundle</button>', '<button type="submit" form="other">สร้าง Bundle</button>')
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    with pytest.raises(AztekLocatorError, match='สร้าง Bundle'):
        run_bundle(save=True)
    assert writes == [] and unexpected == []


@pytest.mark.parametrize('status,saved,bundle_id', [(200,True,'4242'),(500,False,None)])
def test_create_redirect_does_not_override_a_rejected_write(monkeypatch, status, saved, bundle_id):
    html = HEADER.replace("{method:'POST',body:JSON.stringify({name:document.getElementById('bundle-name').value})})",
        "{method:'POST',body:JSON.stringify({name:document.getElementById('bundle-name').value})}).then(()=>history.pushState({},'', '/combo/cabalpc/shop/bundles/4242'))")
    writes, _, unexpected = routed_bundle(monkeypatch, html, write_status=status, write_body={})
    result, _ = run_bundle(save=True)
    assert (result['saved'],result['bundle_id']) == (saved,bundle_id)
    assert writes == [{'name':'Pack'}] and unexpected == []


def test_a_missing_write_response_is_not_reported_as_created(monkeypatch):
    writes, _, unexpected = routed_bundle(monkeypatch, HEADER, drop_write=True)
    result, _ = run_bundle(save=True)
    assert (result['saved'],result['bundle_id']) == (False,None)
    assert writes == [{'name':'Pack'}] and unexpected == []


def test_create_waits_for_a_late_enabled_submit_action(monkeypatch):
    html = HEADER.replace('<button type="submit">สร้าง Bundle</button>', '<button type="submit" disabled>สร้าง Bundle</button>')
    html += '<script>setTimeout(()=>document.querySelector(\'main button[type="submit"]\').disabled=false,6500)</script>'
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(save=True)
    assert result['saved'] and result['bundle_id'] == '777'
    assert writes == [{'name':'Pack'}] and unexpected == []


@pytest.mark.parametrize('mutation', ['type','role','owner','duplicate','duplicate-form'])
def test_create_revalidates_the_action_after_waiting_for_readiness(monkeypatch, mutation):
    html = HEADER.replace('<button type="submit">สร้าง Bundle</button>', '<button type="submit" disabled>สร้าง Bundle</button>')
    change = {'type':"b.type='button'", 'role':"b.setAttribute('role','switch')",
        'owner':"document.body.insertAdjacentHTML('beforeend','<form id=other></form>');b.setAttribute('form','other')",
        'duplicate':"b.after(b.cloneNode(true))",
        'duplicate-form':"document.querySelector('main').insertAdjacentHTML('beforeend','<form></form>')"}[mutation]
    html += '<script>setTimeout(()=>{const b=document.querySelector(\'main button[type="submit"]\');%s;b.disabled=false},6500)</script>' % change
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    with pytest.raises(AztekLocatorError, match='สร้าง Bundle|Bundle form'):
        run_bundle(save=True)
    assert writes == [] and unexpected == []


def reward_form():
    # Mirror the observed Radix dialog/search/listbox relation, not stable IDs.
    panel = '''<div role="tablist"><button id="radix-credit-tab" aria-controls="radix-credit-panel" type="button" role="tab" aria-selected="false"
onclick="this.setAttribute('aria-selected','true')">Credit</button></div>
<div id="radix-credit-panel" role="tabpanel" data-state="active" aria-labelledby="radix-credit-tab"><button type="button" role="combobox"
aria-expanded="false" onclick="openReward(this)">เลือก Currency</button>
<input type="number" placeholder="Qty" value="1">
<button type="button" onclick="addReward(this)">เพิ่ม</button></div>
<div id="cards"></div><input id="added-name"><input id="added-qty">'''
    outside = '''<input id="wrong" value="untouched"><div data-radix-popper-content-wrapper>
<input value="outside"><div role="option" onclick="document.getElementById('wrong').value='clicked'">cabalm-alz - Alz</div></div>'''
    script = '''<script>
let rewardPicker;
function openReward(button){
rewardPicker=button;button.setAttribute('aria-expanded','true');button.setAttribute('aria-controls','radix-dialog-live');
const portal=document.createElement('div');portal.setAttribute('data-radix-popper-content-wrapper','');
portal.innerHTML=`<div id="radix-dialog-live" role="dialog"><input role="combobox" type="text" aria-controls="radix-list-live">
<div role="listbox" id="radix-list-live"><div role="option" onclick="chooseReward(this)">cabalm-alz - Alz</div></div></div>`;
document.body.append(portal);
}
function chooseReward(option){rewardPicker.textContent=option.textContent;
rewardPicker.setAttribute('aria-expanded','false');option.closest('[data-radix-popper-content-wrapper]').remove();}
function addReward(button){
const panel=button.parentElement;
document.getElementById('added-name').value=panel.querySelector('button[role="combobox"]').textContent;
document.getElementById('added-qty').value=panel.querySelector('input').value;
document.getElementById('cards').innerHTML=`<div><div>
<button type="button" aria-label="ย่อ" aria-expanded="true"><p>Alz</p><span>WALLET_CREDIT</span></button></div>
<div><label>ชื่อ</label><p>Alz</p></div>
<input type="number" name="items.0.quantity" value="7"><button type="button" role="combobox">Tier</button>
<select><option value=""></option><option value="0">Common</option></select></div>`;
}
</script>'''
    return outside + HEADER.replace('</form>', panel + '</form>') + script


def reward_card_form():
    html = reward_form().replace('name="items.0.quantity" value="7"',
                                 'name="items.4.quantity" value="99"')
    html = html.replace('<option value="0">Common</option></select>',
                        '<option value="0">Common</option><option value="1">Rare</option></select>'
                        '<input type="number" id="items.4.secret_chance" name="items.4.secret_chance" value="55">'
                        '<input type="number" id="items.4.chance" name="items.4.chance" value="66">')
    html = html.replace('<select><option value="">', '<select name="reward-tier"><option value="">')
    # A separate form's old row zero must never be used for this reward.
    decoy = '''<form><div><input type="number" name="items.0.quantity" value="41">
<select name="outside-tier"><option value="">Choose</option><option value="0">Common</option><option value="1">Rare</option></select>
<input type="number" id="items.0.secret_chance" name="items.0.secret_chance" value="42"></div></form>'''
    return decoy + html


def test_currency_card_fields_follow_identity_and_current_index_not_row_zero(monkeypatch):
    # Catches positional reward writes and confusing actual with display rate.
    writes, snapshots, unexpected = routed_bundle(monkeypatch, reward_card_form())
    result, _ = run_bundle(rewards=[{'type':'CREDIT','value':'cabalm-alz - Alz',
                                     'qty':'7','tier':'Rare','rate':0}])
    assert result['fields_complete'] is True and result['rewards_added'] == 1
    fields = snapshots[0]
    assert next(e for e in fields if e['name']=='items.4.quantity')['value'] == '7'
    assert next(e for e in fields if e['name']=='items.0.quantity')['value'] == '41'
    assert next(e for e in fields if e['name']=='outside-tier')['value'] == ''
    assert next(e for e in fields if e['id']=='items.4.secret_chance')['value'] == '0'
    assert next(e for e in fields if e['id']=='items.4.chance')['value'] == '66'
    assert next(e for e in fields if e['id']=='items.0.secret_chance')['value'] == '42'
    assert next(e for e in fields if e['name']=='reward-tier')['value'] == '1'
    assert writes == unexpected == []


def test_currency_card_with_numeric_zero_rate_and_no_explicit_tier_gets_its_fields(monkeypatch):
    writes, snapshots, unexpected = routed_bundle(monkeypatch, reward_card_form())
    result, _ = run_bundle(rewards=[{'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7','rate':0}])
    assert result['fields_complete'] is True
    fields = snapshots[0]
    assert next(e for e in fields if e['name']=='items.4.quantity')['value'] == '7'
    assert next(e for e in fields if e['id']=='items.4.secret_chance')['value'] == '0'
    assert next(e for e in fields if e['name']=='reward-tier')['value'] == '0'
    assert next(e for e in fields if e['name']=='outside-tier')['value'] == ''
    assert writes == unexpected == []


def test_default_tier_never_changes_an_unrequested_card_in_the_same_form(monkeypatch):
    unrelated = '''<div><div><button type="button" aria-label="ย่อ" aria-expanded="true"><p>Other Item</p><span>ITEM</span></button></div>
<label>Item ID</label><p>777</p><input type="number" name="items.99.quantity" value="8">
<button type="button" role="combobox">Tier</button><select name="unrequested-tier"><option value="">Choose</option><option value="0">Common</option></select></div>'''
    html = reward_form().replace('<div id="cards"></div>', unrelated + '<div id="cards"></div>')
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(btype='FIXED', rewards=[{'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7'}])
    assert result['fields_complete'] is True
    assert next(e for e in snapshots[0] if e['name']=='unrequested-tier')['value'] == ''
    assert writes == unexpected == []


def test_reward_names_with_thai_and_quotes_select_and_map_exactly(monkeypatch):
    value = 'cabalm-special - เงินพิเศษ "A"'
    html = reward_form().replace('cabalm-alz - Alz', value).replace('>Alz<','>เงินพิเศษ "A"<')
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(btype='FIXED', rewards=[{'type':'CREDIT','value':value,'qty':'9'}])
    assert result['fields_complete'] is True
    assert next(e for e in snapshots[0] if e['name']=='items.0.quantity')['value'] == '9'
    assert next(e for e in snapshots[0] if e['id']=='added-name')['value'] == value
    assert writes == unexpected == []


def test_reward_default_common_preserves_a_tier_already_chosen_on_aztek(monkeypatch):
    html = reward_card_form().replace('<option value="1">Rare</option>', '<option selected value="1">Rare</option>')
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(btype='FIXED', rewards=[{'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7'}])
    assert result['fields_complete'] is True
    assert next(e for e in snapshots[0] if e['name']=='reward-tier')['value'] == '1'
    assert writes == unexpected == []


def test_reward_tier_preservation_does_not_require_an_unrequested_common_option(monkeypatch):
    html = reward_card_form().replace('<option value="0">Common</option>', '')
    html = html.replace('<option value="1">Rare</option>', '<option selected value="1">Rare</option>')
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(btype='FIXED', rewards=[{'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7'}])
    assert result['fields_complete'] is True
    assert next(e for e in snapshots[0] if e['name']=='reward-tier')['value'] == '1'
    assert writes == unexpected == []


def test_repeated_reward_requests_that_merge_into_one_card_stop_before_save(monkeypatch):
    writes, snapshots, unexpected = routed_bundle(monkeypatch, reward_card_form())
    with pytest.raises(AztekLocatorError, match='reward.*ซ้ำ'):
        run_bundle(save=True, rewards=[
            {'type':'CREDIT','value':'cabalm-alz - Alz','qty':'4','tier':'Rare','rate':'50'},
            {'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7','tier':'Common','rate':'50'},
        ])
    assert [e['value'] for e in snapshots[0] if e['name']=='items.4.quantity'] == ['99']
    assert writes == unexpected == []


def test_currency_add_uses_only_the_open_picker_not_an_outside_matching_option(monkeypatch):
    writes, snapshots, unexpected = routed_bundle(monkeypatch, reward_form())
    result, _ = run_bundle(btype='FIXED', rewards=[{'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7'}])
    assert result['rewards_added'] == 1 and result['fields_complete'] is True
    fields = {e['id']:e['value'] for e in snapshots[0] if e['id']}
    assert fields['wrong'] == 'untouched'
    assert (fields['added-name'], fields['added-qty']) == ('cabalm-alz - Alz', '7')
    assert writes == unexpected == []


def test_currency_selection_that_reads_back_another_name_stops_before_add(monkeypatch):
    html = reward_form().replace('rewardPicker.textContent=option.textContent', "rewardPicker.textContent='Different currency'")
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    with pytest.raises(AztekLocatorError, match='reward'):
        run_bundle(save=True, btype='FIXED', rewards=[{'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7'}])
    assert next(e for e in snapshots[0] if e['id']=='added-name')['value'] == ''
    assert writes == unexpected == []


def test_currency_add_waits_for_selected_value_to_mount(monkeypatch):
    html = reward_form().replace('function chooseReward(option){rewardPicker',
                                'function chooseReward(option){setTimeout(()=>{rewardPicker')
    html = html.replace("option.closest('[data-radix-popper-content-wrapper]').remove();}",
                        "option.closest('[data-radix-popper-content-wrapper]').remove();},700);}")
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(btype='FIXED', rewards=[{'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7'}])
    assert result['rewards_added'] == 1 and result['fields_complete'] is True
    assert next(e for e in snapshots[0] if e['id']=='added-name')['value'] == 'cabalm-alz - Alz'
    assert writes == unexpected == []


def test_currency_add_rejects_a_submit_button_in_the_reward_panel(monkeypatch):
    html = reward_form().replace('<button type="button" onclick="addReward(this)">',
                                '<button type="submit" onclick="addReward(this)">')
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    with pytest.raises(AztekLocatorError, match='reward'):
        run_bundle(save=True, btype='FIXED', rewards=[{'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7'}])
    assert next(e for e in snapshots[0] if e['id']=='added-name')['value'] == ''
    assert writes == unexpected == []


@pytest.mark.parametrize('kind,tab,badge,value', [
    ('DEBIT','Debit','WALLET','cabalm-leaf-gem - Leaf Gem'),
    ('MILEAGE','Mileage','WALLET_MILEAGE','cabalm-mileage - Mileage'),
    ('PLAYER_EXP','Player Exp.','PLAYER_EXPERIENCE','Player Experience - PC'),
])
def test_reward_add_preserves_selected_kind_and_amount(monkeypatch, kind, tab, badge, value):
    html = reward_form().replace('>Credit</button>', '>%s</button>' % tab)
    html = html.replace('cabalm-alz - Alz', value).replace('WALLET_CREDIT', badge)
    display = value.split(' - ', 1)[1] if value.startswith('cabalm-') else value
    html = html.replace('>Alz<', '>%s<' % display)
    if kind == 'PLAYER_EXP':
        html = html.replace('<label>ชื่อ</label>', '<label>ชื่อ Monarchy</label>')
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(btype='FIXED', rewards=[{'type':kind,'value':value,'qty':'7'}])
    assert result['rewards_added'] == 1 and result['fields_complete'] is True
    fields = {e['id']:e['value'] for e in snapshots[0] if e['id']}
    assert (fields['added-name'],fields['added-qty'],fields['wrong']) == (value,'7','untouched')
    assert writes == unexpected == []


@pytest.mark.parametrize('mutation', ['missing-rate','duplicate-rate','wrong-rate-type',
                                     'duplicate-quantity','wrong-quantity-type','wrong-header-name',
                                     'duplicate-body-name','duplicate-tier','wrong-tier-trigger','duplicate-card'])
def test_reward_card_contract_failure_stops_before_save(monkeypatch, mutation):
    html = reward_card_form()
    if mutation == 'missing-rate':
        html = html.replace('id="items.4.secret_chance"', 'id="renamed-rate"')
    elif mutation == 'duplicate-rate':
        html = html.replace('name="items.4.chance" value="66">',
                            'name="items.4.chance" value="66"><input hidden type="number" id="items.4.secret_chance" value="88">')
    elif mutation == 'wrong-rate-type':
        html = html.replace('type="number" id="items.4.secret_chance"', 'type="text" id="items.4.secret_chance"')
    elif mutation == 'duplicate-quantity':
        html = html.replace('name="items.4.quantity" value="99">',
                            'name="items.4.quantity" value="99"><input hidden type="number" name="items.5.quantity" value="88">')
    elif mutation == 'wrong-quantity-type':
        html = html.replace('type="number" name="items.4.quantity"', 'type="text" name="items.4.quantity"')
    elif mutation == 'wrong-header-name':
        html = html.replace('aria-expanded="true"><p>Alz</p>', 'aria-expanded="true"><p>Different name</p>')
    elif mutation == 'duplicate-body-name':
        html = html.replace('<label>ชื่อ</label><p>Alz</p>',
                            '<label>ชื่อ</label><p>Alz</p><label>ชื่อ</label><p>Alz</p>')
    elif mutation == 'duplicate-tier':
        html = html.replace('<select name="reward-tier">', '<select hidden><option>Common</option></select><select name="reward-tier">')
    elif mutation == 'wrong-tier-trigger':
        html = html.replace('role="combobox">Tier', 'role="checkbox">Tier')
    else:
        html = html.replace('</script>', "document.addEventListener('click',e=>{if(e.target.textContent==='เพิ่ม'){const card=document.getElementById('cards').firstElementChild;if(card)card.after(card.cloneNode(true));}});</script>")
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    with pytest.raises(AztekLocatorError, match='reward'):
        run_bundle(save=True, rewards=[{'type':'CREDIT','value':'cabalm-alz - Alz',
                                        'qty':'7','tier':'Rare','rate':'0'}])
    assert writes == unexpected == []


def test_player_exp_card_waits_for_expansion_before_setting_common(monkeypatch):
    html = reward_form().replace('>Credit</button>', '>Player Exp.</button>')
    html = html.replace('cabalm-alz - Alz', 'Player Experience - PC').replace('>Alz<','>Player Experience - PC<')
    html = html.replace('WALLET_CREDIT','PLAYER_EXPERIENCE').replace('<label>ชื่อ</label>','<label>ชื่อ Monarchy</label>')
    html = html.replace('aria-label="ย่อ" aria-expanded="true"',
                        'aria-label="ขยาย" aria-expanded="false" onclick="setTimeout(()=>{this.setAttribute(\'aria-label\',\'ย่อ\');this.setAttribute(\'aria-expanded\',\'true\');document.getElementById(\'exp-fields\').hidden=false;},700)"')
    html = html.replace('<div><label>ชื่อ Monarchy</label>', '<div hidden id="exp-fields"><div><label>ชื่อ Monarchy</label>')
    html = html.replace('<option value="0">Common</option></select></div>`', '<option value="0">Common</option></select></div></div>`')
    html = html.replace('<select><option value="">', '<select name="exp-tier"><option value="">')
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(btype='FIXED', rewards=[{'type':'PLAYER_EXP','value':'Player Experience - PC','qty':'6'}])
    assert result['fields_complete'] is True
    assert next(e for e in snapshots[0] if e['name']=='items.0.quantity')['value'] == '6'
    assert next(e for e in snapshots[0] if e['name']=='exp-tier')['value'] == '0'
    assert writes == unexpected == []


@pytest.mark.parametrize('mutation', ['duplicate-option','wrong-qty','duplicate-add','wrong-add-role','wrong-panel','missing-tab-relation','missing-dialog'])
def test_reward_ambiguous_or_wrong_controls_stop_before_add(monkeypatch, mutation):
    html = reward_form()
    if mutation == 'duplicate-option':
        html = html.replace('<div role="listbox" id="radix-list-live">',
                            '<div role="listbox" id="radix-list-live"><div hidden role="option">cabalm-alz - Alz</div>')
    elif mutation == 'wrong-qty':
        html = html.replace('type="number" placeholder="Qty"','type="text" placeholder="Qty"')
    elif mutation == 'duplicate-add':
        # Duplicate belongs to the intended active panel, not the whole form.
        html = html.replace('onclick="addReward(this)">เพิ่ม</button>',
                            'onclick="addReward(this)">เพิ่ม</button><button hidden type="button">เพิ่ม</button>')
    elif mutation == 'wrong-panel':
        html = html.replace('aria-labelledby="radix-credit-tab"','aria-labelledby="unrelated-tab"')
    elif mutation == 'wrong-add-role':
        html = html.replace('onclick="addReward(this)"', 'role="checkbox" onclick="addReward(this)"')
    elif mutation == 'missing-tab-relation':
        html = html.replace('id="radix-credit-tab"', '').replace('aria-labelledby="radix-credit-tab"','')
    else:
        html = html.replace('id="radix-dialog-live" role="dialog"','id="radix-dialog-live" role="alertdialog"')
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    with pytest.raises(AztekLocatorError, match='reward'):
        run_bundle(save=True, btype='FIXED', rewards=[{'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7'}])
    assert next(e for e in snapshots[0] if e['id']=='added-name')['value'] == ''
    assert writes == unexpected == []


def test_currency_selection_waits_for_label_after_the_dialog_closes(monkeypatch):
    html = reward_form().replace('rewardPicker.textContent=option.textContent',
                                'setTimeout(()=>rewardPicker.textContent=option.textContent,600)')
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(btype='FIXED', rewards=[{'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7'}])
    assert result['rewards_added'] == 1 and result['fields_complete'] is True
    assert next(e for e in snapshots[0] if e['id']=='added-name')['value'] == 'cabalm-alz - Alz'
    assert writes == unexpected == []


@pytest.mark.parametrize('phase', ['tab','picker','panel','search'])
def test_reward_waits_for_delayed_active_widget_state(monkeypatch, phase):
    html = reward_form()
    if phase == 'tab':
        html = html.replace("this.setAttribute('aria-selected','true')", "setTimeout(()=>this.setAttribute('aria-selected','true'),700)")
    elif phase == 'picker':
        html = html.replace("button.setAttribute('aria-expanded','true')", "setTimeout(()=>button.setAttribute('aria-expanded','true'),700)")
    elif phase == 'panel':
        html = html.replace('aria-labelledby="radix-credit-tab"', 'aria-labelledby="previous-tab"')
        html = html.replace("this.setAttribute('aria-selected','true')", "this.setAttribute('aria-selected','true');setTimeout(()=>document.getElementById('radix-credit-panel').setAttribute('aria-labelledby','radix-credit-tab'),700)")
    else:
        html = html.replace('role="combobox" type="text" aria-controls="radix-list-live"', 'role="combobox" type="text"')
        html = html.replace('document.body.append(portal);', "document.body.append(portal);setTimeout(()=>portal.querySelector('input[role=combobox]').setAttribute('aria-controls','radix-list-live'),700);")
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(btype='FIXED', rewards=[{'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7'}])
    assert result['rewards_added'] == 1 and result['fields_complete'] is True
    assert next(e for e in snapshots[0] if e['id']=='added-name')['value'] == 'cabalm-alz - Alz'
    assert writes == unexpected == []


def reward_catalog_form(*, delayed=False):
    html = reward_form()
    tabs = ''.join('<button type="button" role="tab" id="tab-%s" aria-controls="radix-credit-panel" '
                   'aria-selected="false" onclick="activateReward(this)">%s</button>' % (kind, name)
                   for kind, name in [('CREDIT','Credit'),('DEBIT','Debit'),('MILEAGE','Mileage'),('PLAYER_EXP','Player Exp.'),('ITEM','Item')])
    html = html.replace('this.setAttribute(\'aria-selected\',\'true\')', 'activateReward(this)')
    html = html.replace('>Credit</button></div>', '>Credit</button>' + tabs.replace(
        '<button type="button" role="tab" id="tab-CREDIT" aria-controls="radix-credit-panel" aria-selected="false" onclick="activateReward(this)">Credit</button>', '') + '</div>')
    html = html.replace('let rewardPicker;', '''let rewardPicker; let rewardValue;
function activateReward(tab){
document.querySelectorAll('main form [role="tab"]').forEach(t=>t.setAttribute('aria-selected','false'));
tab.setAttribute('aria-selected','true');const panel=document.getElementById('radix-credit-panel');
panel.setAttribute('aria-labelledby',tab.id);panel.setAttribute('data-state','active');
rewardValue={Credit:'cabalm-alz - Alz',Debit:'cabalm-leaf-gem - Leaf Gem',Mileage:'cabalm-mileage - Mileage','Player Exp.':'Player Experience - PC'}[tab.textContent];
}
document.addEventListener('keydown',event=>{if(event.key==='Escape'){
document.getElementById('radix-dialog-live')?.closest('[data-radix-popper-content-wrapper]').remove();
rewardPicker?.setAttribute('aria-expanded','false');}});''')
    html = html.replace('onclick="chooseReward(this)">cabalm-alz - Alz', 'onclick="chooseReward(this)">${rewardValue}')
    if delayed:
        html = html.replace('role="listbox" id="radix-list-live"', 'role="listbox" style="min-height:24px" id="radix-list-live"')
        html = html.replace('document.body.append(portal);', '''document.body.append(portal);
const list=portal.querySelector('[role="listbox"]');const contents=list.innerHTML;list.innerHTML='';
setTimeout(()=>list.innerHTML=contents,2400);''')
    return html


def test_fetch_reward_catalog_waits_for_options_in_each_correct_dialog(monkeypatch):
    writes, snapshots, unexpected = routed_bundle(monkeypatch, reward_catalog_form(delayed=True))
    result = asyncio.run(bundle_runner.fetch_reward_options('CabalPC TH', {'cookies':[], 'origins':[]}, lambda *args:None))
    assert result == {'CREDIT':['cabalm-alz - Alz'], 'DEBIT':['cabalm-leaf-gem - Leaf Gem'],
                      'MILEAGE':['cabalm-mileage - Mileage'], 'PLAYER_EXP':['Player Experience - PC']}
    assert next(e for e in snapshots[0] if e['id']=='added-name')['value'] == ''
    assert writes == unexpected == []


def multi_reward_card_form():
    html = reward_catalog_form()
    start = html.index('function addReward(button){')
    end = html.index('\n</script>', start)
    html = html[:start] + '''const addedRewards=[];
function addReward(button){
const selected=document.querySelector('main form [role="tab"][aria-selected="true"]').textContent;
const kinds={Credit:'WALLET_CREDIT',Debit:'WALLET',Mileage:'WALLET_MILEAGE','Player Exp.':'PLAYER_EXPERIENCE'};
const keys={Credit:'CREDIT',Debit:'DEBIT',Mileage:'MILEAGE','Player Exp.':'PLAYER_EXP'};
const display={Credit:'Alz',Debit:'Leaf Gem',Mileage:'Mileage','Player Exp.':'Player Experience - PC'};
addedRewards.push({kind:kinds[selected],key:keys[selected],name:display[selected]});
document.getElementById('cards').innerHTML=[...addedRewards].reverse().map((r,i)=>`
<div><div><button type="button" aria-label="ย่อ" aria-expanded="true"><p>${r.name}</p><span>${r.kind}</span></button></div>
<div><label>${r.key==='PLAYER_EXP'?'ชื่อ Monarchy':'ชื่อ'}</label><p>${r.name}</p></div>
<input type="number" name="items.${i}.quantity" value="99">
<button type="button" role="combobox">Tier</button><select name="tier-${r.key}">
<option value=""></option><option value="0">Common</option><option value="1">Rare</option><option value="2">Epic</option></select>
<input type="number" id="items.${i}.secret_chance" name="items.${i}.secret_chance" value="55">
<input type="number" id="items.${i}.chance" name="items.${i}.chance" value="66"></div>`).join('');
}
''' + html[end:]
    return html


def test_all_reward_kinds_keep_their_fields_when_cards_are_reordered(monkeypatch):
    writes, snapshots, unexpected = routed_bundle(monkeypatch, multi_reward_card_form())
    result, _ = run_bundle(rewards=[
        {'type':'CREDIT','value':'cabalm-alz - Alz','qty':'2','tier':'Rare','rate':0},
        {'type':'DEBIT','value':'cabalm-leaf-gem - Leaf Gem','qty':'3','tier':'Common','rate':'25'},
        {'type':'MILEAGE','value':'cabalm-mileage - Mileage','qty':'4','tier':'Epic','rate':'25'},
        {'type':'PLAYER_EXP','value':'Player Experience - PC','qty':'5','rate':'50'},
    ])
    assert result['fields_complete'] is True and result['rewards_added'] == 4
    fields = snapshots[0]
    assert [e['value'] for e in fields if e['name'].endswith('.quantity')] == ['5','4','3','2']
    assert [e['value'] for e in fields if e['name'].startswith('tier-')] == ['0','2','0','1']
    assert [e['value'] for e in fields if e['id'].endswith('.secret_chance')] == ['50','25','25','0']
    assert [e['value'] for e in fields if e['id'].endswith('.chance')] == ['66','66','66','66']
    assert writes == unexpected == []


def test_rewards_with_different_codes_but_the_same_visible_identity_stop(monkeypatch):
    html = multi_reward_card_form().replace('let rewardValue;', 'let rewardValue; let creditVisits=0;')
    html = html.replace("[tab.textContent];", "[tab.textContent];if(tab.textContent==='Credit' && ++creditVisits>1)rewardValue='cabalm-alz-b - Alz';")
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    with pytest.raises(AztekLocatorError, match='reward'):
        run_bundle(save=True, btype='FIXED', rewards=[
            {'type':'CREDIT','value':'cabalm-alz - Alz','qty':'2','tier':'Rare'},
            {'type':'CREDIT','value':'cabalm-alz-b - Alz','qty':'9','tier':'Common'},
        ])
    assert [e['value'] for e in snapshots[0] if e['name'].endswith('.quantity')] == ['99','99']
    assert writes == unexpected == []


def test_late_reward_card_is_expanded_after_its_identity_mounts(monkeypatch):
    html = reward_card_form().replace('aria-label="ย่อ" aria-expanded="true"',
        '''aria-label="ขยาย" aria-expanded="false" onclick="this.setAttribute('aria-label','ย่อ');this.setAttribute('aria-expanded','true');document.getElementById('late-fields').hidden=false"''')
    html = html.replace('<div><label>ชื่อ</label>', '<div hidden id="late-fields"><div><label>ชื่อ</label>')
    html = html.replace('name="items.4.chance" value="66"></div>`;', 'name="items.4.chance" value="66"></div></div>`;')
    html = html.replace("document.getElementById('cards').innerHTML=", "setTimeout(()=>{document.getElementById('cards').innerHTML=")
    html = html.replace('</div></div>`;\n}', '</div></div>`;},1700);\n}')
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(rewards=[{'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7','tier':'Rare','rate':'0'}])
    assert result['fields_complete'] is True
    assert next(e for e in snapshots[0] if e['name']=='items.4.quantity')['value'] == '7'
    assert next(e for e in snapshots[0] if e['id']=='items.4.secret_chance')['value'] == '0'
    assert writes == unexpected == []


def test_random_reward_without_an_explicit_rate_keeps_aztek_default(monkeypatch):
    writes, snapshots, unexpected = routed_bundle(monkeypatch, reward_card_form())
    result, _ = run_bundle(rewards=[{'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7'}])
    assert result['fields_complete'] is True
    assert next(e for e in snapshots[0] if e['id']=='items.4.secret_chance')['value'] == '55'
    assert next(e for e in snapshots[0] if e['name']=='reward-tier')['value'] == '0'
    assert writes == unexpected == []


def test_reward_rate_uses_the_new_current_index_after_quantity_changes(monkeypatch):
    html = reward_card_form().replace('name="items.4.quantity" value="99"',
        '''name="items.4.quantity" value="99" oninput="this.name='items.8.quantity';
document.getElementById('items.4.secret_chance').id='items.8.secret_chance';
document.getElementById('items.4.chance').id='items.8.chance'"''')
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(rewards=[{'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7','tier':'Rare','rate':'12.5'}])
    assert result['fields_complete'] is True
    assert next(e for e in snapshots[0] if e['id']=='items.8.secret_chance')['value'] == '12.5'
    assert next(e for e in snapshots[0] if e['id']=='items.8.chance')['value'] == '66'
    assert writes == unexpected == []


@pytest.mark.parametrize('control', ['quantity','tier','rate'])
def test_reward_card_readback_mismatch_keeps_the_bundle_unsaved(monkeypatch, control):
    html = reward_card_form()
    if control == 'quantity':
        html = html.replace('name="items.4.quantity"', 'oninput="this.value=98" name="items.4.quantity"')
    elif control == 'tier':
        html = html.replace('<select name="reward-tier">', '<select onchange="this.value=0" name="reward-tier">')
    else:
        html = html.replace('id="items.4.secret_chance"', 'oninput="this.value=98" id="items.4.secret_chance"')
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    with pytest.raises(AztekLocatorError, match='อ่านกลับไม่ตรง'):
        run_bundle(save=True, rewards=[{'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7','tier':'Rare','rate':'25'}])
    assert writes == unexpected == []


@pytest.mark.parametrize('save', [False,True])
def test_public_api_reports_reward_card_failure_without_losing_session(client, monkeypatch, save):
    _connect_aztek(client)
    html = reward_card_form().replace('type="number" name="items.4.quantity"','type="text" name="items.4.quantity"')
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    response = client.post('/api/bundles/run', json={'game':GAME, 'do_save':save, 'bundles':[{
        'client_key':'reward-card-contract-failure','name':'Reward Pack','bundle_type':'FIXED',
        'items':[], 'rewards':[{'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7'}],
    }]})
    if save:
        assert response.status_code == 200, response.text
        result = response.json()['results'][0]
        assert response.json()['created'] == 0 and result['fields_complete'] is False
        assert not result['saved'] and not result.get('creation_uncertain')
        assert 'reward' in result['error']
    else:
        assert response.status_code == 502, response.text
        assert 'reward' in response.json()['detail']
    assert client.get('/api/aztek/status').json()['status'] == 'active'
    assert writes == unexpected == []


@pytest.mark.parametrize('initial,deliver,clicks', [('true', True, '0'), ('false', True, '1'), ('true', False, '1')])
def test_delivery_switch_preserves_matching_state_and_ignores_hidden_checkbox(monkeypatch, initial, deliver, clicks):
    html = HEADER.replace('aria-checked="true"', f'aria-checked="{initial}"')
    html = html.replace('<main>', '<input id="clicks" value="0"><main>')
    html = html.replace('onclick="this.setAttribute', 'onclick="document.getElementById(\'clicks\').value++;this.setAttribute')
    html = html.replace('</form>', '<input id="hidden-checkbox" type="checkbox" checked hidden></form>')
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(deliver=deliver)
    assert result['fields_complete'] is True
    assert next(e for e in snapshots[0] if e['id'] == 'clicks')['value'] == clicks
    assert next(e for e in snapshots[0] if e['id'] == 'immediately-send')['checked'] == str(deliver).lower()
    assert next(e for e in snapshots[0] if e['id'] == 'hidden-checkbox')['isChecked'] is True
    assert writes == unexpected == []


def test_header_ids_win_over_misleading_fields_outside_the_form(monkeypatch):
    writes, snapshots, unexpected = routed_bundle(monkeypatch, HEADER)
    result, _ = run_bundle()
    assert result['fields_complete'] is True
    fields = snapshots[0]
    assert next(e for e in fields if e['id'] == 'bundle-name')['value'] == 'Pack'
    assert next(e for e in fields if e['id'] == 'immediately-send')['checked'] == 'false'
    assert [e['value'] for e in fields if e['value'] in ('Wrong', 'RANDOM')] == ['Wrong', 'RANDOM']
    assert fields[1]['value'] == 'outside'
    assert writes == unexpected == []


@pytest.mark.parametrize('late', ['select', 'options'])
def test_header_waits_for_lazy_native_type_control_and_options(monkeypatch, late):
    select = '<select><option>FIXED</option><option>RANDOM</option></select>'
    if late == 'select':
        html = HEADER.replace(select, '<span id="mount-type"></span>')
        script = "document.getElementById('mount-type').outerHTML=" + repr(select)
    else:
        html = HEADER.replace(select, '<select id="type-options"></select>')
        script = "document.getElementById('type-options').innerHTML='<option>FIXED</option><option>RANDOM</option>'"
    html += '<script>setTimeout(()=>{' + script + '},3700)</script>'
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle()
    assert result['fields_complete'] is True
    assert any(e['value'] == 'RANDOM' for e in snapshots[0])
    assert writes == unexpected == []


def item_form(*, duplicate=False, missing=False, delayed=False, lazy_card=False, card_mutation=None):
    card = '''<div><div><p>Item 91</p><span>ITEM</span>
<button type="button" aria-label="ย่อ" aria-expanded="true">Toggle</button></div>
<div><label>Item ID</label><p>91</p></div><input name="items.0.quantity" type="number" value="1">
<select><option>Common</option><option>Rare</option></select>
<input type="number" id="items.0.secret_chance" name="items.0.secret_chance" value="1">
<input type="number" id="items.0.chance" value="77"></div>'''
    if lazy_card:
        card = card.replace('<input name="items.0.quantity"', '<section hidden><input name="items.0.quantity"')
        card = card.replace('value="77"></div>', 'value="77"></section></div>')
        card = card.replace('aria-label="ย่อ" aria-expanded="true">Toggle', 'aria-label="ขยาย" aria-expanded="false" onclick="this.setAttribute(\'aria-expanded\',\'true\');this.setAttribute(\'aria-label\',\'ย่อ\');this.parentElement.parentElement.querySelector(\'section\').hidden=false">Toggle')
    if card_mutation == 'missing-rate':
        card = card.replace('id="items.0.secret_chance"', 'id="renamed-rate"')
        card += '<input name="items.0.randomRate" type="number" required value="99">'
    elif card_mutation == 'duplicate-rate':
        card = card.replace('</select>', '</select><input hidden type="number" id="items.0.secret_chance" value="99">')
    elif card_mutation == 'wrong-rate':
        card = card.replace('type="number" id="items.0.secret_chance"', 'type="text" id="items.0.secret_chance"')
    elif card_mutation == 'duplicate-card':
        card += card.replace('items.0.', 'items.1.')
    elif card_mutation == 'duplicate-tier':
        card = card.replace('</select>', '</select><select hidden><option>Common</option></select>')
    elif card_mutation == 'ambiguous-identity':
        card = card.replace('<input name="items.0.quantity"', '<div><label>Item ID</label><p>92</p></div><input name="items.0.quantity"')
    elif card_mutation == 'wrong-card-expander':
        card = card.replace('type="button" aria-label="ย่อ"', 'type="submit" aria-label="ย่อ"')
    elif card_mutation == 'wrong-card-kind':
        card = card.replace('<span>ITEM</span>', '<span>WALLET</span>')
    elif card_mutation == 'wrong-card-role':
        card = card.replace('aria-label="ย่อ"', 'role="checkbox" aria-label="ย่อ"')
    elif card_mutation == 'late-tier-options':
        card = card.replace('<select><option>Common</option><option>Rare</option></select>', '<select id="lazy-tier"></select>')
        card = card.replace('name="items.0.quantity"', 'name="items.0.quantity" oninput="setTimeout(()=>document.getElementById(\'lazy-tier\').innerHTML=\'<option>Common</option><option>Rare</option>\',800)"')
    if card_mutation != 'missing-tier-trigger':
        role = 'checkbox' if card_mutation == 'wrong-tier-trigger' else 'combobox'
        card = card.replace('<select', f'<button type="button" role="{role}">Tier</button><select', 1)
    card = card.replace('<select', '<select aria-hidden="true" style="position:absolute;width:1px;height:1px;clip:rect(0,0,0,0)"')
    script = "document.getElementById('cards').innerHTML=" + repr(card)
    if card_mutation == 'late-card':
        script = 'setTimeout(()=>{' + script + '},1700)'
    add_script = "<script>function addRequested(){" + script + "}</script>"
    hit = '''<div><span>ID: 91</span><button type="button" onclick="addRequested()">เพิ่ม</button></div>'''
    panel = '''<div role="tablist"><button type="button" role="tab" aria-selected="true">Item</button></div>
<div role="tabpanel" data-state="active" aria-label="Item"><input placeholder="ค้นหาชื่อ Item...">
<div><span>ID: 910</span><button type="button" onclick="document.getElementById('wrong').value='clicked'">เพิ่ม</button></div>'''
    panel += ('' if missing else hit) + (hit if duplicate else '') + '</div><div id="cards"></div>'
    if delayed:
        panel = panel.replace(hit, '<div id="late-item"></div>')
        handler = "setTimeout(()=>{document.getElementById('late-item').outerHTML=" + repr(hit) + "},1800)"
        panel = panel.replace('placeholder="ค้นหาชื่อ Item..."', 'placeholder="ค้นหาชื่อ Item..." oninput="' + handler.replace(chr(34), '&quot;') + '"')
    return HEADER.replace('<main>', '<input placeholder="ค้นหาชื่อ Item..."><input id="wrong" value="untouched"><main>').replace('<input id="bundle-name"', panel + '<input id="bundle-name"') + add_script


def reordered_item_form(*, lazy_cards=False):
    def card(item_id, index):
        html = f'''<div><div><p>Item {item_id}</p><span>ITEM</span>
<button type="button" aria-label="ย่อ" aria-expanded="true">Toggle</button></div>
<div><label>Item ID</label><p>{item_id}</p></div>
<input name="items.{index}.quantity" type="number" value="1">
<button type="button" role="combobox">Tier</button>
<select name="tier-{item_id}"><option>Common</option><option>Rare</option></select>
<input type="number" id="items.{index}.secret_chance" name="items.{index}.secret_chance" value="1">
<input type="number" id="items.{index}.chance" value="77"></div>'''
        if lazy_cards:
            html = html.replace('<div><label>Item ID', '<section hidden><div><label>Item ID')
            html = html.replace('value="77"></div>', 'value="77"></section></div>')
            html = html.replace('aria-label="ย่อ" aria-expanded="true">Toggle', 'aria-label="ขยาย" aria-expanded="false" onclick="document.getElementById(\'expand-count\').value++;this.setAttribute(\'aria-expanded\',\'true\');this.setAttribute(\'aria-label\',\'ย่อ\');this.parentElement.parentElement.querySelector(\'section\').hidden=false">Toggle')
        return html
    html = item_form(missing=True)
    html = html.replace('<main>', '<input id="expand-count" value="0"><main>')
    results = '''<div><span>ID: 91</span><button type="button" onclick="addPair(false)">เพิ่ม</button></div>
<div><span>ID: 92</span><button type="button" onclick="addPair(true)">เพิ่ม</button></div>'''
    html = html.replace('</div><div id="cards">', results + '</div><div id="cards">')
    return html + '<script>function addPair(second){document.getElementById("cards").innerHTML=second?' + repr(card(92, 0) + card(91, 1)) + ':' + repr(card(91, 0)) + '}</script>'


@pytest.mark.parametrize('lazy_cards', [False, True])
def test_reordered_cards_keep_quantity_tier_and_draw_rate_with_their_item(monkeypatch, lazy_cards):
    # Reusing the submitted index instead of the current Item ID swaps all values.
    writes, snapshots, unexpected = routed_bundle(monkeypatch, reordered_item_form(lazy_cards=lazy_cards))
    result, _ = run_bundle(items=[
        {'id': '91', 'qty': '4', 'tier': 'Rare', 'rate': '0'},
        {'id': '92', 'qty': '7', 'tier': 'Common', 'rate': '100'},
    ])
    assert result['fields_complete'] is True
    fields = snapshots[0]
    assert [e['value'] for e in fields if e['name'].endswith('.quantity')] == ['7', '4']
    assert [e['value'] for e in fields if e['name'].startswith('tier-')] == ['Common', 'Rare']
    assert [e['value'] for e in fields if e['id'].endswith('.secret_chance')] == ['100', '0']
    assert [e['value'] for e in fields if e['id'].endswith('.chance')] == ['77', '77']
    assert next(e for e in fields if e['id'] == 'expand-count')['value'] == ('2' if lazy_cards else '0')
    assert writes == unexpected == []


def test_lazy_item_card_is_expanded_before_required_fields_are_resolved(monkeypatch):
    html = item_form(lazy_card=True)
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(items=[{'id': '91', 'qty': '4', 'tier': 'Rare', 'rate': '0'}])
    assert result['fields_complete'] is True
    assert next(e for e in snapshots[0] if e['name'] == 'items.0.quantity')['value'] == '4'
    assert writes == unexpected == []


@pytest.mark.parametrize('mutation,control', [
    ('missing-rate', 'เรทสุ่ม'), ('duplicate-rate', 'เรทสุ่ม'),
    ('wrong-rate', 'เรทสุ่ม'), ('duplicate-card', 'การ์ด Item'),
    ('duplicate-tier', 'Tier'), ('ambiguous-identity', 'การ์ด Item'),
    ('missing-tier-trigger', 'Tier'), ('wrong-tier-trigger', 'Tier'),
    ('wrong-card-expander', 'การ์ด Item'),
    ('wrong-card-kind', 'การ์ด Item'), ('wrong-card-role', 'การ์ด Item'),
])
def test_broken_item_card_contract_never_uses_a_decoy_or_submits(monkeypatch, mutation, control):
    writes, _, unexpected = routed_bundle(monkeypatch, item_form(card_mutation=mutation))
    with pytest.raises(AztekLocatorError, match=control):
        run_bundle(save=True, items=[{'id': '91', 'qty': '4', 'tier': 'Rare', 'rate': '0'}])
    assert writes == unexpected == []


@pytest.mark.parametrize('lazy_card', [False, True])
def test_new_item_card_waits_for_mount_before_treating_it_as_missing(monkeypatch, lazy_card):
    writes, snapshots, unexpected = routed_bundle(monkeypatch, item_form(card_mutation='late-card', lazy_card=lazy_card))
    result, _ = run_bundle(items=[{'id': '91', 'qty': '4', 'tier': 'Rare', 'rate': '0'}])
    assert result['fields_complete'] is True
    assert next(e for e in snapshots[0] if e['name'] == 'items.0.quantity')['value'] == '4'
    assert writes == unexpected == []


def test_item_tier_waits_for_native_options_after_quantity_is_filled(monkeypatch):
    writes, snapshots, unexpected = routed_bundle(monkeypatch, item_form(card_mutation='late-tier-options'))
    result, _ = run_bundle(items=[{'id': '91', 'qty': '4', 'tier': 'Rare', 'rate': '0'}])
    assert result['fields_complete'] is True
    assert next(e for e in snapshots[0] if e['id'] == 'lazy-tier')['value'] == 'Rare'
    assert writes == unexpected == []


def test_repeated_item_identity_cannot_silently_overwrite_one_merged_card(monkeypatch):
    writes, _, unexpected = routed_bundle(monkeypatch, item_form())
    with pytest.raises(AztekLocatorError, match='91'):
        run_bundle(save=True, items=[
            {'id': '91', 'qty': '4', 'tier': 'Rare', 'rate': '50'},
            {'id': '91', 'qty': '7', 'tier': 'Common', 'rate': '50'},
        ])
    assert writes == unexpected == []


def repeated_item_form():
    # Each add creates a distinct node; later additions move old nodes and
    # renumber their controls. Index is deliberately not occurrence identity.
    html = item_form()
    start = html.index('<script>function addRequested()')
    card = '''<div><div><p>Item 91</p><span>ITEM</span>
<button type="button" aria-label="ย่อ" aria-expanded="true">Toggle</button></div>
<div><label>Item ID</label><p>91</p></div>
<input type="number" name="items.0.quantity" value="1">
<button type="button" role="combobox">Tier</button>
<select name="tier"><option>Common</option><option>Rare</option></select>
<input type="number" id="items.0.secret_chance" value="55">
<input type="number" id="items.0.chance" value="77"></div>'''
    return html[:start] + '''<script>
function renumber(){[...document.getElementById('cards').children].forEach((c,i)=>{
c.querySelector('input[name]').name=`items.${i*3+2}.quantity`;
c.querySelector('input[id$=".secret_chance"]').id=`items.${i*3+2}.secret_chance`;
c.querySelector('input[id$=".chance"]').id=`items.${i*3+2}.chance`;});}
function addRequested(){const holder=document.createElement('div');holder.innerHTML=''' + repr(card) + ''';
document.getElementById('cards').prepend(holder.firstElementChild);renumber();}
</script>'''


def test_repeated_items_preserve_distinct_values_after_reorder_and_renumber(monkeypatch):
    # A first-match, merged identity or cached index loses/swaps one occurrence.
    writes, snapshots, unexpected = routed_bundle(monkeypatch, repeated_item_form())
    result, _ = run_bundle(items=[
        {'id':'91', 'qty':'4', 'tier':'Rare', 'rate':0},
        {'id':'91', 'qty':'7', 'tier':'Common', 'rate':'100'},
    ])
    assert result['fields_complete'] is True and result['added'] == 2
    fields = snapshots[0]
    assert [e['value'] for e in fields if e['name'].endswith('.quantity')] == ['7','4']
    assert [e['value'] for e in fields if e['name']=='tier'] == ['Common','Rare']
    assert [e['value'] for e in fields if e['id'].endswith('.secret_chance')] == ['100','0']
    assert [e['value'] for e in fields if e['id'].endswith('.chance')] == ['77','77']
    assert writes == unexpected == []


@pytest.mark.parametrize('btype', ['FIXED','RANDOM'])
def test_duplicate_current_indexes_stop_repeated_cards_before_create(monkeypatch, btype):
    html = repeated_item_form().replace('i*3+2','2')
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    with pytest.raises(AztekLocatorError, match='index|เรทสุ่ม'):
        run_bundle(save=True, btype=btype, items=[
            {'id':'91','qty':'4','tier':'Rare','rate':0},
            {'id':'91','qty':'7','tier':'Common','rate':'100'},
        ])
    assert writes == unexpected == []


def test_repeated_card_moving_during_quantity_input_keeps_its_own_tier(monkeypatch):
    html = repeated_item_form() + '''<script>document.addEventListener('input',event=>{
if(event.target.name?.endsWith('.quantity')){
document.getElementById('cards').prepend(event.target.parentElement);renumber();}});</script>'''
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(items=[
        {'id':'91','qty':'4','tier':'Rare','rate':0},
        {'id':'91','qty':'7','tier':'Common','rate':'100'},
    ])
    assert result['fields_complete'] is True
    fields = snapshots[0]
    assert [e['value'] for e in fields if e['name'].endswith('.quantity')] == ['7','4']
    assert [e['value'] for e in fields if e['name']=='tier'] == ['Common','Rare']
    assert [e['value'] for e in fields if e['id'].endswith('.secret_chance')] == ['100','0']
    assert writes == unexpected == []


def test_repeated_card_reordering_while_tier_options_mount_keeps_its_own_select(monkeypatch):
    html = repeated_item_form() + '''<script>document.addEventListener('input',event=>{
if(event.target.name?.endsWith('.quantity') && event.target.value==='4'){
const card=event.target.parentElement;const select=card.querySelector('select');
const options=select.innerHTML;select.innerHTML='';
setTimeout(()=>{document.getElementById('cards').prepend(card);renumber();},150);
setTimeout(()=>{select.innerHTML=options;},600);}});</script>'''
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(items=[
        {'id':'91','qty':'4','tier':'Rare','rate':0},
        {'id':'91','qty':'7','tier':'Common','rate':'100'},
    ])
    assert result['fields_complete'] is True
    fields = snapshots[0]
    assert [e['value'] for e in fields if e['name'].endswith('.quantity')] == ['4','7']
    assert [e['value'] for e in fields if e['name']=='tier'] == ['Rare','Common']
    assert [e['value'] for e in fields if e['id'].endswith('.secret_chance')] == ['0','100']
    assert writes == unexpected == []


def test_repeated_item_readback_rejects_a_previous_card_changed_by_later_input(monkeypatch):
    html = repeated_item_form().replace("document.getElementById('cards').prepend",
        '''holder.firstElementChild.querySelector('input[name]').addEventListener('input',event=>{
const cards=document.getElementById('cards');if(cards.firstElementChild.contains(event.target))
cards.lastElementChild.querySelector('input[name]').value='99';});
document.getElementById('cards').prepend''')
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    with pytest.raises(AztekLocatorError, match='จำนวน'):
        run_bundle(save=True, items=[
            {'id':'91','qty':'4','tier':'Rare','rate':0},
            {'id':'91','qty':'7','tier':'Common','rate':'100'},
        ])
    assert writes == unexpected == []


def repeated_reward_form():
    html = multi_reward_card_form()
    start = html.index('const addedRewards=[];')
    end = html.index('\n</script>', start)
    script = html[start:end]
    script = script.replace('const addedRewards=[];', 'let addedCount=0;')
    script = script.replace('addedRewards.push({kind:kinds[selected],key:keys[selected],name:display[selected]});',
        'const r={kind:kinds[selected],key:keys[selected],name:display[selected]};addedCount++;')
    script = script.replace('document.getElementById(\'cards\').innerHTML=[...addedRewards].reverse().map((r,i)=>`',
        'const holder=document.createElement("div");const i=0;holder.innerHTML=`')
    script = script.replace("</div>`).join('');", '''</div>`;
document.getElementById('cards').prepend(holder.firstElementChild);
[...document.getElementById('cards').children].forEach((c,i)=>{
c.querySelector('input[name]').name=`items.${i*3+2}.quantity`;
c.querySelector('input[id$=".secret_chance"]').id=`items.${i*3+2}.secret_chance`;
c.querySelector('input[id$=".chance"]').id=`items.${i*3+2}.chance`;});''')
    return html[:start] + script + html[end:]


@pytest.mark.parametrize('kind,value', [
    ('CREDIT','cabalm-alz - Alz'), ('DEBIT','cabalm-leaf-gem - Leaf Gem'),
    ('MILEAGE','cabalm-mileage - Mileage'), ('PLAYER_EXP','Player Experience - PC'),
])
def test_repeated_rewards_keep_each_amount_tier_and_rate(monkeypatch, kind, value):
    writes, snapshots, unexpected = routed_bundle(monkeypatch, repeated_reward_form())
    result, _ = run_bundle(rewards=[
        {'type':kind,'value':value,'qty':'2','tier':'Rare','rate':0},
        {'type':kind,'value':value,'qty':'9','rate':'100'},
    ])
    assert result['fields_complete'] is True and result['rewards_added'] == 2
    fields = snapshots[0]
    assert [e['value'] for e in fields if e['name'].endswith('.quantity')] == ['9','2']
    assert [e['value'] for e in fields if e['name'].startswith('tier-')] == ['0','1']
    assert [e['value'] for e in fields if e['id'].endswith('.secret_chance')] == ['100','0']
    assert [e['value'] for e in fields if e['id'].endswith('.chance')] == ['66','66']
    assert writes == unexpected == []


def test_repeated_currency_with_same_name_in_another_kind_never_shares_a_card(monkeypatch):
    html = repeated_reward_form().replace('cabalm-leaf-gem - Leaf Gem','cabalm-alz-debit - Alz').replace("Debit:'Leaf Gem'", "Debit:'Alz'")
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(rewards=[
        {'type':'CREDIT','value':'cabalm-alz - Alz','qty':'2','tier':'Rare','rate':0},
        {'type':'CREDIT','value':'cabalm-alz - Alz','qty':'9','rate':'40'},
        {'type':'DEBIT','value':'cabalm-alz-debit - Alz','qty':'3','rate':'20'},
        {'type':'PLAYER_EXP','value':'Player Experience - PC','qty':'5','rate':'40'},
    ])
    assert result['fields_complete'] is True and result['rewards_added'] == 4
    fields = snapshots[0]
    assert [e['value'] for e in fields if e['name'].endswith('.quantity')] == ['5','3','9','2']
    assert [e['value'] for e in fields if e['name'].startswith('tier-')] == ['0','0','0','1']
    assert [e['value'] for e in fields if e['id'].endswith('.secret_chance')] == ['40','20','40','0']
    assert writes == unexpected == []


def test_api_duplicate_item_id_rule_is_unchanged_by_locator_migration(client, monkeypatch):
    writes, snapshots, unexpected = routed_bundle(monkeypatch, repeated_item_form())
    response = client.post('/api/bundles/run',json={'game':GAME,'do_save':True,'bundles':[{
        'client_key':'existing-rule','name':'Duplicate','items':[{'id':'91'},{'id':'91'}],
    }]})
    assert response.status_code == 400
    assert 'Item ID ห้ามซ้ำ' in response.json()['detail']
    assert writes == snapshots == unexpected == []


def test_item_and_repeated_rewards_keep_values_after_shared_indexes_change(monkeypatch):
    from test_bundle_recheck_id_first import saved_card
    card = saved_card('0','1').replace('<select>', '<select name="tier-ITEM">').replace('<option value="0" selected>Common</option>',
        '<option value="0">Common</option><option value="1">Rare</option>')
    card = card[:-6] + '<input type="number" id="items.0.secret_chance" value="55"><input type="number" id="items.0.chance" value="77"></div>'
    item_panel = '''<input placeholder="ค้นหาชื่อ Item..."><div><span>ID: 91</span>
<button type="button" onclick="addMixedItem()">เพิ่ม</button></div>'''
    html = repeated_reward_form() + '''<script>
const rewardMarkup=document.getElementById('radix-credit-panel').innerHTML;
const originalActivate=activateReward;
activateReward=tab=>{document.getElementById('radix-credit-panel').innerHTML=
tab.textContent==='Item'?''' + repr(item_panel) + ''':rewardMarkup;originalActivate(tab);};
function addMixedItem(){const holder=document.createElement('div');holder.innerHTML=''' + repr(card) + ''';
document.getElementById('cards').prepend(holder.firstElementChild);}
</script>'''
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(items=[{'id':'91','qty':'4','tier':'Rare','rate':0}], rewards=[
        {'type':'CREDIT','value':'cabalm-alz - Alz','qty':'2','rate':'40'},
        {'type':'CREDIT','value':'cabalm-alz - Alz','qty':'9','tier':'Rare','rate':'60'},
    ])
    assert result['fields_complete'] is True and result['added']==1 and result['rewards_added']==2
    fields = snapshots[0]
    assert [e['value'] for e in fields if e['name'].endswith('.quantity')] == ['9','2','4']
    # Native tiers are encoded as 0/1 on the verified widgets.
    assert [e['value'] for e in fields if e['name'].startswith('tier-')] == ['1','0','1']
    assert [e['value'] for e in fields if e['id'].endswith('.secret_chance')] == ['60','40','0']
    assert writes == unexpected == []


@pytest.mark.parametrize('defect', ['merged','replaced','removed','quantity-changed'])
def test_repeated_card_failure_keeps_api_draft_retryable_without_a_write(client, monkeypatch, defect):
    _connect_aztek(client)
    html = reward_card_form() if defect == 'merged' else repeated_reward_form()
    if defect == 'replaced':
        html = html.replace("document.getElementById('cards').prepend(holder.firstElementChild);",
            "document.getElementById('cards').prepend(holder.firstElementChild);if(document.getElementById('cards').children.length>1){const old=document.getElementById('cards').lastElementChild;old.replaceWith(old.cloneNode(true));}")
    elif defect == 'removed':
        html = html.replace("document.getElementById('cards').prepend(holder.firstElementChild);",
            "document.getElementById('cards').prepend(holder.firstElementChild);if(document.getElementById('cards').children.length>1)document.getElementById('cards').lastElementChild.remove();")
    elif defect == 'quantity-changed':
        html = html.replace("document.getElementById('cards').prepend",
            '''holder.firstElementChild.querySelector('input[name]').addEventListener('input',event=>{
const cards=document.getElementById('cards');if(cards.firstElementChild.contains(event.target))
cards.lastElementChild.querySelector('input[name]').value='99';});
document.getElementById('cards').prepend''')
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    payload = {'game':GAME,'do_save':True,'bundles':[{
        'client_key':'repeated-safe-stop','name':'Repeated','bundle_type':'RANDOM',
        'rewards':[{'type':'CREDIT','value':'cabalm-alz - Alz','qty':'4','tier':'Rare','rate':'0'},
                   {'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7','tier':'Common','rate':'100'}],
    }]}
    for _ in range(2):
        response = client.post('/api/bundles/run', json=payload)
        assert response.status_code == 200, response.text
        result = response.json()['results'][0]
        assert response.json()['created'] == 0 and result['fields_complete'] is False
        assert not result['saved'] and not result.get('creation_uncertain')
        assert 'reward' in result['error']
    assert client.get('/api/aztek/status').json()['status'] == 'active'
    assert writes == unexpected == []


@pytest.mark.parametrize('defect,outcome', [('none','passed'), ('qty','mismatch'),
    ('tier','mismatch'), ('rate','mismatch'), ('merged','mismatch')])
def test_repeated_reward_create_rechecks_every_occurrence_and_prevents_replay(client, monkeypatch, defect, outcome):
    from test_bundle_recheck_id_first import saved_card, saved_bundle
    _connect_aztek(client)
    html = repeated_reward_form().replace('/combo/cabalpc/', '/combo/cabalm/')
    endpoint = 'https://admin-api-v2.combo-interactive.com/cabalm/warehouse/bundles'
    html = html.replace("fetch('/combo/cabalm/shop/bundles'", "fetch('" + endpoint + "'")
    html = html.replace("name:document.getElementById('bundle-name').value", """name:document.getElementById('bundle-name').value,
rewards:[...document.getElementById('cards').children].map(c=>({type:'CREDIT',value:'Alz',
qty:c.querySelector('input[name]').value,tier:c.querySelector('select').value,
rate:[...c.querySelectorAll('input')].find(e=>e.id.endsWith('.secret_chance')).value}))""")
    last = saved_card('5','4').replace('>Common<','>Rare<').replace('value="0" selected','value="1" selected')
    last = last.replace('</select></div>', '</select></div><input type="number" id="items.5.secret_chance" value="0">')
    first = saved_card('2','7').replace('</select></div>', '</select></div><input type="number" id="items.2.secret_chance" value="100">')
    if defect == 'qty':
        first = first.replace('value="7"','value="8"')
    elif defect == 'tier':
        first = first.replace('>Common<','>Rare<')
    elif defect == 'rate':
        first = first.replace('value="100"','value="99"')
    elif defect == 'merged':
        first = first.replace('value="7"','value="11"')
        last = ''
    cards = (first+last).replace('>ITEM<','>WALLET_CREDIT<').replace('>Item 91<','>Alz<').replace('>Item ID<','>ชื่อ<').replace('>91<','>Alz<')
    pages = {'/combo/cabalm/shop/bundles/42':saved_bundle(cards,1 if defect=='merged' else 2,'RANDOM')}
    writes, _, unexpected = routed_bundle(monkeypatch, html, write_url=endpoint,
                                          write_body={'id':42}, pages=pages)
    reference = {'game':GAME,'filename':'source.xlsx','rewards':[
        {'type':'CREDIT','value':'Alz','qty':'4','tier':'Rare','rate':'0'},
        {'type':'CREDIT','value':'Alz','qty':'7','tier':'Common','rate':'100'},
    ]}
    payload = {'game':GAME,'do_save':True,'bundles':[{
        'client_key':'repeated-created','name':'Repeated','bundle_type':'RANDOM',
        'rewards':[{'type':'CREDIT','value':'cabalm-alz - Alz','qty':'4','tier':'Rare','rate':'0'},
                   {'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7','tier':'Common','rate':'100'}],
        'document_reference':reference,
    }]}
    response = client.post('/api/bundles/run',json=payload)
    assert response.status_code == 200, response.text
    result = response.json()['results'][0]
    assert response.json()['created'] == 1 and result['saved'] is True, response.text
    assert result['recheck']['outcome'] == outcome, response.text
    assert writes == [{'name':'Repeated','rewards':[
        {'type':'CREDIT','value':'Alz','qty':'7','tier':'0','rate':'100'},
        {'type':'CREDIT','value':'Alz','qty':'4','tier':'1','rate':'0'},
    ]}]
    history = client.get('/api/bundles/rechecks').json()['rows']
    assert len(history) == 1 and history[0]['history'][0]['outcome'] == outcome
    assert history[0]['submitted_values']['document_reference'] == reference
    assert client.post('/api/bundles/run',json=payload).status_code == 409
    assert len(writes) == 1 and unexpected == []


def test_preview_never_clicks_an_expander_outside_an_actual_reward_card(monkeypatch):
    html = item_form().replace('</form>', '''<button type="button" aria-label="ขยาย" aria-expanded="false"
onclick="fetch('/combo/cabalpc/shop/bundles',{method:'POST',body:'{}'})">Unrelated</button></form>''')
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    with pytest.raises(AztekLocatorError, match='การ์ด'):
        run_bundle(items=[{'id': '91', 'qty': '4', 'tier': 'Rare', 'rate': '0'}])
    assert writes == unexpected == []


@pytest.mark.parametrize('raw_rate,want', [(0, '0'), ('0', '0'), ('12.5', '12.5')])
def test_add_item_matches_exact_business_id_inside_active_panel(monkeypatch, raw_rate, want):
    writes, snapshots, unexpected = routed_bundle(monkeypatch, item_form())
    result, _ = run_bundle(items=[{'id': '91', 'qty': '4', 'tier': 'Rare', 'rate': raw_rate}])
    assert result['added'] == 1
    assert result['fields_complete'] is True
    fields = snapshots[0]
    assert next(e for e in fields if e['id'] == 'wrong')['value'] == 'untouched'
    assert next(e for e in fields if e['name'] == 'items.0.quantity')['value'] == '4'
    assert next(e for e in fields if e['id'] == 'items.0.secret_chance')['value'] == want
    assert next(e for e in fields if e['id'] == 'items.0.chance')['value'] == '77'
    assert writes == unexpected == []


def test_item_fill_does_not_overwrite_an_existing_currency_amount(monkeypatch):
    html = item_form().replace('</form>', '''<div><div><p>Ark Gem</p><span>WALLET</span>
<button type="button" aria-label="ย่อ" aria-expanded="true">Reward</button></div>
<input name="items.1.quantity" type="number" value="500"><select><option>Common</option></select>
</div></form>''')
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    result, _ = run_bundle(items=[{'id': '91', 'qty': '7', 'tier': 'Rare', 'rate': '100'}])
    assert result['fields_complete'] is True
    assert [e['value'] for e in snapshots[0] if e['name'].endswith('.quantity')] == ['7', '500']
    assert writes == unexpected == []


def test_search_waits_for_delayed_exact_item_result(monkeypatch):
    writes, snapshots, unexpected = routed_bundle(monkeypatch, item_form(delayed=True))
    result, _ = run_bundle(items=[{'id': '91', 'qty': '4', 'tier': 'Rare', 'rate': '0'}])
    assert result['added'] == 1
    assert result['fields_complete'] is True
    assert next(e for e in snapshots[0] if e['id'] == 'wrong')['value'] == 'untouched'
    assert writes == unexpected == []


def test_missing_item_never_clicks_an_unrelated_add_button(monkeypatch):
    writes, snapshots, unexpected = routed_bundle(monkeypatch, item_form(missing=True))
    result, _ = run_bundle(save=True, items=[{'id': '91', 'rate': '100'}])
    assert result['added'] == 0
    assert result['saved'] is False
    assert next(e for e in snapshots[0] if e['id'] == 'wrong')['value'] == 'untouched'
    assert writes == unexpected == []


def test_ambiguous_matching_item_stops_without_choosing_first(monkeypatch):
    writes, _, unexpected = routed_bundle(monkeypatch, item_form(duplicate=True))
    with pytest.raises(AztekLocatorError, match='91'):
        run_bundle(save=True, items=[{'id': '91', 'rate': '100'}])
    assert writes == unexpected == []


def test_matching_item_without_own_add_never_borrows_a_sibling_button(monkeypatch):
    html = item_form(missing=True).replace('</div><div id="cards">', '<div><span>ID: 91</span></div></div><div id="cards">')
    writes, snapshots, unexpected = routed_bundle(monkeypatch, html)
    with pytest.raises(AztekLocatorError, match='91'):
        run_bundle(save=True, items=[{'id': '91', 'rate': '100'}])
    assert next(e for e in snapshots[0] if e['id'] == 'wrong')['value'] == 'untouched'
    assert writes == unexpected == []


@pytest.mark.parametrize('mutation,field', [
    ('missing-name', 'ชื่อ Bundle'), ('duplicate-name', 'ชื่อ Bundle'),
    ('wrong-name', 'ชื่อ Bundle'), ('missing-switch', 'ส่งทันที'),
    ('wrong-switch', 'ส่งทันที'), ('invalid-switch-state', 'ส่งทันที'),
    ('duplicate-type', 'ประเภท Bundle'), ('missing-type', 'ประเภท Bundle'),
])
def test_broken_header_contract_stops_before_any_create(monkeypatch, mutation, field):
    html = HEADER
    if mutation == 'missing-name':
        html = html.replace('id="bundle-name"', 'id="renamed"')
    elif mutation == 'duplicate-name':
        html = html.replace('<input id="bundle-name"', '<input hidden id="bundle-name"><input id="bundle-name"')
    elif mutation == 'wrong-name':
        html = html.replace('id="bundle-name" name=', 'type="number" id="bundle-name" name=')
    elif mutation == 'missing-switch':
        html = html.replace('id="immediately-send"', 'id="renamed"')
    elif mutation == 'wrong-switch':
        html = html.replace('id="immediately-send" role="switch"', 'id="immediately-send" role="checkbox"')
    elif mutation == 'invalid-switch-state':
        html = html.replace('aria-checked="true"', 'aria-checked="mixed"')
    elif mutation == 'missing-type':
        html = html.replace('<select><option>FIXED</option><option>RANDOM</option></select>', '')
    else:
        html = html.replace('</form>', '<div><label>ประเภท Bundle *</label><button role="combobox">FIXED</button><select><option>RANDOM</option></select></div></form>')
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    with pytest.raises(AztekLocatorError, match=field):
        run_bundle(save=True)
    assert writes == unexpected == []


def test_batch_header_failure_reports_incomplete_and_never_reserves_a_write(monkeypatch):
    writes, _, unexpected = routed_bundle(monkeypatch, HEADER.replace('id="bundle-name"', 'id="renamed"'))
    checkpoints = []
    builder = bundle_runner.BundleBuilder(lambda *_: None)
    results = asyncio.run(builder.run_many('CabalPC TH', [
        {'name': 'Pack', 'type': 'RANDOM', 'items': []},
        {'name': 'Next', 'type': 'RANDOM', 'items': []},
    ], {'cookies': [], 'origins': []}, checkpoint=lambda bundle, entry: checkpoints.append(dict(entry))))
    assert len(results) == 1
    assert results[0]['saved'] is False
    assert results[0]['fields_complete'] is False
    assert 'ชื่อ Bundle' in results[0]['error']
    assert not results[0].get('creation_uncertain')
    assert checkpoints == writes == unexpected == []


@pytest.mark.parametrize('save', [False, True])
def test_public_api_reports_header_failure_and_preserves_session(client, monkeypatch, save):
    _connect_aztek(client)
    writes, _, unexpected = routed_bundle(monkeypatch, HEADER.replace('id="bundle-name"', 'id="renamed"'))
    response = client.post('/api/bundles/run', json={
        'game': GAME, 'do_save': save, 'bundles': [{
            'client_key': 'header-contract-failure', 'name': 'Pack',
            'items': [{'id': '91', 'qty': '4', 'tier': 'Rare'}],
        }]})
    if save:
        assert response.status_code == 200, response.text
        assert response.json()['created'] == 0
        result = response.json()['results'][0]
        assert result['saved'] is False
        assert result['fields_complete'] is False
        assert 'ชื่อ Bundle' in result['error']
    else:
        assert response.status_code == 502, response.text
        assert 'ชื่อ Bundle' in response.json()['detail']
    assert client.get('/api/aztek/status').json()['status'] == 'active'
    assert writes == unexpected == []


@pytest.mark.parametrize('save', [False, True])
def test_public_api_reports_reward_failure_and_preserves_session(client, monkeypatch, save):
    _connect_aztek(client)
    html = reward_form().replace('onclick="addReward(this)"', 'role="checkbox" onclick="addReward(this)"')
    writes, _, unexpected = routed_bundle(monkeypatch, html)
    response = client.post('/api/bundles/run', json={
        'game': GAME, 'do_save': save, 'bundles': [{
            'client_key': 'reward-contract-failure', 'name': 'Currency Pack', 'bundle_type': 'FIXED',
            'items': [], 'rewards': [{'type':'CREDIT','value':'cabalm-alz - Alz','qty':'7'}],
        }]})
    if save:
        assert response.status_code == 200, response.text
        assert response.json()['created'] == 0
        result = response.json()['results'][0]
        assert result['saved'] is False and result['fields_complete'] is False
        assert 'reward' in result['error']
        assert not result.get('creation_uncertain')
    else:
        assert response.status_code == 502, response.text
        assert 'reward' in response.json()['detail']
    assert client.get('/api/aztek/status').json()['status'] == 'active'
    assert writes == unexpected == []
