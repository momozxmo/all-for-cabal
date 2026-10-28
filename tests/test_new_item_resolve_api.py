"""Recover a real captured receipt after an interrupted saved-checkpoint step."""
from copy import deepcopy

import pytest

from web.models import Job
from web.new_item_store import NewItemRepository
from test_new_item_create_flow import CREATE_GAMES, boundary, prepare, run
from test_new_item_recovery_api import reopen
from test_new_item_reader import saved_html
from test_web_validation import _connect_aztek


def interrupt_saved_commit(monkeypatch):
    original = NewItemRepository.finish_submission_group
    interrupted = []

    def finish(self, owner, members, attempt, **kwargs):
        if kwargs.get('item_id') and not interrupted:
            interrupted.append(True)
            raise RuntimeError('Synthetic interruption after response, before saved commit')
        return original(self, owner, members, attempt, **kwargs)

    monkeypatch.setattr(NewItemRepository, 'finish_submission_group', finish)


def history_row(client, identity):
    return next(row for row in client.get('/api/new-items/history').json()['rows'] if row['id'] == identity)


def resolve(client, entry, *, game='CabalM TH', item_id='91', **changes):
    row = history_row(client, entry['id'])
    payload = {'game': game, 'revision': entry['revision'], 'item_id': item_id,
               'expected_history_count': len(row['history'])}
    payload.update(changes)
    return client.post('/api/new-items/' + entry['id'] + '/resolve', json=payload)


def interrupted_create(client, test_database, monkeypatch, *, game='CabalM TH', saved=None):
    entry, frozen = prepare(client, game=game)
    _connect_aztek(client)
    interrupt_saved_commit(monkeypatch)
    observed = boundary(monkeypatch, test_database, entry['id'], game=game, saved=saved)
    response = run(client, entry, game=game)
    assert response.status_code == 200, response.text
    row = history_row(client, entry['id'])
    assert row['state'] == 'unconfirmed' and not row['result']['creation'].get('item_id')
    assert len(observed['posts']) == 1 and not observed['unexpected']
    return entry, frozen, observed


@pytest.mark.parametrize('game', list(CREATE_GAMES))
def test_retained_response_resolves_after_restart_with_fresh_get_not_another_post(
        client, test_database, monkeypatch, game):
    entry, frozen, observed = interrupted_create(client, test_database, monkeypatch, game=game)
    with reopen(client, test_database) as again:
        before = history_row(again, entry['id'])
        response = resolve(again, entry, game=game)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result['creation']['state'] == 'saved'
        assert result['creation']['item_id'] == '91'
        assert result['creation']['source'] == 'created'
        assert result['recheck']['outcome'] == 'passed' and not result['recheck']['incomplete']
        row = history_row(again, entry['id'])
        assert row['frozen'] == frozen
        assert len(row['history']) == len(before['history']) + 1
        assert row['history'][:-1] == before['history']
        before_gets = len(observed['gets'])
        assert resolve(again, entry, game=game).status_code == 409
        assert len(observed['gets']) == before_gets
    assert len(observed['posts']) == 1 and not observed['unexpected']
    slug = CREATE_GAMES[game][0]
    assert observed['gets'] == [
        f'https://aztek-tools-v2.combo-interactive.com/combo/{slug}/shop/items/create',
        f'https://aztek-tools-v2.combo-interactive.com/combo/{slug}/shop/items/91']


@pytest.mark.parametrize('change', ['candidate', 'game', 'revision', 'history', 'client_proof'])
def test_wrong_or_client_supplied_recovery_claim_opens_no_browser(
        client, test_database, monkeypatch, change):
    entry, _, observed = interrupted_create(client, test_database, monkeypatch)
    before = deepcopy(history_row(client, entry['id']))
    changes = {'candidate': {'item_id': '92'}, 'game': {'game': 'CabalPC TH'},
               'revision': {'revision': entry['revision'] + 1}, 'history': {'expected_history_count': 99},
               'client_proof': {'proof': {'id': 91, 'passed': True}}}[change]
    response = resolve(client, entry, **changes)
    assert response.status_code == (422 if change == 'client_proof' else 409), response.text
    assert history_row(client, entry['id']) == before
    assert len(observed['gets']) == 1 and len(observed['posts']) == 1


@pytest.mark.parametrize('field,bad', [('source', 'name_search'), ('game', 'CabalPC TH'),
    ('attempt_id', 'another-attempt'), ('revision', 999), ('payload_hash', 'another-payload')])
def test_stored_receipt_must_bind_exact_current_attempt_payload_and_game(
        client, test_database, monkeypatch, field, bad):
    entry, _, observed = interrupted_create(client, test_database, monkeypatch)
    with test_database.session() as db:
        job = db.get(Job, entry['id'])
        result = deepcopy(job.result)
        receipt = result['creation'].get('receipt') or {}
        receipt[field] = bad
        result['creation']['receipt'] = receipt
        job.result = result
    response = resolve(client, entry)
    assert response.status_code == 409, response.text
    assert history_row(client, entry['id'])['state'] == 'unconfirmed'
    assert len(observed['gets']) == 1 and len(observed['posts']) == 1


