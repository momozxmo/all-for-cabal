import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from starlette.websockets import WebSocketDisconnect

from web import app as web_app
from web import workspaces as workspace_module
from web.models import Job, PendingImportRecord, WorkspaceRecord
from web.workspaces import PendingImportNotFound, WorkspaceNotFound, WorkspaceRepository


def test_anonymous_item_finder_routes_return_json_401_and_health_is_public(
    anonymous_client
):
    assert anonymous_client.get('/api/health').json() == {'ok': True}

    responses = [
        anonymous_client.get('/api/games'),
        anonymous_client.get('/api/modes'),
        anonymous_client.get('/api/template'),
        anonymous_client.post('/api/import-template', files={
            'file': ('template.xlsx', b'not-read', 'application/octet-stream'),
        }),
        anonymous_client.post('/api/import-plan', files={
            'file': ('plan.xlsx', b'not-read', 'application/octet-stream'),
        }),
        anonymous_client.post('/api/import-plan/apply', json={
            'pending_id': 'missing', 'selected_sheets': ['One'],
        }),
        anonymous_client.post('/api/products/options', json={
            'game': 'CabalM TH', 'kinds': ['currencies'],
        }),
        anonymous_client.get('/api/workspaces/missing'),
        anonymous_client.delete('/api/workspaces/missing'),
        anonymous_client.get('/api/workspaces/missing/export.csv'),
        anonymous_client.get('/api/workspaces/missing/export.xlsx'),
        anonymous_client.get('/api/workspaces/missing/products'),
        anonymous_client.post('/api/workspaces/missing/bundles', json={
            'selected_indexes': [],
        }),
    ]

    for response in responses:
        assert response.status_code == 401
        assert response.headers['content-type'].startswith('application/json')
        assert response.json()['detail']


def test_other_user_cannot_read_export_delete_or_bundle(
    client_for, test_database, member, other_member
):
    legacy_workspace = web_app.WORKSPACES.create('event', 'owned.xlsx')
    legacy_workspace.results = [
        {'aztek_id': '1', 'item_name': 'owned', 'sources': ['G1']},
    ]
    with test_database.session() as db:
        db.add(WorkspaceRecord(
            id=legacy_workspace.id,
            owner_user_id=member.id,
            mode='event',
            filename='owned.xlsx',
            results=[{'aztek_id': '1', 'item_name': 'owned', 'sources': ['G1']}],
        ))
    outsider = client_for(other_member)
    wid = legacy_workspace.id

    assert outsider.get(f'/api/workspaces/{wid}').status_code == 404
    assert outsider.get(f'/api/workspaces/{wid}/export.csv').status_code == 404
    assert outsider.get(f'/api/workspaces/{wid}/export.xlsx').status_code == 404
    assert outsider.get(f'/api/workspaces/{wid}/products').status_code == 404
    assert outsider.delete(f'/api/workspaces/{wid}').status_code == 404
    assert outsider.post(
        f'/api/workspaces/{wid}/bundles', json={'selected_indexes': []}
    ).status_code == 404


def test_other_user_cannot_apply_a_pending_import(
    client_for, test_database, member, other_member
):
    legacy_workspace = web_app.WORKSPACES.create('event', 'owned.xlsx')
    legacy_pending = web_app.WORKSPACES.add_pending(
        legacy_workspace.id, [('One', [{'kind': '1'}])], []
    )
    with test_database.session() as db:
        db.add(WorkspaceRecord(
            id=legacy_workspace.id,
            owner_user_id=member.id,
            mode='event',
            filename='owned.xlsx',
        ))
        db.add(PendingImportRecord(
            id=legacy_pending.id,
            owner_user_id=member.id,
            workspace_id=legacy_workspace.id,
            sheets=[('One', [{'kind': '1'}])],
            skipped=[],
        ))

    response = client_for(other_member).post('/api/import-plan/apply', json={
        'pending_id': legacy_pending.id,
        'selected_sheets': ['One'],
    })

    assert response.status_code == 404


def test_unauthenticated_websocket_is_rejected(anonymous_client):
    with pytest.raises(WebSocketDisconnect) as error:
        with anonymous_client.websocket_connect('/ws/search'):
            pass
    assert error.value.code == 4401


