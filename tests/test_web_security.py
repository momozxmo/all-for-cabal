import base64
# 'inspect' alone is taken by sqlalchemy's below.
import inspect as pyinspect
import importlib.util
import json
import os
import shutil
import tempfile
from dataclasses import replace
from datetime import datetime
from datetime import timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.exc import IntegrityError, StatementError

from web import app as web_app
from web import security
from web.auth_service import AuthService
from web.db import Database
from web.models import (Job, PairingToken, PendingImportRecord, User, WebSession,
                        WorkspaceRecord, utc_now)
from web.search_coordinator import SearchCoordinator
from web.settings import Settings


PRODUCTION_SETTINGS = {
    'APP_SECRET_KEY': 'production-signing-secret-with-32-chars',
    'AZTEK_SESSION_ENCRYPTION_KEY': base64.urlsafe_b64encode(
        b'p' * 32
    ).decode('ascii'),
    'BOOTSTRAP_ADMIN_USERNAME': 'production.owner',
    'BOOTSTRAP_ADMIN_PASSWORD': 'production-password',
}

APPLICATION_TABLES = {
    'users', 'web_sessions', 'pairing_tokens', 'aztek_sessions',
    'workspaces', 'pending_imports', 'jobs', 'audit_logs',
}


@pytest.fixture
def settings(test_database):
    return Settings(
        app_env='test',
        database_url=str(test_database.engine.url),
        app_secret_key='task-3-test-secret',
        aztek_encryption_key=base64.urlsafe_b64encode(
            b'k' * 32
        ).decode('ascii'),
        bootstrap_admin_username='Bootstrap.Admin',
        bootstrap_admin_password='bootstrap password',
        session_cookie_secure=False,
        session_ttl_seconds=3600,
    )


@pytest.fixture
def auth_service(settings):
    return AuthService(settings)


@pytest.fixture
def member(auth_service, db_session):
    return auth_service.create_user(
        db_session, ' Member.Name ', 'correct horse', role='member'
    )


def test_password_and_encryption_never_store_plaintext(settings):
    encoded = security.hash_password('correct horse')
    assert 'correct horse' not in encoded
    assert security.verify_password('correct horse', encoded)
    assert not security.verify_password('wrong', encoded)

    state = {
        'cookies': [{'name': 'token', 'value': 'secret'}],
        'origins': [],
    }
    ciphertext = security.encrypt_storage_state(state, settings)
    assert 'secret' not in ciphertext
    assert security.decrypt_storage_state(ciphertext, settings) == state


def test_storage_encryption_uses_random_nonce_and_stable_json(
    monkeypatch, settings
):
    nonce_sizes = []

    def fixed_random(size):
        nonce_sizes.append(size)
        return b'n' * size

    monkeypatch.setattr(security.os, 'urandom', fixed_random)
    first = security.encrypt_storage_state({'b': 2, 'a': 1}, settings)
    second = security.encrypt_storage_state({'a': 1, 'b': 2}, settings)

    assert first == second
    assert nonce_sizes == [12, 12]


def test_storage_decryption_rejects_malformed_and_tampered_state(settings):
    ciphertext = security.encrypt_storage_state({'cookies': []}, settings)
    tampered = bytearray(base64.urlsafe_b64decode(ciphertext.encode('ascii')))
    tampered[-1] ^= 1
    tampered_ciphertext = base64.urlsafe_b64encode(tampered).decode('ascii')

    with pytest.raises(security.InvalidEncryptedState):
        security.decrypt_storage_state('not valid base64!', settings)
    with pytest.raises(security.InvalidEncryptedState):
        security.decrypt_storage_state(tampered_ciphertext, settings)


def test_storage_encryption_requires_decoded_32_byte_key(settings):
    invalid_settings = replace(
        settings,
        aztek_encryption_key=base64.urlsafe_b64encode(b'x' * 31).decode('ascii'),
    )

    with pytest.raises(ValueError, match='32-byte'):
        security.encrypt_storage_state({}, invalid_settings)


def test_storage_encryption_rejects_non_urlsafe_base64_key(settings):
    standard_base64_key = base64.b64encode(b'\xfb' * 32).decode('ascii')
    assert '+' in standard_base64_key or '/' in standard_base64_key
    invalid_settings = replace(
        settings, aztek_encryption_key=standard_base64_key
    )

    with pytest.raises(ValueError, match='URL-safe base64'):
        security.encrypt_storage_state({}, invalid_settings)


