"""Acknowledging a problem records intent; it cannot manufacture a passed Item."""
from copy import deepcopy

import pytest

from web.models import Job
from test_new_item_handoff import passed_occurrences, payload as handoff_payload
from test_new_item_recheck_api import saved_checkpoint


@pytest.mark.parametrize('action', ['skip', 'continue'])
def test_acknowledge_cannot_unlock_handoff(client, member, test_database, monkeypatch, action):
    identity, frozen, _, requests = passed_occurrences(client, test_database, member, monkeypatch)
    with test_database.session() as db:
        record = db.get(Job, identity)
        result, history = deepcopy(record.result), deepcopy(record.log)
        result['recheck']['outcome'] = 'mismatch'
        result['recheck']['differences'] = ['name']
        history[-1]['recheck'] = deepcopy(result['recheck'])
        record.result, record.log = result, history
    before = client.get('/api/new-items/history').json()['rows'][0]
    response = client.post(f'/api/new-items/{identity}/acknowledge', json={
        'action': action, 'expected_history_count': len(before['history'])})
    assert response.status_code == 200, response.text
    after = client.get('/api/new-items/history').json()['rows'][0]
    assert after['result'] == before['result']
    assert after['frozen'] == before['frozen'] and after['state'] == before['state']
    assert after['history'][:-1] == before['history']
    assert after['history'][-1]['event'] == 'operator_acknowledgement'
    assert after['history'][-1]['action'] == action
    assert client.post('/api/new-items/handoff', json=handoff_payload(identity, frozen)).status_code == 409
    assert len(requests) == 1  # No browser or queue resume from acknowledgement.


def test_unconfirmed_creation_stays_unconfirmed_after_skip(client, test_database):
    identity, _, creation = saved_checkpoint(client, test_database)
    with test_database.session() as db:
        record = db.get(Job, identity)
        record.status = 'unconfirmed'
        record.result = {'creation': dict(creation, state='unconfirmed')}
    response = client.post(f'/api/new-items/{identity}/acknowledge', json={
        'action': 'skip', 'expected_history_count': 0})
    assert response.status_code == 200, response.text
    row = client.get('/api/new-items/history').json()['rows'][0]
    assert row['state'] == row['result']['creation']['state'] == 'unconfirmed'
    assert row['result']['creation']['item_id'] == '91'
    assert client.post(f'/api/new-items/{identity}/recheck', json={}).status_code == 409


def test_stale_or_duplicate_acknowledgement_is_conflict(client, test_database):
    identity, _, creation = saved_checkpoint(client, test_database)
    with test_database.session() as db:
        record = db.get(Job, identity)
        record.result = {'creation': creation, 'recheck': {'outcome': 'failed', 'incomplete': True}}
    body = {'action': 'skip', 'expected_history_count': 0}
    assert client.post(f'/api/new-items/{identity}/acknowledge', json=body).status_code == 200
    assert client.post(f'/api/new-items/{identity}/acknowledge', json=body).status_code == 409
    assert len(client.get('/api/new-items/history').json()['rows'][0]['history']) == 1


def test_acknowledgement_is_owned_and_cannot_override_result(client, test_database, client_for, other_member):
    identity, _, _ = saved_checkpoint(client, test_database)
    body = {'action': 'skip', 'expected_history_count': 0}
    assert client_for(other_member).post(f'/api/new-items/{identity}/acknowledge', json=body).status_code == 404
    assert client.post(f'/api/new-items/{identity}/acknowledge', json=body | {'passed': True}).status_code == 422
    assert client.post(f'/api/new-items/{identity}/acknowledge', json=body | {'action': 'retry_create'}).status_code == 422


def test_no_problem_cannot_be_acknowledged(client, test_database, member, monkeypatch):
    identity, _, _, requests = passed_occurrences(client, test_database, member, monkeypatch)
    before = client.get('/api/new-items/history').json()['rows'][0]
    assert before['result']['recheck']['outcome'] == 'passed'
    assert before['result']['recheck']['incomplete'] is False
    assert len(before['history']) == 1
    assert client.post(f'/api/new-items/{identity}/acknowledge', json={
        'action': 'skip', 'expected_history_count': 1}).status_code == 409
    assert client.get('/api/new-items/history').json()['rows'][0] == before
    assert len(requests) == 1  # Rejecting intent does not open another browser.


def test_saved_without_readback_acknowledgement_keeps_incomplete_identity(client, test_database):
    identity, _, creation = saved_checkpoint(client, test_database)
    before = client.get('/api/new-items/history').json()['rows'][0]
    response = client.post(f'/api/new-items/{identity}/acknowledge', json={
        'action': 'skip', 'expected_history_count': 0})
    assert response.status_code == 200, response.text
    after = client.get('/api/new-items/history').json()['rows'][0]
    assert after['result'] == before['result'] == {'creation': creation}
    assert after['state'] == 'saved' and after['result']['creation']['item_id'] == '91'
    assert after['frozen'] == before['frozen']
    assert len(after['history']) == 1 and after['history'][0]['event'] == 'operator_acknowledgement'
