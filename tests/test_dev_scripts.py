"""Run the PowerShell entry points; replace only downloads and the GUI launcher."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which('powershell.exe')
pytestmark = pytest.mark.skipif(
    sys.platform != 'win32' or not POWERSHELL,
    reason='Windows PowerShell developer entry points',
)


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def run_ps(command, cwd):
    return subprocess.run(
        [POWERSHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', command],
        cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=60,
    )


@pytest.fixture
def project(tmp_path):
    root = tmp_path / 'source with spaces'
    (root / 'scripts').mkdir(parents=True)
    for name in ('setup_dev.ps1', 'start_dev.ps1'):
        source = ROOT / 'scripts' / name
        assert source.exists(), f'Missing developer entry point: {name}'
        shutil.copy2(source, root / 'scripts' / name)
    for name in ('requirements.txt', 'requirements-build.txt', 'requirements-dev.txt'):
        (root / name).write_text('# พัฒนา: UTF-8 dependency boundary\n', encoding='utf-8')
    return root


def test_setup_invalid_interpreter_does_not_create_runtime(project, tmp_path):
    result = run_ps(
        f"& {ps_quote(project / 'scripts/setup_dev.ps1')} "
        f"-PythonExecutable {ps_quote(tmp_path / 'missing-python.exe')}", tmp_path,
    )
    assert result.returncode != 0
    assert not (project / '.venv').exists()
    assert not (project / '.local-runtime').exists()


@pytest.mark.parametrize('pip_status', [0, 9])
def test_setup_uses_repo_venv_and_stops_on_dependency_failure(project, tmp_path, pip_status):
    # The real venv is created. Network/package installation alone is replaced.
    (project / 'pip.py').write_text(
        "import json, pathlib, sys\n"
        "assert sys.prefix != sys.base_prefix, 'global pip is forbidden'\n"
        "pathlib.Path('requirements.txt').read_text()\n"
        "pathlib.Path('pip-call.json').write_text(json.dumps(sys.argv[1:]))\n"
        f"raise SystemExit({pip_status})\n", encoding='utf-8',
    )
    (project / 'playwright.py').write_text(
        "import json, os, pathlib, sys\n"
        "assert sys.prefix != sys.base_prefix\n"
        "pathlib.Path('browser-call.json').write_text(json.dumps({"
        "'args': sys.argv[1:], 'cache': os.environ['PLAYWRIGHT_BROWSERS_PATH']}))\n",
        encoding='utf-8',
    )
    result = run_ps(
        f"$env:PLAYWRIGHT_BROWSERS_PATH = 'existing-cache'; "
        f"try {{ & {ps_quote(project / 'scripts/setup_dev.ps1')} "
        f"-PythonExecutable {ps_quote(sys.executable)} }} "
        "catch { Write-Output 'setup-failed' }; "
        "Write-Output ('restored=' + $env:PLAYWRIGHT_BROWSERS_PATH)", tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert (project / '.venv/Scripts/python.exe').exists()
    assert json.loads((project / 'pip-call.json').read_text()) == [
        'install', '-r', 'requirements-dev.txt',
    ]
    assert 'restored=existing-cache' in result.stdout
    if pip_status:
        assert 'setup-failed' in result.stdout
        assert not (project / 'browser-call.json').exists()
    else:
        assert 'setup-failed' not in result.stdout, result.stderr
        call = json.loads((project / 'browser-call.json').read_text())
        assert call['args'] == ['install', 'chromium']
        assert Path(call['cache']) == project / 'build-cache/ms-playwright'


def test_start_without_setup_stops_before_touching_runtime(project, tmp_path):
    result = run_ps(f"& {ps_quote(project / 'scripts/start_dev.ps1')}", tmp_path)
    assert result.returncode != 0
    assert 'setup_dev.ps1' in result.stderr
    assert not (project / '.local-runtime').exists()


def test_start_refuses_an_occupied_app_port(project, tmp_path):
    (project / '.venv/Scripts').mkdir(parents=True)
    (project / '.venv/Scripts/python.exe').touch()
    result = run_ps(
        "function Get-NetTCPConnection { [pscustomobject]@{LocalPort=8000} }; "
        f"& {ps_quote(project / 'scripts/start_dev.ps1')}", tmp_path,
    )
    assert result.returncode != 0
    assert '8000' in result.stderr
    assert not (project / '.local-runtime').exists()


@pytest.mark.parametrize('launcher_status', [0, 7])
def test_start_isolates_data_and_restores_shell_environment(project, tmp_path, launcher_status):
    subprocess.run([sys.executable, '-m', 'venv', '--without-pip',
                    str(project / '.venv')], check=True, timeout=30)
    package = project / 'local_app'
    package.mkdir()
    (package / '__init__.py').touch()
    (package / 'launcher.py').write_text(
        "import json, os, pathlib, sys\n"
        "pathlib.Path('launch-env.json').write_text(json.dumps({"
        "'data': os.environ['LOCALAPPDATA'], "
        "'cache': os.environ['PLAYWRIGHT_BROWSERS_PATH']}))\n"
        f"raise SystemExit({launcher_status})\n", encoding='utf-8',
    )
    result = run_ps(
        "function Get-NetTCPConnection {}; "
        "$env:LOCALAPPDATA = 'installed-app-data'; "
        "Remove-Item Env:PLAYWRIGHT_BROWSERS_PATH -ErrorAction SilentlyContinue; "
        f"try {{ & {ps_quote(project / 'scripts/start_dev.ps1')} }} "
        "catch { Write-Output 'launcher-failed' }; "
        "Write-Output ('restored=' + $env:LOCALAPPDATA); "
        "Write-Output ('cachePresent=' + (Test-Path Env:PLAYWRIGHT_BROWSERS_PATH))",
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    call = json.loads((project / 'launch-env.json').read_text())
    assert Path(call['data']) == project / '.local-runtime/developer-appdata'
    assert Path(call['cache']) == project / 'build-cache/ms-playwright'
    assert 'restored=installed-app-data' in result.stdout
    assert 'cachePresent=False' in result.stdout
    assert ('launcher-failed' in result.stdout) == bool(launcher_status)
