import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from web import app as web_app
from web.audit import write_audit
from web.models import AuditLog, PendingImportRecord, WorkspaceRecord
from web.workspaces import WorkspaceRepository


def _audit_rows(db):
    return db.scalars(select(AuditLog).order_by(AuditLog.created_at)).all()


def test_write_audit_keeps_only_allowlisted_scalar_summary_and_request_metadata(
    db_session,
):
    request = SimpleNamespace(
        client=SimpleNamespace(host='9' * 300),
        headers={
            'user-agent': 'browser/' + ('x' * 600),
            'authorization': 'Bearer do-not-store',
            'cookie': 'afc_session=do-not-store',
        },
    )

    write_audit(
        db_session,
        user_id=None,
        action='test.sanitized',
        status='success',
        summary={
            'mode': 'event',
            'count': 3,
            'password': 'do-not-store',
            'token_hint': 'do-not-store',
            'nested': {'not': 'scalar'},
            'reason': ['not', 'scalar'],
        },
        request=request,
    )
    db_session.flush()

    row = _audit_rows(db_session)[0]
    assert json.loads(row.summary) == {'count': 3, 'mode': 'event'}
    assert len(row.ip_address) == 255
    assert len(row.user_agent) == 512
    assert 'do-not-store' not in row.summary
    assert 'do-not-store' not in row.user_agent


def test_write_audit_truncates_summary_as_valid_json_within_storage_limit(db_session):
    write_audit(
        db_session,
        user_id=None,
        action='test.truncated',
        status='success',
        summary={'filename': 'x' * 10000, 'reason': 'y' * 10000},
    )
    db_session.flush()

    summary = _audit_rows(db_session)[0].summary
    assert len(summary) <= 2000
    assert isinstance(json.loads(summary), dict)


def test_write_audit_truncation_is_deterministic_across_summary_key_order(db_session):
    write_audit(
        db_session,
        user_id=None,
        action='test.deterministic-first',
        status='success',
        summary={'filename': 'f' * 2000, 'reason': 'r' * 2000},
    )
    write_audit(
        db_session,
        user_id=None,
        action='test.deterministic-second',
        status='success',
        summary={'reason': 'r' * 2000, 'filename': 'f' * 2000},
    )
    db_session.flush()

    first, second = _audit_rows(db_session)
    assert first.summary == second.summary


def test_write_audit_uses_the_callers_transaction(db_session):
    write_audit(
        db_session, user_id=None, action='test.transaction', status='success'
    )
    db_session.rollback()

    assert _audit_rows(db_session) == []


def test_password_change_audits_one_sanitized_success_only(
    client, client_for, member, test_database
):
    current_password = 'correct horse'
    new_password = 'new password for audit'
    changed = client.post('/api/auth/change-password', json={
        'current_password': current_password,
        'new_password': new_password,
    })

    assert changed.status_code == 204
    with test_database.session() as db:
        rows = db.scalars(select(AuditLog).where(
            AuditLog.action == 'auth.password_changed'
        )).all()

    assert len(rows) == 1
    row = rows[0]
    assert row.status == 'success'
    assert row.user_id == member.id
    assert row.resource_type == 'user'
    assert row.resource_id == member.id
    assert row.summary == '{}'
    stored_values = '\n'.join(
        str(getattr(row, column.name) or '')
        for column in AuditLog.__table__.columns
    )
    assert current_password not in stored_values
    assert new_password not in stored_values

    authenticated_client = client_for(member)
    rejected = authenticated_client.post('/api/auth/change-password', json={
        'current_password': 'wrong current password',
        'new_password': 'another private password',
    })
    short_new_password = authenticated_client.post('/api/auth/change-password', json={
        'current_password': new_password,
        'new_password': 'short',
    })

    assert rejected.status_code == 400
    assert short_new_password.status_code == 400
    with test_database.session() as db:
        successes = db.scalars(select(AuditLog).where(
            AuditLog.action == 'auth.password_changed',
            AuditLog.status == 'success',
        )).all()
    assert len(successes) == 1


