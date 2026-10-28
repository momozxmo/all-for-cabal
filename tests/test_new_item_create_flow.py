"""Create through the public API and real browser; replace external traffic only."""
import json
from types import SimpleNamespace

import pytest
from playwright.async_api import async_playwright

from web.models import Job
from test_new_item_import_api import one_draft
from test_new_item_reference_api import confirm
from test_new_item_reader import ORIGIN, saved_html
from test_web_validation import _connect_aztek

GAME = 'CabalM TH'
LIST = ORIGIN + '/combo/cabalm/shop/items'
POST = 'https://admin-api-v2.combo-interactive.com/cabalm/game/items'
GAME_UUID = '6eaad7c6-bfc8-48ce-a616-061a2cef8f41'
CREATE_GAMES = {
    'CabalM TH': ('cabalm', '6eaad7c6-bfc8-48ce-a616-061a2cef8f41'),
    'CabalPC TH': ('cabalpc', '97ac0f24-541a-486c-9d15-e9e1397b46ae'),
    'CabalPC SEA': ('cabalpcsea', '88a51177-8468-4bbc-8117-a717de2458a2'),
    'CabalM SEA': ('cabalmsea', '5f0740de-8045-42d4-8460-b03f340f01a6'),
}


def create_html(*, replay=False, corrupt='', game=GAME):
    # Observed IDs, fixed M GENERAL, no-ID submit and active confirmation.
    form = saved_html(game).replace('<h1>แก้ไข Item</h1><p>ID: <span>91</span></p>',
                                    '<h1>สร้าง Item</h1>')
    form = form.replace('<button type="submit">บันทึก</button>',
                        '<button type="submit">สร้าง Item</button>')
    form = form.replace('id="item-name"', 'id="item-name" data-owned="yes"')
    if game.startswith('CabalPC '):
        form = form.replace('role="combobox">GENERAL', 'role="combobox">เลือกหมวดหมู่')
        form = form.replace('<option value="GENERAL" selected>',
                            '<option value="" selected>เลือกหมวดหมู่</option><option value="GENERAL">')
        form += '''<script>document.querySelector('[role="combobox"]').onclick=()=>{
          const menu=document.createElement('div');menu.setAttribute('role','listbox');
          for(const value of ['GENERAL','CABALPC_PREMIUM']){
            const option=document.createElement('div');option.setAttribute('role','option');
            option.textContent=value;option.onclick=()=>{
              document.querySelector('select').value=value;
              document.querySelector('[role="combobox"]').textContent=value;menu.remove();};
            menu.append(option);}document.body.append(menu);};</script>'''
    script = '''<script>
    for (const b of document.querySelectorAll('[aria-checked]')) b.onclick=()=>{
      b.setAttribute('aria-checked', b.getAttribute('aria-checked')==='true'?'false':'true');
    };
    const f=document.querySelector('form');
    f.onsubmit=e=>{e.preventDefault();const d=document.createElement('div');
      d.setAttribute('role','alertdialog');d.innerHTML='<h2>ยืนยันการสร้าง</h2><p>ต้องการสร้าง Item ใช่หรือไม่?</p><button>ยกเลิก</button><button>ยืนยัน</button>';
      document.body.append(d);d.querySelector('button').onclick=()=>d.remove();
      d.querySelectorAll('button')[1].onclick=async()=>{
        const v=id=>document.getElementById(id).value;
        const data=new FormData();
        const fields={
          'data[th][name]':v('item-name'),'data[en][name]':v('item-name'),
          'data[th][detail]':v('item-detail'),'data[en][detail]':v('item-detail'),
          'data[game_item_type]':'GENERAL','data[game_item_id]':v('item-game-item-id'),
          'data[is_game_stackable]':'false',
          'data[game_options_1][itemOption]':v('item-option'),
          'data[game_options_1][durationIndex]':v('duration-index'),
          'data[game_options_1][tradeable]':document.getElementById('game-tradeable').getAttribute('aria-checked'),
          'data[display_options][is_tradable]':document.getElementById('game-tradeable').getAttribute('aria-checked')};
        CORRUPT
        for (const [k,v] of Object.entries(fields)) data.append(k,v);
        const file=f.querySelector('input[type=file]').files[0];
        if(file){data.append('files[th][thumbnail]',file);data.append('files[en][thumbnail]',file);}
        try { const pending=fetch('POST_URL',{method:'POST',body:data}); REPLAY await pending; } catch(e){}
      };};</script>'''
    post = 'https://admin-api-v2.combo-interactive.com/' + CREATE_GAMES[game][0] + '/game/items'
    if game != GAME:
        script = script.replace('[itemOption]', '[item_option]').replace('[durationIndex]', '[duration_index]')
    if game.startswith('CabalPC '):
        script = script.replace("'data[game_item_type]':'GENERAL'",
                                "'data[game_item_type]':document.querySelector('select').value")
    return form + script.replace('POST_URL', post).replace('CORRUPT', corrupt).replace(
        'REPLAY', "fetch('" + post + "',{method:'POST',body:data}).catch(()=>{});" if replay else '')


