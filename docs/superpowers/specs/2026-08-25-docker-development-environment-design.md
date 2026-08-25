# Docker Development Environment Design

## Purpose

Add a reproducible Docker environment for developing and testing All for Cabal Web without changing how teammates install or run the Local Windows release.

The container is a developer tool. PyInstaller, Inno Setup, the Local launcher, and the downloadable Windows Setup remain native Windows workflows.

## Goals

- Run the FastAPI application and its Playwright Chromium worker in Docker Desktop.
- Run the existing Python and browser regression tests in the same container image.
- Expose the development web UI only on `127.0.0.1:8000`.
- Keep Playwright's Python package and browser image on the same pinned version.
- Preserve development SQLite data and encrypted Aztek sessions across container restarts without committing them.
- Keep secrets, databases, browser profiles, workbooks, build output, and release artifacts out of the Docker image and Git.
- Leave the Windows installer build and release verification commands unchanged.

## Non-goals

- No production deployment.
- No PostgreSQL, Railway, Neon, CI/CD, or multi-user hosting in this change.
- No browser GUI or VNC desktop inside the container.
- No automatic creation of real Bundle, Item Code, Event, or Product records during verification.
- No replacement of the native Windows smoke test for IPA, Aztek, corporate VPN, or the final Setup executable.

## Chosen Approach

Use a hybrid development workflow:

1. Docker runs FastAPI, Playwright Chromium in headless mode, SQLite, and the automated tests.
2. The developer opens the tool from the Windows host at `http://127.0.0.1:8000`.
3. Docker data lives in a named volume. Stable development secrets live in an ignored `.env.docker.local` file.
4. Real IPA/Aztek authentication and corporate VPN behavior receive a separate Windows-host smoke test before a release.
5. The existing native `scripts/build_local_installer.ps1` remains the only path that builds the team Setup executable.

This gives repeatable Python and browser dependencies without forcing teammates to install Docker or moving the release workflow into Linux.

## Alternatives Considered

### Docker for tests only

This is simpler, but it leaves the development server and Playwright worker running under a different environment from the test suite. It provides less protection against environment-specific failures.

### Run the complete interactive browser inside Docker

A headed browser exposed through VNC would make the container self-contained, but adds display, input, authentication, and VPN complexity. It also differs from the Windows browser flow used by the team. It is intentionally excluded.

## Files and Responsibilities

### `Dockerfile.dev`

- Base on `mcr.microsoft.com/playwright/python:v1.60.0-noble`.
- Install `requirements.txt` using `constraints-docker.txt` so the Python Playwright package remains exactly `1.60.0`, matching the browser image.
- Copy only application source, migrations, tests, and runtime configuration required by development and testing.
- Start Uvicorn on `0.0.0.0:8000`.
- Use `init: true` and host IPC through Compose for reliable Chromium process cleanup and shared memory.

### `constraints-docker.txt`

- Pin `playwright==1.60.0` for deterministic compatibility with the Docker base image.
- Do not change the looser Windows dependency policy in `requirements.txt` as part of this task.

### `compose.yaml`

- Define one `web` service built from `Dockerfile.dev`.
- Publish only `127.0.0.1:8000:8000`.
- Set `APP_ENV=development`, `BROWSER_CONCURRENCY=1`, and a SQLite URL under `/data`.
- Load secret values from `.env.docker.local`.
- Mount a named volume at `/data` for the database and session state.
- Add an HTTP health check against `/api/health`.
- Do not mount the host `.env`, databases, Chrome profiles, uploaded workbooks, `dist`, `artifacts`, or build caches.

### `.dockerignore`

Exclude at minimum:

- Git metadata and worktrees.
- `.env*` except the non-secret `.env.docker.example` documentation file.
- SQLite/database files.
- browser profiles, cookies, tokens, and local runtime state.
- uploaded spreadsheets and temporary files.
- `dist`, `build`, `artifacts`, `build-cache`, caches, and generated presentations/documents.

### `.env.docker.example`

- Document the required variable names with empty or obviously non-secret placeholders.
- Never contain working credentials or encryption keys.

