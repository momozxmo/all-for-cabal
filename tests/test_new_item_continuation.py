"""Explicit new scope after acknowledgement, never an original write replay."""
from test_new_item_create_flow import GAME, boundary, prepare, receipt, run
from test_new_item_reader import saved_html
from test_web_validation import _connect_aztek


def test_problem_blocks_new_scope_until_ack_without_changing_original_result(
        client, test_database, monkeypatch):
    first, _ = prepare(client)
    second, _ = prepare(client, name='Second item')
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, first['id'], saved=saved_html(GAME).replace(
        'value="Synthetic name"', 'value="Wrong"'))
    assert run(client, first, second).status_code == 200
    original = {r['id']: r for r in client.get('/api/new-items/history').json()['rows']}[first['id']]
    assert original['result']['recheck']['outcome'] == 'mismatch'
    before = len(observed['gets'])
    rejected = run(client, second)
    assert rejected.status_code == 409, rejected.text
    assert len(observed['gets']) == before and len(observed['posts']) == 1
    ack = client.post('/api/new-items/' + first['id'] + '/acknowledge', json={
        'action': 'continue', 'expected_history_count': len(original['history'])})
    assert ack.status_code == 200, ack.text
    assert len(observed['posts']) == 1
    assert ack.json()['result'] == original['result']
    assert run(client, first).status_code == 409
    current = {r['id']: r for r in client.get('/api/new-items/history').json()['rows']}
    assert current[first['id']]['result'] == original['result']
    assert current[second['id']]['state'] == 'confirmed'


def test_acknowledged_unconfirmed_is_never_replayed_but_explicit_other_scope_can_run(
        client, test_database, monkeypatch):
    first, _ = prepare(client)
    second, _ = prepare(client, name='Second item')
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, first['id'], lose=True)
    response = run(client, first, second)
    assert response.status_code == 200, response.text
    original = {r['id']: r for r in client.get('/api/new-items/history').json()['rows']}[first['id']]
    assert original['state'] == 'unconfirmed'
    assert run(client, second).status_code == 409
    ack = client.post('/api/new-items/' + first['id'] + '/acknowledge', json={
        'action': 'skip', 'expected_history_count': len(original['history'])})
    assert ack.status_code == 200 and ack.json()['result'] == original['result']
    assert len(observed['posts']) == 1
    # A completely new, explicitly selected scope gets a different synthetic ID.
    next_run = boundary(monkeypatch, test_database, second['id'], saved_id=92,
        response=receipt(id=92, name='Second item'),
        saved=saved_html(GAME).replace('Synthetic name', 'Second item').replace('<span>91</span>', '<span>92</span>'))
    result = run(client, second)
    assert result.status_code == 200, result.text
    assert result.json()['items'][0]['result']['creation']['item_id'] == '92'
    assert result.json()['items'][0]['result']['recheck']['outcome'] == 'passed'
    assert run(client, first).status_code == 409
    assert len(next_run['posts']) == 1 and not next_run['unexpected']
    restored = {r['id']: r for r in client.get('/api/new-items/history').json()['rows']}[first['id']]
    assert restored['result'] == original['result'] and restored['state'] == 'unconfirmed'


def test_new_failed_readback_requires_fresh_acknowledgement(client, test_database, monkeypatch):
    from test_new_item_recheck_api import browser_boundary
    first, _ = prepare(client)
    second, _ = prepare(client, name='Second item')
    _connect_aztek(client)
    boundary(monkeypatch, test_database, first['id'], saved=saved_html(GAME).replace(
        'value="Synthetic name"', 'value="Wrong"'))
    assert run(client, first).status_code == 200
    row = {r['id']: r for r in client.get('/api/new-items/history').json()['rows']}[first['id']]
    assert client.post('/api/new-items/' + first['id'] + '/acknowledge', json={
        'action': 'continue', 'expected_history_count': len(row['history'])}).status_code == 200
    remote, unexpected = browser_boundary(monkeypatch, saved_html(GAME).replace(
        'value="Synthetic name"', 'value="Still wrong"'))
    recheck = client.post('/api/new-items/' + first['id'] + '/recheck', json={})
    assert recheck.status_code == 200 and recheck.json()['recheck']['outcome'] == 'mismatch'
    before = len(remote)
    assert run(client, second).status_code == 409
    assert len(remote) == before and not unexpected


def test_other_users_problem_does_not_block_current_owner(
        client, client_for, other_member, test_database, monkeypatch):
    other = client_for(other_member)
    foreign, _ = prepare(other)
    _connect_aztek(other)
    boundary(monkeypatch, test_database, foreign['id'], lose=True)
    assert run(other, foreign).status_code == 200
    own, _ = prepare(client)
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, own['id'])
    result = run(client, own)
    assert result.status_code == 200 and result.json()['items'][0]['result']['creation']['state'] == 'saved'
    assert len(observed['posts']) == 1 and not observed['unexpected']


def test_other_game_problem_does_not_block_mth_scope(client, test_database, monkeypatch):
    from test_new_item_recheck_api import browser_boundary, saved_checkpoint
    existing, _, _ = saved_checkpoint(client, test_database, game='CabalPC TH')
    _connect_aztek(client)
    browser_boundary(monkeypatch, saved_html('CabalPC TH').replace('value="Synthetic name"', 'value="Wrong"'))
    checked = client.post('/api/new-items/' + existing + '/recheck', json={})
    assert checked.status_code == 200 and checked.json()['recheck']['outcome'] == 'mismatch'
    entry, _ = prepare(client)
    observed = boundary(monkeypatch, test_database, entry['id'])
    response = run(client, entry)
    assert response.status_code == 200, response.text
    assert len(observed['posts']) == 1 and not observed['unexpected']


def test_problem_changed_while_waiting_for_gate_is_rechecked_before_browser(
        client, application, test_database, monkeypatch):
    from contextlib import asynccontextmanager
    from copy import deepcopy
    from types import SimpleNamespace
    from web.models import Job
    first, _ = prepare(client)
    second, _ = prepare(client, name='Second item')
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, first['id'], saved=saved_html(GAME).replace(
        'value="Synthetic name"', 'value="Wrong"'))
    assert run(client, first).status_code == 200
    row = {r['id']: r for r in client.get('/api/new-items/history').json()['rows']}[first['id']]
    assert client.post('/api/new-items/' + first['id'] + '/acknowledge', json={
        'action': 'continue', 'expected_history_count': len(row['history'])}).status_code == 200
    @asynccontextmanager
    async def slot():
        # Concurrent completed reader writes a new result while this run waits.
        with test_database.session() as db:
            job = db.get(Job, first['id'])
            job.log = [*deepcopy(job.log), {'recheck': deepcopy(job.result['recheck'])}]
        yield
    monkeypatch.setattr(application.state, 'browser_gate', SimpleNamespace(slot=slot))
    before = len(observed['gets'])
    assert run(client, second).status_code == 409
    assert len(observed['gets']) == before and len(observed['posts']) == 1