def test_workspace_import_export_and_bundle_actions_are_audited(
    client, member, test_database, monkeypatch
):
    import item_finder
    from web import item_service

    monkeypatch.setattr(item_finder, 'read_template', lambda _path: [
        {'kind': '1', 'opt': '', 'dur': '', 'name': 'Item'},
    ])
    imported = client.post(
        '/api/import-template',
        data={'mode': 'event'},
        files={'file': ('template.xlsx', b'workbook', 'application/octet-stream')},
    )
    assert imported.status_code == 200, imported.text
    imported_workspace_id = imported.json()['workspace_id']
    assert client.delete('/api/workspaces/' + imported_workspace_id).status_code == 204

    monkeypatch.setattr(item_service, 'parser_for_mode', lambda _mode: (
        lambda _path: ([('One', [{'kind': '1', 'sources': ['G1']}])], [])
    ))
    pending = client.post(
        '/api/import-plan',
        data={'mode': 'shop'},
        files={'file': ('plan.xlsx', b'workbook', 'application/octet-stream')},
    )
    assert pending.status_code == 200, pending.text
    applied = client.post('/api/import-plan/apply', json={
        'pending_id': pending.json()['pending_id'], 'selected_sheets': ['One'],
    })
    assert applied.status_code == 200, applied.text

    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(member.id, 'event', 'results.xlsx')
        workspace.game = 'CabalM SEA'
        workspace.results = [{'aztek_id': '1', 'item_name': 'Item', 'sources': ['G1']}]
        workspace.group_meta = {'G1': {'activity': 'Event'}}
        result_workspace_id = workspace.id

    assert client.get(f'/api/workspaces/{result_workspace_id}/export.csv').status_code == 200
    assert client.get(f'/api/workspaces/{result_workspace_id}/export.xlsx').status_code == 200
    assert client.post(
        f'/api/workspaces/{result_workspace_id}/bundles',
        json={'selected_indexes': [0]},
    ).status_code == 200

    with test_database.session() as db:
        actions = {row.action for row in _audit_rows(db)}
    assert {
        'workspace.created',
        'workspace.deleted',
        'template.imported',
        'plan.imported',
        'plan.applied',
        'workspace.exported_csv',
        'workspace.exported_xlsx',
        'bundle.previewed',
    } <= actions


def test_apply_audit_failure_after_claim_restores_workspace_and_pending(
    client, member, test_database, monkeypatch
):
    with test_database.session() as db:
        repository = WorkspaceRepository(db)
        workspace = repository.create(
            member.id, 'event', 'audit-rollback.xlsx', [{'kind': 'old'}])
        pending = repository.add_pending(
            member.id, workspace.id,
            [('Plan', [{'kind': 'new', 'sources': ['A']}])], [])
        workspace_id = workspace.id
        pending_id = pending.id

    original_write_audit = web_app.write_audit

    def fail_plan_audit(*args, **kwargs):
        if kwargs.get('action') == 'plan.applied':
            raise RuntimeError('plan audit failed')
        return original_write_audit(*args, **kwargs)

    monkeypatch.setattr(web_app, 'write_audit', fail_plan_audit)
    with pytest.raises(RuntimeError, match='plan audit failed'):
        client.post('/api/import-plan/apply', json={
            'pending_id': pending_id, 'selected_sheets': ['Plan'],
        })

    with test_database.session() as db:
        unchanged = db.get(WorkspaceRecord, workspace_id)
        assert unchanged.criteria == [{'kind': 'old'}]
        assert db.get(PendingImportRecord, pending_id) is not None
        assert db.scalar(select(AuditLog).where(
            AuditLog.action == 'plan.applied')) is None


def test_workspace_delete_commits_workspace_and_audit_inside_guard(
    client, application, member, test_database, monkeypatch
):
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(
            member.id, 'event', 'guard-commit.xlsx')
        workspace_id = workspace.id

    checkpoints = []

    @contextmanager
    def checking_guard(requested_workspace_id):
        assert requested_workspace_id == workspace_id
        checkpoints.append('entered')
        yield
        with test_database.session() as db:
            assert db.get(WorkspaceRecord, workspace_id) is None
            audit = db.scalar(select(AuditLog).where(
                AuditLog.action == 'workspace.deleted',
                AuditLog.resource_id == workspace_id,
            ))
            assert audit is not None
        checkpoints.append('committed-before-exit')

    monkeypatch.setattr(
        application.state.search_coordinator, 'deletion_guard', checking_guard,
        raising=False)

    response = client.delete(f'/api/workspaces/{workspace_id}')

    assert response.status_code == 204
    assert checkpoints == ['entered', 'committed-before-exit']


def test_workspace_delete_audit_failure_rolls_back_inside_guard(
    client, application, member, test_database, monkeypatch
):
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(
            member.id, 'event', 'guard-rollback.xlsx')
        workspace_id = workspace.id

    checkpoints = []

    @contextmanager
    def checking_guard(requested_workspace_id):
        assert requested_workspace_id == workspace_id
        checkpoints.append('entered')
        try:
            yield
        finally:
            with test_database.session() as db:
                assert db.get(WorkspaceRecord, workspace_id) is not None
                assert db.scalar(select(AuditLog).where(
                    AuditLog.action == 'workspace.deleted',
                    AuditLog.resource_id == workspace_id,
                )) is None
            checkpoints.append('rolled-back-before-exit')

    original_write_audit = web_app.write_audit

    def fail_delete_audit(*args, **kwargs):
        if kwargs.get('action') == 'workspace.deleted':
            raise RuntimeError('delete audit failed')
        return original_write_audit(*args, **kwargs)

    monkeypatch.setattr(
        application.state.search_coordinator, 'deletion_guard', checking_guard,
        raising=False)
    monkeypatch.setattr(web_app, 'write_audit', fail_delete_audit)

    with pytest.raises(RuntimeError, match='delete audit failed'):
        client.delete(f'/api/workspaces/{workspace_id}')

    assert checkpoints == ['entered', 'rolled-back-before-exit']