def test_create_user_normalizes_identity_and_hashes_password(
    auth_service, db_session
):
    user = auth_service.create_user(
        db_session, ' Mixed.Case-User_1 ', 'ten letters!', role='admin'
    )

    assert user.username == 'mixed.case-user_1'
    assert user.role == 'admin'
    assert user.password_hash != 'ten letters!'
    assert 'ten letters!' not in user.password_hash


@pytest.mark.parametrize(
    'username',
    ['ab', 'a' * 81, 'white space', 'slash/name', 'ภาษาไทย'],
)
def test_create_user_rejects_invalid_username(auth_service, db_session, username):
    with pytest.raises(ValueError, match='username'):
        auth_service.create_user(db_session, username, 'correct horse')


def test_create_user_rejects_short_password_and_unknown_role(
    auth_service, db_session
):
    with pytest.raises(ValueError, match='password'):
        auth_service.create_user(db_session, 'shortpass', 'too short')
    with pytest.raises(ValueError, match='role'):
        auth_service.create_user(
            db_session, 'unknownrole', 'correct horse', role='owner'
        )


def test_create_user_rejects_non_string_role(auth_service, db_session):
    with pytest.raises(ValueError, match='role'):
        auth_service.create_user(
            db_session, 'invalidrole', 'correct horse', role=[]
        )


def test_create_user_rejects_duplicate_normalized_username(
    auth_service, db_session
):
    auth_service.create_user(
        db_session, 'Member.Name', 'correct horse'
    )

    with pytest.raises(IntegrityError):
        auth_service.create_user(
            db_session, ' member.name ', 'correct horse'
        )
    db_session.rollback()


def test_authenticate_accepts_valid_credentials_and_rejects_invalid_or_disabled(
    auth_service, db_session, member
):
    assert member.last_login_at is None
    assert auth_service.authenticate(
        db_session, ' MEMBER.NAME ', 'correct horse'
    ) is member
    assert member.last_login_at is not None
    assert auth_service.authenticate(
        db_session, 'member.name', 'wrong password'
    ) is None

    member.is_active = False
    db_session.flush()
    assert auth_service.authenticate(
        db_session, 'member.name', 'correct horse'
    ) is None


def test_session_token_is_stored_as_hmac_hash_and_resolution_is_read_only(
    auth_service, db_session, member, settings
):
    raw = auth_service.create_session(db_session, member)
    record = db_session.scalar(
        select(WebSession).where(WebSession.user_id == member.id)
    )

    assert record is not None
    assert raw != record.token_hash
    assert record.token_hash == security.hash_token(raw, settings)
    assert record.expires_at > utc_now() + timedelta(minutes=59)
    assert auth_service.resolve_session(db_session, raw).id == member.id
    assert record.last_seen_at is None

    assert auth_service.resolve_session(
        db_session, raw, touch=True
    ).id == member.id
    assert record.last_seen_at is not None


def test_expired_revoked_and_disabled_sessions_do_not_resolve(
    auth_service, db_session, member
):
    expired_token = auth_service.create_session(db_session, member)
    expired_record = db_session.scalar(
        select(WebSession).where(
            WebSession.token_hash == security.hash_token(
                expired_token, auth_service.settings
            )
        )
    )
    expired_record.expires_at = utc_now() - timedelta(seconds=1)
    db_session.flush()
    assert auth_service.resolve_session(db_session, expired_token) is None

    revoked_token = auth_service.create_session(db_session, member)
    auth_service.revoke_session(db_session, revoked_token)
    assert auth_service.resolve_session(db_session, revoked_token) is None

    disabled_token = auth_service.create_session(db_session, member)
    member.is_active = False
    db_session.flush()
    assert auth_service.resolve_session(db_session, disabled_token) is None


def test_revoke_session_revokes_only_the_supplied_token(
    auth_service, db_session, member
):
    revoked_token = auth_service.create_session(db_session, member)
    remaining_token = auth_service.create_session(db_session, member)

    auth_service.revoke_session(db_session, revoked_token)

    assert auth_service.resolve_session(db_session, revoked_token) is None
    assert (
        auth_service.resolve_session(db_session, remaining_token).id == member.id
    )


