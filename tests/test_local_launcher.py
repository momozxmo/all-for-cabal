from __future__ import annotations

import tempfile
import threading
import os
import queue
import time
import subprocess
from pathlib import Path

import pytest

from local_app.runtime import RuntimePaths
from local_app.server import (
    BrowserLaunchError,
    LocalServer,
    PortInUseError,
    StartupTimeoutError,
)
from local_app import launcher


class FakeHttp:
    def __init__(self, health=None, launch_token='one-use-token'):
        self.health_response = health
        self.health_responses = []
        self.launch_token = launch_token
        self.launch_headers = None

    def health(self):
        if self.health_responses:
            return self.health_responses.pop(0)
        return self.health_response

    def launch(self, secret):
        self.launch_headers = {'X-AFC-Launcher-Secret': secret}
        return self.launch_token


class WaitingUvicornServer:
    def __init__(self, config=None):
        self.config = config
        self.should_exit = False
        self.ran = threading.Event()

    def run(self):
        self.ran.set()
        self.ran.wait(2)


def _paths():
    root = Path(tempfile.mkdtemp(prefix='afc_launcher_test_'))
    return RuntimePaths(
        root=root,
        database=root / 'app.db',
        config=root / 'config.json',
        logs=root / 'logs',
        backups=root / 'backups',
    )


def _config():
    return {
        'app_secret_key': 'app-secret',
        'aztek_encryption_key': 'encryption-key',
        'launcher_secret': 'launcher-secret',
    }


def test_second_launcher_reuses_server_and_opens_new_bootstrap_url(monkeypatch):
    opened = []
    monkeypatch.setattr('local_app.server.webbrowser.open', opened.append)
    http = FakeHttp(
        health={'ok': True, 'product': 'all-for-cabal-local'},
    )
    server = LocalServer(
        _paths(),
        _config(),
        http=http,
        port_is_open=lambda: True,
    )

    assert server.ensure_started() == 'reused'
    server.open_browser()

    assert opened == [
        'http://127.0.0.1:8000/local-start#one-use-token'
    ]
    assert http.launch_headers == {
        'X-AFC-Launcher-Secret': 'launcher-secret'
    }


@pytest.mark.skipif(os.name != 'nt', reason='Windows browser discovery')
@pytest.mark.parametrize(('browser', 'relative'), [
    ('chrome', 'Google/Chrome/Application/chrome.exe'),
    ('edge', 'Microsoft/Edge/Application/msedge.exe'),
    ('firefox', 'Mozilla Firefox/firefox.exe'),
])
def test_selected_browser_opens_directly_with_a_fresh_token_each_time(monkeypatch, tmp_path, browser, relative):
    import winreg

    def absent_registry(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(winreg, 'OpenKey', absent_registry)
    monkeypatch.setenv('ProgramFiles', str(tmp_path))
    monkeypatch.setenv('ProgramFiles(x86)', str(tmp_path / 'x86'))
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'appdata'))
    executable = tmp_path / relative
    executable.parent.mkdir(parents=True)
    executable.touch()
    opened = []
    default_opened = []
    monkeypatch.setattr(subprocess, 'Popen', lambda args, **kwargs: opened.append((args, kwargs)))
    monkeypatch.setattr('local_app.server.webbrowser.open', default_opened.append)

    class FreshHttp(FakeHttp):
        def launch(self, secret):
            self.launch_token = str(int(self.launch_token) + 1)
            return super().launch(secret)

    http = FreshHttp(health={'ok': True, 'product': 'all-for-cabal-local'}, launch_token='0')
    server = LocalServer(_paths(), _config(), http=http)
    server.open_browser(browser)
    server.open_browser(browser)

    assert [args for args, _options in opened] == [
        [str(executable), 'http://127.0.0.1:8000/local-start#1'],
        [str(executable), 'http://127.0.0.1:8000/local-start#2'],
    ]
    assert all(options.get('shell') is False for _args, options in opened)
    assert default_opened == []


