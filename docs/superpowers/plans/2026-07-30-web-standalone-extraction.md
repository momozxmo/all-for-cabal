# Web Standalone Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an independent runnable snapshot of the All for Cabal FastAPI web application at `C:\Users\koomo\Documents\Crazy\all for cabal web`.

**Architecture:** Assemble an exact allow-listed file set in a unique temporary staging directory, add web-only launch/documentation files there, and validate all imports and tests without the original checkout on `PYTHONPATH`. Promote the validated stage to the approved sibling path only after secret/artifact scans pass.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, SQLAlchemy/Alembic, Playwright Chromium, PowerShell, pytest, Windows Tkinter local controller.

## Global Constraints

- Source worktree is `C:\Users\koomo\Documents\Crazy\all for cabal\.worktrees\codex-web-auth`.
- Baseline application source is commit `03c08ff`; design-only commits after it do not alter application behavior.
- Destination is exactly `C:\Users\koomo\Documents\Crazy\all for cabal web`.
- Do not move or delete application files from the source worktree.
- Do not copy `.env`, databases, browser profiles, cookies, pairing tokens, uploaded workbooks, runtime preferences, caches, `build/`, `dist/`, `artifacts/`, or `build-cache/`.
- Do not copy `.git` or initialize/push a destination repository.
- Do not create a Bundle, Item Code, Event, or other real Aztek record during validation.
- Do not publish an installer or GitHub release.

## File Structure

The destination contains:

- `web/`: FastAPI routes, services, runners, parsers, and static browser UI.
- `local_app/`: Windows local controller and runtime management.
- `alembic/` and `alembic.ini`: database migrations.
- Root compatibility modules: the existing parser and automation dependencies imported by `web`.
- `installer/`, `local_web.spec`, and `scripts/build_local_installer.ps1`: optional later installer build support.
- `scripts/prepare_web_env.ps1`: shared source-environment preparation.
- `run_local.ps1`: local controller entry point.
- `run_web.ps1`: direct development-server entry point.
- `tests/test_standalone_layout.py`: isolation and exclusion regression checks.
- The existing web/local tests and a web-only `README.md`.

---

### Task 1: Assemble the allow-listed staging tree

**Files:**
- Copy: `web/**`
- Copy: `local_app/**`
- Copy: `alembic/**`
- Copy: `installer/**`
- Copy: `scripts/build_local_installer.ps1`
- Copy: `tests/conftest.py`
- Copy: `tests/test_web_*.py`
- Copy: `tests/test_local_*.py`
- Copy: `tests/test_aztek_pairing.py`
- Copy root files listed in Step 2

**Interfaces:**
- Consumes: clean tracked source files in the approved source worktree.
- Produces: a unique temporary directory whose path is stored in `$Stage`.

- [ ] **Step 1: Verify destination and source before copying**

Run from the source worktree:

```powershell
$Source = (Get-Location).Path
$Destination = 'C:\Users\koomo\Documents\Crazy\all for cabal web'
if ($Source -ne 'C:\Users\koomo\Documents\Crazy\all for cabal\.worktrees\codex-web-auth') {
    throw "Wrong source worktree: $Source"
}
if (Test-Path -LiteralPath $Destination) {
    throw "Destination already exists; inspect it instead of overwriting it: $Destination"
}
$Stage = Join-Path ([System.IO.Path]::GetTempPath()) (
    'all-for-cabal-web-stage-' + [guid]::NewGuid().ToString('N')
)
New-Item -ItemType Directory -Path $Stage | Out-Null
$Stage
```

Expected: a new empty directory under the current Windows temporary directory.

- [ ] **Step 2: Copy the exact root files and directories**

```powershell
$RootFiles = @(
    '.dockerignore',
    '.env.example',
    'alembic.ini',
    'aztek_core.py',
    'config.py',
    'Dockerfile',
    'event_tool.py',
    'finder_core.py',
    'icon.ico',
    'icon_256.png',
    'item_finder.py',
    'itemcode_tool.py',
    'local_web.spec',
    'new_tool.py',
    'render.yaml',
    'requirements-build.txt',
    'requirements.txt',
    'tool_registry.py',
    'ui_common.py'
)
foreach ($Relative in $RootFiles) {
    Copy-Item -LiteralPath (Join-Path $Source $Relative) -Destination $Stage
}
$TrackedTrees = git -C $Source ls-files -- web local_app alembic installer
if ($LASTEXITCODE -ne 0 -or -not $TrackedTrees) {
    throw 'อ่านรายการ tracked web files ไม่สำเร็จ'
}
foreach ($Relative in $TrackedTrees) {
    $Target = Join-Path $Stage $Relative
    $TargetParent = Split-Path -Parent $Target
    New-Item -ItemType Directory -Path $TargetParent -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $Source $Relative) -Destination $Target
}
New-Item -ItemType Directory -Path (Join-Path $Stage 'scripts') | Out-Null
Copy-Item -LiteralPath (
    Join-Path $Source 'scripts\build_local_installer.ps1'
) -Destination (Join-Path $Stage 'scripts')
New-Item -ItemType Directory -Path (Join-Path $Stage 'docs') | Out-Null
Copy-Item -LiteralPath (
    Join-Path $Source 'docs\LOCAL_INSTALL.md'
) -Destination (Join-Path $Stage 'docs')
```

