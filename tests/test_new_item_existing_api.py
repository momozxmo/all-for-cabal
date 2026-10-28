"""Real public API/storage/Finder/readback; only external browser traffic is routed."""
from contextlib import asynccontextmanager
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest
from playwright.async_api import async_playwright

from web.models import Job
from test_new_item_import_api import one_draft
from test_new_item_reference_api import confirm
from test_new_item_reader import GAMES, ORIGIN, saved_html
from test_web_validation import _connect_aztek


def confirmed(client, game='CabalPC TH'):
    draft = one_draft(client, ['Synthetic name', 123, 0, 0, 'GENERAL', False,
                              'Synthetic description'], game=game)
    return draft, confirm(client, draft, game=game)


def boundary(monkeypatch, game, *, broken=None, changed=False, paged=False,
             empty=False, probe_write=False, on_detail=None):
    """Keep browser and real readers; reject every non-fixture request."""
    from web import new_item_runner
    slug = dict(GAMES)[game]
    base = f'{ORIGIN}/combo/{slug}/shop/items'
    requests, unexpected = [], []
    link = f'{base}/91'
    if broken == 'foreign_link':
        link = 'https://other.invalid/items/91'
    anchors = f'<a href="{link}">เปิด</a>'
    if broken == 'missing_link':
        anchors = ''
    if broken == 'duplicate_link':
        anchors *= 2
    rows = (f'<tr><td>91</td><td>List name is not identity{anchors}</td>'
            '<td>123</td><td>0</td><td>0</td></tr>'
            f'<tr><td>92</td><td>Another<a href="{base}/92">เปิด</a></td>'
            '<td>123</td><td>0</td><td>0</td></tr>'
            f'<tr><td>93</td><td>Different option<a href="{base}/93">เปิด</a></td>'
            '<td>123</td><td>9</td><td>0</td></tr>')
    list_html = '''<main><form onsubmit="event.preventDefault();
      if(this.querySelector('input').value!=='123') document.querySelector('tbody').innerHTML=''">
      <input type="text" placeholder="ค้นหา Item..."><button type="submit">ค้นหา</button></form>
      <table><thead><tr><th>Aztek Item Id</th><th>ชื่อ</th><th>ItemKind</th>
      <th>ItemOption</th><th>DurationIndex</th></tr></thead><tbody>''' + rows + '''</tbody></table>
      <button disabled>Next ›</button></main>'''
    if paged:
        second = (f'<tr><td>92</td><td>Another<a href="{base}/92">เปิด</a></td>'
                  '<td>123</td><td>0</td><td>0</td></tr>')
        list_html = list_html.replace(second, '')
        list_html = list_html.replace('<button disabled>Next ›</button>',
            '<button id="pager" onclick="nextPage()">Next ›</button>')
        list_html += '<script>function nextPage(){document.querySelector("tbody").innerHTML=' + json.dumps(second) + ';document.getElementById("pager").disabled=true;}</script>'
    if empty:
        start, end = list_html.index('<table>'), list_html.index('</table>') + len('</table>')
        list_html = list_html[:start] + '<p>ไม่พบ Item ที่ตรงกับเงื่อนไข</p>' + list_html[end:]
    if probe_write:
        list_html += "<script>fetch('/not-allowed-write',{method:'POST'}).catch(()=>{});</script>"
    html = saved_html(game)
    if changed:
        html = html.replace('value="Synthetic name"', 'value="Changed after search"')
    if broken == 'wrong_saved_id':
        html = html.replace('ID: <span>91</span>', 'ID: <span>99</span>')
    class RoutedPlaywright:
        async def __aenter__(self):
            self.driver = await async_playwright().start()
            async def launch(**kwargs):
                browser = await self.driver.chromium.launch(**kwargs)
                async def new_context(**options):
                    context = await browser.new_context(**options)
                    async def serve(route):
                        r = route.request
                        requests.append((r.method, r.url))
                        if r.method == 'GET' and r.url == base:
                            await route.fulfill(body=list_html, content_type='text/html; charset=utf-8')
                        elif r.method == 'GET' and r.url == base + '/91':
                            if on_detail:
                                on_detail()
                            await route.fulfill(body=html, content_type='text/html; charset=utf-8')
                        else:
                            unexpected.append((r.method, r.url))
                            await route.abort()
                    await context.route('**/*', serve)
                    return context
                return SimpleNamespace(new_context=new_context, close=browser.close)
            return SimpleNamespace(chromium=SimpleNamespace(launch=launch))
        async def __aexit__(self, *_args):
            await self.driver.stop()
    monkeypatch.setattr(new_item_runner, 'async_playwright', RoutedPlaywright)
    return requests, unexpected


def search(client, draft, game='CabalPC TH'):
    r = client.post('/api/new-items/search', json={
        'game': game, 'selected': [{'id': draft['draft_id'], 'revision': draft['revision']}]})
    assert r.status_code == 200, r.text
    return r.json()['searches'][0]


def choose(client, draft, snapshot, **overrides):
    return client.post(f"/api/new-items/{draft['draft_id']}/use-existing", json={
        'game': snapshot['game'], 'revision': draft['revision'],
        'search_id': snapshot['search_id'], 'item_id': '91', **overrides})