@pytest.mark.skipif(os.name != 'nt', reason='Windows App Paths registry')
def test_browser_installed_in_custom_location_uses_registered_app_path(monkeypatch, tmp_path):
    import winreg
    executable = tmp_path / 'custom-browser/chrome.exe'
    executable.parent.mkdir()
    executable.touch()

    class RegistryKey:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

    monkeypatch.setattr(winreg, 'OpenKey', lambda *_args: RegistryKey())
    monkeypatch.setattr(winreg, 'QueryValueEx', lambda *_args: (str(executable), winreg.REG_SZ))
    for name in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        monkeypatch.setenv(name, str(tmp_path / 'no-standard-install'))
    opened = []
    monkeypatch.setattr(subprocess, 'Popen', lambda args, **_kwargs: opened.append(args))
    server = LocalServer(_paths(), _config(), http=FakeHttp())
    server.open_browser('chrome')
    assert opened == [[str(executable), 'http://127.0.0.1:8000/local-start#one-use-token']]


@pytest.mark.skipif(os.name != 'nt', reason='Windows browser discovery')
def test_successful_browser_choice_is_used_on_next_launcher_open(monkeypatch, tmp_path):
    monkeypatch.setattr('local_app.server.webbrowser.open', lambda _url: True)
    # Use the actual preference API while replacing only the OS browser process.
    import winreg
    def absent_registry(*_args):
        raise FileNotFoundError
    monkeypatch.setattr(winreg, 'OpenKey', absent_registry)
    for name in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        monkeypatch.setenv(name, str(tmp_path))
    executable = tmp_path / 'Microsoft/Edge/Application/msedge.exe'
    executable.parent.mkdir(parents=True)
    executable.touch()
    opened = []
    monkeypatch.setattr(subprocess, 'Popen', lambda args, **_kwargs: opened.append(args))
    paths = _paths()
    LocalServer(paths, _config(), http=FakeHttp()).open_browser('edge')
    LocalServer(paths, _config(), http=FakeHttp()).open_browser()
    assert len(opened) == 2
    assert all(args[0] == str(executable) for args in opened)


@pytest.mark.skipif(os.name != 'nt', reason='Windows Launcher UI')
def test_launcher_selection_routes_open_button_to_selected_browser(monkeypatch, tmp_path):
    import tkinter as tk
    import winreg
    def absent_registry(*_args):
        raise FileNotFoundError
    monkeypatch.setattr(winreg, 'OpenKey', absent_registry)
    for name in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        monkeypatch.setenv(name, str(tmp_path))
    executable = tmp_path / 'Mozilla Firefox/firefox.exe'
    executable.parent.mkdir()
    executable.touch()
    opened = []
    monkeypatch.setattr(subprocess, 'Popen', lambda args, **_kwargs: opened.append(args))
    root = tk.Tk()
    root.withdraw()
    try:
        server = LocalServer(_paths(), _config(), http=FakeHttp())
        controller = launcher.LauncherController(root, server)
        assert tuple(controller.browser_selector['values']) == (
            'Default (ตาม Windows)', 'Google Chrome', 'Microsoft Edge', 'Mozilla Firefox',
        )
        controller.browser_selector.set('Mozilla Firefox')
        controller.open_button.invoke()
        deadline = time.monotonic() + 2
        while controller.status.get() != 'พร้อมใช้งาน' and time.monotonic() < deadline:
            root.update()
            time.sleep(0.01)
        assert opened == [[str(executable), 'http://127.0.0.1:8000/local-start#one-use-token']]
        assert controller.status.get() == 'พร้อมใช้งาน'
        assert str(controller.browser_selector['state']) == 'readonly'
    finally:
        root.destroy()