def test_websocket_rejects_unknown_and_foreign_workspaces(
    client_for, other_member, workspace_for_member
):
    for workspace_id in ('missing-workspace', workspace_for_member.id):
        client = client_for(other_member)
        with client.websocket_connect('/ws/search') as websocket:
            websocket.send_json({'workspace_id': workspace_id})
            with pytest.raises(WebSocketDisconnect) as error:
                websocket.receive_json()
        assert error.value.code == 4404


def test_workspace_repository_scopes_every_workspace_lookup_and_mutation(
    db_session, member, other_member
):
    repo = WorkspaceRepository(db_session)
    workspace = repo.create(member.id, 'event', 'a.xlsx', [{'kind': '1'}])

    assert repo.get_owned(member.id, workspace.id).id == workspace.id

    for owner_id, workspace_id in (
        (other_member.id, workspace.id),
        (member.id, 'missing-workspace'),
    ):
        with pytest.raises(WorkspaceNotFound):
            repo.get_owned(owner_id, workspace_id)
        with pytest.raises(WorkspaceNotFound):
            repo.delete_owned(owner_id, workspace_id)
        with pytest.raises(WorkspaceNotFound):
            repo.replace_template(owner_id, workspace_id, 'b.xlsx', [])
        with pytest.raises(WorkspaceNotFound):
            repo.save_results(
                owner_id, workspace_id, game='cabal', results=[], not_found=[]
            )

    assert repo.get_owned(member.id, workspace.id).filename == 'a.xlsx'
    replaced = repo.replace_template(member.id, workspace.id, 'b.xlsx', [{'kind': '2'}])
    assert replaced.filename == 'b.xlsx'
    assert replaced.criteria == [{'kind': '2'}]
    saved = repo.save_results(
        member.id, workspace.id, game='cabal', results=[{'id': '10'}], not_found=['2']
    )
    assert (saved.game, saved.results, saved.not_found) == (
        'cabal', [{'id': '10'}], ['2']
    )

    repo.delete_owned(member.id, workspace.id)
    with pytest.raises(WorkspaceNotFound):
        repo.get_owned(member.id, workspace.id)


def test_pending_import_cannot_cross_users_or_attach_to_foreign_workspace(
    db_session, member, other_member
):
    repo = WorkspaceRepository(db_session)
    workspace = repo.create(member.id, 'shop')

    with pytest.raises(WorkspaceNotFound):
        repo.add_pending(other_member.id, workspace.id, [], [])
    with pytest.raises(WorkspaceNotFound):
        repo.add_pending(member.id, 'missing-workspace', [], [])

    pending = repo.add_pending(
        member.id,
        workspace.id,
        [
            ('Selected', [{'kind': '1', 'sources': ['A']}]),
            ('Not selected', [{'kind': '2', 'sources': ['B']}]),
        ],
        ['skip'],
    )
    for owner_id, pending_id in (
        (other_member.id, pending.id),
        (member.id, 'missing-pending'),
    ):
        with pytest.raises(PendingImportNotFound):
            repo.apply_pending(owner_id, pending_id, ['Selected'])

    applied = repo.apply_pending(member.id, pending.id, ['Selected'])
    assert applied.criteria == [{'kind': '1', 'sources': ['A']}]
    assert applied.occurrences == [{'kind': '1', 'sources': ['A']}]
    assert applied.skipped == ['skip']
    with pytest.raises(PendingImportNotFound):
        repo.apply_pending(member.id, pending.id, ['Selected'])


def test_apply_pending_rolls_back_claim_if_workspace_update_fails(
    db_session, test_database, member, monkeypatch
):
    repo = WorkspaceRepository(db_session)
    workspace = repo.create(member.id, 'event')
    pending = repo.add_pending(
        member.id, workspace.id, [('One', [{'kind': '1', 'sources': ['A']}])], []
    )
    db_session.commit()

    def fail_workspace_update(*_args, **_kwargs):
        raise RuntimeError('workspace update failed after claim')

    monkeypatch.setattr(repo, '_update_workspace', fail_workspace_update)
    with pytest.raises(RuntimeError, match='workspace update failed after claim'):
        repo.apply_pending(member.id, pending.id, ['One'])

    with test_database.session() as fresh_session:
        fresh_repo = WorkspaceRepository(fresh_session)
        unchanged = fresh_repo.get_owned(member.id, workspace.id)
        persisted_pending = fresh_session.get(PendingImportRecord, pending.id)

        assert unchanged.criteria == []
        assert unchanged.occurrences == []
        assert persisted_pending is not None
        assert persisted_pending.sheets == [['One', [{'kind': '1', 'sources': ['A']}]]]


