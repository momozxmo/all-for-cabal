# Docker Development Environment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repeatable Docker Desktop workflow for developing and testing All for Cabal Web while leaving the native Windows Setup workflow unchanged.

**Architecture:** Build one development image from the pinned Playwright Python image, run FastAPI and headless Chromium through Docker Compose, and persist only the development SQLite database in a named volume. A PowerShell wrapper generates ignored stable local secrets, provides start/test/logs/stop commands, and falls back to the per-user Docker Desktop CLI path when the current terminal has stale `PATH` state.

**Tech Stack:** Docker Desktop, Docker Compose, Playwright Python 1.60.0, Chromium, Python 3.12, FastAPI/Uvicorn, SQLite, PowerShell, pytest

**Spec:** `docs/superpowers/specs/2026-08-25-docker-development-environment-design.md`

## Global Constraints

- Docker is a developer-only workflow; teammates continue to use the native Windows Setup.
- Base image and Python package must both use Playwright `1.60.0`.
- Publish the web service only as `127.0.0.1:8000:8000`.
- Set `BROWSER_CONCURRENCY=1` in the container.
- Persist Docker development data in a named volume, never in Git.
- Never copy or commit `.env`, `.env.docker.local`, databases, browser profiles, cookies, tokens, uploaded workbooks, `dist`, `build`, `artifacts`, or `build-cache`.
- Do not modify `scripts/build_local_installer.ps1`, PyInstaller specs, or Inno Setup files.
- Verification must not submit or create real Aztek records.
- Docker-to-Aztek access remains subject to corporate VPN and firewall policy.

---

## File Map

- Create `Dockerfile.dev`: deterministic Playwright/FastAPI development image.
- Create `constraints-docker.txt`: exact Docker-only Playwright package constraint.
- Create `compose.yaml`: loopback service, persistent SQLite volume, health check, and browser process settings.
- Create `.dockerignore`: Docker build-context security boundary.
- Create `.env.docker.example`: non-secret variable-name reference.
- Modify `.gitignore`: explicitly ignore generated Docker environment state.
- Create `scripts/docker_dev.ps1`: PowerShell lifecycle and secret-generation interface.
- Create `docs/DEVELOPMENT_DOCKER.md`: developer instructions and native-release boundary.
- Create `tests/test_docker_development.py`: static security/configuration contract tests.

---

### Task 1: Docker image and Compose security contract

**Files:**
- Create: `tests/test_docker_development.py`
- Create: `Dockerfile.dev`
- Create: `constraints-docker.txt`
- Create: `compose.yaml`
- Create: `.dockerignore`
- Create: `.env.docker.example`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: existing `requirements.txt`, `web.app:app`, and `/api/health`.
- Produces: Compose service `web`, named volume `all-for-cabal-dev-data`, and image entrypoint `python -m uvicorn web.app:app --host 0.0.0.0 --port 8000`.

- [ ] **Step 1: Write failing configuration tests**

Create `tests/test_docker_development.py` with these initial tests:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding='utf-8')


def test_dockerfile_pins_matching_playwright_image_and_constraint():
    dockerfile = read('Dockerfile.dev')
    constraints = read('constraints-docker.txt')
    assert 'mcr.microsoft.com/playwright/python:v1.60.0-noble' in dockerfile
    assert 'pip install --no-cache-dir -c constraints-docker.txt -r requirements.txt' in dockerfile
    assert constraints.strip() == 'playwright==1.60.0'


def test_compose_is_loopback_only_single_browser_and_persistent():
    compose = read('compose.yaml')
    assert '127.0.0.1:8000:8000' in compose
    assert 'BROWSER_CONCURRENCY: "1"' in compose
    assert 'DATABASE_URL: sqlite:////data/all_for_cabal_web.db' in compose
    assert 'all-for-cabal-dev-data:/data' in compose
    assert 'init: true' in compose
    assert 'ipc: host' in compose
    assert '/api/health' in compose


