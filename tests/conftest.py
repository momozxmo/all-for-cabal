from __future__ import annotations

import base64
import os
import shutil
import tempfile
from collections.abc import Iterator
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

# Module collection constructs ``web.app.app``. Keep that construction explicit
# and independent of any developer shell or gitignored .env file.
os.environ.update({
    'APP_ENV': 'development',
    'DATABASE_URL': 'sqlite:///:memory:',
    'APP_SECRET_KEY': 'test-collection-signing-secret-000000000000',
    'AZTEK_SESSION_ENCRYPTION_KEY': base64.urlsafe_b64encode(
        b'c' * 32
    ).decode('ascii'),
    'BOOTSTRAP_ADMIN_USERNAME': '',
    'BOOTSTRAP_ADMIN_PASSWORD': '',
    'SESSION_COOKIE_SECURE': 'false',
    'BROWSER_CONCURRENCY': '1',
    'LOCAL_DESKTOP_MODE': 'false',
    'LOCAL_RUNTIME_DIR': '',
    'LOCAL_LAUNCHER_SECRET': '',
})

from web import app as web_app
from web import settings as settings_module
from web.db import Database
from web.models import Base, User
from web.settings import Settings
from web.workspaces import WorkspaceRepository


@pytest.fixture(autouse=True)
def ignore_local_env_file(monkeypatch):
    """Keep the developer's own .env out of the tests.

    ``Settings.from_env`` reads it so a local server keeps its signing key across
    restarts; a suite that picked it up would pass or fail depending on whose
    machine it ran on.
    """
    monkeypatch.setattr(settings_module, '_ENV_FILE',
                        os.path.join(tempfile.gettempdir(), 'afc-no-such.env'))
    monkeypatch.delenv('APP_SECRET_KEY', raising=False)
    monkeypatch.delenv('AZTEK_SESSION_ENCRYPTION_KEY', raising=False)


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        app_env='test',
        # This URL also keeps tests that switch only ``app_env`` to production
        # valid; ``test_database`` injects the isolated SQLite database that the
        # suite actually uses.
        database_url='postgresql://test:test@localhost/test',
        app_secret_key='test-signing-secret-with-at-least-32-chars',
        aztek_encryption_key=base64.urlsafe_b64encode(b'k' * 32).decode('ascii'),
        bootstrap_admin_username='admin',
        bootstrap_admin_password='bootstrap-password',
        session_cookie_secure=False,
    )


@pytest.fixture
def test_database(test_settings) -> Iterator[Database]:
    tmpdir = tempfile.mkdtemp(prefix='afc_test_db_')
    db_url = 'sqlite:///%s' % os.path.join(tmpdir, 'test.db').replace('\\', '/')
    database = Database(replace(test_settings, database_url=db_url))
    Base.metadata.create_all(database.engine)
    try:
        yield database
    finally:
        Base.metadata.drop_all(database.engine)
        database.engine.dispose()
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def db_session(test_database):
    with test_database.session() as session:
        yield session


@pytest.fixture
def application(test_settings, test_database):
    return web_app.create_app(test_settings, test_database)


@pytest.fixture
def anonymous_client(application):
    return TestClient(application)


@pytest.fixture
def member(application, test_database):
    with test_database.session() as db:
        return application.state.auth_service.create_user(
            db, 'workspace.member', 'correct horse'
        )


@pytest.fixture
def other_member(application, test_database):
    with test_database.session() as db:
        return application.state.auth_service.create_user(
            db, 'workspace.other', 'correct horse'
        )


@pytest.fixture
def client_for(application, test_database):
    def make_client(user: User) -> TestClient:
        with test_database.session() as db:
            persisted_user = db.get(User, user.id)
            assert persisted_user is not None
            token = application.state.auth_service.create_session(db, persisted_user)
        client = TestClient(application)
        client.cookies.set('afc_session', token)
        return client

    return make_client


@pytest.fixture
def client(client_for, member):
    return client_for(member)


@pytest.fixture
def workspace_for_member(test_database, member):
    with test_database.session() as db:
        return WorkspaceRepository(db).create(member.id, 'event', 'owned.xlsx')