def receipt(*, game=GAME, **changes):
    data = {'id': 91, 'game_id': CREATE_GAMES[game][1], 'game_item_type': 'GENERAL',
            'game_item_id': 123, 'name': 'Synthetic name', 'detail': 'Synthetic description',
            'game_options_1': {'itemOption': 0, 'durationIndex': 0},
            'display_options': {'is_tradable': False}, 'thumbnail_url': None}
    data.update(changes)
    if game != GAME:
        data['game_options_1'] = {'item_option': '0', 'duration_index': '0'}
    return {'success': True, 'message': 'Game item created', 'data': {'data': data}}


def prepare(client, *, game=GAME, name='Synthetic name', item_type='GENERAL'):
    draft = one_draft(client, [name, 123, 0, 0, item_type, False,
                              'Synthetic description'], game=game)
    frozen = confirm(client, draft, game=game)
    return creation_entry(client, draft['draft_id'], frozen), frozen


def creation_entry(client, identity, frozen):
    # Seed a prior owned search through the real producer/storage boundary.
    # Search's browser/API integration is covered separately; creation still
    # uses the real route, form, POST matcher, checkpoints and readback.
    from web.new_item_store import NewItemRepository
    with client.app.state.database.session() as db:
        job = db.get(Job, identity)
        snapshot = NewItemRepository(db).record_search(job.owner_user_id, identity, frozen, [])
    return {'id': identity, 'revision': frozen['revision'], 'decision': 'create_new',
            'search_id': snapshot['search_id']}


def run(client, *entries, game=GAME):
    return client.post('/api/new-items/run', json={'game': game, 'selected': list(entries)})


def boundary(monkeypatch, test_database, identity, *, response=None, html=None,
             saved=None, lose=False, on_create=None, saved_id=91, cohort_ids=None, game=GAME):
    from web import new_item_runner
    observed = {'posts': [], 'unexpected': [], 'gets': [], 'checkpoints': [], 'attempts': []}
    list_url = ORIGIN + '/combo/' + CREATE_GAMES[game][0] + '/shop/items'
    post_url = 'https://admin-api-v2.combo-interactive.com/' + CREATE_GAMES[game][0] + '/game/items'

    class RoutedPlaywright:
        async def __aenter__(self):
            self.driver = await async_playwright().start()

            async def launch(**kwargs):
                browser = await self.driver.chromium.launch(**kwargs)

                async def new_context(**options):
                    context = await browser.new_context(**options)
                    context.on('request', lambda req: observed['attempts'].append((req.method, req.url)))

                    async def serve(route):
                        request = route.request
                        if request.method == 'GET' and request.url == list_url + '/create':
                            observed['gets'].append(request.url)
                            if on_create:
                                on_create()
                            await route.fulfill(body=html or create_html(game=game), content_type='text/html; charset=utf-8')
                        elif request.method == 'GET' and request.url == list_url + '/' + str(saved_id):
                            observed['gets'].append(request.url)
                            # The saved ID must already survive in another transaction.
                            with test_database.session() as db:
                                job = db.get(Job, identity)
                                observed['checkpoints'].append(job.result['creation']['state'])
                                assert job.result['creation']['item_id'] == str(saved_id)
                                if cohort_ids:
                                    observed['cohort_saved'] = [
                                        (db.get(Job, key).status, db.get(Job, key).result['creation'].get('item_id'))
                                        for key in cohort_ids]
                            await route.fulfill(body=saved or saved_html(game), content_type='text/html; charset=utf-8')
                        elif request.method == 'POST' and request.url == post_url:
                            observed['posts'].append(request.post_data_buffer)
                            with test_database.session() as db:
                                job = db.get(Job, identity)
                                observed['checkpoints'].append(job.status)
                                assert job.status == 'submitting'
                                assert job.result['creation']['state'] == 'submitting'
                                if cohort_ids:
                                    observed['cohort_post'] = [
                                        (db.get(Job, key).status, db.get(Job, key).result['creation']['state'])
                                        for key in cohort_ids]
                            if lose:
                                await route.abort()
                            else:
                                await route.fulfill(status=200, body=json.dumps(
                                    receipt(game=game, id=saved_id) if response is None else response),
                                    content_type='application/json', headers={'Access-Control-Allow-Origin': ORIGIN})
                        else:
                            observed['unexpected'].append((request.method, request.url))
                            await route.abort()
                    await context.route('**/*', serve)
                    return context
                return SimpleNamespace(new_context=new_context, close=browser.close)
            return SimpleNamespace(chromium=SimpleNamespace(launch=launch))

        async def __aexit__(self, *_args):
            await self.driver.stop()

    monkeypatch.setattr(new_item_runner, 'async_playwright', RoutedPlaywright)
    return observed