def test_docker_build_context_excludes_private_and_generated_state():
    ignored = read('.dockerignore')
    for value in (
        '.env*', '*.db', '*.sqlite', '*.sqlite3', '.cabal_chrome_profile/',
        '.local-runtime/', 'runtime-local/', 'dist/', 'build/', 'artifacts/',
        'build-cache/', '*.xlsx', '*.xls',
    ):
        assert value in ignored


def test_generated_docker_environment_is_gitignored():
    ignored = read('.gitignore')
    assert '.env.docker.local' in ignored
```

- [ ] **Step 2: Run tests and verify they fail because the Docker files do not exist**

Run:

```powershell
python -B -m pytest -p no:cacheprovider -q tests/test_docker_development.py
```

Expected: FAIL with `FileNotFoundError` for `Dockerfile.dev`.

- [ ] **Step 3: Create the pinned image definition**

Create `constraints-docker.txt`:

```text
playwright==1.60.0
```

Create `Dockerfile.dev`:

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.60.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt constraints-docker.txt ./
RUN python -m pip install --no-cache-dir -c constraints-docker.txt -r requirements.txt

COPY . .

CMD ["python", "-m", "uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: Create the Compose service**

Create `compose.yaml`:

```yaml
name: all-for-cabal-dev

services:
  web:
    build:
      context: .
      dockerfile: Dockerfile.dev
    env_file:
      - .env.docker.local
    environment:
      APP_ENV: development
      BROWSER_CONCURRENCY: "1"
      DATABASE_URL: sqlite:////data/all_for_cabal_web.db
      SESSION_COOKIE_SECURE: "false"
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - all-for-cabal-dev-data:/data
    init: true
    ipc: host
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"
      interval: 5s
      timeout: 4s
      retries: 20
      start_period: 10s

volumes:
  all-for-cabal-dev-data:
```

- [ ] **Step 5: Add Docker and Git exclusions**

Create `.dockerignore` with:

```text
.git/
.worktrees/
.claude/
.codex-tmp/
.codex_tmp/
.superpowers/
.understand-anything/
.env*
!.env.docker.example
*.db
*.sqlite
*.sqlite3
.cabal_chrome_profile/
.local-runtime/
runtime-local/
dist/
build/
artifacts/
build-cache/
__pycache__/
*.pyc
.pytest_cache/
tmp/
*.xlsx
*.xls
*.pptx
*.docx
```

Create `.env.docker.example`:

```text
APP_SECRET_KEY=replace-with-a-random-local-value
AZTEK_SESSION_ENCRYPTION_KEY=replace-with-a-32-byte-urlsafe-base64-value
BOOTSTRAP_ADMIN_USERNAME=docker-admin
BOOTSTRAP_ADMIN_PASSWORD=replace-with-a-random-local-password
```

Append this exact entry to `.gitignore`:

```text
.env.docker.local
```

- [ ] **Step 6: Run the focused tests**

Run:

```powershell
python -B -m pytest -p no:cacheprovider -q tests/test_docker_development.py
```

Expected: `4 passed`.

- [ ] **Step 7: Check formatting and commit Task 1**

Run:

```powershell
git diff --check
git add Dockerfile.dev constraints-docker.txt compose.yaml .dockerignore .env.docker.example .gitignore tests/test_docker_development.py
git commit -m "build: add Docker development image"
```

---

### Task 2: Safe PowerShell Docker lifecycle wrapper

**Files:**
- Modify: `tests/test_docker_development.py`
- Create: `scripts/docker_dev.ps1`

**Interfaces:**
- Consumes: Compose service `web`, `.env.docker.local`, and Docker CLI.
- Produces: `scripts/docker_dev.ps1 -Action <start|test|logs|stop>` with `start` as the default action.

- [ ] **Step 1: Add failing script contract tests**

Append to `tests/test_docker_development.py`:

```python
def test_docker_script_has_safe_lifecycle_actions_and_cli_fallback():
    script = read('scripts/docker_dev.ps1')
    for action in ('start', 'test', 'logs', 'stop'):
        assert "'%s'" % action in script
    assert 'Programs\\DockerDesktop\\resources\\bin\\docker.exe' in script
    assert '.env.docker.local' in script
    assert 'RandomNumberGenerator' in script
    assert 'compose up --build --detach' not in script
    assert "@('compose', 'up', '--build', '-d')" in script
    assert "@('compose', 'down')" in script
    assert "@('compose', 'down', '-v')" not in script


