# -*- coding: utf-8 -*-
"""Authenticated API-level tests for Item Finder web parity endpoints."""
import asyncio
import io
import json
import os
import sys
import tempfile
import threading
import time
import traceback
from contextlib import suppress
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sqlalchemy import select  # noqa: E402

import pytest  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

import item_finder  # noqa: E402
from web import item_service, search_runner  # noqa: E402
from web.models import Job, WorkspaceRecord  # noqa: E402
from web.search_coordinator import SearchCoordinator  # noqa: E402
from web import workspaces as workspace_module  # noqa: E402
from web.workspaces import WorkspaceRepository  # noqa: E402


def make_template_bytes():
    handle, path = tempfile.mkstemp(suffix='.xlsx')
    os.close(handle)
    try:
        item_finder.download_template(path)
        with open(path, 'rb') as stream:
            return stream.read()
    finally:
        os.unlink(path)


def _connect_aztek(client):
    """Attach a valid encrypted Aztek session so /ws/search can run."""
    token = client.post('/api/aztek/pairing-token').json()['pairing_token']
    response = client.post('/api/aztek/pair', json={
        'pairing_token': token,
        'storage_state': {
            'cookies': [{
                'name': 'session', 'value': 'cookie-value',
                'domain': '.combo-interactive.com', 'path': '/',
            }],
            'origins': [],
        },
    })
    assert response.status_code == 200


def test_modes_and_template_download(client):
    response = client.get('/api/modes')
    assert response.status_code == 200
    assert set(response.json()) == {'event', 'itemcode', 'shop'}
    assert response.json()['event'] == {
        'web_mode': 'no', 'web_locked': False, 'read_desc': False,
    }
    assert response.json()['itemcode']['web_locked'] is True
    response = client.get('/api/template')
    assert response.status_code == 200
    assert response.content[:2] == b'PK'
    assert 'attachment' in response.headers['content-disposition']