def test_create_commits_before_post_and_before_fresh_readback(client, test_database, monkeypatch):
    entry, frozen = prepare(client)
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entry['id'])
    response = run(client, entry)
    assert response.status_code == 200, response.text
    result = response.json()['items'][0]['result']
    assert result['creation']['state'] == 'saved'
    assert result['creation']['source'] == 'created'
    assert result['creation']['item_id'] == '91'
    assert result['recheck']['outcome'] == 'passed' and not result['recheck']['incomplete']
    row = client.get('/api/new-items/history').json()['rows'][0]
    assert row['frozen'] == frozen and row['state'] == 'saved'
    assert observed['checkpoints'] == ['submitting', 'saved']
    assert len(observed['posts']) == 1 and not observed['unexpected']
    assert run(client, entry).status_code == 409
    assert len(observed['posts']) == 1


@pytest.mark.parametrize('game', ['CabalPC TH', 'CabalPC SEA', 'CabalM SEA'])
def test_proven_game_commits_once_then_reads_saved_item(client, test_database, monkeypatch, game):
    entry, _ = prepare(client, game=game)
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entry['id'], game=game)
    response = run(client, entry, game=game)
    assert response.status_code == 200, response.text
    result = response.json()['items'][0]['result']
    assert result['creation']['state'] == 'saved'
    assert result['creation']['item_id'] == '91'
    assert result['recheck']['outcome'] == 'passed' and not result['recheck']['incomplete']
    assert observed['checkpoints'] == ['submitting', 'saved']
    assert len(observed['posts']) == 1 and not observed['unexpected']
    body = observed['posts'][0]
    assert b'data[game_options_1][item_option]' in body
    assert b'data[game_options_1][duration_index]' in body
    assert b'data[game_options_1][itemOption]' not in body
    assert run(client, entry, game=game).status_code == 409
    assert len(observed['posts']) == 1


@pytest.mark.parametrize('game', ['CabalPC TH', 'CabalPC SEA', 'CabalM SEA'])
@pytest.mark.parametrize('change', ['casing', 'other_game_endpoint', 'other_game_receipt', 'replay'])
def test_proven_game_still_stops_cross_game_contract_or_replay(
        client, test_database, monkeypatch, game, change):
    entry, _ = prepare(client, game=game)
    _connect_aztek(client)
    html = create_html(game=game, replay=change == 'replay')
    response_body = receipt(game=game)
    if change == 'casing':
        html = html.replace('[item_option]', '[itemOption]')
    elif change == 'other_game_endpoint':
        html = html.replace('/' + CREATE_GAMES[game][0] + '/game/items', '/cabalm/game/items')
    elif change == 'other_game_receipt':
        response_body = receipt()
    observed = boundary(monkeypatch, test_database, entry['id'], game=game,
                        html=html, response=response_body)
    response = run(client, entry, game=game)
    row = client.get('/api/new-items/history').json()['rows'][0]
    if change in ('casing', 'other_game_endpoint'):
        assert response.status_code == 409, response.text
        assert not observed['posts'] and row['state'] == 'confirmed'
    else:
        assert response.status_code == 200, response.text
        assert len(observed['posts']) == 1
        assert row['state'] == ('saved' if change == 'replay' else 'unconfirmed')
        if change == 'other_game_receipt':
            assert not row['result']['creation'].get('item_id')
        else:
            post = 'https://admin-api-v2.combo-interactive.com/' + CREATE_GAMES[game][0] + '/game/items'
            assert observed['attempts'].count(('POST', post)) == 2
    assert not observed['unexpected']