@pytest.mark.parametrize('game,slug', GAMES)
def test_multiple_candidates_need_explicit_choice_and_fresh_readback(
        client, monkeypatch, game, slug):
    draft, frozen = confirmed(client, game)
    _connect_aztek(client)
    requests, unexpected = boundary(monkeypatch, game)
    snapshot = search(client, draft, game)
    assert [c['item_id'] for c in snapshot['candidates']] == ['91', '92']
    before = client.get('/api/new-items/history').json()['rows'][0]
    assert before['state'] == 'confirmed' and not before['result']
    assert before['frozen'] == frozen
    result = choose(client, draft, snapshot)
    assert result.status_code == 200, result.text
    stored = result.json()
    assert stored['creation']['source'] == 'existing'
    assert stored['creation']['state'] == 'saved' and stored['creation']['item_id'] == '91'
    assert stored['recheck']['outcome'] == 'passed' and not stored['recheck']['incomplete']
    assert stored['recheck']['actual']['values']['name'] == 'Synthetic name'
    after = client.get('/api/new-items/history').json()['rows'][0]
    assert after['frozen'] == frozen
    assert after['history'][-1]['event'] == 'use_existing'
    selected = client.post('/api/new-items/handoff', json={
        'game': game, 'selected_ids': [draft['draft_id']],
        'occurrence_ids': [o['occurrence_id'] for o in frozen['occurrences']]})
    assert selected.status_code == 200, selected.text
    assert requests == [('GET', f'{ORIGIN}/combo/{slug}/shop/items'),
                        ('GET', f'{ORIGIN}/combo/{slug}/shop/items/91')]
    assert unexpected == []
    # A second click cannot choose/recheck silently again.
    assert choose(client, draft, snapshot).status_code == 409
    assert len(requests) == 2


def test_existing_selection_keeps_fresh_difference_and_cannot_handoff(client, monkeypatch):
    draft, frozen = confirmed(client)
    _connect_aztek(client)
    boundary(monkeypatch, 'CabalPC TH', changed=True)
    snapshot = search(client, draft)
    result = choose(client, draft, snapshot)
    assert result.status_code == 200, result.text
    assert result.json()['recheck']['outcome'] == 'mismatch'
    assert result.json()['recheck']['actual']['values']['name'] == 'Changed after search'
    assert client.post('/api/new-items/handoff', json={
        'game': 'CabalPC TH', 'selected_ids': [draft['draft_id']],
        'occurrence_ids': [o['occurrence_id'] for o in frozen['occurrences']]}).status_code == 409


@pytest.mark.parametrize('broken', ['foreign_link', 'missing_link', 'duplicate_link'])
def test_unsupported_list_link_cannot_materialize_candidate(client, monkeypatch, broken):
    draft, frozen = confirmed(client)
    _connect_aztek(client)
    requests, unexpected = boundary(monkeypatch, 'CabalPC TH', broken=broken)
    r = client.post('/api/new-items/search', json={
        'game': 'CabalPC TH', 'selected': [{'id': draft['draft_id'], 'revision': draft['revision']}]})
    assert r.status_code == 409, r.text
    row = client.get('/api/new-items/history').json()['rows'][0]
    assert row['state'] == 'confirmed' and row['frozen'] == frozen and not row['result']
    assert all(method == 'GET' for method, _ in requests) and not unexpected


@pytest.mark.parametrize('change', ['item_id', 'search_id', 'revision', 'game'])
def test_only_current_owned_confirmed_candidate_can_be_used(client, monkeypatch, change):
    draft, frozen = confirmed(client)
    _connect_aztek(client)
    requests, unexpected = boundary(monkeypatch, 'CabalPC TH')
    snapshot = search(client, draft)
    values = {'item_id': '999', 'search_id': 'stale', 'revision': 99, 'game': 'CabalM TH'}
    response = choose(client, draft, snapshot, **{change: values[change]})
    assert response.status_code == 409, response.text
    assert len(requests) == 1 and unexpected == []
    assert client.get('/api/new-items/history').json()['rows'][0]['frozen'] == frozen


def test_search_and_choice_are_owned_and_require_session(
        client, client_for, other_member, monkeypatch):
    draft, _ = confirmed(client)
    body = {'game': 'CabalPC TH', 'selected': [{'id': draft['draft_id'], 'revision': draft['revision']}]}
    assert client.post('/api/new-items/search', json=body).status_code == 409
    other = client_for(other_member)
    assert other.post('/api/new-items/search', json=body).status_code == 404
    assert other.post(f"/api/new-items/{draft['draft_id']}/use-existing", json={
        'game': 'CabalPC TH', 'revision': draft['revision'], 'search_id': 'x', 'item_id': '91'
    }).status_code == 404


