import hashlib

import pytest


class WindowsEffects:
    def __init__(self):
        self.installed = []
        self.opened = []
        self.exit_code = 0
        self.version = '0.1.31'

    def wait_for_parent(self, pid):
        return True

    def ready_to_install(self):
        return True

    def install(self, installer, application):
        self.installed.append(installer)
        return self.exit_code

    def open_app(self, application):
        self.opened.append(application)

    def wait_for_health(self, version):
        return self.version == version


def test_helper_updates_then_opens_target_version_and_retries_failure(tmp_path):
    from local_app.update_helper import perform_update
    installer = tmp_path / 'All.for.Cabal.Web.Setup-0.1.31.exe'
    installer.write_bytes(b'MZfixture')
    request = {'installer': str(installer), 'application': str(tmp_path / 'All for Cabal Web.exe'),
               'sha256': hashlib.sha256(b'MZfixture').hexdigest(), 'version': '0.1.31', 'parent_pid': 123}
    system = WindowsEffects()
    system.exit_code = 2
    with pytest.raises(RuntimeError, match='ติดตั้ง'):
        perform_update(request, system)
    assert system.opened == []
    system.exit_code = 0
    assert perform_update(request, system)['version'] == '0.1.31'
    assert len(system.opened) == 1
    system.version = '0.1.30'
    with pytest.raises(RuntimeError, match='เปิด'):
        perform_update(request, system)


def test_helper_never_installs_tampered_file_or_while_parent_is_running(tmp_path):
    from local_app.update_helper import perform_update
    installer = tmp_path / 'All.for.Cabal.Web.Setup-0.1.31.exe'
    installer.write_bytes(b'MZchanged')
    request = {'installer': str(installer), 'application': str(tmp_path / 'All for Cabal Web.exe'),
               'sha256': hashlib.sha256(b'MZfixture').hexdigest(), 'version': '0.1.31', 'parent_pid': 123}
    system = WindowsEffects()
    with pytest.raises(RuntimeError, match='ไฟล์'):
        perform_update(request, system)
    system.wait_for_parent = lambda pid: False
    with pytest.raises(RuntimeError, match='ยังไม่ปิด'):
        perform_update(request, system)
    assert system.installed == []