def test_two_pending_imports_persist_both_merges_across_fresh_sessions(
    db_session, test_database, member
):
    repo = WorkspaceRepository(db_session)
    workspace = repo.create(member.id, 'event')
    first = repo.add_pending(
        member.id, workspace.id, [('One', [{'kind': '1', 'sources': ['A']}])], []
    )
    second = repo.add_pending(
        member.id, workspace.id, [('Two', [{'kind': '2', 'sources': ['B']}])], []
    )
    db_session.commit()

    with test_database.session() as first_session:
        WorkspaceRepository(first_session).apply_pending(member.id, first.id, ['One'])

    with test_database.session() as second_session:
        WorkspaceRepository(second_session).apply_pending(member.id, second.id, ['Two'])

    with test_database.session() as final_session:
        persisted = WorkspaceRepository(final_session).get_owned(member.id, workspace.id)

        assert [row['kind'] for row in persisted.criteria] == ['1', '2']
        assert [row['kind'] for row in persisted.occurrences] == ['1', '2']


def _workspace_pending_snapshot(database, workspace_id, pending_id):
    with database.session() as db:
        workspace = db.get(WorkspaceRecord, workspace_id)
        pending = db.get(PendingImportRecord, pending_id)
        return (
            None if workspace is None else (
                list(workspace.criteria), list(workspace.occurrences),
                list(workspace.skipped),
            ),
            None if pending is None else (
                list(pending.sheets), list(pending.skipped),
            ),
        )


@pytest.mark.parametrize(
    'selected_sheets,stored_sheets,exception_name',
    [
        ([], [('Plan', [{'kind': '1'}])], 'EmptySheetSelection'),
        (['Plan', 'Plan'], [('Plan', [{'kind': '1'}])],
         'DuplicateSheetSelection'),
        (['Plan'], [('Plan', [{'kind': '1'}]), ('Plan', [{'kind': '2'}])],
         'DuplicateSheetSelection'),
        (['plan'], [('Plan', [{'kind': '1'}])], 'UnknownSheetSelection'),
        (['Missing'], [('Plan', [{'kind': '1'}])], 'UnknownSheetSelection'),
    ],
)
def test_apply_pending_rejects_invalid_exact_sheet_selection_without_mutation(
    test_database, member, selected_sheets, stored_sheets, exception_name
):
    with test_database.session() as db:
        repository = WorkspaceRepository(db)
        workspace = repository.create(
            member.id, 'event', 'exact.xlsx', [{'kind': 'old'}])
        workspace.occurrences = [{'kind': 'old'}]
        workspace.skipped = ['existing']
        pending = repository.add_pending(
            member.id, workspace.id, stored_sheets, ['pending-skip'])
        workspace_id = workspace.id
        pending_id = pending.id

    before = _workspace_pending_snapshot(
        test_database, workspace_id, pending_id)
    expected_error = getattr(workspace_module, exception_name, ValueError)

    with pytest.raises(expected_error):
        with test_database.session() as db:
            WorkspaceRepository(db).apply_pending(
                member.id, pending_id, selected_sheets)

    assert _workspace_pending_snapshot(
        test_database, workspace_id, pending_id) == before


def test_apply_pending_two_fresh_sessions_have_exactly_one_winner(
    test_database, member
):
    with test_database.session() as db:
        repository = WorkspaceRepository(db)
        workspace = repository.create(member.id, 'event', 'race.xlsx')
        pending = repository.add_pending(
            member.id, workspace.id,
            [('Plan', [{'kind': '1', 'sources': ['A']}])], [])
        workspace_id = workspace.id
        pending_id = pending.id

    barrier = threading.Barrier(2)

    def apply_once():
        barrier.wait(timeout=5)
        try:
            with test_database.session() as db:
                WorkspaceRepository(db).apply_pending(
                    member.id, pending_id, ['Plan'])
            return 'success'
        except PendingImportNotFound:
            return 'not_found'

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _index: apply_once(), range(2)))

    assert sorted(outcomes) == ['not_found', 'success']
    with test_database.session() as db:
        workspace = db.get(WorkspaceRecord, workspace_id)
        assert [row['kind'] for row in workspace.criteria] == ['1']
        assert db.get(PendingImportRecord, pending_id) is None