def test_import_template_creates_workspace_and_clear_deletes_it(client):
    response = client.post(
        '/api/import-template', data={'mode': 'event'},
        files={'file': (
            'template.xlsx', make_template_bytes(),
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['workspace_id']
    assert body['mode'] == 'event'
    assert body['count'] == 2
    assert len(body['items']) == 2
    workspace_id = body['workspace_id']
    assert client.get('/api/workspaces/' + workspace_id).status_code == 200
    assert client.delete('/api/workspaces/' + workspace_id).status_code == 204
    assert client.get('/api/workspaces/' + workspace_id).status_code == 404


def test_plan_import_returns_sheet_picker_then_applies_selected_sheets(client, monkeypatch):
    monkeypatch.setattr(item_service, 'parser_for_mode', lambda mode: (
        lambda path: ([
            ('One', [{'kind': '1', 'sources': ['G1']}]),
            ('Two', [{'kind': '2', 'sources': ['G2']}]),
        ], ['Skipped'])
    ))
    response = client.post(
        '/api/import-plan', data={'mode': 'shop'},
        files={'file': ('plan.xlsx', b'fake workbook', 'application/octet-stream')},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['needs_sheet_selection'] is True
    assert [sheet['name'] for sheet in body['sheets']] == ['One', 'Two']
    response = client.post('/api/import-plan/apply', json={
        'pending_id': body['pending_id'], 'selected_sheets': ['Two'],
    })
    assert response.status_code == 200, response.text
    applied = response.json()
    assert applied['mode'] == 'shop'
    assert [row['kind'] for row in applied['items']] == ['2']
    assert applied['skipped'] == ['Skipped']


def test_sql_pending_import_preserves_same_reward_from_two_event_sheets(
        client, member, test_database, monkeypatch):
    row = {
        'kind': '1', 'opt': '', 'dur': '', 'name': 'Prize',
        'sources': ['Lucky Draw'],
        'group_meta': {
            'event_name': 'Event', 'reward': 'Lucky Draw',
            'end_date': '2026-08-31',
        },
    }
    monkeypatch.setattr(item_service, 'parser_for_mode', lambda mode: (
        lambda path: ([
            ('Activity A', [row]),
            ('Activity B', [dict(row)]),
        ], [])
    ))
    imported = client.post(
        '/api/import-plan', data={'mode': 'event'},
        files={'file': ('plan.xlsx', b'fake', 'application/octet-stream')},
    ).json()

    response = client.post('/api/import-plan/apply', json={
        'pending_id': imported['pending_id'],
        'selected_sheets': ['Activity A', 'Activity B'],
    })

    assert response.status_code == 200, response.text
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).get_owned(
            member.id, imported['workspace_id'])
        assert len(workspace.group_meta) == 2
        assert {meta['sheet'] for meta in workspace.group_meta.values()} == {
            'Activity A', 'Activity B',
        }
        assert workspace.occurrences[0]['group_keys'] != \
            workspace.occurrences[1]['group_keys']


def test_workspace_results_export_and_bundle_preview(client, member, test_database):
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(member.id, 'event', 'plan.xlsx')
        workspace.game = 'CabalM SEA'
        workspace.group_meta = {
            'G1': {'activity': 'Event A'}, 'G2': {'activity': 'Event A'},
        }
        workspace.results = [
            {'aztek_id': '99', 'item_name': 'Shared', 'item_kind': '1',
             'sources': ['G1']},
            {'aztek_id': '11', 'item_name': 'Only 1', 'item_kind': '2',
             'sources': ['G1']},
            {'aztek_id': '99', 'item_name': 'Shared', 'item_kind': '1',
             'sources': ['G2']},
            {'aztek_id': '22', 'item_name': 'Only 2', 'item_kind': '3',
             'sources': ['G2']},
        ]
        workspace.not_found = [['#5 Kind=404', 'missing row']]
        workspace_id = workspace.id

    response = client.get(f'/api/workspaces/{workspace_id}')
    assert response.status_code == 200
    assert response.json()['result_count'] == 4
    assert len(response.json()['results']) == 4
    assert response.json()['not_found'][0][0].startswith('#5')

    response = client.get(f'/api/workspaces/{workspace_id}/export.csv')
    assert response.status_code == 200
    assert response.content.startswith(b'\xef\xbb\xbf')
    response = client.get(f'/api/workspaces/{workspace_id}/export.xlsx')
    assert response.status_code == 200
    assert response.content[:2] == b'PK'

    response = client.post(
        f'/api/workspaces/{workspace_id}/bundles',
        json={'selected_indexes': [0, 1, 2, 3]},
    )
    assert response.status_code == 200, response.text
    bundles = response.json()['bundles']
    assert [bundle['name'] for bundle in bundles] == ['Event A - G1', 'Event A - G2']
    # Plan-file order, shared items included — not shared-last.
    assert [[item['id'] for item in bundle['items']] for bundle in bundles] == [
        ['99', '11'], ['99', '22'],
    ]


def test_workspace_restore_keeps_a_persisted_item_description(
        client, member, test_database):
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(member.id, 'event', 'plan.xlsx')
        workspace.results = [{
            'aztek_id': '10', 'item_name': 'Saved Prize',
            'desc': 'description saved before this workspace was reopened',
        }]
        workspace_id = workspace.id

    restored = client.get(f'/api/workspaces/{workspace_id}')

    assert restored.status_code == 200
    assert restored.json()['results'][0]['desc'] == (
        'description saved before this workspace was reopened')


def test_event_bundle_preview_carries_only_selected_event_drafts(
        client, member, test_database):
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(
            member.id, 'event', 'plan.xlsx')
        workspace.game = 'CabalM SEA'
        workspace.group_meta = {
            'ga': {
                'sheet': 'Activity A', 'sheet_key': 'sheet-a',
                'group_key': 'ga', 'event_name': 'Event A',
                'reward': 'Lucky Draw', 'end_date': '2026-08-31',
            },
            'gb': {
                'sheet': 'Activity B', 'sheet_key': 'sheet-b',
                'group_key': 'gb', 'event_name': 'Event B',
                'reward': 'Lucky Draw', 'end_date': '2026-09-30',
            },
        }
        workspace.results = [
            {'aztek_id': '11', 'item_name': 'A', 'sources': ['Lucky Draw'],
             'group_keys': ['ga']},
            {'aztek_id': '22', 'item_name': 'B', 'sources': ['Lucky Draw'],
             'group_keys': ['gb']},
        ]
        workspace_id = workspace.id

    response = client.post(
        '/api/workspaces/%s/bundles' % workspace_id,
        json={'selected_indexes': [1]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body['bundles'][0]['group'] == 'Lucky Draw'
    assert body['bundles'][0]['group_key'] == 'gb'
    assert [draft['sheet'] for draft in body['event_drafts']] == ['Activity B']
    assert body['event_drafts'][0]['rewards'][0]['group_key'] == 'gb'


def test_itemcode_bundle_preview_carries_the_complete_selected_draft(
        client, member, test_database):
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(
            member.id, 'itemcode', 'plan.xlsx')
        workspace.game = 'CabalPC TH'
        workspace.group_meta = {
            'ga': {
                'group_key': 'ga', 'activity': 'Summer Event',
                'reward': 'Winner Prize', 'expire': '2026-08-31',
                'codes_per_set': '20', 'set_count': '1', 'total': '20',
                'unique_code': True,
            },
        }
        workspace.results = [
            {'aztek_id': '11', 'item_name': 'Prize',
             'sources': ['Winner Prize'], 'group_keys': ['ga']},
        ]
        workspace_id = workspace.id

    response = client.post(
        '/api/workspaces/%s/bundles' % workspace_id,
        json={'selected_indexes': [0]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body['event_drafts'] == []
    assert len(body['itemcode_drafts']) == 1
    draft = body['itemcode_drafts'][0]
    assert draft['group'] == 'ga'
    assert draft['name_en'] == 'Summer Event - Winner Prize'
    assert draft['start_time'].endswith('00:00:00')
    assert draft['limited'] is True
    assert (draft['quantity'], draft['remaining']) == ('30', '30')


def test_search_websocket_persists_results_not_found_and_regroups(
    client, member, test_database, monkeypatch
):
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(member.id, 'event', 'plan.xlsx')
        workspace.criteria = [{'kind': '1', 'opt': '', 'dur': '', 'name': 'A'}]
        workspace.occurrences = [
            {'kind': '1', 'opt': '', 'dur': '', 'name': 'A file', 'sources': ['G1']},
            {'kind': '1', 'opt': '', 'dur': '', 'name': 'A file', 'sources': ['G2']},
        ]
        workspace_id = workspace.id

    _connect_aztek(client)

    async def fake_run(finder, data, storage_state):
        row = {
            'aztek_id': '10', 'item_name': 'A web', 'item_kind': '1',
            'item_option': '', 'duration_index': '', 'game': data['game'],
        }
        finder._results = [row]
        finder.add_result_row(row)
        finder._not_found = [['#2 Kind=404', 'missing row']]
        finder._regroup_results()

    monkeypatch.setattr(search_runner.HeadlessFinder, 'run', fake_run)
    messages = []
    with client.websocket_connect('/ws/search') as websocket:
        websocket.send_json({
            'workspace_id': workspace_id, 'game': 'CabalM SEA', 'web_mode': 'any',
        })
        while True:
            message = websocket.receive_json()
            messages.append(message)
            if message['type'] == 'done':
                break

    assert [message['type'] for message in messages].count('reset_results') == 1
    assert [message['type'] for message in messages].count('result') == 3
    done = messages[-1]
    assert done['count'] == 2
    assert done['not_found'][0][0].startswith('#2')
    with test_database.session() as db:
        saved = db.get(WorkspaceRecord, workspace_id)
        assert saved is not None
        # Results are persisted in the streamed result_view shape (sources are
        # joined into the 'groups' field, not a raw 'sources' list).
        assert [row['groups'] for row in saved.results] == ['G1', 'G2']


def _searchable_workspace(member, test_database):
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(member.id, 'event', 'plan.xlsx')
        workspace.criteria = [{'kind': '1', 'opt': '', 'dur': '', 'name': 'A'}]
        workspace.occurrences = [
            {'kind': '1', 'opt': '', 'dur': '', 'name': 'A file', 'sources': ['G1']}]
        return workspace.id


class _StubAztek:
    """Just enough session service to let a search start."""

    def load_storage_state(self, db, user):
        return {'cookies': [], 'origins': []}

    def mark_expired(self, db, user):
        return None


def _coordinator(test_settings, test_database):
    return SearchCoordinator(test_database, test_settings, _StubAztek())


def _hold_then_find(release):
    """A run that produces one row, once the test lets it."""
    async def fake_run(finder, data, storage_state):
        await release.wait()
        row = {'aztek_id': '10', 'item_name': 'A web', 'item_kind': '1',
               'item_option': '', 'duration_index': '', 'game': data['game']}
        finder._results = [row]
        finder.add_result_row(row)
    return fake_run


async def _settle(coordinator, workspace_id, timeout=5.0):
    deadline = time.monotonic() + timeout
    while coordinator.live(workspace_id) is not None:
        if time.monotonic() > deadline:
            raise AssertionError('การค้นหาไม่จบภายในเวลาที่รอ')
        await asyncio.sleep(0.02)


# These drive the coordinator directly rather than through TestClient: its
# websocket portal ends with the request, which would take a detached task with
# it and prove nothing about a real server.
def test_a_search_outlives_the_page_that_started_it(
    test_settings, test_database, member, monkeypatch
):
    """Create Bundle is its own page, so leaving mid-search is normal use.

    The run belongs to the application: the watcher going away must not cancel
    it, and the results must be recorded with nobody watching at all.
    """
    workspace_id = _searchable_workspace(member, test_database)
    coordinator = _coordinator(test_settings, test_database)
    request = {'game': 'CabalM SEA', 'web_mode': 'any'}

    async def scenario():
        release = asyncio.Event()
        monkeypatch.setattr(search_runner.HeadlessFinder, 'run',
                            _hold_then_find(release))
        seen = []
        assert await coordinator.start(
            member.id, workspace_id, request, lambda m: seen.append(m) or _noop())
        # The watcher leaves before a single result exists.
        release.set()
        await _settle(coordinator, workspace_id)

    asyncio.run(scenario())
    with test_database.session() as db:
        saved = db.get(WorkspaceRecord, workspace_id)
        assert [row['aztek_id'] for row in saved.results] == ['10']
        job = db.scalars(select(Job).where(Job.workspace_id == workspace_id)).one()
        assert job.status == 'done'


def test_scoped_item_finder_search_excludes_sibling_product_group(
        test_settings, test_database, member, monkeypatch):
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(
            member.id, 'shop', 'direct-plan.xlsx')
        workspace.criteria = [
            {'kind': '11', 'name': 'A only', 'sources': ['Product A'],
             'group_keys': ['group-a']},
            {'kind': '12', 'name': 'Shared',
             'sources': ['Product A', 'Product B'],
             'group_keys': ['group-a', 'group-b']},
            {'kind': '99', 'name': 'B only', 'sources': ['Product B'],
             'group_keys': ['group-b']},
        ]
        workspace.occurrences = [dict(row) for row in workspace.criteria]
        workspace_id = workspace.id

    coordinator = _coordinator(test_settings, test_database)
    ran_with = {}

    async def fake_run(finder, data, storage_state):
        ran_with['criteria'] = [
            (row['kind'], row.get('sources'), row.get('group_keys'))
            for row in data['multi']]
        ran_with['occurrences'] = [
            (row['kind'], row.get('sources'), row.get('group_keys'))
            for row in finder._occurrences]

    async def scenario():
        monkeypatch.setattr(search_runner.HeadlessFinder, 'run', fake_run)
        assert await coordinator.start(
            member.id, workspace_id,
            {'game': 'CabalM SEA', 'web_mode': 'any',
             'source_group_key': 'group-a'},
            lambda message: _noop())
        await _settle(coordinator, workspace_id)

    asyncio.run(scenario())
    expected = [
        ('11', ['Product A'], ['group-a']),
        ('12', ['Product A'], ['group-a']),
    ]
    assert ran_with['criteria'] == expected
    assert ran_with['occurrences'] == expected


def test_sequential_scoped_searches_preserve_both_product_groups_in_api(
        client, test_settings, test_database, member, monkeypatch):
    """Searching Product B must not erase the Product A result persisted first."""
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(
            member.id, 'shop', 'two-products.xlsx')
        workspace.criteria = [
            {'kind': '11', 'opt': '', 'dur': '', 'name': 'A only',
             'sources': ['Product A'], 'group_keys': ['group-a']},
            {'kind': '12', 'opt': '', 'dur': '', 'name': 'Shared',
             'sources': ['Product A', 'Product B'],
             'group_keys': ['group-a', 'group-b']},
            {'kind': '13', 'opt': '', 'dur': '', 'name': 'B only',
             'sources': ['Product B'], 'group_keys': ['group-b']},
        ]
        workspace.occurrences = [dict(row) for row in workspace.criteria]
        workspace.results = [{
            'aztek_id': '404', 'item_name': 'Unscoped existing',
            'item_kind': '77', 'item_option': '', 'duration_index': '',
            'sources': [], 'group_keys': [], 'groups': ''}]
        workspace_id = workspace.id

    coordinator = _coordinator(test_settings, test_database)
    ids = {'11': '101', '12': '202', '13': '303'}

    async def fake_run(finder, data, storage_state):
        finder._results = [
            {'aztek_id': ids[row['kind']], 'item_name': row['name'] + ' web',
             'item_kind': row['kind'], 'item_option': row.get('opt', ''),
             'duration_index': row.get('dur', ''), 'game': data['game']}
            for row in data['multi']]
        finder._regroup_results()

    async def scenario():
        monkeypatch.setattr(search_runner.HeadlessFinder, 'run', fake_run)
        for group_key in ('group-a', 'group-b'):
            assert await coordinator.start(
                member.id, workspace_id,
                {'game': 'CabalM SEA', 'web_mode': 'any',
                 'source_group_key': group_key},
                lambda message: _noop())
            await _settle(coordinator, workspace_id)

    asyncio.run(scenario())
    response = client.get('/api/workspaces/' + workspace_id)
    assert response.status_code == 200
    rows = response.json()['results']
    assert [row['aztek_id'] for row in rows] == ['101', '202', '303', '404']
    assert [row['group_keys'] for row in rows] == [
        ['group-a'], ['group-a', 'group-b'], ['group-b'], []]
    assert len([row for row in rows if row['aztek_id'] == '202']) == 1


def test_sequential_shared_group_searches_keep_changed_ids_in_exact_scope(
        client, test_settings, test_database, member, monkeypatch):
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(
            member.id, 'shop', 'changed-shared-result.xlsx')
        workspace.criteria = [{
            'kind': '12', 'opt': '', 'dur': '', 'name': 'Shared',
            'sources': ['Product A', 'Product B'],
            'group_keys': ['group-a', 'group-b']}]
        workspace.occurrences = [dict(workspace.criteria[0])]
        workspace.results = [{
            'aztek_id': '404', 'item_name': 'Unscoped existing',
            'item_kind': '77', 'item_option': '', 'duration_index': '',
            'sources': [], 'group_keys': [], 'groups': ''}]
        workspace_id = workspace.id

    coordinator = _coordinator(test_settings, test_database)

    async def fake_run(finder, data, storage_state):
        group_key = data['multi'][0]['group_keys'][0]
        finder._results = [{
            'aztek_id': '20' if group_key == 'group-a' else '21',
            'item_name': 'Shared web', 'item_kind': '12',
            'item_option': '', 'duration_index': '', 'game': data['game']}]
        finder._regroup_results()

    async def scenario():
        monkeypatch.setattr(search_runner.HeadlessFinder, 'run', fake_run)
        for group_key in ('group-a', 'group-b'):
            assert await coordinator.start(
                member.id, workspace_id,
                {'game': 'CabalM SEA', 'web_mode': 'any',
                 'source_group_key': group_key}, lambda message: _noop())
            await _settle(coordinator, workspace_id)

    asyncio.run(scenario())
    response = client.get('/api/workspaces/' + workspace_id)
    assert response.status_code == 200
    by_id = {row['aztek_id']: row for row in response.json()['results']}
    assert set(by_id) == {'20', '21', '404'}
    assert (by_id['20']['sources'], by_id['20']['group_keys']) == (
        ['Product A'], ['group-a'])
    assert (by_id['21']['sources'], by_id['21']['group_keys']) == (
        ['Product B'], ['group-b'])
    assert (by_id['404']['sources'], by_id['404']['group_keys']) == ([], [])


async def _noop():
    return None


def test_coming_back_replays_the_log_and_streams_the_rest(
    test_settings, test_database, member, monkeypatch
):
    """Reconnecting subscribes to the same run rather than starting a second."""
    workspace_id = _searchable_workspace(member, test_database)
    coordinator = _coordinator(test_settings, test_database)
    request = {'game': 'CabalM SEA', 'web_mode': 'any'}
    seen = []

    async def scenario():
        release = asyncio.Event()
        monkeypatch.setattr(search_runner.HeadlessFinder, 'run',
                            _hold_then_find(release))

        async def emit(message):
            seen.append(message)

        assert await coordinator.start(member.id, workspace_id, request, emit)
        # Starting again is the reconnect: same run, no second job.
        assert await coordinator.start(member.id, workspace_id, request, emit)
        watcher = asyncio.ensure_future(coordinator.attach(workspace_id, emit))
        # Let it subscribe before the run can finish out from under it.
        while not coordinator.live(workspace_id).subscribers:
            await asyncio.sleep(0.01)
        release.set()
        await _settle(coordinator, workspace_id)
        await watcher

    asyncio.run(scenario())
    # The 'job' line was published before this watcher attached — it is replay.
    assert seen and seen[0]['type'] == 'job'
    assert [m['type'] for m in seen].count('result') == 1
    assert seen[-1]['type'] == 'done'
    with test_database.session() as db:
        jobs = db.scalars(select(Job).where(Job.workspace_id == workspace_id)).all()
    assert len(jobs) == 1, 'reconnecting must not start a second search'


def test_scoped_start_refuses_an_unscoped_live_search_and_exposes_its_scope(
        client, test_settings, test_database, member, monkeypatch):
    """A Product handoff cannot reuse a workspace-wide run's result stream."""
    workspace_id = _searchable_workspace(member, test_database)
    coordinator = _coordinator(test_settings, test_database)
    refused = []

    async def scenario():
        release = asyncio.Event()
        monkeypatch.setattr(search_runner.HeadlessFinder, 'run',
                            _hold_then_find(release))
        assert await coordinator.start(
            member.id, workspace_id,
            {'game': 'CabalM SEA', 'web_mode': 'any'},
            lambda message: _noop())
        live = coordinator.live(workspace_id)
        assert live.source_group_key == ''

        async def emit(message):
            refused.append(message)

        assert await coordinator.start(
            member.id, workspace_id,
            {'game': 'CabalM SEA', 'web_mode': 'any',
             'source_group_key': 'group-a'}, emit) is False
        response = client.get('/api/workspaces/' + workspace_id)
        assert response.json()['running_job']['source_group_key'] == ''
        release.set()
        await _settle(coordinator, workspace_id)

    asyncio.run(scenario())
    assert [message['type'] for message in refused] == ['error', 'done']
    assert refused[0]['code'] == 'search_scope_mismatch'


def test_attach_replays_only_when_the_requested_scope_matches(
        test_settings, test_database, member, monkeypatch):
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(member.id, 'shop', 'a.xlsx')
        workspace.criteria = [{
            'kind': '1', 'opt': '', 'dur': '', 'name': 'A',
            'sources': ['Product A'], 'group_keys': ['group-a']}]
        workspace.occurrences = [dict(workspace.criteria[0])]
        workspace_id = workspace.id
    coordinator = _coordinator(test_settings, test_database)
    refused = []
    matched = []

    async def scenario():
        release = asyncio.Event()
        monkeypatch.setattr(search_runner.HeadlessFinder, 'run',
                            _hold_then_find(release))
        assert await coordinator.start(
            member.id, workspace_id,
            {'game': 'CabalM SEA', 'web_mode': 'any',
             'source_group_key': 'group-a'}, lambda message: _noop())

        async def refused_emit(message):
            refused.append(message)

        assert await coordinator.attach(
            workspace_id, refused_emit, 'group-b') is False

        async def matched_emit(message):
            matched.append(message)

        watcher = asyncio.ensure_future(coordinator.attach(
            workspace_id, matched_emit, 'group-a'))
        while not coordinator.live(workspace_id).subscribers:
            await asyncio.sleep(0.01)
        release.set()
        await _settle(coordinator, workspace_id)
        assert await watcher is True

    asyncio.run(scenario())
    assert [message['type'] for message in refused] == ['error', 'done']
    assert refused[0]['code'] == 'search_scope_mismatch'
    assert not any(message['type'] == 'result' for message in refused)
    assert any(message['type'] == 'result' for message in matched)


def test_stopping_is_a_request_of_its_own(
    test_settings, test_database, member, monkeypatch
):
    """A closed socket no longer cancels, so Stop is asked for on its own."""
    workspace_id = _searchable_workspace(member, test_database)
    coordinator = _coordinator(test_settings, test_database)

    async def scenario():
        release = asyncio.Event()
        monkeypatch.setattr(search_runner.HeadlessFinder, 'run',
                            _hold_then_find(release))
        assert await coordinator.start(
            member.id, workspace_id, {'game': 'CabalM SEA', 'web_mode': 'any'},
            lambda m: _noop())
        assert coordinator.stop(workspace_id) is True
        release.set()
        await _settle(coordinator, workspace_id)
        # Nothing running: the answer is no, not an error.
        assert coordinator.stop(workspace_id) is False

    asyncio.run(scenario())
    with test_database.session() as db:
        job = db.scalars(select(Job).where(Job.workspace_id == workspace_id)).one()
    assert job.status == 'cancelled'


def test_searching_again_runs_only_the_misses_and_keeps_the_finds(
    test_settings, test_database, member, monkeypatch
):
    """Re-running the whole plan to chase two stragglers costs the whole plan.

    The retry searches only the rows that came back empty, and what the first
    pass found is still there when it ends.
    """
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(member.id, 'event', 'plan.xlsx')
        workspace.criteria = [
            {'kind': '1', 'opt': '', 'dur': '', 'name': 'found'},
            {'kind': '2', 'opt': '', 'dur': '', 'name': 'missing'},
        ]
        workspace.occurrences = [
            {'kind': '1', 'opt': '', 'dur': '', 'name': 'found', 'sources': ['G1']},
            {'kind': '2', 'opt': '', 'dur': '', 'name': 'missing', 'sources': ['G1']},
        ]
        # As if a first pass had found one of the two.
        workspace.results = [{'aztek_id': '10', 'item_name': 'A', 'item_kind': '1',
                              'item_option': '', 'duration_index': '',
                              'sources': ['G1'], 'groups': 'G1'}]
        workspace.not_found = [['#2 Kind=2', 'ไม่พบ row ที่ตรงเงื่อนไข']]
        workspace_id = workspace.id

    coordinator = _coordinator(test_settings, test_database)
    ran_with = {}

    async def fake_run(finder, data, storage_state):
        ran_with['kinds'] = [row['kind'] for row in data['multi']]
        row = {'aztek_id': '20', 'item_name': 'B', 'item_kind': '2',
               'item_option': '', 'duration_index': '', 'game': data['game']}
        finder._results = [row]
        finder.add_result_row(row)

    async def scenario():
        monkeypatch.setattr(search_runner.HeadlessFinder, 'run', fake_run)
        assert await coordinator.start(
            member.id, workspace_id,
            {'game': 'CabalM SEA', 'web_mode': 'any', 'only_missing': True},
            lambda m: _noop())
        await _settle(coordinator, workspace_id)

    asyncio.run(scenario())
    assert ran_with['kinds'] == ['2'], 'the row already found must not be searched again'
    with test_database.session() as db:
        saved = db.get(WorkspaceRecord, workspace_id)
    assert [row['aztek_id'] for row in saved.results] == ['10', '20']


def test_scoped_retry_persists_every_scope_but_replays_only_its_product_group(
        client, test_settings, test_database, member, monkeypatch):
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(
            member.id, 'shop', 'scoped-retry.xlsx')
        workspace.criteria = [
            {'kind': '1', 'opt': '', 'dur': '', 'name': 'A found',
             'sources': ['Product A'], 'group_keys': ['group-a']},
            {'kind': '2', 'opt': '', 'dur': '', 'name': 'A missing',
             'sources': ['Product A'], 'group_keys': ['group-a']},
            {'kind': '3', 'opt': '', 'dur': '', 'name': 'B sibling',
             'sources': ['Product B'], 'group_keys': ['group-b']},
        ]
        workspace.occurrences = [dict(row) for row in workspace.criteria]
        workspace.results = [
            {'aztek_id': '10', 'item_name': 'A found', 'item_kind': '1',
             'item_option': '', 'duration_index': '',
             'sources': ['Product A'], 'group_keys': ['group-a'],
             'groups': 'Product A'},
            {'aztek_id': '30', 'item_name': 'B sibling', 'item_kind': '3',
             'item_option': '', 'duration_index': '',
             'sources': ['Product B'], 'group_keys': ['group-b'],
             'groups': 'Product B'},
            {'aztek_id': '40', 'item_name': 'Unscoped', 'item_kind': '4',
             'item_option': '', 'duration_index': '',
             'sources': [], 'group_keys': [], 'groups': ''},
        ]
        workspace.not_found = [['#2 Kind=2', 'missing']]
        workspace_id = workspace.id

    coordinator = _coordinator(test_settings, test_database)
    streamed = []

    async def scenario():
        release = asyncio.Event()

        async def fake_run(finder, data, storage_state):
            await release.wait()
            row = {'aztek_id': '20', 'item_name': 'A recovered',
                   'item_kind': '2', 'item_option': '',
                   'duration_index': '', 'game': data['game']}
            finder._results = [row]
            finder.add_result_row(row)

        monkeypatch.setattr(search_runner.HeadlessFinder, 'run', fake_run)
        assert await coordinator.start(
            member.id, workspace_id,
            {'game': 'CabalM SEA', 'web_mode': 'any', 'only_missing': True,
             'source_group_key': 'group-a'}, lambda message: _noop())

        async def emit(message):
            streamed.append(message)

        watcher = asyncio.ensure_future(
            coordinator.attach(workspace_id, emit, 'group-a'))
        while not coordinator.live(workspace_id).subscribers:
            await asyncio.sleep(0.01)
        release.set()
        await _settle(coordinator, workspace_id)
        await watcher

    asyncio.run(scenario())
    reset_at = max(index for index, message in enumerate(streamed)
                   if message['type'] == 'reset_results')
    replayed_ids = [message['item']['aztek_id']
                    for message in streamed[reset_at + 1:]
                    if message['type'] == 'result']
    assert replayed_ids == ['10', '20']

    response = client.get('/api/workspaces/' + workspace_id)
    assert response.status_code == 200
    assert [row['aztek_id'] for row in response.json()['results']] == [
        '10', '20', '30', '40']


def test_searching_again_with_nothing_missing_does_not_start_a_browser(
    test_settings, test_database, member, monkeypatch
):
    """Nothing to chase is an answer, not a run — and must not wipe the results."""
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(member.id, 'event', 'plan.xlsx')
        workspace.criteria = [{'kind': '1', 'opt': '', 'dur': '', 'name': 'found'}]
        workspace.results = [{'aztek_id': '10', 'item_kind': '1',
                              'item_option': '', 'duration_index': ''}]
        workspace_id = workspace.id

    coordinator = _coordinator(test_settings, test_database)
    started = []

    async def never(finder, data, storage_state):
        started.append(True)

    async def scenario():
        monkeypatch.setattr(search_runner.HeadlessFinder, 'run', never)
        seen = []

        async def emit(message):
            seen.append(message)

        assert await coordinator.start(
            member.id, workspace_id,
            {'game': 'CabalM SEA', 'web_mode': 'any', 'only_missing': True},
            emit) is False
        return seen

    seen = asyncio.run(scenario())
    assert not started
    assert seen[-1]['type'] == 'done' and seen[-1]['count'] == 1
    with test_database.session() as db:
        assert len(db.get(WorkspaceRecord, workspace_id).results) == 1


def test_start_reservation_blocks_deletion_before_a_job_exists(
    test_settings, test_database, member, monkeypatch
):
    workspace_id = _searchable_workspace(member, test_database)
    entered = threading.Event()
    release = threading.Event()
    original_get_owned = WorkspaceRepository.get_owned

    def blocking_get_owned(repository, owner_user_id, requested_workspace_id):
        entered.set()
        assert release.wait(timeout=5)
        return original_get_owned(
            repository, owner_user_id, requested_workspace_id)

    class NoAztekSession(_StubAztek):
        def load_storage_state(self, db, user):
            return None

    monkeypatch.setattr(WorkspaceRepository, 'get_owned', blocking_get_owned)
    coordinator = SearchCoordinator(
        test_database, test_settings, NoAztekSession())

    async def emit(_message):
        return None

    def begin_start():
        return asyncio.run(coordinator.start(
            member.id, workspace_id,
            {'game': 'CabalM SEA', 'web_mode': 'any'}, emit))

    expected_busy = getattr(workspace_module, 'WorkspaceBusy', RuntimeError)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(begin_start)
        assert entered.wait(timeout=5)
        try:
            with test_database.session() as db:
                assert db.scalar(select(Job).where(
                    Job.workspace_id == workspace_id)) is None
            with pytest.raises(expected_busy):
                with coordinator.deletion_guard(workspace_id):
                    pass
        finally:
            release.set()
        assert future.result(timeout=5) is False

    with coordinator.deletion_guard(workspace_id):
        pass


def test_deletion_guard_blocks_start_with_exact_terminal_events(
    test_settings, test_database, member
):
    workspace_id = _searchable_workspace(member, test_database)
    coordinator = _coordinator(test_settings, test_database)
    seen = []

    async def emit(message):
        seen.append(message)

    with coordinator.deletion_guard(workspace_id):
        started = asyncio.run(coordinator.start(
            member.id, workspace_id,
            {'game': 'CabalM SEA', 'web_mode': 'any'}, emit))

    assert started is False
    assert seen == [
        {
            'type': 'error', 'code': 'workspace_busy',
            'msg': 'workspace กำลังใช้งานอยู่',
        },
        {'type': 'done', 'count': 0, 'not_found': []},
    ]
    with test_database.session() as db:
        assert db.scalar(select(Job).where(
            Job.workspace_id == workspace_id)) is None


def test_start_reservation_releases_after_emit_exception_and_cancellation(
    test_settings, test_database, member
):
    workspace_id = _searchable_workspace(member, test_database)

    class NoAztekSession(_StubAztek):
        def load_storage_state(self, db, user):
            return None

    coordinator = SearchCoordinator(
        test_database, test_settings, NoAztekSession())

    async def raise_emit(_message):
        raise RuntimeError('emit failed')

    with pytest.raises(RuntimeError, match='emit failed'):
        asyncio.run(coordinator.start(
            member.id, workspace_id,
            {'game': 'CabalM SEA', 'web_mode': 'any'}, raise_emit))
    with coordinator.deletion_guard(workspace_id):
        pass

    async def cancel_scenario():
        emit_entered = asyncio.Event()

        async def wait_emit(_message):
            emit_entered.set()
            await asyncio.Future()

        task = asyncio.create_task(coordinator.start(
            member.id, workspace_id,
            {'game': 'CabalM SEA', 'web_mode': 'any'}, wait_emit))
        await emit_entered.wait()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    asyncio.run(cancel_scenario())
    with coordinator.deletion_guard(workspace_id):
        pass


def test_live_search_blocks_deletion_until_finalize_has_committed(
    test_settings, test_database, member, monkeypatch
):
    workspace_id = _searchable_workspace(member, test_database)
    coordinator = _coordinator(test_settings, test_database)
    expected_busy = getattr(workspace_module, 'WorkspaceBusy', RuntimeError)

    async def scenario():
        release = asyncio.Event()
        monkeypatch.setattr(
            search_runner.HeadlessFinder, 'run', _hold_then_find(release))
        assert await coordinator.start(
            member.id, workspace_id,
            {'game': 'CabalM SEA', 'web_mode': 'any'},
            lambda _message: _noop())
        with pytest.raises(expected_busy):
            with coordinator.deletion_guard(workspace_id):
                pass
        release.set()
        await _settle(coordinator, workspace_id)
        with coordinator.deletion_guard(workspace_id):
            pass

    asyncio.run(scenario())
    with test_database.session() as db:
        job = db.scalar(select(Job).where(Job.workspace_id == workspace_id))
        assert job.status == 'done'


@pytest.mark.parametrize('failure_point', ['finder', 'scheduler'])
def test_pre_live_failure_terminalizes_queued_job_and_releases_reservation(
    test_settings, test_database, member, monkeypatch, failure_point
):
    workspace_id = _searchable_workspace(member, test_database)
    coordinator = _coordinator(test_settings, test_database)
    expected_busy = getattr(workspace_module, 'WorkspaceBusy', RuntimeError)
    original_terminalize = coordinator._fail_unstarted_job

    def terminalize_while_reserved(job_id, error):
        with pytest.raises(expected_busy):
            with coordinator.deletion_guard(workspace_id):
                pass
        original_terminalize(job_id, error)

    monkeypatch.setattr(
        coordinator, '_fail_unstarted_job', terminalize_while_reserved)

    if failure_point == 'finder':
        def fail_finder(*_args, **_kwargs):
            raise RuntimeError(
                'finder construction failed secret-cookie-value')

        monkeypatch.setattr(search_runner, 'HeadlessFinder', fail_finder)
    else:
        def fail_scheduler(coroutine):
            coroutine.close()
            raise RuntimeError(
                'task scheduling failed secret-cookie-value')

        monkeypatch.setattr(asyncio, 'ensure_future', fail_scheduler)

    seen = []

    async def emit(message):
        seen.append(message)

    started = asyncio.run(coordinator.start(
        member.id, workspace_id,
        {'game': 'CabalM SEA', 'web_mode': 'any'}, emit))

    assert started is False
    assert seen == [
        {
            'type': 'error', 'code': 'search_start_failed',
            'msg': 'เริ่มการค้นหาไม่สำเร็จ',
        },
        {'type': 'done', 'count': 0, 'not_found': []},
    ]
    assert 'secret-cookie-value' not in json.dumps(seen, ensure_ascii=False)
    assert coordinator.live(workspace_id) is None
    with coordinator.deletion_guard(workspace_id):
        pass
    with test_database.session() as db:
        job = db.scalar(select(Job).where(Job.workspace_id == workspace_id))
        assert job.status == 'failed'
        assert job.finished_at is not None
        assert job.result['reason'] == 'search_start_failed'
        assert 'secret-cookie-value' not in json.dumps(job.result)


@pytest.mark.parametrize('failure_point', ['finder', 'scheduler'])
def test_pre_live_failure_emit_preserves_websocket_disconnect_without_context(
    test_settings, test_database, member, monkeypatch, failure_point
):
    workspace_id = _searchable_workspace(member, test_database)
    coordinator = _coordinator(test_settings, test_database)

    if failure_point == 'finder':
        def fail_finder(*_args, **_kwargs):
            raise RuntimeError('finder failed secret-cookie-value')

        monkeypatch.setattr(search_runner, 'HeadlessFinder', fail_finder)
    else:
        def fail_scheduler(coroutine):
            coroutine.close()
            raise RuntimeError('scheduler failed secret-cookie-value')

        monkeypatch.setattr(asyncio, 'ensure_future', fail_scheduler)

    async def disconnected_emit(_message):
        raise WebSocketDisconnect(code=1001)

    with pytest.raises(WebSocketDisconnect) as error:
        asyncio.run(coordinator.start(
            member.id, workspace_id,
            {'game': 'CabalM SEA', 'web_mode': 'any'}, disconnected_emit))

    assert error.value.code == 1001
    assert error.value.__context__ is None
    assert error.value.__cause__ is None
    formatted = ''.join(traceback.format_exception(error.value))
    assert 'secret-cookie-value' not in formatted
    assert coordinator.live(workspace_id) is None
    with coordinator.deletion_guard(workspace_id):
        pass
    with test_database.session() as db:
        job = db.scalar(select(Job).where(Job.workspace_id == workspace_id))
        assert job.status == 'failed'
        assert job.result['reason'] == 'search_start_failed'
        assert 'secret-cookie-value' not in json.dumps(job.result)


@pytest.mark.parametrize('failure_point', ['finder', 'scheduler'])
def test_pre_live_failure_keeps_reservation_through_sanitized_emit(
    test_settings, test_database, member, monkeypatch, failure_point
):
    workspace_id = _searchable_workspace(member, test_database)
    coordinator = _coordinator(test_settings, test_database)
    expected_busy = getattr(workspace_module, 'WorkspaceBusy', RuntimeError)

    if failure_point == 'finder':
        def fail_finder(*_args, **_kwargs):
            raise RuntimeError('finder failed secret-cookie-value')

        monkeypatch.setattr(search_runner, 'HeadlessFinder', fail_finder)
    else:
        def fail_scheduler(coroutine):
            coroutine.close()
            raise RuntimeError('scheduler failed secret-cookie-value')

        monkeypatch.setattr(asyncio, 'ensure_future', fail_scheduler)

    first_seen = []
    second_seen = []

    async def scenario():
        emit_entered = asyncio.Event()
        release_emit = asyncio.Event()

        async def paused_emit(message):
            first_seen.append(message)
            if message['type'] == 'error':
                emit_entered.set()
                await release_emit.wait()

        async def second_emit(message):
            second_seen.append(message)

        first = asyncio.create_task(coordinator.start(
            member.id, workspace_id,
            {'game': 'CabalM SEA', 'web_mode': 'any'}, paused_emit))
        await emit_entered.wait()

        second_started = await coordinator.start(
            member.id, workspace_id,
            {'game': 'CabalM SEA', 'web_mode': 'any'}, second_emit)
        assert second_started is False
        assert second_seen == [
            {
                'type': 'error', 'code': 'workspace_busy',
                'msg': 'workspace กำลังใช้งานอยู่',
            },
            {'type': 'done', 'count': 0, 'not_found': []},
        ]
        with pytest.raises(expected_busy):
            with coordinator.deletion_guard(workspace_id):
                pass

        release_emit.set()
        assert await first is False
        with coordinator.deletion_guard(workspace_id):
            pass

    asyncio.run(scenario())

    assert first_seen == [
        {
            'type': 'error', 'code': 'search_start_failed',
            'msg': 'เริ่มการค้นหาไม่สำเร็จ',
        },
        {'type': 'done', 'count': 0, 'not_found': []},
    ]
    assert 'secret-cookie-value' not in json.dumps(
        first_seen + second_seen, ensure_ascii=False)
    with test_database.session() as db:
        jobs = db.scalars(select(Job).where(
            Job.workspace_id == workspace_id)).all()
        assert len(jobs) == 1
        assert jobs[0].status == 'failed'


def test_stop_route_is_owner_checked(client, other_member, client_for, member,
                                     test_database):
    """Stopping reaches into another session's run, so it is own-checked."""
    workspace_id = _searchable_workspace(member, test_database)
    assert client.post(
        '/api/workspaces/%s/search/stop' % workspace_id).json()['stopped'] is False
    intruder = client_for(other_member)
    assert intruder.post(
        '/api/workspaces/%s/search/stop' % workspace_id).status_code == 404


def test_a_job_from_a_dead_process_is_not_left_running(
    application, test_database, member
):
    """A run cannot survive a restart, so a job still marked running at startup
    belongs to nobody — and a page would wait on it forever."""
    workspace_id = _searchable_workspace(member, test_database)
    with test_database.session() as db:
        db.add(Job(owner_user_id=member.id, workspace_id=workspace_id,
                   tool='item_finder', status='running', config={}))

    swept = application.state.search_coordinator.sweep_interrupted_jobs()
    assert swept == 1
    with test_database.session() as db:
        job = db.scalars(select(Job).where(Job.workspace_id == workspace_id)).one()
    assert job.status == 'failed'
    assert job.result['code'] == 'interrupted'


def test_failed_search_clears_previous_workspace_results(client, member, test_database):
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(
            member.id, 'event', 'template.xlsx', [{'kind': '1'}]
        )
        workspace.results = [{'aztek_id': 'OLD'}]
        workspace.not_found = [['old', 'old']]
        workspace_id = workspace.id

    _connect_aztek(client)
    with client.websocket_connect('/ws/search') as websocket:
        websocket.send_json({
            'workspace_id': workspace_id, 'game': 'INVALID GAME', 'web_mode': 'any',
        })
        while True:
            message = websocket.receive_json()
            if message['type'] == 'done':
                break

    with test_database.session() as db:
        saved = db.get(WorkspaceRecord, workspace_id)
        assert saved is not None
        assert saved.results == []
        assert saved.not_found == []


def test_invalid_mode_and_bundle_indexes_are_rejected_not_server_errors(
    client, member, test_database
):
    response = client.post(
        '/api/import-template', data={'mode': 'invalid'},
        files={'file': ('template.xlsx', make_template_bytes(), 'application/octet-stream')},
    )
    assert response.status_code in (400, 422)
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(member.id, 'event')
        workspace.results = [{'aztek_id': '1', 'item_name': 'A'}]
        workspace_id = workspace.id
    response = client.post(
        f'/api/workspaces/{workspace_id}/bundles',
        json={'selected_indexes': [0, 'bad']},
    )
    assert response.status_code in (400, 422)