@pytest.mark.parametrize('game', ['CabalPC TH', 'CabalPC SEA'])
def test_pc_premium_uses_selected_type_without_converting_to_general(
        client, test_database, monkeypatch, game):
    entry, _ = prepare(client, game=game, item_type='CABALPC_PREMIUM')
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entry['id'], game=game,
        response=receipt(game=game, game_item_type='CABALPC_PREMIUM'), saved=premium_saved_html(game))
    response = run(client, entry, game=game)
    assert response.status_code == 200, response.text
    result = response.json()['items'][0]['result']
    assert result['creation']['state'] == 'saved' and result['creation']['item_id'] == '91'
    assert result['recheck']['outcome'] == 'passed' and not result['recheck']['incomplete']
    assert result['recheck']['actual']['values']['item_type'] == 'CABALPC_PREMIUM'
    assert len(observed['posts']) == 1 and not observed['unexpected']
    assert b'CABALPC_PREMIUM' in observed['posts'][0]
    row = client.get('/api/new-items/history').json()['rows'][0]
    assert row['frozen']['submitted_values']['item_type'] == 'CABALPC_PREMIUM'


def premium_saved_html(game):
    # Observed PC select schema, synthetic Premium saved state (not a live receipt).
    return saved_html(game).replace('role="combobox">GENERAL', 'role="combobox">CABALPC_PREMIUM').replace(
        '<option value="GENERAL" selected>', '<option value="GENERAL">').replace(
        '<option value="CABALPC_PREMIUM">', '<option value="CABALPC_PREMIUM" selected>')


@pytest.mark.parametrize('game', ['CabalPC TH', 'CabalPC SEA'])
def test_premium_receipt_cannot_substitute_general_identity(client, test_database, monkeypatch, game):
    entry, _ = prepare(client, game=game, item_type='CABALPC_PREMIUM')
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entry['id'], game=game, response=receipt(game=game))
    response = run(client, entry, game=game)
    assert response.status_code == 200, response.text
    creation = response.json()['items'][0]['result']['creation']
    assert creation['state'] == 'unconfirmed' and not creation.get('item_id')
    assert len(observed['posts']) == 1 and len(observed['gets']) == 1


@pytest.mark.parametrize('game', ['CabalPC TH', 'CabalPC SEA'])
@pytest.mark.parametrize('change', ['unknown_option', 'duplicate_trigger'])
def test_pc_type_contract_break_stops_before_post(client, test_database, monkeypatch, game, change):
    entry, _ = prepare(client, game=game)
    _connect_aztek(client)
    html = create_html(game=game)
    if change == 'unknown_option':
        html = html.replace('<option value="CABALPC_PREMIUM">', '<option value="UNKNOWN">')
    else:
        html = html.replace('<select aria-hidden=', '<button type="button" role="combobox">GENERAL</button><select aria-hidden=')
    observed = boundary(monkeypatch, test_database, entry['id'], game=game, html=html)
    assert run(client, entry, game=game).status_code == 409
    assert not observed['posts'] and not observed['unexpected']
    assert client.get('/api/new-items/history').json()['rows'][0]['state'] == 'confirmed'


def test_lost_response_is_unconfirmed_and_cannot_repeat(client, test_database, monkeypatch):
    first, _ = prepare(client)
    second, _ = prepare(client, name='Second item')
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, first['id'], lose=True)
    response = run(client, first, second)
    assert response.status_code == 200, response.text
    rows = {r['id']: r for r in client.get('/api/new-items/history').json()['rows']}
    assert rows[first['id']]['state'] == 'unconfirmed'
    assert rows[first['id']]['result']['creation']['state'] == 'unconfirmed'
    assert rows[second['id']]['state'] == 'confirmed'
    assert run(client, first).status_code == 409
    assert len(observed['posts']) == 1 and not observed['unexpected']


