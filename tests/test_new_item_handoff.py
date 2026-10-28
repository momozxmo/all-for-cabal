"""Selected latest-passed occurrences become Finder data, never Bundle jobs."""
from copy import deepcopy

import pytest
from sqlalchemy import select

from web.models import Job, WorkspaceRecord
from web.workspaces import WorkspaceRepository
from test_new_item_reference_api import confirm
from test_new_item_recheck_api import browser_boundary
from test_new_item_reader import ORIGIN, saved_html
from test_web_validation import _connect_aztek


def passed_occurrences(client, test_database, member, monkeypatch):
    with test_database.session() as db:
        source = WorkspaceRepository(db).create(member.id, 'event', 'selected.xlsx')
        source.game = 'CabalPC TH'
        source.criteria = [{'kind': '123', 'opt': '0', 'dur': '0', 'name': 'Synthetic name'},
                           {'kind': '999', 'opt': '0', 'dur': '0', 'name': 'Not selected'}]
        source.occurrences = [dict(source.criteria[0], amt=amount, source_sheet=sheet,
                                   source_row=row, group_keys=[group])
                              for amount, sheet, row, group in [('2', 'A', 2, 'g1'), ('3', 'B', 8, 'g2')]]
        source.group_meta = {'g1': {'group': 'First'}, 'g2': {'group': 'Second'}}
        source_id = source.id
    response = client.post('/api/new-items/from-finder', json={
        'workspace_id': source_id, 'selected_missing_indexes': [0], 'game': 'CabalPC TH',
        'snapshot_token': client.get('/api/workspaces/' + source_id).json()['new_item_snapshot']})
    assert response.status_code == 200, response.text
    draft = response.json()['drafts'][0]
    edited = client.patch('/api/new-items/drafts/' + draft['draft_id'], json={
        'revision': draft['revision'], 'values': {}, 'confirmed_fields': ['item_type', 'tradeable']})
    frozen = confirm(client, edited.json())
    identity = draft['draft_id']
    creation = {'state': 'saved', 'item_id': '91', 'evidence': {
        'detail_url': f'{ORIGIN}/combo/cabalpc/shop/items/91'}}
    with test_database.session() as db:
        record = db.get(Job, identity)
        record.status = 'saved'
        record.result = {'creation': creation}
    _connect_aztek(client)
    requests, unexpected = browser_boundary(monkeypatch, saved_html('CabalPC TH'))
    checked = client.post(f'/api/new-items/{identity}/recheck', json={})
    assert checked.status_code == 200 and checked.json()['recheck']['outcome'] == 'passed'
    assert unexpected == []
    return identity, frozen, source_id, requests


def payload(identity, frozen, occurrences=None):
    return {'selected_ids': [identity], 'game': 'CabalPC TH', 'occurrence_ids':
            occurrences if occurrences is not None else [o['occurrence_id'] for o in frozen['occurrences']]}


def test_selected_occurrences_keep_amounts(client, test_database, member, monkeypatch):
    identity, frozen, source_id, requests = passed_occurrences(client, test_database, member, monkeypatch)
    before = client.get(f'/api/workspaces/{source_id}').json()
    response = client.post('/api/new-items/handoff', json=payload(identity, frozen))
    assert response.status_code == 200, response.text
    workspace_id = response.json()['workspace_id']
    assert workspace_id != source_id
    workspace = client.get(f'/api/workspaces/{workspace_id}').json()
    assert [r['aztek_id'] for r in workspace['results']] == ['91', '91']
    assert [r['amt'] for r in workspace['results']] == ['2', '3']
    assert [r['group_keys'] for r in workspace['results']] == [['g1'], ['g2']]
    assert [r['document_reference']['source_row'] for r in workspace['results']] == [2, 8]
    assert workspace['game'] == 'CabalPC TH'
    assert client.get(f'/api/workspaces/{source_id}').json() == before
    assert len(requests) == 1  # The handoff does not open Aztek again or submit.
    with test_database.session() as db:
        assert not list(db.scalars(select(Job).where(Job.tool == 'bundle_recheck')))


