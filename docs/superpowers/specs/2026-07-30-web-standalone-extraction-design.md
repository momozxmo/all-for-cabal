# Web Standalone Extraction Design

## Goal

Create an independent, runnable web-source folder at:

`C:\Users\koomo\Documents\Crazy\all for cabal web`

The new folder is a clean source snapshot for the FastAPI web application and
its Windows local controller. It must not read code from, import through, or
depend on paths inside the original `all for cabal` checkout.

The extraction is non-destructive. No application file is moved from or deleted
from the source worktree.

## Source of truth

- Source worktree:
  `C:\Users\koomo\Documents\Crazy\all for cabal\.worktrees\codex-web-auth`
- Source branch: `codex/local-windows-installer`
- Baseline commit at design time: `03c08ff`
- The destination is a one-time standalone snapshot. It does not automatically
  synchronize when the source worktree changes.

## Extraction approach

Copy the smallest practical dependency closure while leaving the proven runtime
logic unchanged. This avoids a risky parser/automation refactor during the
separation.

The web layer currently imports reusable functions from several original
desktop modules. Those compatibility modules must therefore be copied even
though they still contain dormant Tkinter classes. The standalone web runtime
does not launch those desktop tools. The only graphical shell it intentionally
uses is `local_app`, the Windows controller for starting and stopping the local
web server.

## Included files

### Web application

- `web/`
- `local_app/`
- `alembic/`
- `alembic.ini`

### Shared runtime compatibility modules

- `aztek_core.py`
- `config.py`
- `event_tool.py`
- `finder_core.py`
- `item_finder.py`
- `itemcode_tool.py`
- `new_tool.py`
- `tool_registry.py`
- `ui_common.py`

These files are included because the current FastAPI parsers and Playwright
runners import them directly or transitively.

### Installation, packaging, and deployment

- `requirements.txt`
- `requirements-build.txt`
- `.env.example`
- `.gitignore`
- `.dockerignore`
- `Dockerfile`
- `render.yaml`
- `local_web.spec`
- `installer/`
- `scripts/build_local_installer.ps1`
- `icon.ico`
- `icon_256.png`

### Documentation and launch helpers

- A new web-only `README.md`
- Relevant local installation documentation
- `run_local.ps1` for installing/checking dependencies and starting the local
  controller from source
- `run_web.ps1` for starting FastAPI directly in development mode

### Tests

- `tests/conftest.py`
- `tests/test_web_*.py`
- `tests/test_local_*.py`
- `tests/test_aztek_pairing.py`
- Parser tests required by those tests, when dependency discovery proves they
  are needed

## Explicit exclusions

The extraction must not copy:

- `.env` or any real credentials
- SQLite/database files
- Chrome/Playwright user profiles, cookies, storage state, or pairing tokens
- imported or uploaded workbooks
- `.aztek_prefs.json`, `.item_finder_prefs.json`, or other machine-local state
- `.git`, linked-worktree metadata, IDE state, or Codex/Claude state
- `build/`, `dist/`, `artifacts/`, `build-cache/`, caches, or bytecode
- the original desktop entry point `all_for_cabal.py`
- the desktop PyInstaller spec `all_for_cabal.spec`
- the legacy desktop build script `build.bat`
- unrelated design documents and desktop-only tests

The destination receives an explicit `.gitignore` that preserves these
boundaries after first run.

## Runtime behavior

### Local controller

`run_local.ps1` prepares a local virtual environment when needed, installs the
requirements, installs Playwright Chromium when missing, and launches
`python -m local_app.launcher`.

Runtime databases, logs, and generated secrets remain machine-local and outside
version-controlled source, following the existing `local_app` behavior.

### Direct development server

`run_web.ps1` prepares the same development environment, applies Alembic
migrations, then runs:

`python -m uvicorn web.app:app --host 127.0.0.1 --port 8000`

The script must stop with a clear message if required configuration is absent
instead of inventing production secrets.

## Validation

Validation runs from the destination folder only:

1. Scan tracked/source files for prohibited state and secret filenames.
2. Confirm every local import resolves without adding the original checkout to
   `PYTHONPATH`.
3. Import `web.app` and `local_app.launcher`.
4. Run the extracted web/local pytest suite.
5. Start the local server and verify `/api/health`, without creating any real
   Aztek Bundle, Item Code, or Event.
6. Confirm `git status` in the original source worktree contains no copied
   runtime artifacts or application edits caused by extraction.

Installer compilation is optional for this extraction. The existing build files
are included so the standalone folder can build a later installer, but a new
release is not published as part of this task.

## Success criteria

- The destination exists at the approved sibling path.
- It runs without importing from the original project path.
- Web and local-controller tests pass from the destination.
- No secret, database, browser profile, workbook, or build artifact is copied.
- The original application source remains unchanged and no GitHub push or
  release is performed.
