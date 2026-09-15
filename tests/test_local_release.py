from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess

import pytest

from local_app.release_verify import verify_tree, write_checksum


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('prefix', ['', '_internal/'])
def test_release_verifier_accepts_shipped_bundle_template(tmp_path, prefix):
    package = tmp_path / 'package'
    target = package / f'{prefix}web/static/templates/bundle-template.xlsx'
    target.parent.mkdir(parents=True)
    target.write_bytes((ROOT / 'web/static/templates/bundle-template.xlsx').read_bytes())
    verify_tree(package)


@pytest.mark.parametrize('relative', [
    'uploads/bundle-template.xlsx',
    '_internal/web/static/templates/private.xlsx',
    '_internal/web/static/templates/nested/bundle-template.xlsx',
])
def test_release_verifier_still_rejects_other_workbooks(tmp_path, relative):
    package = tmp_path / 'package'
    target = package / relative
    target.parent.mkdir(parents=True)
    target.write_bytes(b'private')
    with pytest.raises(ValueError, match='private runtime suffix'):
        verify_tree(package)


def test_release_verifier_rejects_private_runtime_files(tmp_path):
    package = tmp_path / 'package'
    package.mkdir()
    (package / 'web').mkdir()
    (package / 'web' / 'app.py').write_text('safe', encoding='utf-8')
    (package / 'all_for_cabal_web.db').write_bytes(b'private')

    with pytest.raises(ValueError, match='all_for_cabal_web.db'):
        verify_tree(package)


@pytest.mark.parametrize(
    'relative_path',
    [
        '.ENV',
        'CONFIG.JSON',
        'data/private.SQLite3',
        'uploads/plan.XLSM',
        '__pycache__/module.pyc',
        'nested/.git/config',
        'nested/build/output.bin',
        'nested/.cabal_chrome_profile/Default/Cookies',
    ],
)
def test_release_verifier_is_case_insensitive_and_checks_every_component(
    tmp_path, relative_path
):
    package = tmp_path / 'package'
    target = package / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b'private')

    with pytest.raises(ValueError, match=target.name):
        verify_tree(package)


def test_release_verifier_accepts_app_and_writes_sha256(tmp_path):
    package = tmp_path / 'package'
    package.mkdir()
    executable = package / 'All for Cabal Web.exe'
    executable.write_bytes(b'installer')

    verify_tree(package)
    checksum = write_checksum(executable)

    expected = hashlib.sha256(b'installer').hexdigest()
    assert checksum.name == 'All for Cabal Web.exe.sha256'
    assert checksum.read_text(encoding='ascii') == (
        f'{expected} *All for Cabal Web.exe\n'
    )


def test_pyinstaller_spec_is_one_directory_and_bundles_offline_assets():
    spec = (ROOT / 'local_web.spec').read_text(encoding='utf-8')

    assert "['local_app/launcher.py']" in spec
    assert 'console=False' in spec
    assert 'COLLECT(' in spec
    for fragment in (
        'web/static',
        'alembic.ini',
        'build-cache',
        'ms-playwright',
        'pyinstaller_runtime_hook.py',
        "'fastapi'",
        "'uvicorn.logging'",
        "'sqlalchemy.dialects.sqlite.pysqlite'",
        "'alembic.runtime.migration'",
        "'cryptography.hazmat.primitives.ciphers.aead'",
        "'argon2'",
        "'openpyxl.worksheet._reader'",
        "'playwright.async_api'",
    ):
        assert fragment in spec


def test_installer_contract_preserves_local_data_and_starts_launcher():
    installer = (
        ROOT / 'installer' / 'AllForCabalWeb.iss'
    ).read_text(encoding='utf-8')

    for fragment in (
        'AppId={{6B5A3461-9A4C-4D08-A72A-6F7426F22C91}',
        'ArchitecturesAllowed=x64compatible',
        'ArchitecturesInstallIn64BitMode=x64compatible',
        'PrivilegesRequired=lowest',
        'All for Cabal Web.exe',
        'postinstall',
        'desktopicon',
    ):
        assert fragment in installer
    assert '[UninstallDelete]' not in installer
    assert 'AllForCabalWeb' not in installer.split('[Files]', 1)[-1]


def test_build_script_installs_browser_runs_tests_and_verifies_release():
    script = (
        ROOT / 'scripts' / 'build_local_installer.ps1'
    ).read_text(encoding='utf-8')

    for fragment in (
        "$ErrorActionPreference = 'Stop'",
        'requirements-build.txt',
        'PLAYWRIGHT_BROWSERS_PATH',
        'reset_playwright_cache.ps1',
        'sanitize_playwright_cache.ps1',
        'playwright install chromium',
        'python -m pytest -q tests',
        'python -m PyInstaller',
        'local_app.release_verify',
        'ISCC.exe',
        'LOCALAPPDATA',
    ):
        assert fragment in script


def test_browser_cache_reset_removes_stale_revisions_without_touching_siblings(
    tmp_path,
):
    build_cache = tmp_path / 'build-cache'
    browser_cache = build_cache / 'ms-playwright'
    stale_browser = browser_cache / 'chromium-1223' / 'chrome.exe'
    stale_browser.parent.mkdir(parents=True)
    stale_browser.write_bytes(b'old browser')
    sibling = build_cache / 'keep.txt'
    sibling.write_text('keep', encoding='utf-8')

    result = subprocess.run(
        [
            'powershell.exe',
            '-NoProfile',
            '-ExecutionPolicy',
            'Bypass',
            '-File',
            str(ROOT / 'scripts' / 'reset_playwright_cache.ps1'),
            '-BuildCache',
            str(build_cache),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert browser_cache.is_dir()
    assert list(browser_cache.iterdir()) == []
    assert sibling.read_text(encoding='utf-8') == 'keep'


def test_browser_cache_sanitizer_removes_runtime_logs_only(tmp_path):
    build_cache = tmp_path / 'build-cache'
    browser_cache = build_cache / 'ms-playwright'
    browser = browser_cache / 'chromium-1228' / 'chrome.exe'
    runtime_log = browser.parent / 'debug.log'
    browser.parent.mkdir(parents=True)
    browser.write_bytes(b'current browser')
    runtime_log.write_text('runtime noise', encoding='utf-8')
    sibling_log = build_cache / 'keep.log'
    sibling_log.write_text('keep', encoding='utf-8')

    result = subprocess.run(
        [
            'powershell.exe',
            '-NoProfile',
            '-ExecutionPolicy',
            'Bypass',
            '-File',
            str(ROOT / 'scripts' / 'sanitize_playwright_cache.ps1'),
            '-BuildCache',
            str(build_cache),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert browser.read_bytes() == b'current browser'
    assert not runtime_log.exists()
    assert sibling_log.read_text(encoding='utf-8') == 'keep'