@pytest.mark.skipif(os.name != 'nt', reason='Windows browser discovery')
def test_missing_browser_does_not_fall_back_or_request_a_token(monkeypatch, tmp_path):
    import winreg
    def absent_registry(*_args):
        raise FileNotFoundError
    monkeypatch.setattr(winreg, 'OpenKey', absent_registry)
    for name in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        monkeypatch.setenv(name, str(tmp_path))
    opened = []
    monkeypatch.setattr('local_app.server.webbrowser.open', opened.append)
    monkeypatch.setattr(subprocess, 'Popen', lambda *_args, **_kwargs: opened.append('process'))
    http = FakeHttp()
    server = LocalServer(_paths(), _config(), http=http)
    with pytest.raises(BrowserLaunchError, match='ไม่พบ Google Chrome'):
        server.open_browser('chrome')
    assert opened == []
    assert http.launch_headers is None


@pytest.mark.skipif(os.name != 'nt', reason='Windows browser discovery')
def test_failed_browser_launch_preserves_preference_and_hides_token(monkeypatch, tmp_path):
    import winreg
    from local_app.browsers import read_browser_preference, save_browser_preference
    def absent_registry(*_args):
        raise FileNotFoundError
    monkeypatch.setattr(winreg, 'OpenKey', absent_registry)
    for name in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        monkeypatch.setenv(name, str(tmp_path))
    executable = tmp_path / 'Google/Chrome/Application/chrome.exe'
    executable.parent.mkdir(parents=True)
    executable.touch()
    def failed_launch(args, **_kwargs):
        raise OSError(f'cannot open {args}')
    monkeypatch.setattr(subprocess, 'Popen', failed_launch)
    paths = _paths()
    save_browser_preference(paths.root, 'edge')
    server = LocalServer(paths, _config(), http=FakeHttp())
    with pytest.raises(BrowserLaunchError) as failure:
        server.open_browser('chrome')
    assert 'one-use-token' not in str(failure.value)
    assert read_browser_preference(paths.root) == 'edge'


@pytest.mark.parametrize('content', ['{', '[]', '{"browser": "unknown"}', '{"browser": []}'])
def test_invalid_preference_defaults_to_windows_browser(monkeypatch, content):
    paths = _paths()
    (paths.root / 'launcher-preferences.json').write_text(content, encoding='utf-8')
    opened = []
    monkeypatch.setattr('local_app.server.webbrowser.open', opened.append)
    LocalServer(paths, _config(), http=FakeHttp()).open_browser()
    assert opened == ['http://127.0.0.1:8000/local-start#one-use-token']


def test_preference_save_failure_does_not_cancel_browser_open(monkeypatch):
    def failed_save(*_args):
        raise OSError('disk full')
    monkeypatch.setattr('local_app.server.save_browser_preference', failed_save)
    opened = []
    monkeypatch.setattr('local_app.server.webbrowser.open', opened.append)
    paths = _paths()
    result = LocalServer(paths, _config(), http=FakeHttp()).open_browser('default')
    assert opened == [result]
    log = (paths.logs / 'all-for-cabal-web.log').read_text(encoding='utf-8')
    assert 'browser preference could not be saved' in log
    assert 'one-use-token' not in log


def test_unknown_process_on_port_8000_is_rejected():
    server = LocalServer(
        _paths(),
        _config(),
        http=FakeHttp(health={'ok': True, 'product': 'another-product'}),
        port_is_open=lambda: True,
    )

    with pytest.raises(PortInUseError, match='8000'):
        server.ensure_started()


@pytest.mark.parametrize('action', ['ensure_started', 'open_browser'])
def test_installed_launcher_rejects_other_running_version(monkeypatch, action):
    monkeypatch.setattr('local_app.server.sys.frozen', True, raising=False)
    monkeypatch.setattr('local_app.updates.current_version', lambda: '0.1.34')
    http = FakeHttp(health={'ok': True, 'product': 'all-for-cabal-local',
                            'version': '0.1.30'})
    server = LocalServer(_paths(), _config(), http=http, port_is_open=lambda: True)
    with pytest.raises(PortInUseError, match='8000'):
        getattr(server, action)()
    assert http.launch_headers is None


