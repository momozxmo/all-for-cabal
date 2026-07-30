import pytest
from starlette.websockets import WebSocketDisconnect

from web import app as web_app
from web.models import PendingImportRecord, WorkspaceRecord
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


def test_apply_pending_rolls_back_workspace_and_pending_if_delete_fails(
    db_session, test_database, member, monkeypatch
):
    repo = WorkspaceRepository(db_session)
    workspace = repo.create(member.id, 'event')
    pending = repo.add_pending(
        member.id, workspace.id, [('One', [{'kind': '1', 'sources': ['A']}])], []
    )
    db_session.commit()

    def fail_pending_delete(model):
        if model is PendingImportRecord:
            raise RuntimeError('pending delete failed')
        raise AssertionError(f'unexpected delete target: {model}')

    monkeypatch.setattr('web.workspaces.delete', fail_pending_delete)
    with pytest.raises(RuntimeError, match='pending delete failed'):
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
