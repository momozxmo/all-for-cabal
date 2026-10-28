"""Restart recovery never turns an uncertain submission into permission to retry."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from web.app import create_app
from web.models import Job
from test_new_item_recheck_api import saved_checkpoint


def reopen(client, test_database):
    app = create_app(client.app.state.settings, test_database)
    return TestClient(app, cookies=dict(client.cookies))


@pytest.mark.parametrize('known_id', [None, '91'])
def test_restart_keeps_unconfirmed(client, test_database, monkeypatch, known_id):
    identity, frozen, original = saved_checkpoint(client, test_database)
    creation = dict(original, state='submitting', item_id=known_id)
    previous_attempt = {'checked_at': '2026-10-25T00:00:00+00:00',
                        'recheck': {'outcome': 'failed', 'incomplete': True}}
    with test_database.session() as db:
        record = db.get(Job, identity)
        record.status = 'submitting'
        record.result = {'creation': creation, 'recheck': previous_attempt['recheck']}
        record.log = [previous_attempt]
    from web import new_item_runner
    browser_calls = []
    def forbidden_browser():
        browser_calls.append('browser')
        raise AssertionError('Restart must not open an Aztek browser')
    monkeypatch.setattr(new_item_runner, 'async_playwright', forbidden_browser)
    with reopen(client, test_database) as restored_client:
        row = restored_client.get('/api/new-items/history').json()['rows'][0]
        assert row['state'] == 'unconfirmed'
        assert row['result']['creation']['state'] == 'unconfirmed'
        assert row['result']['creation']['item_id'] == known_id
        assert row['result']['creation']['evidence'] == original['evidence']
        assert row['frozen'] == frozen
        assert row['result']['recheck'] == previous_attempt['recheck']
        assert row['history'][0] == previous_attempt
        assert len(row['history']) == 2
        assert restored_client.post(f'/api/new-items/{identity}/recheck', json={}).status_code == 409
        first_restore = deepcopy(row)
    with reopen(client, test_database) as again:
        assert again.get('/api/new-items/history').json()['rows'][0] == first_restore
    assert browser_calls == []


def test_startup_does_not_change_saved_new_item_or_other_tools(client, test_database, member):
    identity, frozen, creation = saved_checkpoint(client, test_database)
    with test_database.session() as db:
        db.add(Job(id='other-tool-interrupted', owner_user_id=member.id,
                   tool='other_tool', status='submitting',
                   config={'schema_version': 1}, result={'sentinel': 'preserve'}, log=[]))
    with reopen(client, test_database) as again:
        row = again.get('/api/new-items/history').json()['rows'][0]
        assert row['state'] == 'saved' and row['result']['creation'] == creation
        assert row['frozen'] == frozen and row['history'] == []
    with test_database.session() as db:
        other = db.get(Job, 'other-tool-interrupted')
        assert other.status == 'submitting' and other.result == {'sentinel': 'preserve'}


def test_recovery_preserves_unknown_schema_without_guessing(client, test_database):
    identity, _, creation = saved_checkpoint(client, test_database)
    with test_database.session() as db:
        record = db.get(Job, identity)
        record.status = 'submitting'
        config = deepcopy(record.config)
        config['schema_version'] = 999
        record.config = config
        record.result = {'creation': dict(creation, state='submitting')}
    with reopen(client, test_database) as again:
        row = again.get('/api/new-items/history').json()['rows'][0]
        assert row['state'] == 'submitting' and row['history'] == []
        assert again.post(f'/api/new-items/{identity}/recheck', json={}).status_code == 409