def test_installed_launcher_reuses_matching_version(monkeypatch):
    monkeypatch.setattr('local_app.server.sys.frozen', True, raising=False)
    monkeypatch.setattr('local_app.updates.current_version', lambda: '0.1.34')
    server = LocalServer(_paths(), _config(),
        http=FakeHttp(health={'ok': True, 'product': 'all-for-cabal-local',
                             'version': '0.1.34'}), port_is_open=lambda: True)
    assert server.ensure_started() == 'reused'


def test_startup_timeout_stops_the_partially_started_server():
    clock_values = iter([0.0, 21.0])
    fake = WaitingUvicornServer()
    server = LocalServer(
        _paths(),
        _config(),
        http=FakeHttp(),
        port_is_open=lambda: False,
        app_factory=lambda: object(),
        config_factory=lambda **kwargs: kwargs,
        server_factory=lambda _config: fake,
        clock=lambda: next(clock_values),
        sleep=lambda _seconds: None,
    )

    with pytest.raises(StartupTimeoutError):
        server.start()

    assert fake.should_exit is True


def test_restart_stops_before_starting(monkeypatch):
    server = LocalServer(
        _paths(), _config(), http=FakeHttp(), port_is_open=lambda: False)
    events = []
    monkeypatch.setattr(server, 'stop', lambda: events.append('stop'))
    monkeypatch.setattr(server, 'start', lambda: events.append('start'))

    server.restart()

    assert events == ['stop', 'start']


def test_stop_sets_should_exit_and_joins_thread():
    fake = WaitingUvicornServer()

    class FakeThread:
        def __init__(self):
            self.joined_with = None

        def join(self, timeout):
            self.joined_with = timeout

    thread = FakeThread()
    server = LocalServer(
        _paths(), _config(), http=FakeHttp(), port_is_open=lambda: False)
    server._uvicorn_server = fake
    server._thread = thread

    server.stop()

    assert fake.should_exit is True
    assert thread.joined_with == 5


def test_uvicorn_config_disables_access_log_and_thread_is_not_daemon():
    captured = {}
    fake = WaitingUvicornServer()
    http = FakeHttp()
    http.health_responses = [
        {'ok': True, 'product': 'all-for-cabal-local'}
    ]

    def config_factory(**kwargs):
        captured.update(kwargs)
        return kwargs

    server = LocalServer(
        _paths(),
        _config(),
        http=http,
        port_is_open=lambda: False,
        app_factory=lambda: object(),
        config_factory=config_factory,
        server_factory=lambda _config: fake,
        sleep=lambda _seconds: None,
    )

    server.start()

    assert captured['host'] == '127.0.0.1'
    assert captured['port'] == 8000
    assert captured['access_log'] is False
    assert captured['log_config'] is None
    assert server._thread.daemon is False
    server.stop()


def test_browser_launch_failure_is_thai_and_does_not_stop_server(monkeypatch):
    monkeypatch.setattr('local_app.server.webbrowser.open', lambda _url: False)
    fake = WaitingUvicornServer()
    server = LocalServer(
        _paths(),
        _config(),
        http=FakeHttp(
            health={'ok': True, 'product': 'all-for-cabal-local'},
        ),
        port_is_open=lambda: True,
    )
    server._uvicorn_server = fake

    with pytest.raises(BrowserLaunchError, match='เบราว์เซอร์'):
        server.open_browser()

    assert fake.should_exit is False


def test_rotating_log_redacts_every_runtime_secret():
    paths = _paths()
    server = LocalServer(
        paths,
        _config(),
        http=FakeHttp(),
        port_is_open=lambda: False,
    )

    server._logger.info(
        'values %s %s %s',
        'app-secret',
        'encryption-key',
        'launcher-secret',
    )
    for handler in server._logger.handlers:
        handler.flush()
    contents = (paths.logs / 'all-for-cabal-web.log').read_text(
        encoding='utf-8')

    assert 'app-secret' not in contents
    assert 'encryption-key' not in contents
    assert 'launcher-secret' not in contents
    assert contents.count('[redacted]') == 3