Expected: only the explicitly listed source/runtime files exist in the stage.

- [ ] **Step 3: Copy only the web/local tests**

```powershell
$StageTests = Join-Path $Stage 'tests'
New-Item -ItemType Directory -Path $StageTests | Out-Null
Copy-Item -LiteralPath (Join-Path $Source 'tests\conftest.py') `
    -Destination $StageTests
Copy-Item -LiteralPath (Join-Path $Source 'tests\test_aztek_pairing.py') `
    -Destination $StageTests
Get-ChildItem -LiteralPath (Join-Path $Source 'tests') -File |
    Where-Object {
        $_.Name -like 'test_web_*.py' -or $_.Name -like 'test_local_*.py'
    } |
    Copy-Item -Destination $StageTests
```

Expected: the stage has no desktop UI test modules.

- [ ] **Step 4: Verify prohibited source state was not copied**

```powershell
$ForbiddenNames = @(
    '.env', '.git', '.cabal_chrome_profile', '.local-runtime',
    'build', 'dist', 'artifacts', 'build-cache', '__pycache__',
    '.pytest_cache', 'all_for_cabal_web.db', 'all_for_cabal_web_dev.db'
)
$FoundForbidden = Get-ChildItem -LiteralPath $Stage -Recurse -Force |
    Where-Object { $_.Name -in $ForbiddenNames }
if ($FoundForbidden) {
    $FoundForbidden.FullName
    throw 'Forbidden source state was copied'
}
```

Expected: no output and exit code 0.

### Task 2: Add standalone launch and documentation files

**Files:**
- Create: destination `.gitignore`
- Create: destination `requirements-dev.txt`
- Create: destination `scripts/prepare_web_env.ps1`
- Create: destination `run_local.ps1`
- Create: destination `run_web.ps1`
- Create: destination `README.md`
- Create: destination `tests/test_standalone_layout.py`

**Interfaces:**
- Consumes: `$Stage` from Task 1.
- Produces: self-contained setup/launch commands and regression tests.

- [ ] **Step 1: Create the standalone `.gitignore`**

Create `$Stage\.gitignore` with:

```gitignore
.env
.venv/
*.db
*.sqlite
*.sqlite3
__pycache__/
*.py[cod]
.pytest_cache/
.cabal_chrome_profile/
.local-runtime/
runtime-local/
.aztek_prefs.json
.item_finder_prefs.json
.new_tool_prefs.json
build/
dist/
artifacts/
build-cache/
extension/config.local.js
```

- [ ] **Step 2: Create the development requirements**

Create `$Stage\requirements-dev.txt` with:

```text
-r requirements.txt
pytest>=8,<9
```

- [ ] **Step 3: Create the shared environment preparation script**

Create `$Stage\scripts\prepare_web_env.ps1` with:

```powershell
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot
)

$ErrorActionPreference = 'Stop'
$Venv = Join-Path $ProjectRoot '.venv'
$Python = Join-Path $Venv 'Scripts\python.exe'
$Requirements = Join-Path $ProjectRoot 'requirements.txt'
$Marker = Join-Path $Venv '.requirements.sha256'

if (-not (Test-Path -LiteralPath $Python)) {
    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($PyLauncher) {
        & py -3.12 -m venv $Venv
    } else {
        & python -m venv $Venv
    }
    if ($LASTEXITCODE -ne 0) {
        throw 'สร้าง Python virtual environment ไม่สำเร็จ'
    }
}

$RequiredHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Requirements).Hash
$InstalledHash = if (Test-Path -LiteralPath $Marker) {
    (Get-Content -Raw -LiteralPath $Marker).Trim()
} else {
    ''
}
if ($InstalledHash -ne $RequiredHash) {
    & $Python -m pip install --upgrade pip
    & $Python -m pip install -r $Requirements
    if ($LASTEXITCODE -ne 0) {
        throw 'ติดตั้ง Python dependencies ไม่สำเร็จ'
    }
    Set-Content -LiteralPath $Marker -Value $RequiredHash -NoNewline
}

& $Python -m playwright install chromium
if ($LASTEXITCODE -ne 0) {
    throw 'ติดตั้ง Playwright Chromium ไม่สำเร็จ'
}
```

