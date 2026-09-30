from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


BROWSERS = {
    'default': ('Default (ตาม Windows)', ''),
    'chrome': ('Google Chrome', 'Google/Chrome/Application/chrome.exe'),
    'edge': ('Microsoft Edge', 'Microsoft/Edge/Application/msedge.exe'),
    'firefox': ('Mozilla Firefox', 'Mozilla Firefox/firefox.exe'),
}


def read_browser_preference(root: Path) -> str:
    try:
        data = json.loads((root / 'launcher-preferences.json').read_text(encoding='utf-8'))
        choice = data.get('browser') if isinstance(data, dict) else None
        return choice if isinstance(choice, str) and choice in BROWSERS else 'default'
    except (OSError, ValueError):
        return 'default'


def save_browser_preference(root: Path, choice: str) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=root,
                                         prefix='launcher-preferences-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({'browser': choice}, stream)
        os.replace(temporary, root / 'launcher-preferences.json')
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def browser_executable(choice: str) -> Path | None:
    if choice not in BROWSERS:
        raise ValueError('เบราว์เซอร์ที่เลือกไม่รองรับ')
    if choice == 'default':
        return None
    label, relative = BROWSERS[choice]
    if os.name == 'nt':
        import winreg
        key_path = str(Path(r'Software\Microsoft\Windows\CurrentVersion\App Paths') / Path(relative).name)
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ | view) as key:
                        value, _kind = winreg.QueryValueEx(key, '')
                    if isinstance(value, str):
                        candidate = Path(os.path.expandvars(value.strip().strip('"')))
                        if candidate.is_absolute() and candidate.is_file():
                            return candidate
                except OSError:
                    continue
    for name in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        base = os.environ.get(name)
        if base:
            candidate = Path(base) / relative
            if candidate.is_absolute() and candidate.is_file():
                return candidate
    raise FileNotFoundError(f'ไม่พบ {label} บนเครื่องนี้ กรุณาติดตั้งหรือเลือกเบราว์เซอร์อื่น')
