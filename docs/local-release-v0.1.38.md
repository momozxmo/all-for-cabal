# Local release v0.1.38 — Launcher browser selection

วันที่ตรวจ: 2026-09-30

- Build source: `673bd82bd6a3678656e95eb17ca98850e64e0119`.
- Adds Default/Chrome/Edge/Firefox selection, Windows App Paths discovery, last-successful preference and fresh bootstrap rights on every Launcher open.
- Full build-time suite: **1,662 passed, 2 warnings in 532.93s**. Warnings were process-local development secrets and an unwritable pytest cache; no failed tests.
- Developer `.venv` suite also passed: **1,662 passed, 2 warnings in 580.74s**.
- Build: `scripts/build_local_installer.ps1 -Version 0.1.38`, exit 0; tests were not skipped. Build uses Python 3.12.9, FastAPI 0.128.7, Starlette 0.52.1 and Playwright 1.60.0, matching the previous Setup environment.
- Release privacy verification passed for the program tree and Setup artifacts.
- Packaged version and Setup ProductVersion are `0.1.38`; the update helper is included.
- Actual packaged executable passed health, Local bootstrap/session and every tool-page smoke with an isolated runtime. A second shortcut reused the server and remembered Chrome. Only the owned smoke process was stopped; the user runtime was not used.
- Real Chrome/Edge headless browser checks passed fresh bootstrap and five tool pages without invalidating the first browser's session. Firefox is not installed here; its executable-launch path was tested with an OS process test double only.
- Setup size: **279,092,115 bytes**.
- Setup SHA-256: `A74DA81C327062F1DF5CC905A34A7C1DA0D7102A48CE1ABCDC21AD3F0469F782`.
- Production `LocalUpdate` discovered stable `0.1.38` from simulated installed version `0.1.37`, with both exact asset names present. It downloaded the published checksum and Setup; downloaded size and on-disk SHA-256 matched the local build. State reached `ready`; the installer was not launched.
- Installer/docs repository main commit: `31de52d374ef5f214b80f25fc18abd1b5569d714`. Only public Markdown documentation was committed there; binaries are GitHub Release assets.
- Existing browser-local drafts/queues do not move between browsers. Aztek automation still uses bundled Chromium; no real Aztek creation was performed.
- This release was not installed over the user application. Clean-VM installation remains untested and Setup is unsigned. The user initiates the in-app update when ready.

Release: https://github.com/momozxmo/tool-cabal-local/releases/tag/v0.1.38