@pytest.mark.parametrize('response', [
    {'success': False, 'data': {'data': {'id': 91, 'game_id': GAME_UUID}}},
    {'success': True, 'data': {'id': 91, 'game_id': GAME_UUID}},
    receipt(id=True), receipt(id=0), receipt(id='91'), receipt(game_id='another-game'),
])
def test_ambiguous_response_never_invents_saved_id(client, test_database, monkeypatch, response):
    entry, _ = prepare(client)
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entry['id'], response=response)
    result = run(client, entry)
    assert result.status_code == 200, result.text
    creation = result.json()['items'][0]['result']['creation']
    assert creation['state'] == 'unconfirmed' and not creation.get('item_id')
    assert len(observed['posts']) == 1 and observed['gets'] == [LIST + '/create']


def test_frontend_retry_is_blocked_and_saved_id_retained_on_readback_failure(
        client, test_database, monkeypatch):
    entry, _ = prepare(client)
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entry['id'], html=create_html(replay=True),
                        saved=saved_html(GAME).replace('id="item-option"', 'id="broken-option"'))
    response = run(client, entry)
    assert response.status_code == 200, response.text
    result = response.json()['items'][0]['result']
    assert result['creation']['state'] == 'saved' and result['creation']['item_id'] == '91'
    assert result['recheck']['incomplete'] and result['recheck']['outcome'] == 'failed'
    assert len(observed['posts']) == 1 and not observed['unexpected']
    assert observed['attempts'].count(('POST', POST)) == 2


def test_payload_tampering_never_reaches_server_or_claims_submission(client, test_database, monkeypatch):
    entry, _ = prepare(client)
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entry['id'], html=create_html(
        corrupt="fields['data[game_item_id]']='999';"))
    response = run(client, entry)
    assert response.status_code == 409, response.text
    assert not observed['posts'] and not observed['unexpected']
    row = client.get('/api/new-items/history').json()['rows'][0]
    assert row['state'] == 'confirmed' and not row['result'].get('creation')


def test_mismatch_stops_before_next_confirmed_item(client, test_database, monkeypatch):
    first, _ = prepare(client)
    second, _ = prepare(client, name='Second item')
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, first['id'], saved=saved_html(GAME).replace(
        'value="Synthetic name"', 'value="Saved wrong name"'))
    response = run(client, first, second)
    assert response.status_code == 200, response.text
    assert response.json()['items'][0]['result']['recheck']['outcome'] == 'mismatch'
    rows = {r['id']: r for r in client.get('/api/new-items/history').json()['rows']}
    assert rows[second['id']]['state'] == 'confirmed'
    assert len(observed['posts']) == 1


def test_exact_private_image_is_sent_twice_in_one_post_not_a_separate_upload(
        client, test_database, monkeypatch):
    from test_new_item_media import attach, image_bytes
    draft = one_draft(client, ['Synthetic name', 123, 0, 0, 'GENERAL', False,
                              'Synthetic description'], game=GAME)
    attached = attach(client, draft)
    assert attached.status_code == 200, attached.text
    updated = attached.json()
    frozen = confirm(client, updated, game=GAME)
    entry = creation_entry(client, draft['draft_id'], frozen)
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entry['id'], saved=saved_html(GAME, image=True))
    response = run(client, entry)
    assert response.status_code == 200, response.text
    result = response.json()['items'][0]['result']
    assert result['creation']['state'] == 'saved'
    assert len(observed['posts']) == 1 and not observed['unexpected']
    body = observed['posts'][0]
    assert body.count(image_bytes()) == 2
    assert b'files[th][thumbnail]' in body and b'files[en][thumbnail]' in body
    # Presence alone is not a claim of image-content equality.
    assert result['recheck']['image_status'] != 'verified'


def test_other_owner_stale_revision_and_missing_session_open_no_browser(
        client, client_for, other_member, test_database, monkeypatch):
    entry, _ = prepare(client)
    observed = boundary(monkeypatch, test_database, entry['id'])
    assert run(client_for(other_member), entry).status_code == 404
    assert run(client, dict(entry, revision=entry['revision'] + 1)).status_code == 409
    assert run(client, entry).status_code == 409
    assert not observed['gets'] and not observed['posts']


def test_entire_selection_is_checked_before_first_browser(client, test_database, monkeypatch):
    first, _ = prepare(client)
    second, _ = prepare(client, name='Second')
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, first['id'])
    assert run(client, first, dict(second, revision=99)).status_code == 409
    assert run(client, first, first).status_code == 400
    assert not observed['gets'] and not observed['posts']
    assert all(r['state'] == 'confirmed' for r in client.get('/api/new-items/history').json()['rows'])


