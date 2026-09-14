from dataclasses import replace
import hashlib
import pytest

from fastapi.testclient import TestClient

from web.app import create_app


class UpdateNetwork:
    def latest_release(self):
        base = 'https://github.com/momozxmo/tool-cabal-local/releases/download/v0.1.31/'
        name = 'All.for.Cabal.Web.Setup-0.1.31.exe'
        return {'tag_name': 'v0.1.31', 'draft': False, 'prerelease': False,
                'body': 'แก้ Import และเพิ่มระบบอัปเดต', 'assets': [
                    {'name': name, 'browser_download_url': base + name, 'size': 7},
                    {'name': name + '.sha256', 'browser_download_url': base + name + '.sha256', 'size': 100},
                ]}

    def asset_chunks(self, url):
        if url.endswith('.sha256'):
            yield (hashlib.sha256(b'MZsetup').hexdigest() + ' *All for Cabal Web Setup-0.1.31.exe').encode()
        else:
            yield b'MZsetup'


def local_client(settings, database, tmp_path, network):
    settings = replace(settings, app_env='local-desktop',
                       local_desktop_mode=True, local_runtime_dir=str(tmp_path),
                       local_launcher_secret='test-launcher-secret-' * 3,
                       bootstrap_admin_username='', bootstrap_admin_password='')
    app = create_app(settings, database, update_io=network)
    client = TestClient(app, base_url='http://127.0.0.1:8000',
                        client=('127.0.0.1', 50000))
    token = client.post('/api/local/launch', headers={
        'X-AFC-Launcher-Secret': settings.local_launcher_secret}).json()['token']
    client.post('/api/local/session', json={'token': token})
    client.headers['Origin'] = 'http://127.0.0.1:8000'
    return client


def test_operator_can_check_release_and_claim_popup_once_across_restarts(
    test_settings, test_database, tmp_path,
):
    client = local_client(test_settings, test_database, tmp_path, UpdateNetwork())
    response = client.post('/api/local/update/check')
    assert response.status_code == 200
    assert response.json()['release']['version'] == '0.1.31'
    assert 'แก้ Import' in response.json()['release']['notes']
    assert client.post('/api/local/update/seen').json()['show'] is True
    assert client.post('/api/local/update/seen').json()['show'] is False
    again = local_client(test_settings, test_database, tmp_path, UpdateNetwork())
    again.post('/api/local/update/check')
    assert again.post('/api/local/update/seen').json()['show'] is False
    assert again.get('/api/local/update').json()['release']['version'] == '0.1.31'


def test_operator_downloads_verified_setup_and_is_not_installed_yet(
    test_settings, test_database, tmp_path,
):
    client = local_client(test_settings, test_database, tmp_path, UpdateNetwork())
    client.post('/api/local/update/check')
    response = client.post('/api/local/update/download')
    assert response.status_code == 200
    assert response.json()['state'] == 'ready'
    assert response.json()['downloaded'] == 7
    assert client.get('/api/local/update').json()['state'] == 'ready'


def test_update_preparation_waits_for_saved_tabs_and_releases_work_on_cancel(
    test_settings, test_database, tmp_path,
):
    client = local_client(test_settings, test_database, tmp_path, UpdateNetwork())
    client.post('/api/local/update/check')
    client.post('/api/local/update/tabs', json={'id': 'tab-a', 'page': '/bundles'})
    with client.app.state.browser_gate.work():
        assert client.post('/api/local/update/prepare').status_code == 409
    response = client.post('/api/local/update/prepare')
    assert response.status_code == 200
    assert response.json()['state'] == 'preparing'
    token = response.json()['preparation']
    assert response.json()['tabs_ready'] is False
    with pytest.raises(RuntimeError):
        with client.app.state.browser_gate.work():
            pass
    response = client.post('/api/local/update/tabs', json={
        'id': 'tab-a', 'page': '/bundles', 'prepared': token, 'saved': True})
    assert response.json()['tabs_ready'] is True
    assert client.post('/api/local/update/cancel').status_code == 200
    with client.app.state.browser_gate.work():
        pass


