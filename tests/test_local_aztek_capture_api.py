from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient
from sqlalchemy import select

from web import app as web_app, security
from web.local_aztek_capture import LocalCaptureTimeout
from web.models import AztekSession, User


LOCAL_SECRET = 'local-capture-launcher-secret-with-48-characters-01'


def storage_state(value='complete-http-only-cookie'):
    return {
        'cookies': [{
            'name': 'sso', 'value': value,
            'domain': '.combo-interactive.com', 'path': '/',
            'httpOnly': True, 'secure': True, 'sameSite': 'Lax',
        }],
        'origins': [{
            'origin': 'https://aztek-tools-v2.combo-interactive.com',
            'localStorage': [],
        }],
    }


def local_application(test_settings, test_database):
    settings = replace(
        test_settings,
        app_env='local-desktop',
        local_desktop_mode=True,
        local_runtime_dir='C:/AFC',
        local_launcher_secret=LOCAL_SECRET,
        bootstrap_admin_username='',
        bootstrap_admin_password='',
    )
    return web_app.create_app(settings, test_database)


def signed_in_local_client(application, *, host='127.0.0.1'):
    client = TestClient(
        application, client=(host, 50000), follow_redirects=False)
    issued = client.post(
        '/api/local/launch',
        headers={'X-AFC-Launcher-Secret': LOCAL_SECRET},
    )
    assert issued.status_code == 200
    response = client.post(
        '/api/local/session', json={'token': issued.json()['token']})
    assert response.status_code == 204
    return client


class SuccessfulCapture:
    def __init__(self, state):
        self.state = state
        self.called = 0
        self.seed_state = None

    async def capture(self, seed_state=None):
        self.called += 1
        self.seed_state = seed_state
        return self.state


class FailingCapture:
    def __init__(self):
        self.called = 0

    async def capture(self, seed_state=None):
        self.called += 1
        raise LocalCaptureTimeout()


def test_local_capture_endpoint_saves_complete_state(
        test_settings, test_database):
    application = local_application(test_settings, test_database)
    client = signed_in_local_client(application)
    capture = SuccessfulCapture(storage_state())
    application.state.local_aztek_capture = capture

    response = client.post('/api/aztek/local-capture')

    assert response.status_code == 200
    assert response.json() == {
        'status': 'connected', 'account_label': 'Local Chromium'}
    assert capture.called == 1
    assert client.get('/api/aztek/status').json()['status'] == 'active'
    with test_database.session() as db:
        session = db.scalar(select(AztekSession))
        assert security.decrypt_storage_state(
            session.encrypted_state, application.state.settings
        ) == storage_state()


def test_local_capture_seeds_browser_with_expired_encrypted_session(
        test_settings, test_database):
    application = local_application(test_settings, test_database)
    client = signed_in_local_client(application)
    old_state = storage_state('old-sso-cookie')
    with test_database.session() as db:
        owner = db.scalar(select(User).where(User.username == 'local.owner'))
        application.state.aztek_session_service.save_storage_state(
            db, owner.id, old_state, 'old')
        application.state.aztek_session_service.mark_expired(db, owner)

    capture = SuccessfulCapture(storage_state('fresh-cookie'))
    application.state.local_aztek_capture = capture

    response = client.post('/api/aztek/local-capture')

    assert response.status_code == 200
    assert capture.seed_state == old_state


def test_hosted_mode_rejects_local_capture_before_browser_runs(
        application, client):
    capture = SuccessfulCapture(storage_state())
    application.state.local_aztek_capture = capture

    response = client.post('/api/aztek/local-capture')

    assert response.status_code == 404
    assert capture.called == 0


def test_non_loopback_rejects_local_capture_before_browser_runs(
        test_settings, test_database):
    application = local_application(test_settings, test_database)
    local = signed_in_local_client(application)
    capture = SuccessfulCapture(storage_state())
    application.state.local_aztek_capture = capture
    remote = TestClient(
        application, client=('10.0.0.8', 50000), follow_redirects=False)
    remote.cookies.update(local.cookies)

    response = remote.post('/api/aztek/local-capture')

    assert response.status_code == 404
    assert capture.called == 0


def test_failed_capture_keeps_the_previous_encrypted_session(
        test_settings, test_database):
    application = local_application(test_settings, test_database)
    client = signed_in_local_client(application)
    old_state = storage_state('old-cookie-that-must-survive')
    with test_database.session() as db:
        owner = db.scalar(select(User).where(User.username == 'local.owner'))
        application.state.aztek_session_service.save_storage_state(
            db, owner.id, old_state, 'old')
    capture = FailingCapture()
    application.state.local_aztek_capture = capture

    response = client.post('/api/aztek/local-capture')

    assert response.status_code == 409
    assert capture.called == 1
    with test_database.session() as db:
        session = db.scalar(select(AztekSession))
        assert session.account_label == 'old'
        assert security.decrypt_storage_state(
            session.encrypted_state, application.state.settings
        ) == old_state
