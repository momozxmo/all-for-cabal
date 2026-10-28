"""Real API/storage/reader/comparison; only Aztek browser traffic is replaced."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from playwright.async_api import async_playwright

from web.models import Job
from test_new_item_import_api import one_draft
from test_new_item_reference_api import confirm
from test_new_item_reader import GAMES, ORIGIN, saved_html
from test_web_validation import _connect_aztek


def saved_checkpoint(client, test_database, game='CabalPC TH'):
    # Storage seam: a previously saved checkpoint, not a fabricated runner return.
    draft = one_draft(client, ['Synthetic name', 123, 0, 0, 'GENERAL', False,
                              'Synthetic description'], game=game)
    frozen = confirm(client, draft, game=game)
    url = f'{ORIGIN}/combo/{dict(GAMES)[game]}/shop/items/91'
    creation = {'state': 'saved', 'item_id': '91', 'evidence': {'detail_url': url}}
    with test_database.session() as db:
        record = db.get(Job, draft['draft_id'])
        record.result = {'creation': creation}
        record.status = 'saved'
    return draft['draft_id'], frozen, creation


def browser_boundary(monkeypatch, html):
    # Removing the reader or comparator must break these API assertions.
    import importlib.util
    assert importlib.util.find_spec('web.new_item_runner'), 'New Item read-only runner missing'
    from web import new_item_runner
    requests, unexpected = [], []

    class RoutedPlaywright:
        async def __aenter__(self):
            self.driver = await async_playwright().start()

            async def launch(**kwargs):
                browser = await self.driver.chromium.launch(**kwargs)

                async def new_context(**options):
                    context = await browser.new_context(**options)

                    async def serve(route):
                        request = route.request
                        requests.append((request.method, request.url))
                        if request.method == 'GET' and request.url in {
                            f'{ORIGIN}/combo/{slug}/shop/items/91' for _, slug in GAMES
                        }:
                            await route.fulfill(body=html, content_type='text/html; charset=utf-8')
                        else:
                            unexpected.append((request.method, request.url))
                            await route.abort()
                    await context.route('**/*', serve)
                    return context
                return SimpleNamespace(new_context=new_context, close=browser.close)
            return SimpleNamespace(chromium=SimpleNamespace(launch=launch))

        async def __aexit__(self, *_args):
            await self.driver.stop()

    monkeypatch.setattr(new_item_runner, 'async_playwright', RoutedPlaywright)
    return requests, unexpected


@pytest.mark.parametrize('game,slug', GAMES)
def test_recheck_is_read_only_and_uses_fresh_saved_fields(
        client, test_database, monkeypatch, game, slug):
    identity, frozen, creation = saved_checkpoint(client, test_database, game)
    _connect_aztek(client)
    requests, unexpected = browser_boundary(monkeypatch, saved_html(game))
    response = client.post(f'/api/new-items/{identity}/recheck', json={})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['creation'] == creation
    assert result['recheck']['outcome'] == 'passed'
    assert result['recheck']['incomplete'] is False
    assert result['recheck']['actual']['values'] == {
        key: value for key, value in frozen['submitted_values'].items() if key != 'image_key'}
    assert result['recheck']['actual']['evidence']['identity_verified'] is True
    history = client.get('/api/new-items/history').json()['rows']
    assert len(history) == 1 and len(history[0]['history']) == 1
    assert history[0]['history'][0]['recheck'] == result['recheck']
    assert history[0]['frozen'] == frozen
    assert requests == [('GET', creation['evidence']['detail_url'])]
    assert unexpected == []


def test_difference_and_unreadable_both_visible_from_api(client, test_database, monkeypatch):
    identity, _, creation = saved_checkpoint(client, test_database)
    _connect_aztek(client)
    html = saved_html('CabalPC TH').replace('value="Synthetic name"', 'value="Different"')
    html = html.replace('aria-checked="false"', 'aria-checked="mixed"')
    requests, unexpected = browser_boundary(monkeypatch, html)
    response = client.post(f'/api/new-items/{identity}/recheck', json={})
    assert response.status_code == 200, response.text
    checked = response.json()['recheck']
    assert checked['outcome'] == 'mismatch' and checked['incomplete'] is True
    assert checked['actual']['values']['tradeable'] is None
    assert response.json()['creation'] == creation
    assert all(method == 'GET' for method, _ in requests) and unexpected == []


def test_recheck_appends_history_without_changing_previous_attempt(client, test_database, monkeypatch):
    identity, frozen, creation = saved_checkpoint(client, test_database)
    _connect_aztek(client)
    browser_boundary(monkeypatch, saved_html('CabalPC TH').replace('value="123"', 'value="456"'))
    first = client.post(f'/api/new-items/{identity}/recheck', json={})
    assert first.status_code == 200, first.text
    previous = deepcopy(client.get('/api/new-items/history').json()['rows'][0]['history'][0])
    browser_boundary(monkeypatch, saved_html('CabalPC TH'))
    second = client.post(f'/api/new-items/{identity}/recheck', json={})
    assert second.status_code == 200 and second.json()['recheck']['outcome'] == 'passed'
    row = client.get('/api/new-items/history').json()['rows'][0]
    assert row['history'][0] == previous and len(row['history']) == 2
    assert row['result']['creation'] == creation and row['frozen'] == frozen


def test_broken_id_records_failed_attempt_but_keeps_saved_creation(client, test_database, monkeypatch):
    identity, _, creation = saved_checkpoint(client, test_database)
    _connect_aztek(client)
    requests, unexpected = browser_boundary(monkeypatch, saved_html('CabalPC TH').replace(
        'id="item-option"', 'id="broken-option"'))
    response = client.post(f'/api/new-items/{identity}/recheck', json={})
    assert response.status_code == 200, response.text
    assert response.json()['recheck']['outcome'] == 'failed'
    assert response.json()['recheck']['incomplete'] is True
    assert 'option' in response.json()['recheck']['error']
    assert response.json()['creation'] == creation
    assert len(client.get('/api/new-items/history').json()['rows'][0]['history']) == 1
    assert all(method == 'GET' for method, _ in requests) and unexpected == []


@pytest.mark.parametrize('state', ['confirmed', 'submitting', 'unconfirmed'])
def test_no_saved_checkpoint_cannot_start_recheck(client, test_database, state):
    identity, _, creation = saved_checkpoint(client, test_database)
    _connect_aztek(client)
    with test_database.session() as db:
        record = db.get(Job, identity)
        record.status = state
        record.result = {'creation': dict(creation, state=state)}
    assert client.post(f'/api/new-items/{identity}/recheck', json={}).status_code == 409


@pytest.mark.parametrize('change', ['bad_id', 'wrong_game', 'missing_url'])
def test_invalid_checkpoint_never_opens_browser(client, test_database, change):
    identity, _, creation = saved_checkpoint(client, test_database)
    _connect_aztek(client)
    with test_database.session() as db:
        record = db.get(Job, identity)
        if change == 'bad_id':
            creation['item_id'] = '91?token=private'
        elif change == 'wrong_game':
            config = deepcopy(record.config)
            config['frozen']['game'] = 'HOF'
            record.config = config
        else:
            creation['evidence'] = {}
        record.result = {'creation': creation}
    assert client.post(f'/api/new-items/{identity}/recheck', json={}).status_code == 409


def test_client_cannot_supply_actual_reference_or_passed(client, test_database):
    identity, _, _ = saved_checkpoint(client, test_database)
    assert client.post(f'/api/new-items/{identity}/recheck', json={
        'actual': {'name': 'Fake'}, 'reference': {}, 'passed': True,
        'item_id': '92'}).status_code == 422


def test_recheck_and_history_are_owned(client, client_for, other_member, test_database):
    identity, _, _ = saved_checkpoint(client, test_database)
    other = client_for(other_member)
    assert other.post(f'/api/new-items/{identity}/recheck', json={}).status_code == 404
    assert other.get('/api/new-items/history').json()['rows'] == []


def test_missing_session_leaves_history_and_saved_id_unchanged(client, test_database):
    identity, _, creation = saved_checkpoint(client, test_database)
    assert client.post(f'/api/new-items/{identity}/recheck', json={}).status_code == 409
    row = client.get('/api/new-items/history').json()['rows'][0]
    assert row['history'] == [] and row['result']['creation'] == creation


def test_readonly_runner_blocks_page_initiated_post(client, test_database, monkeypatch):
    identity, _, creation = saved_checkpoint(client, test_database)
    _connect_aztek(client)
    html = saved_html('CabalPC TH') + '''<script>
      fetch('/unexpected-write', {method:'POST', body:'not allowed'}).catch(()=>{});
    </script>'''
    requests, unexpected = browser_boundary(monkeypatch, html)
    response = client.post(f'/api/new-items/{identity}/recheck', json={})
    assert response.status_code == 200, response.text
    assert response.json()['creation'] == creation
    assert all(method == 'GET' for method, _ in requests)
    assert unexpected == []


def test_browser_error_does_not_persist_private_exception_text(client, test_database, monkeypatch):
    identity, _, creation = saved_checkpoint(client, test_database)
    _connect_aztek(client)
    from web import new_item_runner

    class BrokenBrowser:
        async def __aenter__(self):
            raise RuntimeError('private-session-sentinel?token=secret')
        async def __aexit__(self, *_args):
            pass

    monkeypatch.setattr(new_item_runner, 'async_playwright', BrokenBrowser)
    response = client.post(f'/api/new-items/{identity}/recheck', json={})
    assert response.status_code == 200
    assert response.json()['recheck']['outcome'] == 'failed'
    assert response.json()['creation'] == creation
    assert 'private-session-sentinel' not in response.text
    assert 'private-session-sentinel' not in client.get('/api/new-items/history').text