def test_apply_pending_exhausted_real_sqlite_lock_maps_to_workspace_busy(
    test_database, member
):
    with test_database.session() as db:
        repository = WorkspaceRepository(db)
        workspace = repository.create(member.id, 'event', 'busy.xlsx')
        pending = repository.add_pending(
            member.id, workspace.id, [('Plan', [{'kind': '1'}])], [])
        workspace_id = workspace.id
        pending_id = pending.id

    contender = test_database._session_factory()
    contender.connection().exec_driver_sql('PRAGMA busy_timeout=10')
    contender.rollback()
    locker = test_database.engine.connect()
    locker.exec_driver_sql('BEGIN IMMEDIATE')
    expected_error = getattr(workspace_module, 'WorkspaceBusy', RuntimeError)
    try:
        with pytest.raises(expected_error):
            WorkspaceRepository(contender).apply_pending(
                member.id, pending_id, ['Plan'])
    finally:
        contender.rollback()
        contender.close()
        locker.rollback()
        locker.close()

    workspace_snapshot, pending_snapshot = _workspace_pending_snapshot(
        test_database, workspace_id, pending_id)
    assert workspace_snapshot[0] == []
    assert pending_snapshot is not None


def test_apply_pending_reraises_unrelated_operational_error_after_rollback(
    test_database, member, monkeypatch
):
    with test_database.session() as db:
        repository = WorkspaceRepository(db)
        workspace = repository.create(member.id, 'event', 'unrelated.xlsx')
        pending = repository.add_pending(
            member.id, workspace.id, [('Plan', [{'kind': '1'}])], [])
        workspace_id = workspace.id
        pending_id = pending.id

    original_execute = workspace_module.Session.execute

    def raise_unrelated(session, statement, *args, **kwargs):
        if getattr(statement, 'is_delete', False):
            raise OperationalError(
                'DELETE pending_imports', {},
                sqlite3.OperationalError('unrelated operational failure'))
        return original_execute(session, statement, *args, **kwargs)

    monkeypatch.setattr(workspace_module.Session, 'execute', raise_unrelated)
    with pytest.raises(OperationalError, match='unrelated operational failure'):
        with test_database.session() as db:
            WorkspaceRepository(db).apply_pending(
                member.id, pending_id, ['Plan'])

    workspace_snapshot, pending_snapshot = _workspace_pending_snapshot(
        test_database, workspace_id, pending_id)
    assert workspace_snapshot[0] == []
    assert pending_snapshot is not None


def test_workspace_delete_uses_database_cascade_and_set_null_with_loaded_children(
    test_database, member
):
    with test_database.session() as db:
        repository = WorkspaceRepository(db)
        workspace = repository.create(member.id, 'event', 'history.xlsx')
        pending = repository.add_pending(
            member.id, workspace.id, [('Plan', [{'kind': '1'}])], [])
        job = Job(
            owner_user_id=member.id, workspace_id=workspace.id,
            tool='item_finder', status='done', config={})
        db.add(job)
        db.flush()
        pending_id = pending.id
        job_id = job.id
        workspace_id = workspace.id

    with test_database.session() as db:
        workspace = db.get(WorkspaceRecord, workspace_id)
        assert [row.id for row in workspace.pending_imports] == [pending_id]
        assert [row.id for row in workspace.jobs] == [job_id]
        WorkspaceRepository(db).delete_owned(member.id, workspace_id)

    with test_database.session() as db:
        assert db.get(WorkspaceRecord, workspace_id) is None
        assert db.get(PendingImportRecord, pending_id) is None
        db.expire_all()
        surviving_job = db.get(Job, job_id)
        assert surviving_job is not None
        assert surviving_job.workspace_id is None