def test_prepare_runtime_applies_environment_before_migration(monkeypatch):
    paths = _paths()
    config = _config()
    environment = {
        'APP_ENV': 'local-desktop',
        'LOCAL_LAUNCHER_SECRET': 'launcher-secret',
    }
    events = []
    monkeypatch.setenv('APP_ENV', 'before-test')
    monkeypatch.setenv('LOCAL_LAUNCHER_SECRET', 'before-test')
    monkeypatch.setattr(
        launcher.RuntimePaths,
        'for_user',
        classmethod(lambda cls: paths),
    )
    monkeypatch.setattr(
        launcher,
        'ensure_runtime_config',
        lambda actual: events.append(('config', actual)) or config,
    )
    monkeypatch.setattr(
        launcher,
        'runtime_environment',
        lambda actual_paths, actual_config: (
            events.append(('environment', actual_paths, actual_config))
            or environment
        ),
    )

    def migrate(actual_paths, actual_environment):
        assert os.environ['APP_ENV'] == 'local-desktop'
        events.append(('migrate', actual_paths, actual_environment))

    monkeypatch.setattr(launcher, 'backup_and_migrate', migrate)

    prepared = launcher.prepare_runtime()

    assert prepared == (paths, config)
    assert [event[0] for event in events] == [
        'config', 'environment', 'migrate'
    ]


def test_windows_mutex_reports_an_existing_instance_and_closes_handle():
    class FakeKernel32:
        def __init__(self):
            self.closed = []

        def CreateMutexW(self, _security, _owner, name):
            assert name == r'Local\AllForCabalWebLauncher'
            return 123

        def CloseHandle(self, handle):
            self.closed.append(handle)

    kernel32 = FakeKernel32()
    mutex = launcher.WindowsMutex(
        kernel32=kernel32,
        last_error=lambda: 183,
    )

    assert mutex.already_exists is True
    mutex.close()
    assert kernel32.closed == [123]


def test_controller_asks_only_once_before_stopping():
    class FakeRoot:
        def __init__(self):
            self.destroyed = False

        def after(self, _delay, callback):
            callback()

        def destroy(self):
            self.destroyed = True

    class FakeServer:
        def __init__(self):
            self.stops = 0

        def stop(self):
            self.stops += 1

    asks = []
    controller = launcher.LauncherController.__new__(
        launcher.LauncherController)
    controller.root = FakeRoot()
    controller.server = FakeServer()
    controller._closing = False
    controller._ask_stop = (
        lambda: asks.append('asked') or True
    )
    controller._set_controls_enabled = lambda _enabled: None
    controller._set_status = lambda _text: None
    controller._run_worker = lambda action, on_success=None: (
        action(),
        on_success() if on_success else None,
    )

    controller.request_close()
    controller.request_close()

    assert asks == ['asked']
    assert controller.server.stops == 1
    assert controller.root.destroyed is True


def test_controller_keeps_polling_until_async_stop_destroys_window():
    class FakeRoot:
        def __init__(self):
            self.callbacks = []
            self.destroyed = False

        def after(self, _delay, callback):
            self.callbacks.append(callback)

        def destroy(self):
            self.destroyed = True

    class BlockingServer:
        def __init__(self):
            self.started = threading.Event()
            self.release = threading.Event()

        def stop(self):
            self.started.set()
            self.release.wait(2)

    root = FakeRoot()
    server = BlockingServer()
    controller = launcher.LauncherController.__new__(
        launcher.LauncherController)
    controller.root = root
    controller.server = server
    controller._closing = False
    controller._shutdown_complete = False
    controller._ask_stop = lambda: True
    controller._messages = queue.Queue()
    controller._set_controls_enabled = lambda _enabled: None
    controller._set_status = lambda _text: None

    controller.request_close()
    assert server.started.wait(1)

    # Reproduce the real race: the scheduled poll runs while stop() is still
    # working, so there is no success message to consume yet.
    controller._drain_messages()
    server.release.set()
    deadline = time.monotonic() + 1
    while controller._messages.empty() and time.monotonic() < deadline:
        time.sleep(0.01)

    assert root.callbacks, 'closing must keep polling the worker result'
    root.callbacks.pop(0)()
    assert root.destroyed is True