def test_explicit_decision_and_no_client_success_flags(client):
    entry, _ = prepare(client)
    for changed in [dict(entry, decision='use_existing'),
                    {k: v for k, v in entry.items() if k != 'decision'},
                    dict(entry, passed=True), dict(entry, actual={'id': 91})]:
        assert run(client, changed).status_code == 422


def test_changed_checkpoint_while_waiting_for_gate_stops_before_browser(
        client, application, test_database, monkeypatch):
    from contextlib import asynccontextmanager
    entry, _ = prepare(client)
    _connect_aztek(client)
    @asynccontextmanager
    async def changed_slot():
        with test_database.session() as db:
            db.get(Job, entry['id']).status = 'unconfirmed'
        yield
    monkeypatch.setattr(application.state.browser_gate, 'slot', changed_slot)
    observed = boundary(monkeypatch, test_database, entry['id'])
    assert run(client, entry).status_code == 409
    assert not observed['gets'] and not observed['posts']


def test_two_simultaneous_api_runs_forward_only_once(
        client, test_database, monkeypatch):
    import asyncio
    import httpx
    entry, _ = prepare(client)
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entry['id'])
    async def scenario():
        # A real ASGI server has one loop; two TestClient worker loops would
        # artificially deadlock the shared asyncio gate, not test HTTP concurrency.
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app),
                base_url='http://testserver', cookies=client.cookies) as requests:
            return await asyncio.wait_for(asyncio.gather(*[
                requests.post('/api/new-items/run', json={'game': GAME, 'selected': [entry]})
                for _ in range(2)]), timeout=40)
    responses = asyncio.run(scenario())
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    assert len(observed['posts']) == 1 and not observed['unexpected']


@pytest.mark.parametrize('change', ['host', 'operation', 'method', 'json_body', 'duplicate', 'frame'])
def test_unowned_or_unexpected_write_request_is_never_forwarded(
        client, test_database, monkeypatch, change):
    entry, _ = prepare(client)
    _connect_aztek(client)
    html = create_html()
    if change == 'host':
        html = html.replace(POST, POST.replace('admin-api-v2.', 'not-the-api.'))
    elif change == 'operation':
        html = html.replace(POST, POST + '/delete')
    elif change == 'method':
        html = html.replace("method:'POST'", "method:'PUT'")
    elif change == 'json_body':
        html = html.replace('body:data', "body:JSON.stringify({id:91})")
    elif change == 'duplicate':
        html = html.replace('const file=', "data.append('data[th][name]','Duplicate');const file=")
    else:
        html = html.replace('<main>', '<iframe src="about:blank"></iframe><main>')
        html = html.replace('const pending=fetch(',
                            "const pending=document.querySelector('iframe').contentWindow.fetch(")
    observed = boundary(monkeypatch, test_database, entry['id'], html=html)
    assert run(client, entry).status_code == 409
    assert not observed['posts'] and not observed['unexpected']
    row = client.get('/api/new-items/history').json()['rows'][0]
    assert row['state'] == 'confirmed' and not row['result'].get('creation')


def test_claim_revalidates_after_page_load_before_any_post_is_forwarded(
        client, test_database, monkeypatch):
    entry, _ = prepare(client)
    _connect_aztek(client)
    def change_state():
        with test_database.session() as db:
            db.get(Job, entry['id']).status = 'unconfirmed'
    observed = boundary(monkeypatch, test_database, entry['id'], on_create=change_state)
    assert run(client, entry).status_code == 409
    assert not observed['posts'] and not observed['unexpected']
    assert client.get('/api/new-items/history').json()['rows'][0]['state'] == 'unconfirmed'


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'wrong_type'])
def test_broken_known_name_id_never_uses_misleading_fallback_or_submits(
        client, test_database, monkeypatch, change):
    entry, _ = prepare(client)
    _connect_aztek(client)
    html = create_html()
    if change == 'missing':
        html = html.replace('id="item-name" data-owned="yes"', 'id="broken-name"')
    elif change == 'duplicate':
        html = html.replace('<input id="item-name"', '<input id="item-name"><input id="item-name"')
    else:
        html = html.replace('<input id="item-name"', '<input type="hidden" id="item-name"')
    observed = boundary(monkeypatch, test_database, entry['id'], html=html)
    assert run(client, entry).status_code == 409
    assert not observed['posts']
    assert client.get('/api/new-items/history').json()['rows'][0]['state'] == 'confirmed'