- [ ] **Step 4: Create both launch entry points**

Create `$Stage\run_local.ps1` with:

```powershell
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $ProjectRoot 'scripts\prepare_web_env.ps1') `
    -ProjectRoot $ProjectRoot
& (Join-Path $ProjectRoot '.venv\Scripts\python.exe') -m local_app.launcher
exit $LASTEXITCODE
```

Create `$Stage\run_web.ps1` with:

```powershell
param([ValidateRange(1, 65535)][int]$Port = 8000)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot
& (Join-Path $ProjectRoot 'scripts\prepare_web_env.ps1') `
    -ProjectRoot $ProjectRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
& $Python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    throw 'อัปเดตฐานข้อมูลไม่สำเร็จ'
}
& $Python -m uvicorn web.app:app --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
```

- [ ] **Step 5: Create the isolation regression test**

Create `$Stage\tests\test_standalone_layout.py` with:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_sensitive_and_desktop_only_paths_are_absent():
    forbidden = {
        '.env',
        '.git',
        '.cabal_chrome_profile',
        '.local-runtime',
        'build',
        'dist',
        'artifacts',
        'build-cache',
        'all_for_cabal.py',
        'all_for_cabal.spec',
        'build.bat',
    }
    found = {
        path.name
        for path in ROOT.rglob('*')
        if path.name in forbidden
    }
    assert found == set()


def test_runtime_imports_resolve_inside_standalone():
    for module_name in (
        'web.app',
        'local_app.launcher',
        'item_finder',
        'event_tool',
        'itemcode_tool',
        'new_tool',
        'aztek_core',
    ):
        spec = importlib.util.find_spec(module_name)
        assert spec is not None
        assert spec.origin is not None
        assert Path(spec.origin).resolve().is_relative_to(ROOT)
```

- [ ] **Step 6: Create the web-only README**

Create `$Stage\README.md` containing:

````markdown
# All for Cabal Web

ซอร์สโค้ดแบบ standalone สำหรับ All for Cabal Web ประกอบด้วย Item Finder,
Bundle, Item Code และ Event โดยไม่ต้องอ้างไฟล์จากโปรเจกต์ desktop ต้นฉบับ

## เปิดแบบ Local Controller

เปิด PowerShell ในโฟลเดอร์นี้แล้วรัน:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_local.ps1
```

สคริปต์จะสร้าง `.venv`, ติดตั้ง dependencies และ Playwright Chromium
จากนั้นเปิด Controller สำหรับเริ่ม/หยุดเว็บที่ `http://127.0.0.1:8000`

## เปิดแบบ Development Server

```powershell
powershell -ExecutionPolicy Bypass -File .\run_web.ps1
```

ฐานข้อมูล development จะถูกสร้างในโฟลเดอร์นี้และถูก `.gitignore` ไว้

## ทดสอบ

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

## ข้อมูลที่ไม่ควรนำขึ้น Git

ห้าม commit `.env`, ฐานข้อมูล, Chrome profile, cookies, pairing tokens,
workbook ที่นำเข้า, `.venv`, `build`, `dist`, `artifacts` และ `build-cache`

โฟลเดอร์นี้เป็น snapshot แยกอิสระ การแก้โปรเจกต์ต้นฉบับจะไม่อัปเดตมาที่นี่
อัตโนมัติ
````

### Task 3: Validate the staged standalone application

**Files:**
- Test: all files under `$Stage\tests`
- Inspect: all files under `$Stage`

**Interfaces:**
- Consumes: fully assembled `$Stage`.
- Produces: evidence that the snapshot runs independently and contains no prohibited state.

- [ ] **Step 1: Install the isolated environment**

```powershell
& (Join-Path $Stage 'scripts\prepare_web_env.ps1') -ProjectRoot $Stage
$Python = Join-Path $Stage '.venv\Scripts\python.exe'
& $Python -m pip install -r (Join-Path $Stage 'requirements-dev.txt')
```

Expected: commands exit 0.

- [ ] **Step 2: Clear source-path influence and run isolation tests**

```powershell
$PreviousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = ''
Push-Location $Stage
try {
    & $Python -m pytest tests\test_standalone_layout.py -q
} finally {
    Pop-Location
    $env:PYTHONPATH = $PreviousPythonPath
}
```

Expected: 2 tests pass.

- [ ] **Step 3: Run the complete extracted suite**

```powershell
$PreviousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = ''
Push-Location $Stage
try {
    & $Python -m pytest -q
} finally {
    Pop-Location
    $env:PYTHONPATH = $PreviousPythonPath
}
```