def test_installer_build_remains_native_and_docker_free():
    installer = read('scripts/build_local_installer.ps1').lower()
    assert 'pyinstaller' in installer
    assert 'iscc' in installer
    assert 'docker' not in installer
```

- [ ] **Step 2: Run the new tests and verify the missing-script failure**

Run:

```powershell
python -B -m pytest -p no:cacheprovider -q tests/test_docker_development.py
```

Expected: FAIL with `FileNotFoundError` for `scripts/docker_dev.ps1`.

- [ ] **Step 3: Implement Docker CLI discovery and process execution**

Create `scripts/docker_dev.ps1` with parameter and helper boundaries:

```powershell
param(
    [ValidateSet('start', 'test', 'logs', 'stop')]
    [string]$Action = 'start'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$envFile = Join-Path $projectRoot '.env.docker.local'

function Find-DockerCli {
    $command = Get-Command docker -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $candidate = Join-Path $env:LOCALAPPDATA `
        'Programs\DockerDesktop\resources\bin\docker.exe'
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    throw 'Docker CLI was not found. Start or reinstall Docker Desktop.'
}

function Invoke-Docker([string[]]$Arguments) {
    & $script:DockerCli @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed with exit code $LASTEXITCODE"
    }
}
```

Keep command arguments as arrays so file paths and values are never assembled into a second shell command.

- [ ] **Step 4: Implement stable local secret generation**

Add helpers that use `System.Security.Cryptography.RandomNumberGenerator`:

```powershell
function New-RandomBase64Url([int]$ByteCount) {
    $bytes = [byte[]]::new($ByteCount)
    [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function Ensure-DockerEnvironment {
    if (Test-Path -LiteralPath $envFile) { return }
    $lines = @(
        "APP_SECRET_KEY=$(New-RandomBase64Url 48)",
        "AZTEK_SESSION_ENCRYPTION_KEY=$(New-RandomBase64Url 32)",
        'BOOTSTRAP_ADMIN_USERNAME=docker-admin',
        "BOOTSTRAP_ADMIN_PASSWORD=$(New-RandomBase64Url 18)"
    )
    [IO.File]::WriteAllLines($envFile, $lines, [Text.UTF8Encoding]::new($false))
}
```

Do not print the application secret or encryption key. The `start` path may read and display only `BOOTSTRAP_ADMIN_USERNAME` and `BOOTSTRAP_ADMIN_PASSWORD` from the local file.

- [ ] **Step 5: Implement start, test, logs, and stop**

Use these exact Docker argument arrays:

```powershell
$script:DockerCli = Find-DockerCli
Push-Location $projectRoot
try {
    Invoke-Docker @('info')
    switch ($Action) {
        'start' {
            Ensure-DockerEnvironment
            Invoke-Docker @('compose', 'up', '--build', '-d')
            # Poll http://127.0.0.1:8000/api/health once per second for at most 60 seconds.
            # On timeout, run compose logs --no-color web and throw.
        }
        'test' {
            Ensure-DockerEnvironment
            Invoke-Docker @('compose', 'build', 'web')
            Invoke-Docker @(
                'compose', 'run', '--rm', '--no-deps', 'web',
                'python', '-B', '-m', 'pytest', '-p', 'no:cacheprovider', '-q', 'tests'
            )
        }
        'logs' { Invoke-Docker @('compose', 'logs', '-f', 'web') }
        'stop' { Invoke-Docker @('compose', 'down') }
    }
}
finally {
    Pop-Location
}
```

Implement the health loop with `Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 3`, accept only a response whose `ok` property is true, and call `Start-Sleep -Seconds 1` between attempts.

- [ ] **Step 6: Run focused tests**

Run:

```powershell
python -B -m pytest -p no:cacheprovider -q tests/test_docker_development.py
```

Expected: `6 passed`.

- [ ] **Step 7: Parse-check the PowerShell script without starting Docker**

Run:

```powershell
$errors = $null
[Management.Automation.Language.Parser]::ParseFile(
    (Resolve-Path '.\scripts\docker_dev.ps1'),
    [ref]$null,
    [ref]$errors
) | Out-Null
if ($errors.Count) { $errors | Format-List; exit 1 }
```

Expected: exit code `0` and no parser errors.

- [ ] **Step 8: Commit Task 2**

Run:

```powershell
git add scripts/docker_dev.ps1 tests/test_docker_development.py
git commit -m "build: add Docker development commands"
```

---

### Task 3: Docker developer documentation

**Files:**
- Modify: `tests/test_docker_development.py`
- Create: `docs/DEVELOPMENT_DOCKER.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: `scripts/docker_dev.ps1` lifecycle commands.
- Produces: one discoverable developer workflow and an explicit boundary between Docker development and native Setup releases.

- [ ] **Step 1: Add failing documentation contract test**

Append to `tests/test_docker_development.py`:

```python
def test_docker_documentation_explains_commands_and_release_boundary():
    guide = read('docs/DEVELOPMENT_DOCKER.md')
    for command in ('start', 'test', 'logs', 'stop'):
        assert '.\\scripts\\docker_dev.ps1 ' + command in guide
    assert 'scripts/build_local_installer.ps1' in guide
    assert 'Docker' in read('README.md')
    assert 'VPN' in guide
    assert 'IPA' in guide
    assert 'ไม่สร้างข้อมูลจริง' in guide
```

- [ ] **Step 2: Run the test and verify the missing-guide failure**

Run:

```powershell
python -B -m pytest -p no:cacheprovider -q tests/test_docker_development.py
```

Expected: FAIL with `FileNotFoundError` for `docs/DEVELOPMENT_DOCKER.md`.

- [ ] **Step 3: Write the developer guide**

Create `docs/DEVELOPMENT_DOCKER.md` in Thai with these exact sections:

```markdown
# พัฒนา All for Cabal Web ด้วย Docker

## ขอบเขต
## สิ่งที่ต้องมี
## เริ่มใช้งานครั้งแรก
## คำสั่ง start / test / logs / stop
## ข้อมูลและรหัสผ่านถูกเก็บที่ไหน
## การทดสอบ VPN, IPA และ Aztek
## การสร้าง Windows Setup สำหรับทีม
## การแก้ปัญหา Docker CLI, Engine, Build และ Health Check
```

Document that `stop` retains data, there is no volume-delete command, `.env.docker.local` must never be shared or committed, Docker testing must not create real Aztek records, and the release command remains:

```powershell
.\scripts\build_local_installer.ps1 -Version <version>
```

- [ ] **Step 4: Add a concise README link**

Add a `Docker สำหรับผู้พัฒนา` subsection to `README.md` linking to `docs/DEVELOPMENT_DOCKER.md`. Do not alter end-user Setup instructions.

- [ ] **Step 5: Run focused and existing release tests**

Run:

```powershell
python -B -m pytest -p no:cacheprovider -q tests/test_docker_development.py tests/test_local_release.py tests/test_local_runtime.py
```

Expected: all selected tests PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```powershell
git add docs/DEVELOPMENT_DOCKER.md README.md tests/test_docker_development.py
git commit -m "docs: add Docker development workflow"
```

---

### Task 4: Build and integration verification

**Files:**
- Modify only if a test exposes a defect: Docker-specific files created in Tasks 1–3 and `tests/test_docker_development.py`.
- Do not modify: `scripts/build_local_installer.ps1`, PyInstaller specs, Inno Setup files, or Aztek creation runners.

**Interfaces:**
- Consumes: `scripts/docker_dev.ps1`, Compose service `web`, and `/api/health`.
- Produces: verified developer image and a clean Git worktree with no generated private state staged.

- [ ] **Step 1: Run the complete native regression suite before Docker integration**

Run:

```powershell
python -B -m pytest -p no:cacheprovider -q tests
```

Expected: all repository tests PASS.

- [ ] **Step 2: Build and start the service**

Run:

```powershell
.\scripts\docker_dev.ps1 start
```

Expected: image build succeeds, service becomes healthy, and the script prints `http://127.0.0.1:8000` plus the generated development login.

- [ ] **Step 3: Verify host health and loopback publication**

Run:

```powershell
(Invoke-RestMethod 'http://127.0.0.1:8000/api/health').ok
```

Expected: `True`.

Run:

```powershell
docker compose ps
```

Expected: the published port begins with `127.0.0.1:8000->8000/tcp`, not `0.0.0.0`.

- [ ] **Step 4: Run all tests inside Docker**

Run:

```powershell
.\scripts\docker_dev.ps1 test
```

Expected: all repository tests PASS inside the pinned image.

- [ ] **Step 5: Verify local UI with container Chromium without Aztek submission**

Run the existing browser UI tests inside Docker through the test command and confirm at least the account, sheet-picker, Product, and calendar browser suites pass. Do not open or submit any real Aztek create form.

- [ ] **Step 6: Verify persistence across a normal stop/start**

Record the generated development username/password and confirm `.env.docker.local` exists but is ignored:

```powershell
git check-ignore .env.docker.local
```

Expected: `.env.docker.local`.

Then run:

```powershell
.\scripts\docker_dev.ps1 stop
.\scripts\docker_dev.ps1 start
```

Expected: the same development credentials remain in `.env.docker.local`, the service returns healthy, and Compose does not recreate the named volume.

- [ ] **Step 7: Verify no generated private or build state is staged**

Run:

```powershell
git status --short
git diff --check
```

Expected: only intentional source/documentation changes are present; no `.env.docker.local`, database, workbook, browser profile, token, `dist`, `build`, `artifacts`, or cache path appears.

- [ ] **Step 8: Stop the development service without deleting data**

Run:

```powershell
.\scripts\docker_dev.ps1 stop
```

Expected: containers and network stop; the named volume remains.

- [ ] **Step 9: Final verification commit if integration required corrections**

If and only if Tasks 4.1–4.8 required Docker-specific corrections, rerun the focused tests and commit only those corrections:

```powershell
git add Dockerfile.dev constraints-docker.txt compose.yaml .dockerignore .gitignore .env.docker.example scripts/docker_dev.ps1 docs/DEVELOPMENT_DOCKER.md README.md tests/test_docker_development.py
git commit -m "test: verify Docker development workflow"
```

If no corrections were required, do not create an empty commit.

---

## Final Review Checklist

- [ ] `git diff --check` reports no whitespace errors.
- [ ] `python -B -m pytest -p no:cacheprovider -q tests` passes natively.
- [ ] `.\scripts\docker_dev.ps1 test` passes inside Docker.
- [ ] `/api/health` is reachable from Windows only through `127.0.0.1:8000`.
- [ ] Playwright package and Docker image are both `1.60.0`.
- [ ] `.env.docker.local` and Docker SQLite data are not tracked.
- [ ] Normal `stop` keeps the named volume.
- [ ] Installer source and build script are unchanged.
- [ ] No real Aztek record was created.
