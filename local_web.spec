# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


ROOT = Path(SPEC).resolve().parent
ICON = ROOT / 'icon.ico'
BROWSER_CACHE = ROOT / 'build-cache' / 'ms-playwright'
if not BROWSER_CACHE.is_dir():
    raise SystemExit(
        'Bundled Chromium is missing. Run: '
        'python -m playwright install chromium'
    )

os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(BROWSER_CACHE)

version_source = ROOT / 'local_app' / 'version.txt'
build_version = os.environ.get('AFC_BUILD_VERSION')
if build_version:
    import re
    if not re.fullmatch(r'\d+\.\d+\.\d+', build_version):
        raise SystemExit('Invalid AFC_BUILD_VERSION')
    version_source = ROOT / 'build' / 'local-version' / 'version.txt'
    version_source.parent.mkdir(parents=True, exist_ok=True)
    version_source.write_text(build_version, encoding='utf-8')

def add_tree(source, destination):
    collected = []
    for path in source.rglob('*'):
        relative = path.relative_to(source)
        if (
            not path.is_file()
            or '__pycache__' in relative.parts
            or path.suffix.casefold() in {'.pyc', '.pyo'}
        ):
            continue
        collected.append((
            str(path),
            str(Path(destination) / relative.parent),
        ))
    return collected


datas = (
    add_tree(ROOT / 'web' / 'static', 'web/static')
    + add_tree(ROOT / 'alembic', 'alembic')
    + collect_data_files('playwright')
    + [
    (str(ROOT / 'alembic.ini'), '.'),
    (str(ICON), '.'),
    (str(version_source), 'local_app'),
    (str(BROWSER_CACHE), 'ms-playwright'),
    ]
)
hiddenimports = [
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
    'item_finder',
    'finder_core',
    'aztek_core',
    'ui_common',
    'fastapi',
    'starlette',
    'uvicorn.logging',
    'uvicorn.loops.auto',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan.on',
    'sqlalchemy.dialects.sqlite.pysqlite',
    'alembic.runtime.migration',
    'cryptography.hazmat.primitives.ciphers.aead',
    'argon2',
    'openpyxl.worksheet._reader',
    'playwright.async_api',
    'pydantic',
    'multipart',
    'anyio._backends._asyncio',
    'greenlet',
]

hiddenimports += collect_submodules('web')

a = Analysis(
    ['local_app/launcher.py'],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['local_app/pyinstaller_runtime_hook.py'],
    excludes=[
        'pytest',
        'IPython',
        'jedi',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'nbformat',
        'notebook',
        'psycopg',
        'psycopg_binary',
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='All for Cabal Web',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(ICON),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='All for Cabal Web',
)