def test_revoke_all_sessions_revokes_only_selected_user(
    auth_service, db_session, member
):
    other = auth_service.create_user(
        db_session, 'other.member', 'correct horse'
    )
    member_tokens = [
        auth_service.create_session(db_session, member),
        auth_service.create_session(db_session, member),
    ]
    other_token = auth_service.create_session(db_session, other)

    auth_service.revoke_all_sessions(db_session, member.id)

    assert all(
        auth_service.resolve_session(db_session, token) is None
        for token in member_tokens
    )
    assert auth_service.resolve_session(db_session, other_token).id == other.id


def test_bootstrap_admin_requires_credentials_and_an_empty_user_table(
    settings, db_session
):
    missing_credentials = AuthService(
        replace(settings, bootstrap_admin_password='')
    )
    assert missing_credentials.bootstrap_admin(db_session) is None
    missing_username = AuthService(
        replace(settings, bootstrap_admin_username='   ')
    )
    assert missing_username.bootstrap_admin(db_session) is None

    service = AuthService(settings)
    admin = service.bootstrap_admin(db_session)
    assert admin is not None
    assert admin.username == 'bootstrap.admin'
    assert admin.role == 'admin'
    assert service.bootstrap_admin(db_session) is None


def configure_production(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv(
        'DATABASE_URL',
        'postgresql://production:password@localhost/all_for_cabal',
    )
    for name, value in PRODUCTION_SETTINGS.items():
        monkeypatch.setenv(name, value)


def configure_development(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('APP_SECRET_KEY', 'development-signing-secret-00000000')
    monkeypatch.setenv(
        'AZTEK_SESSION_ENCRYPTION_KEY',
        base64.urlsafe_b64encode(b'd' * 32).decode('ascii'),
    )
    monkeypatch.setenv('BOOTSTRAP_ADMIN_USERNAME', '')
    monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD', '')
    monkeypatch.setenv('LOCAL_DESKTOP_MODE', 'false')
    monkeypatch.setenv('SESSION_COOKIE_SECURE', 'false')
    monkeypatch.setenv('BROWSER_CONCURRENCY', '1')


def test_missing_app_env_fails_closed(monkeypatch):
    monkeypatch.delenv('APP_ENV', raising=False)

    with pytest.raises(ValueError, match='APP_ENV'):
        Settings.from_env()


@pytest.mark.parametrize('value', ['', 'test', 'prod', 'productionn', 'staging'])
def test_unknown_app_env_fails_closed(monkeypatch, value):
    monkeypatch.setenv('APP_ENV', value)

    with pytest.raises(ValueError, match='APP_ENV'):
        Settings.from_env()


@pytest.mark.parametrize('name,value', [
    ('LOCAL_DESKTOP_MODE', 'yes'),
    ('SESSION_COOKIE_SECURE', '0'),
])
def test_environment_booleans_accept_only_true_or_false(
    monkeypatch, name, value
):
    configure_development(monkeypatch)
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=name):
        Settings.from_env()


@pytest.mark.parametrize('value', ['many', '0', '-1', '2'])
def test_browser_concurrency_must_be_exactly_one(monkeypatch, value):
    configure_development(monkeypatch)
    monkeypatch.setenv('BROWSER_CONCURRENCY', value)

    with pytest.raises(ValueError, match='BROWSER_CONCURRENCY'):
        Settings.from_env()


@pytest.mark.parametrize('value', ['', 'not a valid database url'])
def test_database_url_must_be_nonempty_and_parseable(monkeypatch, value):
    configure_development(monkeypatch)
    monkeypatch.setenv('DATABASE_URL', value)

    with pytest.raises(ValueError, match='DATABASE_URL'):
        Settings.from_env()


def test_production_database_url_must_use_postgresql(monkeypatch):
    configure_production(monkeypatch)
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///production.db')

    with pytest.raises(ValueError, match='DATABASE_URL'):
        Settings.from_env()


def test_production_database_url_rejects_postgresql_prefix_spoof(monkeypatch):
    configure_production(monkeypatch)
    monkeypatch.setenv(
        'DATABASE_URL',
        'postgresqlfake://production:password@localhost/all_for_cabal',
    )

    with pytest.raises(ValueError, match='DATABASE_URL'):
        Settings.from_env()


def test_production_rejects_short_signing_secret(monkeypatch):
    configure_production(monkeypatch)
    monkeypatch.setenv('APP_SECRET_KEY', 'too-short')

    with pytest.raises(ValueError, match='APP_SECRET_KEY'):
        Settings.from_env()


@pytest.mark.parametrize('value', [
    base64.b64encode(b'\xfb' * 32).decode('ascii'),
    base64.urlsafe_b64encode(b'k' * 31).decode('ascii'),
])
def test_settings_reject_malformed_encryption_key(monkeypatch, value):
    configure_production(monkeypatch)
    monkeypatch.setenv('AZTEK_SESSION_ENCRYPTION_KEY', value)

    with pytest.raises(ValueError, match='AZTEK_SESSION_ENCRYPTION_KEY'):
        Settings.from_env()


@pytest.mark.parametrize('field', ['aztek_origin', 'aztek_auth_origin'])
def test_settings_reject_non_https_aztek_origins(test_settings, field):
    invalid = replace(
        test_settings,
        app_env='development',
        **{field: 'http://unsafe.example.test'},
    )

    with pytest.raises(ValueError, match=field.upper()):
        invalid.validate()


def test_production_rejects_builtin_admin_credentials(monkeypatch):
    configure_production(monkeypatch)
    monkeypatch.setenv('BOOTSTRAP_ADMIN_USERNAME', 'admin')
    monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD', 'admin123456')

    with pytest.raises(ValueError, match='BOOTSTRAP_ADMIN_PASSWORD'):
        Settings.from_env()


def test_development_has_no_builtin_admin_credentials(monkeypatch):
    configure_development(monkeypatch)

    settings = Settings.from_env()

    assert settings.bootstrap_admin_username == ''
    assert settings.bootstrap_admin_password == ''


@pytest.mark.parametrize(
    'missing_name',
    ['BOOTSTRAP_ADMIN_USERNAME', 'BOOTSTRAP_ADMIN_PASSWORD'],
)
def test_development_rejects_partial_bootstrap_credentials(
    monkeypatch, missing_name
):
    configure_development(monkeypatch)
    monkeypatch.setenv('BOOTSTRAP_ADMIN_USERNAME', 'development.owner')
    monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD', 'development-password')
    monkeypatch.delenv(missing_name)

    with pytest.raises(ValueError, match='BOOTSTRAP_ADMIN'):
        Settings.from_env()


def test_direct_settings_reject_unknown_app_env(test_settings):
    with pytest.raises(ValueError, match='APP_ENV'):
        replace(test_settings, app_env='prod').validate()


def test_direct_test_settings_remain_valid(test_settings):
    test_settings.validate()


def test_create_app_validates_settings_before_database_construction(
    monkeypatch, test_settings
):
    def forbidden_database(_settings):
        raise AssertionError('Database constructed before Settings.validate')

    monkeypatch.setattr(web_app, 'Database', forbidden_database)

    with pytest.raises(ValueError, match='APP_ENV'):
        web_app.create_app(replace(test_settings, app_env='prod'))


def test_settings_default_to_local_sqlite(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.delenv('DATABASE_URL', raising=False)
    with pytest.warns(RuntimeWarning, match='sessions will not survive restart'):
        settings = Settings.from_env()
    assert settings.database_url == 'sqlite:///./all_for_cabal_web.db'
    assert settings.browser_concurrency == 1


@pytest.mark.parametrize('missing_setting', PRODUCTION_SETTINGS)
def test_production_rejects_each_missing_secret(monkeypatch, missing_setting):
    configure_production(monkeypatch)
    monkeypatch.delenv(missing_setting)
    with pytest.raises(ValueError, match=missing_setting):
        Settings.from_env()


def test_production_forces_secure_session_cookie(monkeypatch):
    configure_production(monkeypatch)
    monkeypatch.setenv('SESSION_COOKIE_SECURE', 'false')
    settings = Settings.from_env()
    assert settings.session_cookie_secure is True


def test_development_warns_about_process_local_secrets(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    with pytest.warns(RuntimeWarning, match='sessions will not survive restart'):
        Settings.from_env()


def test_alembic_migration_creates_and_removes_application_schema(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix='afc_test_')
    database_url = 'sqlite:///%s' % os.path.join(tmpdir, 'migration.db').replace('\\', '/')
    configure_development(monkeypatch)
    monkeypatch.setenv('DATABASE_URL', database_url)
    config = Config(str(Path(__file__).parents[1] / 'alembic.ini'))
    engine = create_engine(database_url)

    try:
        command.upgrade(config, 'head')
        schema = inspect(engine)

        assert APPLICATION_TABLES <= set(schema.get_table_names())

        def foreign_keys(table_name):
            return {
                (tuple(item['constrained_columns']), item['referred_table'],
                 tuple(item['referred_columns']))
                for item in schema.get_foreign_keys(table_name)
            }

        def unique_columns(table_name):
            constraints = {
                tuple(item['column_names'])
                for item in schema.get_unique_constraints(table_name)
            }
            indexes = {
                tuple(item['column_names'])
                for item in schema.get_indexes(table_name)
                if item['unique']
            }
            return constraints | indexes

        assert ('username',) in unique_columns('users')
        assert ('token_hash',) in unique_columns('web_sessions')
        assert ('token_hash',) in unique_columns('pairing_tokens')
        assert ('user_id',) in unique_columns('aztek_sessions')
        assert (('user_id',), 'users', ('id',)) in foreign_keys('web_sessions')
        assert (('user_id',), 'users', ('id',)) in foreign_keys('pairing_tokens')
        assert (('user_id',), 'users', ('id',)) in foreign_keys('aztek_sessions')
        assert (('owner_user_id',), 'users', ('id',)) in foreign_keys('workspaces')
        assert (('owner_user_id',), 'users', ('id',)) in foreign_keys('pending_imports')
        assert (('workspace_id',), 'workspaces', ('id',)) in foreign_keys('pending_imports')
        assert (('owner_user_id',), 'users', ('id',)) in foreign_keys('jobs')
        assert (('workspace_id',), 'workspaces', ('id',)) in foreign_keys('jobs')
        assert (('user_id',), 'users', ('id',)) in foreign_keys('audit_logs')

        command.downgrade(config, 'base')
        assert not (APPLICATION_TABLES & set(inspect(engine).get_table_names()))
    finally:
        engine.dispose()
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_schema_creates_all_security_and_job_tables(test_database):
    names = set(inspect(test_database.engine).get_table_names())
    assert {
        'users', 'web_sessions', 'pairing_tokens', 'aztek_sessions',
        'workspaces', 'pending_imports', 'jobs', 'audit_logs',
    } <= names


def test_schema_enforces_identity_and_ownership_constraints(test_database):
    schema = inspect(test_database.engine)

    def foreign_keys(table_name):
        return {
            (tuple(item['constrained_columns']), item['referred_table'],
             tuple(item['referred_columns']))
            for item in schema.get_foreign_keys(table_name)
        }

    def unique_columns(table_name):
        constraints = {
            tuple(item['column_names'])
            for item in schema.get_unique_constraints(table_name)
        }
        indexes = {
            tuple(item['column_names'])
            for item in schema.get_indexes(table_name)
            if item['unique']
        }
        return constraints | indexes

    assert ('username',) in unique_columns('users')
    assert ('token_hash',) in unique_columns('web_sessions')
    assert ('token_hash',) in unique_columns('pairing_tokens')
    assert ('user_id',) in unique_columns('aztek_sessions')

    assert (('user_id',), 'users', ('id',)) in foreign_keys('web_sessions')
    assert (('user_id',), 'users', ('id',)) in foreign_keys('pairing_tokens')
    assert (('user_id',), 'users', ('id',)) in foreign_keys('aztek_sessions')
    assert (('owner_user_id',), 'users', ('id',)) in foreign_keys('workspaces')
    assert (('owner_user_id',), 'users', ('id',)) in foreign_keys('pending_imports')
    assert (('workspace_id',), 'workspaces', ('id',)) in foreign_keys('pending_imports')
    job_columns = {column['name'] for column in schema.get_columns('jobs')}
    assert 'owner_user_id' in job_columns
    assert 'user_id' not in job_columns
    assert (('owner_user_id',), 'users', ('id',)) in foreign_keys('jobs')
    assert (('workspace_id',), 'workspaces', ('id',)) in foreign_keys('jobs')
    assert (('user_id',), 'users', ('id',)) in foreign_keys('audit_logs')
    audit_user_id = next(
        column for column in schema.get_columns('audit_logs')
        if column['name'] == 'user_id'
    )
    assert audit_user_id['nullable'] is True


def test_workspace_fk_and_pairing_partial_index_model_metadata_are_exact():
    pending_fk = next(
        foreign_key for foreign_key in PendingImportRecord.__table__.foreign_keys
        if foreign_key.parent.name == 'workspace_id')
    job_fk = next(
        foreign_key for foreign_key in Job.__table__.foreign_keys
        if foreign_key.parent.name == 'workspace_id')

    assert pending_fk.ondelete == 'CASCADE'
    assert job_fk.ondelete == 'SET NULL'
    assert WorkspaceRecord.pending_imports.property.passive_deletes == 'all'
    assert WorkspaceRecord.jobs.property.passive_deletes == 'all'

    index = next(
        item for item in PairingToken.__table__.indexes
        if item.name == 'uq_pairing_tokens_one_pending_user')
    assert index.unique is True
    assert [column.name for column in index.columns] == ['user_id']
    assert str(index.dialect_options['sqlite']['where']) == (
        "status = 'pending' AND used_at IS NULL")
    assert str(index.dialect_options['postgresql']['where']) == (
        "status = 'pending' AND used_at IS NULL")


def _load_workspace_fk_migration_module():
    path = (Path(__file__).parents[1] / 'alembic' / 'versions' /
            '20260820_workspace_fk_semantics.py')
    spec = importlib.util.spec_from_file_location('workspace_fk_migration', path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_workspace_fk_migration_helper_accepts_named_and_unnamed_constraints():
    migration = _load_workspace_fk_migration_module()
    named = [{
        'name': 'fk_jobs_workspace_postgresql',
        'constrained_columns': ['workspace_id'],
        'referred_table': 'workspaces',
    }]
    unnamed = [{
        'name': None,
        'constrained_columns': ['workspace_id'],
        'referred_table': 'workspaces',
    }]

    assert migration._workspace_fk_name('jobs', named) == (
        'fk_jobs_workspace_postgresql')
    assert migration._workspace_fk_name('pending_imports', unnamed) == (
        'fk_pending_imports_workspace_id_workspaces')


def test_workspace_fk_migration_preserves_data_deduplicates_tokens_and_round_trips(
    monkeypatch
):
    tmpdir = tempfile.mkdtemp(prefix='afc_workspace_fk_')
    database_url = 'sqlite:///%s' % os.path.join(
        tmpdir, 'migration.db').replace('\\', '/')
    configure_development(monkeypatch)
    monkeypatch.setenv('DATABASE_URL', database_url)
    config = Config(str(Path(__file__).parents[1] / 'alembic.ini'))
    engine = create_engine(database_url)

    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute('PRAGMA foreign_keys=ON')

    event.listen(engine, 'connect', enable_foreign_keys)
    now = '2026-08-20 12:00:00.000000'
    later = '2026-08-20 13:00:00.000000'

    try:
        command.upgrade(config, '20260722_auth_sessions')
        with engine.begin() as connection:
            assert connection.exec_driver_sql(
                'PRAGMA foreign_keys').scalar_one() == 1
            connection.execute(text(
                'INSERT INTO users '
                '(id, username, password_hash, role, is_active, '
                'password_changed_at, created_at, updated_at) '
                'VALUES (:id, :username, :password_hash, :role, :is_active, '
                ':password_changed_at, :created_at, :updated_at)'
            ), {
                'id': 'user-one', 'username': 'migration.user',
                'password_hash': 'hash', 'role': 'member', 'is_active': True,
                'password_changed_at': now, 'created_at': now, 'updated_at': now,
            })
            connection.execute(text(
                'INSERT INTO workspaces '
                '(id, owner_user_id, mode, filename, criteria, occurrences, '
                'group_meta, skipped, results, not_found, created_at, updated_at) '
                'VALUES (:id, :owner, :mode, :filename, :criteria, :occurrences, '
                ':group_meta, :skipped, :results, :not_found, :created, :updated)'
            ), {
                'id': 'workspace-one', 'owner': 'user-one', 'mode': 'event',
                'filename': 'preserved.xlsx', 'criteria': json.dumps([{'kind': '1'}]),
                'occurrences': json.dumps([]), 'group_meta': json.dumps({}),
                'skipped': json.dumps([]), 'results': json.dumps([]),
                'not_found': json.dumps([]), 'created': now, 'updated': now,
            })
            connection.execute(text(
                'INSERT INTO pending_imports '
                '(id, owner_user_id, workspace_id, sheets, skipped, created_at, updated_at) '
                'VALUES (:id, :owner, :workspace, :sheets, :skipped, :created, :updated)'
            ), {
                'id': 'pending-one', 'owner': 'user-one',
                'workspace': 'workspace-one',
                'sheets': json.dumps([['Plan', [{'kind': '2'}]]]),
                'skipped': json.dumps([]), 'created': now, 'updated': now,
            })
            connection.execute(text(
                'INSERT INTO jobs '
                '(id, owner_user_id, workspace_id, tool, status, config, result, '
                'log, created_at, updated_at) '
                'VALUES (:id, :owner, :workspace, :tool, :status, :config, :result, '
                ':log, :created, :updated)'
            ), {
                'id': 'job-one', 'owner': 'user-one', 'workspace': 'workspace-one',
                'tool': 'item_finder', 'status': 'done', 'config': json.dumps({}),
                'result': json.dumps({}), 'log': json.dumps([]),
                'created': now, 'updated': now,
            })
            token_rows = [
                ('token-old', 'hash-old', now, None),
                ('token-a', 'hash-a', later, None),
                ('token-z', 'hash-z', later, None),
                ('token-used', 'hash-used', later, later),
            ]
            for token_id, token_hash, created_at, used_at in token_rows:
                connection.execute(text(
                    'INSERT INTO pairing_tokens '
                    '(id, user_id, token_hash, status, created_at, expires_at, used_at) '
                    'VALUES (:id, :user, :token_hash, :status, :created, :expires, :used)'
                ), {
                    'id': token_id, 'user': 'user-one', 'token_hash': token_hash,
                    'status': 'pending', 'created': created_at,
                    'expires': '2026-08-21 12:00:00.000000', 'used': used_at,
                })

        # The original revision's SQLite workspace FKs are deliberately unnamed.
        assert next(
            fk for fk in inspect(engine).get_foreign_keys('pending_imports')
            if fk['constrained_columns'] == ['workspace_id'])['name'] is None

        command.upgrade(config, 'head')
        schema = inspect(engine)
        pending_fk = next(
            fk for fk in schema.get_foreign_keys('pending_imports')
            if fk['constrained_columns'] == ['workspace_id'])
        job_fk = next(
            fk for fk in schema.get_foreign_keys('jobs')
            if fk['constrained_columns'] == ['workspace_id'])
        assert pending_fk['options']['ondelete'] == 'CASCADE'
        assert job_fk['options']['ondelete'] == 'SET NULL'
        pairing_index = next(
            index for index in schema.get_indexes('pairing_tokens')
            if index['name'] == 'uq_pairing_tokens_one_pending_user')
        assert pairing_index['unique'] == 1
        assert pairing_index['column_names'] == ['user_id']
        assert "status = 'pending' AND used_at IS NULL" in str(
            pairing_index['dialect_options']['sqlite_where'])

        with engine.begin() as connection:
            assert connection.execute(text(
                'SELECT filename FROM workspaces WHERE id=:id'),
                {'id': 'workspace-one'}).scalar_one() == 'preserved.xlsx'
            assert connection.execute(text(
                'SELECT id FROM pending_imports WHERE id=:id'),
                {'id': 'pending-one'}).scalar_one() == 'pending-one'
            assert connection.execute(text(
                'SELECT workspace_id FROM jobs WHERE id=:id'),
                {'id': 'job-one'}).scalar_one() == 'workspace-one'
            statuses = dict(connection.execute(text(
                'SELECT id, status FROM pairing_tokens ORDER BY id')).all())
            hashes = dict(connection.execute(text(
                'SELECT id, token_hash FROM pairing_tokens ORDER BY id')).all())
        assert statuses == {
            'token-a': 'expired', 'token-old': 'expired',
            'token-used': 'pending', 'token-z': 'pending',
        }
        assert hashes == {
            'token-a': 'hash-a', 'token-old': 'hash-old',
            'token-used': 'hash-used', 'token-z': 'hash-z',
        }

        command.downgrade(config, '20260722_auth_sessions')
        schema = inspect(engine)
        assert 'uq_pairing_tokens_one_pending_user' not in {
            index['name'] for index in schema.get_indexes('pairing_tokens')}
        assert next(
            fk for fk in schema.get_foreign_keys('pending_imports')
            if fk['constrained_columns'] == ['workspace_id'])['options'].get(
                'ondelete') is None
        assert next(
            fk for fk in schema.get_foreign_keys('jobs')
            if fk['constrained_columns'] == ['workspace_id'])['options'].get(
                'ondelete') is None

        command.upgrade(config, 'head')
        assert 'uq_pairing_tokens_one_pending_user' in {
            index['name'] for index in inspect(engine).get_indexes('pairing_tokens')}
        with engine.begin() as connection:
            connection.execute(text(
                'DELETE FROM workspaces WHERE id=:id'), {'id': 'workspace-one'})
        with engine.connect() as connection:
            assert connection.execute(text(
                'SELECT id FROM pending_imports WHERE id=:id'),
                {'id': 'pending-one'}).first() is None
            assert connection.execute(text(
                'SELECT workspace_id FROM jobs WHERE id=:id'),
                {'id': 'job-one'}).scalar_one() is None
    finally:
        engine.dispose()
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_database_session_commits_and_rolls_back(test_database):
    committed_id = '2' * 32
    rolled_back_id = '3' * 32

    with test_database.session() as session:
        session.add(User(
            id=committed_id, username='committed', password_hash='hash'))

    with test_database.session() as session:
        assert session.get(User, committed_id) is not None

    with pytest.raises(RuntimeError, match='trigger rollback'):
        with test_database.session() as session:
            session.add(User(
                id=rolled_back_id, username='rolled-back', password_hash='hash'))
            session.flush()
            raise RuntimeError('trigger rollback')

    with test_database.session() as session:
        assert session.get(User, rolled_back_id) is None


def test_sqlite_enforces_foreign_keys_for_orphan_records(test_database):
    with pytest.raises(IntegrityError):
        with test_database.session() as session:
            session.add(WorkspaceRecord(
                owner_user_id='9' * 32,
                mode='event',
                filename='orphan.xlsx',
            ))
            session.flush()


def test_timestamps_round_trip_as_utc_aware_values(db_session):
    db_session.add(User(id='1' * 32, username='member', password_hash='hash'))
    db_session.flush()
    db_session.expunge_all()

    user = db_session.get(User, '1' * 32)
    assert user is not None
    assert user.created_at.tzinfo is not None
    assert user.created_at.utcoffset().total_seconds() == 0


def test_timestamps_reject_naive_input(test_database):
    with pytest.raises(StatementError) as error:
        with test_database.session() as session:
            session.add(User(
                id='4' * 32,
                username='naive',
                password_hash='hash',
                password_changed_at=datetime(2026, 1, 1, 12, 0, 0),
            ))
            session.flush()
    assert isinstance(error.value.orig, ValueError)
    assert 'timezone-aware' in str(error.value.orig)


def test_headed_search_is_refused_in_production(settings, test_database):
    """A hosted server has no display, so it must ignore a headed request."""
    coordinator = SearchCoordinator(test_database, settings, aztek_session_service=None)
    assert coordinator.resolve_headed(True) is True
    assert coordinator.resolve_headed(False) is False

    hosted = SearchCoordinator(
        test_database, replace(settings, app_env='production'),
        aztek_session_service=None)
    assert hosted.resolve_headed(True) is False
    assert hosted.resolve_headed(False) is False


def test_the_socket_only_watches_the_search_it_asked_for():
    """Create Bundle is a page of its own now, so leaving mid-search is normal.

    The run has to belong to the application, not to the socket: the endpoint
    starts it and then subscribes, and only an explicit stop cancels it.
    """
    start = pyinspect.getsource(SearchCoordinator._start_reserved)
    assert 'ensure_future' in start, 'the run must outlive the caller'
    assert '_cancel' not in start
    # Cancelling is its own request now.
    assert '_cancel = True' in pyinspect.getsource(SearchCoordinator.stop)
    # And a run cannot survive the process, so nothing may be left claiming to.
    assert 'failed' in pyinspect.getsource(SearchCoordinator.sweep_interrupted_jobs)
