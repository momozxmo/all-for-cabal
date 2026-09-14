from __future__ import annotations

from dataclasses import replace

from fastapi.testclient import TestClient
from sqlalchemy import select

from web import app as web_app
from web.models import User


LOCAL_SECRET = 'launcher-secret-with-at-least-48-characters-0001'


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value


def _local_app(test_settings, test_database, clock=None):
    settings = replace(
        test_settings,
        app_env='local-desktop',
        local_desktop_mode=True,
        local_runtime_dir='C:/Users/Test/AppData/Local/AllForCabalWeb',
        local_launcher_secret=LOCAL_SECRET,
        bootstrap_admin_username='',
        bootstrap_admin_password='',
    )
    return web_app.create_app(
        settings,
        test_database,
        monotonic_clock=clock or Clock(),
    )


def _local_client(application, host='127.0.0.1'):
    return TestClient(
        application,
        client=(host, 50000),
        follow_redirects=False,
    )


def _issue(client, secret=LOCAL_SECRET):
    return client.post(
        '/api/local/launch',
        headers={'X-AFC-Launcher-Secret': secret},
    )


def test_local_launch_requires_loopback_and_exact_launcher_secret(
    test_settings, test_database
):
    application = _local_app(test_settings, test_database)
    client = _local_client(application)
    remote = _local_client(application, '192.168.1.5')

    missing = client.post('/api/local/launch')
    wrong = _issue(client, 'wrong')
    valid = _issue(client)
    not_loopback = _issue(remote)

    assert missing.status_code == 404
    assert wrong.status_code == 404
    assert not_loopback.status_code == 404
    assert valid.status_code == 200
    assert set(valid.json()) == {'token'}
    assert len(valid.json()['token']) >= 32


def test_local_token_is_single_use_and_sets_strict_httponly_cookie(
    test_settings, test_database
):
    client = _local_client(_local_app(test_settings, test_database))
    token = _issue(client).json()['token']

    first = client.post('/api/local/session', json={'token': token})
    replay = client.post('/api/local/session', json={'token': token})

    assert first.status_code == 204
    cookie = first.headers['set-cookie'].lower()
    assert 'afc_session=' in cookie
    assert 'httponly' in cookie
    assert 'samesite=strict' in cookie
    assert replay.status_code == 404
    current_user = client.get('/api/auth/me').json()
    assert current_user == {
        'id': current_user['id'],
        'username': 'local.owner',
        'role': 'admin',
        'is_active': True,
        'local_mode': True,
    }


def test_local_token_expires_after_sixty_seconds(
    test_settings, test_database
):
    clock = Clock()
    application = _local_app(test_settings, test_database, clock)
    client = _local_client(application)
    token = _issue(client).json()['token']

    clock.value = 61.0

    assert client.post(
        '/api/local/session', json={'token': token}).status_code == 404


def test_local_session_creates_one_stable_internal_owner(
    test_settings, test_database
):
    application = _local_app(test_settings, test_database)
    client = _local_client(application)

    for _ in range(2):
        token = _issue(client).json()['token']
        assert client.post(
            '/api/local/session', json={'token': token}).status_code == 204

    with test_database.session() as db:
        users = db.scalars(select(User)).all()

    assert len(users) == 1
    assert users[0].username == 'local.owner'
    assert LOCAL_SECRET not in users[0].password_hash


def test_local_start_page_has_no_visible_login_and_is_loopback_only(
    test_settings, test_database
):
    application = _local_app(test_settings, test_database)
    local = _local_client(application)
    remote = _local_client(application, '10.0.0.8')

    page = local.get('/local-start')

    assert page.status_code == 200
    assert 'loginForm' not in page.text
    assert '/api/local/session' in page.text
    assert remote.get('/local-start').status_code == 404
    assert local.get('/login').status_code == 307
    assert local.get('/login').headers['location'] == '/local-start'
    assert local.post('/api/auth/login', json={
        'username': 'local.owner',
        'password': LOCAL_SECRET,
    }).status_code == 404


def test_non_local_app_preserves_normal_login_and_hides_local_routes(
    test_settings, test_database
):
    application = web_app.create_app(test_settings, test_database)
    client = TestClient(application, follow_redirects=False)

    assert _issue(client).status_code == 404
    assert client.get('/local-start').status_code == 404
    assert client.get('/').headers['location'] == '/login'
    assert client.get('/login').status_code == 200


def test_health_product_marker_is_only_exposed_in_local_mode(
    test_settings, test_database
):
    local = _local_client(_local_app(test_settings, test_database))
    hosted = TestClient(web_app.create_app(test_settings, test_database))

    local_health = local.get('/api/health').json()
    version = local_health.pop('version')
    assert len(version.split('.')) == 3 and all(part.isdecimal() for part in version.split('.'))
    assert local_health == {
        'ok': True,
        'product': 'all-for-cabal-local',
    }
    assert hosted.get('/api/health').json() == {'ok': True}