def test_handoff_excludes_unselected_occurrence(client, test_database, member, monkeypatch):
    identity, frozen, _, _ = passed_occurrences(client, test_database, member, monkeypatch)
    selected = [frozen['occurrences'][1]['occurrence_id']]
    response = client.post('/api/new-items/handoff', json=payload(identity, frozen, selected))
    assert response.status_code == 200, response.text
    workspace = client.get('/api/workspaces/' + response.json()['workspace_id']).json()
    assert len(workspace['results']) == 1
    with test_database.session() as db:
        stored = db.get(WorkspaceRecord, response.json()['workspace_id'])
        assert len(stored.occurrences) == 1
        assert list(stored.group_meta) == ['g2']
    assert workspace['results'][0]['amt'] == '3'
    assert workspace['results'][0]['group_keys'] == ['g2']


@pytest.mark.parametrize('change', ['mismatch', 'incomplete', 'unconfirmed', 'old_pass', 'other_id'])
def test_current_problem_never_uses_old_pass_to_handoff(client, test_database, member, monkeypatch, change):
    identity, frozen, _, _ = passed_occurrences(client, test_database, member, monkeypatch)
    with test_database.session() as db:
        record = db.get(Job, identity)
        result, history = deepcopy(record.result), deepcopy(record.log)
        if change == 'mismatch':
            result['recheck']['outcome'] = 'mismatch'
        elif change == 'incomplete':
            result['recheck']['incomplete'] = True
        elif change == 'unconfirmed':
            result['creation']['state'] = 'unconfirmed'
        elif change == 'old_pass':
            history.append(dict(history[-1], recheck={'outcome': 'failed', 'incomplete': True}))
        else:
            result['creation']['item_id'] = '92'
        record.result, record.log = result, history
    response = client.post('/api/new-items/handoff', json=payload(identity, frozen))
    assert response.status_code == 409, response.text
    with test_database.session() as db:
        assert len(list(db.scalars(select(WorkspaceRecord)))) == 1


@pytest.mark.parametrize('bad', ['foreign_occurrence', 'duplicate', 'empty', 'wrong_game'])
def test_bad_selection_does_not_create_finder_workspace(client, test_database, member, monkeypatch, bad):
    identity, frozen, _, _ = passed_occurrences(client, test_database, member, monkeypatch)
    body = payload(identity, frozen)
    if bad == 'foreign_occurrence':
        body['occurrence_ids'].append('not-owned-occurrence')
    elif bad == 'duplicate':
        body['selected_ids'] *= 2
    elif bad == 'empty':
        body['occurrence_ids'] = []
    else:
        body['game'] = 'CabalM TH'
    assert client.post('/api/new-items/handoff', json=body).status_code == 400
    with test_database.session() as db:
        assert len(list(db.scalars(select(WorkspaceRecord)))) == 1


def test_foreign_job_and_client_passed_override_rejected(client, client_for, other_member,
                                                       test_database, member, monkeypatch):
    identity, frozen, _, _ = passed_occurrences(client, test_database, member, monkeypatch)
    assert client_for(other_member).post('/api/new-items/handoff', json=payload(identity, frozen)).status_code == 404
    assert client.post('/api/new-items/handoff', json=payload(identity, frozen) | {'passed': True}).status_code == 422


def test_equal_group_keys_from_different_workspaces_stay_distinct(client, test_database, member, monkeypatch):
    first, frozen1, source1, _ = passed_occurrences(client, test_database, member, monkeypatch)
    second, frozen2, source2, _ = passed_occurrences(client, test_database, member, monkeypatch)
    body = payload(first, frozen1)
    body['selected_ids'].append(second)
    body['occurrence_ids'] += [o['occurrence_id'] for o in frozen2['occurrences']]
    response = client.post('/api/new-items/handoff', json=body)
    assert response.status_code == 200, response.text
    workspace = client.get('/api/workspaces/' + response.json()['workspace_id']).json()
    with test_database.session() as db:
        stored = db.get(WorkspaceRecord, response.json()['workspace_id'])
        assert len(stored.group_meta) == 4
        assert [r['source_workspace_id'] for r in stored.results] == [source1, source1, source2, source2]
    assert len({r['group_keys'][0] for r in workspace['results']}) == 4