Expected: all collected web/local tests pass with no import from the original
checkout.

- [ ] **Step 4: Apply migrations and verify the health endpoint**

```powershell
Push-Location $Stage
try {
    & $Python -m alembic upgrade head
    $Server = Start-Process -FilePath $Python `
        -ArgumentList @(
            '-m', 'uvicorn', 'web.app:app',
            '--host', '127.0.0.1', '--port', '8015'
        ) `
        -WindowStyle Hidden -PassThru
    try {
        $Deadline = (Get-Date).AddSeconds(30)
        do {
            Start-Sleep -Milliseconds 250
            try {
                $Health = Invoke-RestMethod `
                    -Uri 'http://127.0.0.1:8015/api/health' `
                    -TimeoutSec 1
            } catch {
                $Health = $null
            }
        } until ($Health.ok -eq $true -or (Get-Date) -ge $Deadline)
        if ($Health.ok -ne $true) {
            throw 'Standalone health endpoint did not become ready'
        }
        if ($Health.product -ne 'all-for-cabal-local') {
            throw "Unexpected product: $($Health.product)"
        }
    } finally {
        if ($Server -and -not $Server.HasExited) {
            Stop-Process -Id $Server.Id
            $Server.WaitForExit()
        }
    }
} finally {
    Pop-Location
}
```

Expected: `/api/health` returns `ok=true` and
`product=all-for-cabal-local`. No Aztek creation endpoint is called.

- [ ] **Step 5: Remove validation-generated state**

Resolve and verify every target stays under `$Stage`, then remove only:

```powershell
$GeneratedNames = @(
    '.venv',
    '.pytest_cache',
    '__pycache__',
    'all_for_cabal_web.db'
)
$StageRoot = [System.IO.Path]::GetFullPath($Stage).TrimEnd('\')
Get-ChildItem -LiteralPath $Stage -Recurse -Force |
    Where-Object { $_.Name -in $GeneratedNames } |
    Sort-Object { $_.FullName.Length } -Descending |
    ForEach-Object {
        $Resolved = [System.IO.Path]::GetFullPath($_.FullName)
        if (-not $Resolved.StartsWith($StageRoot + '\')) {
            throw "Refusing to remove outside stage: $Resolved"
        }
        Remove-Item -LiteralPath $Resolved -Recurse -Force
    }
```

Expected: source-only stage remains; no generated database, virtual
environment, or cache remains.

### Task 4: Promote and verify the final sibling folder

**Files:**
- Create: `C:\Users\koomo\Documents\Crazy\all for cabal web\**`
- Verify only: source worktree

**Interfaces:**
- Consumes: validated, cleaned `$Stage`.
- Produces: the approved standalone destination.

- [ ] **Step 1: Recheck the exact promotion paths**

```powershell
$Destination = 'C:\Users\koomo\Documents\Crazy\all for cabal web'
$StageResolved = [System.IO.Path]::GetFullPath($Stage)
$DestinationResolved = [System.IO.Path]::GetFullPath($Destination)
if (-not $StageResolved.StartsWith(
    [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
)) {
    throw "Unexpected stage path: $StageResolved"
}
if ($DestinationResolved -ne
    'C:\Users\koomo\Documents\Crazy\all for cabal web') {
    throw "Unexpected destination path: $DestinationResolved"
}
if (Test-Path -LiteralPath $DestinationResolved) {
    throw "Destination appeared during validation: $DestinationResolved"
}
```

- [ ] **Step 2: Move the validated stage to the destination**

```powershell
Move-Item -LiteralPath $StageResolved -Destination $DestinationResolved
```

Expected: the stage no longer exists and the destination does.

- [ ] **Step 3: Run final source-only validation at the destination**

```powershell
Set-Location -LiteralPath $DestinationResolved
python -c "from web.app import app; from local_app.launcher import main; print(app.title)"
Get-ChildItem -Force | Select-Object Name
```

Expected: imports succeed and the root contains only the standalone allow-list
plus the new web-only support files.

- [ ] **Step 4: Verify the original worktree was not contaminated**

```powershell
git -C 'C:\Users\koomo\Documents\Crazy\all for cabal\.worktrees\codex-web-auth' `
    status --short --branch
```

Expected: only the already committed design/plan history is ahead; no runtime
database, environment, cache, copied application file, or secret is untracked.

- [ ] **Step 5: Report the handoff**

Report:

- exact destination path;
- test count and result;
- health endpoint result;
- confirmation that no secret/state/build artifact was copied;
- confirmation that no real Aztek data was created;
- the commands for `run_local.ps1` and `run_web.ps1`;
- that no destination Git repository or GitHub push was created.
