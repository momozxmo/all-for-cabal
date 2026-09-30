# Local release v0.1.37 — Bundle Recheck

วันที่ตรวจ: 2026-09-30

- Build source: `71fffadb5b3baae4a79a46cd8be96a16ae6da30e`.
- Includes Document Reference preservation, saved Bundle readback, Currency/EXP/Rarity/RANDOM comparisons, read-only retry, local history recovery and downstream confirmation.
- Full build-time suite: **1,641 passed, 2 warnings in 536.11s**. Warnings were development secrets and an unwritable pytest cache; no failed tests.
- Build: `scripts/build_local_installer.ps1 -Version 0.1.37`, exit 0; tests were not skipped.
- Release privacy verification passed for the program tree and Setup artifacts.
- Packaged version and Setup ProductVersion are `0.1.37`; update helper is included.
- Packaged `bundles.html` SHA-256 matches source: `1D1CD641601D05CDEC9D58C8BE78C97A6C629F65CE3FF3210F5D85085496E6FB`.
- Packaged executable smoke passed with an isolated runtime: `/api/health`, Local session login, Bundle Recheck UI and empty history API. The smoke process was stopped afterwards.
- Setup size: **279,104,501 bytes**.
- Setup SHA-256: `AA3FFFB2E364001BC4B64198EED756E5ACD041EC8276F7C744B61CE3AAADF30A`.
- The installed user application is updated only when the user initiates the in-app update. This release was not installed over the user application.
- No clean-VM installation or real Aztek creation was performed; Setup is unsigned.
- Missing document properties remain partial. Saved Currency cards that expose only a display name cannot establish an exact currency code and remain partial.

Release: https://github.com/momozxmo/tool-cabal-local/releases/tag/v0.1.37