@pytest.mark.parametrize('state', ['draft', 'submitting', 'unconfirmed'])
def test_search_cannot_reset_unconfirmed_or_unready_job(client, test_database, state):
    draft, _ = confirmed(client)
    with test_database.session() as db:
        record = db.get(Job, draft['draft_id'])
        record.status = state
    r = client.post('/api/new-items/search', json={
        'game': 'CabalPC TH', 'selected': [{'id': draft['draft_id'], 'revision': draft['revision']}]})
    assert r.status_code == 409, r.text
    assert client.get('/api/new-items/history').json()['rows'][0]['state'] == state


def test_new_search_invalidates_old_choice_without_creating(client, monkeypatch):
    draft, _ = confirmed(client)
    _connect_aztek(client)
    requests, unexpected = boundary(monkeypatch, 'CabalPC TH')
    first, latest = search(client, draft), search(client, draft)
    assert latest['search_id'] != first['search_id']
    assert choose(client, draft, first).status_code == 409
    assert len(requests) == 2 and unexpected == []


def test_client_cannot_invent_candidate_url_actual_or_passed(client):
    draft, _ = confirmed(client)
    r = client.post(f"/api/new-items/{draft['draft_id']}/use-existing", json={
        'game': 'CabalPC TH', 'revision': draft['revision'], 'search_id': 'fake', 'item_id': '91',
        'detail_url': 'https://other.invalid', 'actual': {}, 'passed': True})
    assert r.status_code == 422


def test_wrong_saved_identity_cannot_change_confirmed_draft(client, monkeypatch):
    draft, frozen = confirmed(client)
    _connect_aztek(client)
    requests, unexpected = boundary(monkeypatch, 'CabalPC TH', broken='wrong_saved_id')
    snapshot = search(client, draft)
    r = choose(client, draft, snapshot)
    assert r.status_code == 409, r.text
    row = client.get('/api/new-items/history').json()['rows'][0]
    assert row['state'] == 'confirmed' and row['frozen'] == frozen and not row['result']
    assert len(requests) == 2 and unexpected == []


@pytest.mark.parametrize('operation', ['search', 'choose'])
def test_browser_gate_revalidates_state_before_navigation(client, test_database, monkeypatch, operation):
    draft, _ = confirmed(client)
    _connect_aztek(client)
    requests, unexpected = boundary(monkeypatch, 'CabalPC TH')
    snapshot = search(client, draft) if operation == 'choose' else None
    before = len(requests)
    class ChangedWhileWaiting:
        @asynccontextmanager
        async def slot(self):
            with test_database.session() as db:
                job = db.get(Job, draft['draft_id'])
                job.status = 'unconfirmed'
            yield
    monkeypatch.setattr(client.app.state, 'browser_gate', ChangedWhileWaiting())
    if operation == 'choose':
        result = choose(client, draft, snapshot)
    else:
        result = client.post('/api/new-items/search', json={'game': 'CabalPC TH',
            'selected': [{'id': draft['draft_id'], 'revision': draft['revision']}]})
    assert result.status_code == 409, result.text
    assert len(requests) == before and not unexpected
    assert client.get('/api/new-items/history').json()['rows'][0]['state'] == 'unconfirmed'


def test_search_collects_all_pages_before_option_duration_filter(client, monkeypatch):
    draft, _ = confirmed(client)
    _connect_aztek(client)
    remote, unexpected = boundary(monkeypatch, 'CabalPC TH', paged=True)
    snapshot = search(client, draft)
    assert [c['item_id'] for c in snapshot['candidates']] == ['91', '92']
    assert all(c['option'] == '0' and c['duration'] == '0' for c in snapshot['candidates'])
    assert len(remote) == 1 and not unexpected


def test_completed_empty_search_does_not_create_or_pass(client, monkeypatch):
    draft, frozen = confirmed(client)
    _connect_aztek(client)
    boundary(monkeypatch, 'CabalPC TH', empty=True)
    assert search(client, draft)['candidates'] == []
    row = client.get('/api/new-items/history').json()['rows'][0]
    assert row['state'] == 'confirmed' and not row['result'] and row['frozen'] == frozen


def test_search_blocks_page_initiated_write(client, monkeypatch):
    draft, _ = confirmed(client)
    _connect_aztek(client)
    requests, unexpected = boundary(monkeypatch, 'CabalPC TH', probe_write=True)
    assert len(search(client, draft)['candidates']) == 2
    assert all(method == 'GET' for method, _ in requests) and not unexpected


def test_changed_search_during_readback_cannot_overwrite_latest_snapshot(client, test_database, monkeypatch):
    draft, frozen = confirmed(client)
    _connect_aztek(client)
    boundary(monkeypatch, 'CabalPC TH')
    snapshot = search(client, draft)
    def change_snapshot():
        with test_database.session() as db:
            record = db.get(Job, draft['draft_id'])
            config = deepcopy(record.config)
            config['search']['search_id'] = 'newer-search'
            record.config = config
    requests, unexpected = boundary(monkeypatch, 'CabalPC TH', on_detail=change_snapshot)
    assert choose(client, draft, snapshot).status_code == 409
    row = client.get('/api/new-items/history').json()['rows'][0]
    assert row['state'] == 'confirmed' and not row['result'] and row['frozen'] == frozen
    assert row['search']['search_id'] == 'newer-search'
    assert len(requests) == 1 and not unexpected