@pytest.mark.parametrize('status', ['queued', 'running'])
def test_workspace_delete_route_refuses_any_active_job_for_workspace(
    client, test_database, member, other_member, status
):
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(
            member.id, 'event', f'{status}.xlsx')
        workspace_id = workspace.id
        db.add(Job(
            owner_user_id=other_member.id,
            workspace_id=workspace_id,
            tool='item_finder', status=status, config={},
        ))

    response = client.delete(f'/api/workspaces/{workspace_id}')

    assert response.status_code == 409
    assert response.json() == {'detail': 'workspace_busy'}
    with test_database.session() as db:
        assert db.get(WorkspaceRecord, workspace_id) is not None


def test_workspace_delete_route_allows_terminal_jobs_and_preserves_history(
    client, test_database, member
):
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(
            member.id, 'event', 'terminal.xlsx')
        workspace_id = workspace.id
        jobs = [
            Job(owner_user_id=member.id, workspace_id=workspace_id,
                tool='item_finder', status=status, config={})
            for status in ('done', 'failed', 'cancelled')
        ]
        db.add_all(jobs)
        db.flush()
        job_ids = [job.id for job in jobs]

    assert client.delete(f'/api/workspaces/{workspace_id}').status_code == 204
    with test_database.session() as db:
        assert db.get(WorkspaceRecord, workspace_id) is None
        assert [db.get(Job, job_id).workspace_id for job_id in job_ids] == [
            None, None, None]


def test_cross_owner_delete_returns_404_before_coordinator_guard(
    client_for, application, test_database, member, other_member, monkeypatch
):
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(
            member.id, 'event', 'private.xlsx')
        workspace_id = workspace.id

    def forbidden_guard(_workspace_id):
        raise AssertionError('coordinator state consulted before owner check')

    monkeypatch.setattr(
        application.state.search_coordinator, 'deletion_guard', forbidden_guard,
        raising=False)

    response = client_for(other_member).delete(
        f'/api/workspaces/{workspace_id}')
    assert response.status_code == 404


def test_apply_route_maps_exact_selection_errors_without_mutation(
    client, test_database, member
):
    cases = [
        ([], 'กรุณาเลือกอย่างน้อย 1 sheet'),
        (['Plan', 'Plan'], 'เลือก sheet ซ้ำกัน'),
        (['plan'], 'ไม่พบ sheet ที่เลือก'),
        (['Missing'], 'ไม่พบ sheet ที่เลือก'),
    ]
    for selected, detail in cases:
        with test_database.session() as db:
            repository = WorkspaceRepository(db)
            workspace = repository.create(member.id, 'event', 'route.xlsx')
            pending = repository.add_pending(
                member.id, workspace.id, [('Plan', [{'kind': '1'}])], [])
            workspace_id = workspace.id
            pending_id = pending.id

        response = client.post('/api/import-plan/apply', json={
            'pending_id': pending_id, 'selected_sheets': selected,
        })
        assert response.status_code == 400
        assert response.json() == {'detail': detail}
        workspace_snapshot, pending_snapshot = _workspace_pending_snapshot(
            test_database, workspace_id, pending_id)
        assert workspace_snapshot[0] == []
        assert pending_snapshot is not None


def test_apply_route_real_commit_busy_returns_409_and_restores_both_rows(
    client, test_database, member
):
    with test_database.session() as db:
        repository = WorkspaceRepository(db)
        workspace = repository.create(member.id, 'event', 'commit-busy.xlsx')
        pending = repository.add_pending(
            member.id, workspace.id, [('Plan', [{'kind': '1'}])], [])
        workspace_id = workspace.id
        pending_id = pending.id

    def short_busy_timeout(dbapi_connection, _connection_record, _proxy):
        dbapi_connection.execute('PRAGMA busy_timeout=20')

    event.listen(test_database.engine, 'checkout', short_busy_timeout)
    reader = test_database.engine.connect()
    reader.exec_driver_sql('BEGIN')
    reader.exec_driver_sql('SELECT id FROM workspaces').all()
    try:
        response = client.post('/api/import-plan/apply', json={
            'pending_id': pending_id, 'selected_sheets': ['Plan'],
        })
    finally:
        reader.rollback()
        reader.close()
        event.remove(test_database.engine, 'checkout', short_busy_timeout)

    assert response.status_code == 409
    assert response.json() == {'detail': 'workspace_busy'}
    workspace_snapshot, pending_snapshot = _workspace_pending_snapshot(
        test_database, workspace_id, pending_id)
    assert workspace_snapshot[0] == []
    assert pending_snapshot is not None