### `.env.docker.local`

- Remain Git-ignored and excluded from the image.
- Be generated on first use by `scripts/docker_dev.ps1` when absent.
- Contain stable random `APP_SECRET_KEY`, `AZTEK_SESSION_ENCRYPTION_KEY`, and a generated development admin password so login and encrypted sessions survive restarts.

### `scripts/docker_dev.ps1`

Provide four commands:

- `start`: locate Docker CLI, create `.env.docker.local` if absent, build the image, start the service, wait for health, and display the URL and generated development login.
- `test`: build the current source and run `python -B -m pytest -p no:cacheprovider -q tests` in an ephemeral container.
- `logs`: follow service logs.
- `stop`: stop containers without deleting the named data volume.

The script first uses `docker` from `PATH`. For per-user Docker Desktop installations, it may fall back to `%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin\docker.exe`. Failure messages must distinguish missing CLI, stopped Docker Desktop, build failure, and failed health check.

Destructive cleanup of the named volume is not part of these commands.

### `docs/DEVELOPMENT_DOCKER.md`

Document prerequisites, commands, first-run login, data location, VPN/IPA limitations, troubleshooting, and the native Windows release boundary.

## Runtime and Data Flow

1. The developer runs `scripts/docker_dev.ps1 start`.
2. The script ensures stable ignored development secrets exist.
3. Compose builds the source into a Playwright-compatible image and starts Uvicorn.
4. Windows opens the published loopback URL.
5. FastAPI writes development data and encrypted Aztek sessions to SQLite in the named volume.
6. Playwright launches the image's matching Chromium in headless mode for tool jobs.
7. Container logs remain visible through the `logs` command.
8. `stop` removes the running containers but retains the named volume and local secret file.

## Security Boundaries

- Bind the web port to Windows loopback only; do not expose it to the LAN.
- Never bake secrets into an image layer or Compose file.
- Never copy or mount the Windows Chrome profile into the container.
- Do not commit `.env.docker.local`, Docker volumes, SQLite data, cookies, session exports, pairing tokens, uploaded workbooks, or build artifacts.
- Retain `BROWSER_CONCURRENCY=1`.
- Treat Docker-to-Aztek networking as a development capability that still depends on corporate VPN and firewall policy.
- Verification may navigate and fill preview forms but must not submit real Aztek records without separate explicit approval.

## Error Handling

- If Docker CLI is unavailable, print the checked locations and tell the developer to start or reinstall Docker Desktop.
- If the Docker engine is unavailable, stop before build and show the engine error.
- If secret generation fails, do not start with partial or empty secrets.
- If build or tests fail, preserve logs and return a non-zero exit code.
- If health does not become ready within the bounded timeout, print service logs and return a non-zero exit code.
- If VPN/IPA navigation fails inside Docker, record it as an environment limitation and retain the native Windows smoke path rather than weakening TLS or security settings.

## Verification

1. Static tests confirm Docker files exclude sensitive paths, pin matching Playwright versions, bind only to loopback, retain `BROWSER_CONCURRENCY=1`, and do not alter the installer script.
2. Build `Dockerfile.dev` successfully.
3. Start Compose and verify `/api/health` returns success from the Windows host.
4. Run the full repository test suite inside an ephemeral container.
5. Run a headless Playwright smoke test against the local application.
6. Stop and restart the service, then verify SQLite state and login session continuity.
7. Confirm `git status` contains no generated secret, database, browser, workbook, cache, or image artifact.
8. Confirm the existing native installer tests and build script remain unchanged and runnable on Windows.

Real Aztek creation is excluded from automated verification.

## Completion Criteria

- A developer with Docker Desktop can start, test, inspect, and stop the web application using the documented PowerShell commands.
- The container runs the same verified Playwright `1.60.0` package/browser pair.
- The web UI is reachable only from the local host.
- Development state survives a normal stop/start and remains outside Git.
- Existing Local Windows Setup behavior and build files are unchanged.
- All Docker-specific and existing regression tests pass.