@pytest.mark.parametrize('bad', ['corrupt', 'truncated', 'url'])
def test_download_rejects_bad_setup(test_settings, test_database, tmp_path, bad):
    class Broken(UpdateNetwork):
        def latest_release(self):
            data = super().latest_release()
            if bad == 'url':
                data['assets'][0]['browser_download_url'] = 'https://evil.example/setup.exe'
            return data

        def asset_chunks(self, url):
            if not url.endswith('.sha256') and bad != 'url':
                yield b'MZwrong' if bad == 'corrupt' else b'MZ'
            else:
                yield from super().asset_chunks(url)
    client = local_client(test_settings, test_database, tmp_path, Broken())
    client.post('/api/local/update/check')
    response = client.post('/api/local/update/download')
    assert response.json()['state'] == 'error'
    assert response.json()['message']


def test_update_commands_reject_cross_origin(test_settings, test_database, tmp_path):
    client = local_client(test_settings, test_database, tmp_path, UpdateNetwork())
    client.headers['Origin'] = 'https://evil.example'
    assert client.post('/api/local/update/check').status_code == 403


def test_install_requires_verified_file_and_current_saved_tabs(
    test_settings, test_database, tmp_path,
):
    client = local_client(test_settings, test_database, tmp_path, UpdateNetwork())
    client.post('/api/local/update/check')
    client.post('/api/local/update/tabs', json={'id': 'tab-a', 'page': '/bundles'})
    assert client.post('/api/local/update/install', json={'preparation': 'old'}).status_code == 409
    client.post('/api/local/update/download')
    token = client.post('/api/local/update/prepare').json()['preparation']
    assert client.post('/api/local/update/install', json={'preparation': token}).status_code == 409
    client.post('/api/local/update/tabs', json={
        'id': 'tab-a', 'page': '/bundles', 'saved': True, 'prepared': token})
    response = client.post('/api/local/update/install', json={'preparation': token})
    assert response.status_code == 200
    assert response.json()['state'] == 'installing'


def test_closed_tab_recovery_requires_confirmation_and_rejects_resumed_tabs(
    test_settings, test_database, tmp_path, monkeypatch,
):
    from types import SimpleNamespace
    import local_app.updates as updates
    clock = [100.0]
    monkeypatch.setattr(updates, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    client = local_client(test_settings, test_database, tmp_path, UpdateNetwork())
    client.post('/api/local/update/check')
    client.post('/api/local/update/tabs', json={'id': 'lost', 'page': '/bundles', 'busy': True})
    clock[0] += 20
    client.post('/api/local/update/tabs', json={'id': 'live', 'page': '/products'})
    state = client.get('/api/local/update').json()
    assert state['stale_tabs'] == [{'id': 'lost', 'page': '/bundles'}]
    assert client.post('/api/local/update/prepare').status_code == 409
    assert client.post('/api/local/update/forget-tabs', json={'ids': ['lost']}).status_code == 409
    assert client.post('/api/local/update/forget-tabs', json={
        'ids': ['live'], 'confirmed_closed': True}).status_code == 409
    assert client.post('/api/local/update/forget-tabs', json={
        'ids': ['lost'], 'confirmed_closed': True}).status_code == 200
    assert client.post('/api/local/update/prepare').status_code == 200


@pytest.mark.parametrize('outcome', ['error', 'pending', 'success'])
def test_restart_reports_previous_attempt_without_trusting_or_installing_package(
    test_settings, test_database, tmp_path, outcome,
):
    import json
    updates = tmp_path / 'updates'
    updates.mkdir()
    (updates / 'result.json').write_text(json.dumps({
        'state': outcome, 'version': '0.1.31', 'message': 'ติดตั้งไม่สำเร็จ'}), encoding='utf-8')
    client = local_client(test_settings, test_database, tmp_path, UpdateNetwork())
    state = client.get('/api/local/update').json()
    assert state['last_attempt']['state'] == 'error'
    assert state['last_attempt']['version'] == '0.1.31'
    assert state['state'] == 'idle'
    assert client.post('/api/local/update/install', json={'preparation': 'old'}).status_code == 409
    assert client.post('/api/local/update/check').json()['release']['version'] == '0.1.31'
    assert client.post('/api/local/update/download').json()['state'] == 'ready'