def test_entirely_lost_response_cannot_resolve_from_candidate_or_triple(
        client, test_database, monkeypatch):
    entry, _ = prepare(client)
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entry['id'], lose=True)
    assert run(client, entry).status_code == 200
    assert resolve(client, entry).status_code == 409
    assert history_row(client, entry['id'])['state'] == 'unconfirmed'
    assert len(observed['posts']) == 1 and len(observed['gets']) == 1


def test_foreign_owner_cannot_recover_another_members_receipt(
        client, client_for, other_member, test_database, monkeypatch):
    entry, _, observed = interrupted_create(client, test_database, monkeypatch)
    response = client_for(other_member).post('/api/new-items/' + entry['id'] + '/resolve', json={
        'game': 'CabalM TH', 'revision': entry['revision'], 'item_id': '91', 'expected_history_count': 0})
    assert response.status_code == 404
    assert history_row(client, entry['id'])['state'] == 'unconfirmed'
    assert len(observed['gets']) == 1 and len(observed['posts']) == 1


def test_recovered_identity_does_not_make_mismatching_readback_pass(
        client, test_database, monkeypatch):
    entry, _, observed = interrupted_create(client, test_database, monkeypatch,
        saved=saved_html('CabalM TH').replace('value="Synthetic name"', 'value="Other name"'))
    response = resolve(client, entry)
    assert response.status_code == 200, response.text
    assert response.json()['creation']['state'] == 'saved'
    assert response.json()['recheck']['outcome'] == 'mismatch'
    row = history_row(client, entry['id'])
    rejected = client.post('/api/new-items/handoff', json={'game': 'CabalM TH',
        'selected_ids': [entry['id']],
        'occurrence_ids': [o['occurrence_id'] for o in row['frozen']['occurrences']]})
    assert rejected.status_code == 409
    assert len(observed['posts']) == 1 and not observed['unexpected']


def test_two_concurrent_resolutions_only_read_one_saved_item(
        client, test_database, monkeypatch):
    import asyncio
    import httpx
    entry, _, observed = interrupted_create(client, test_database, monkeypatch)
    payload = {'game': 'CabalM TH', 'revision': entry['revision'], 'item_id': '91',
               'expected_history_count': len(history_row(client, entry['id'])['history'])}

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app),
                base_url='http://testserver', cookies=client.cookies) as requests:
            return await asyncio.wait_for(asyncio.gather(*[
                requests.post('/api/new-items/' + entry['id'] + '/resolve', json=payload)
                for _ in range(2)]), timeout=40)

    responses = asyncio.run(scenario())
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    assert len(history_row(client, entry['id'])['history']) == 1
    assert len(observed['gets']) == 2 and len(observed['posts']) == 1


def test_shared_receipt_recovers_each_original_reference_without_another_post(
        client, test_database, monkeypatch):
    from test_new_item_create_cohorts import converged, grouped_run
    entries, frozen = converged(client)
    _connect_aztek(client)
    interrupt_saved_commit(monkeypatch)
    observed = boundary(monkeypatch, test_database, entries[0]['id'],
                        cohort_ids=[e['id'] for e in entries])
    assert grouped_run(client, entries).status_code == 200
    assert all(history_row(client, e['id'])['state'] == 'unconfirmed' for e in entries)
    for entry, original in zip(entries, frozen):
        response = resolve(client, entry)
        assert response.status_code == 200, response.text
        row = history_row(client, entry['id'])
        assert row['frozen'] == original
        assert row['result']['creation']['item_id'] == '91'
        assert row['result']['recheck']['outcome'] == 'passed'
    assert len(observed['posts']) == 1 and not observed['unexpected']


def test_unreadable_recovered_item_keeps_saved_id_but_never_enables_handoff(
        client, test_database, monkeypatch):
    entry, _, observed = interrupted_create(client, test_database, monkeypatch,
        saved=saved_html('CabalM TH').replace('id="item-name"', 'id="broken-name"'))
    response = resolve(client, entry)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['creation']['item_id'] == '91' and result['creation']['state'] == 'saved'
    assert result['recheck']['outcome'] == 'failed' and result['recheck']['incomplete']
    assert len(observed['posts']) == 1 and not observed['unexpected']


def test_missing_session_keeps_unconfirmed_receipt_without_opening_browser(
        client, test_database, monkeypatch):
    entry, _, observed = interrupted_create(client, test_database, monkeypatch)
    assert client.delete('/api/aztek/session').status_code == 204
    before = history_row(client, entry['id'])
    assert resolve(client, entry).status_code == 409
    assert history_row(client, entry['id']) == before
    assert len(observed['gets']) == 1 and len(observed['posts']) == 1


def test_changed_history_while_waiting_for_gate_cannot_resolve_stale_snapshot(
        client, application, test_database, monkeypatch):
    from contextlib import asynccontextmanager
    entry, _, observed = interrupted_create(client, test_database, monkeypatch)

    @asynccontextmanager
    async def changed_slot():
        with test_database.session() as db:
            job = db.get(Job, entry['id'])
            job.log = [*(job.log or []), {'event': 'operator_acknowledgement', 'action': 'skip'}]
        yield

    monkeypatch.setattr(application.state.browser_gate, 'slot', changed_slot)
    assert resolve(client, entry).status_code == 409
    assert history_row(client, entry['id'])['state'] == 'unconfirmed'
    assert len(observed['gets']) == 1 and len(observed['posts']) == 1
