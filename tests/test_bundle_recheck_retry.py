"""A retry only rereads the saved Bundle; it never invokes create."""
import asyncio

from web import bundle_runner
from web.models import Job
from test_web_validation import _connect_aztek, GAME


def test_read_retry_is_bounded_and_does_not_retry_mismatch(monkeypatch):
    calls = []
    async def check(*_):
        calls.append('read')
        if len(calls) < 3:
            raise TimeoutError('not ready')
        return {'outcome': 'mismatch', 'incomplete': False}
    monkeypatch.setattr(bundle_runner, 'recheck_saved_bundle', check)
    result = asyncio.run(bundle_runner.retry_saved_recheck(None, 'url', {}, {}))
    assert result['outcome'] == 'mismatch'
    assert len(calls) == 3

    calls.clear()
    async def mismatch(*_):
        calls.append('read')
        return {'outcome': 'mismatch', 'incomplete': False}
    monkeypatch.setattr(bundle_runner, 'recheck_saved_bundle', mismatch)
    asyncio.run(bundle_runner.retry_saved_recheck(None, 'url', {}, {}))
    assert len(calls) == 1


def test_expired_session_stops_read_retry(monkeypatch):
    calls = []
    async def check(*_):
        calls.append('read')
        raise bundle_runner.SessionExpiredError('session expired')
    monkeypatch.setattr(bundle_runner, 'recheck_saved_bundle', check)
    result = asyncio.run(bundle_runner.retry_saved_recheck(None, 'url', {}, {}))
    assert result['outcome'] == 'failed'
    assert result['session_expired'] is True
    assert len(calls) == 1


def test_retry_endpoint_uses_existing_id_and_appends_history(
        client, db_session, member, monkeypatch):
    _connect_aztek(client)
    job = Job(owner_user_id=member.id, tool='bundle_recheck', status='failed',
              config={'game': GAME, 'client_key': 'one', 'submitted_values': {
                  'name': 'One', 'game': GAME, 'items': [{'id': '91', 'qty': '1'}],
                  'document_reference': {'game': GAME, 'items': []}}},
              result={'name': 'One', 'saved': True, 'bundle_id': None,
                      'recheck': {'outcome': 'failed', 'incomplete': True}},
              log=[])
    db_session.add(job)
    db_session.commit()
    calls = []
    async def reread(game, bundle_id, *_args, **_kwargs):
        calls.append((game, bundle_id))
        return {'outcome': 'partial', 'incomplete': True, 'rows': [],
                'coverage': {'saved_rows': '1/1', 'properties': '0/4'}}
    monkeypatch.setattr(bundle_runner, 'read_existing_bundle', reread)
    response = client.post(f'/api/bundles/rechecks/{job.id}/retry',
                           json={'bundle_id': '42'})
    assert response.status_code == 200, response.text
    assert calls == [(GAME, '42')]
    assert response.json()['bundle_id'] == '42'
    assert response.json()['recheck']['outcome'] == 'partial'
    listed = client.get('/api/bundles/rechecks')
    assert listed.status_code == 200
    assert listed.json()['rows'][0]['history'][0]['outcome'] == 'partial'
    assert listed.json()['rows'][0]['submitted_values']['game'] == GAME
    assert client.post(f'/api/bundles/rechecks/{job.id}/retry',
                       json={}).status_code == 200
    assert len(client.get('/api/bundles/rechecks').json()['rows'][0]['history']) == 2
    assert len(calls) == 2


def test_retry_requires_saved_id_and_owner_scope(client, client_for, db_session,
                                                  member, other_member, monkeypatch):
    job = Job(owner_user_id=member.id, tool='bundle_recheck', status='pending',
              config={'game': GAME, 'client_key': 'pending',
                      'submitted_values': {'game': GAME, 'name': 'Pending'}},
              result={'name': 'Pending', 'saved': False, 'bundle_id': None,
                      'creation_uncertain': True}, log=[])
    db_session.add(job)
    db_session.commit()
    assert client.post(f'/api/bundles/rechecks/{job.id}/retry', json={}).status_code == 400
    assert client.post(f'/api/bundles/rechecks/{job.id}/retry',
                       json={'bundle_id': '../42'}).status_code == 400
    stranger = client_for(other_member)
    assert stranger.get('/api/bundles/rechecks').json()['rows'] == []
    assert stranger.post(f'/api/bundles/rechecks/{job.id}/retry',
                         json={'bundle_id': '42'}).status_code == 404


def test_failed_manual_id_is_not_locked_and_can_be_corrected(
        client, db_session, member, monkeypatch):
    _connect_aztek(client)
    job = Job(owner_user_id=member.id, tool='bundle_recheck', status='failed',
              config={'game': GAME, 'client_key': 'unknown-id',
                      'submitted_values': {'game': GAME, 'name': 'Unknown ID'}},
              result={'name': 'Unknown ID', 'saved': True, 'bundle_id': None,
                      'recheck': {'outcome': 'failed', 'incomplete': True}}, log=[])
    db_session.add(job)
    db_session.commit()
    calls = []
    async def reread(_game, bundle_id, *_args, **_kwargs):
        calls.append(bundle_id)
        if bundle_id == '42':
            return {'outcome': 'failed', 'incomplete': True,
                    'error': 'Bundle ID ไม่ถูกต้อง'}
        return {'outcome': 'partial', 'incomplete': True, 'actual': {'items': []}}
    monkeypatch.setattr(bundle_runner, 'read_existing_bundle', reread)
    first = client.post(f'/api/bundles/rechecks/{job.id}/retry',
                        json={'bundle_id': '42'})
    assert first.status_code == 200
    assert first.json()['bundle_id'] is None
    second = client.post(f'/api/bundles/rechecks/{job.id}/retry',
                         json={'bundle_id': '43'})
    assert second.status_code == 200
    assert second.json()['bundle_id'] == '43'
    assert calls == ['42', '43']
    history = client.get('/api/bundles/rechecks').json()['rows'][0]['history']
    assert [row['bundle_id'] for row in history] == ['42', '43']
    assert history[0]['error'] == 'Bundle ID ไม่ถูกต้อง'


def test_history_restores_game_into_legacy_submitted_values(
        client, db_session, member):
    job = Job(owner_user_id=member.id, tool='bundle_recheck', status='passed',
              config={'game': GAME, 'client_key': 'legacy',
                      'submitted_values': {'name': 'Legacy', 'items': [], 'rewards': []}},
              result={'name': 'Legacy', 'saved': True, 'bundle_id': '42',
                      'recheck': {'outcome': 'passed', 'incomplete': False}}, log=[])
    db_session.add(job)
    db_session.commit()
    listed = client.get('/api/bundles/rechecks')
    assert listed.status_code == 200
    assert listed.json()['rows'][0]['submitted_values']['game'] == GAME
