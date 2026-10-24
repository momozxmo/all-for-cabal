# ID-first combined Windows release implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to execute this approved delivery sequence inline. Track checkbox steps and rulings in the associated ledger.

**Goal:** Deliver the verified ID-first snapshot, including the Item Code result-ID fix, together with the already shipped checked-all Bundle button through the established Windows Setup/release workflow.

**Architecture:** Reuse the clean isolated `codex/bundle-manual-release` worktree at `ce7eded`, not the dirty source checkout. Port only audited source/tests, preserving the six-file checked-all delta and prior Bundle/Finder identity fixes. Verify the combined source independently before packaging or publication.

**Tech Stack:** Existing Python/pytest/Playwright/FastAPI, PyInstaller, Inno Setup, PowerShell and GitHub Release workflow; no dependency upgrades.

**Spec:** Existing `docs/aztek-id-selector-spec.md`, `docs/agents/aztek-locators.md`, checked-all `docs/bundle-manual-queue-release-20261022.md`, plus the user-approved three-step delivery sequence in this chat24October2026. The original worktree's `docs/tickets/aztek-id-first/itemcode-result-identity-20261024.md` records the latest verified increment.

## Global constraints

- No real Aztek login/probe/create/edit/upload/delete, replay/reset of journal/gates/results, remote issue closure or NewItem12.
- Never copy/stage user `CONTEXT.md`, runtime databases, `.env`, profiles/cookies/keys, uploaded workbooks or build binaries. Original `item_finder.py` already matches the approved committed Finder prerequisite after newline normalization; do not copy it wholesale.
- Preserve every original worktree and retained status/log/JUnit/freeze. No reset/clean/forcepush or cleanup deletion.
- Prefer stable HTML IDs and documented evidence-backed no-ID exceptions; no invented ID/schema/URL fallback or weakened safety gate.
- Scope TEMP/TMP to each command's writable build-cache and restore finally. No machine settings or dependency changes during frozen tests.
- Conditional Setup/commit/push/release authority applies only after exact combined-source gates pass; actual user installation/reopen/data preservation must not be claimed before observed.
- Latest stable was verified asv0.1.40 andv0.1.41tag absent on preflight; recheck current refs/version before mutation/publication.

## Review focus

- Checked-all continuation must not override actual Recheck outcomes or authorize consumer handoff; run both manual safety and consumer pipeline tests.
- Queue removal/reload must preserve submitted workspace/group/document identity; merge overlapping tests, never replace one branch with the other.
- Own Item Code IDs must not borrow nested Bundle/Reward IDs; preserve saved-unknown warnings and no duplicate submit.
- LF/CRLF-only differences must not pull117unchanged files into the release. Preserve committed checked-all API/runner/UI and validation tests.
- Packaged runtime must contain the exact tested source/static/helper and no private runtime data; smoke uses isolated userdata and must not stop/overwrite the user's app.

### Task 1: Exact integration and provenance

Files copied from the verified original snapshot only when content differs after LF normalization:
`web/activity_runner.py`, `web/aztek_form.py`, `web/create_flow.py`, `web/event_runner.py`,
`web/itemcode_runner.py`, `web/product_runner.py`, `tests/test_web_activity.py`,
`tests/test_web_finder_id_first.py`, `tests/test_web_itemcode_id_first.py`, `tests/test_web_product_runner.py`.
Add `tests/consumer_create_pipeline_support.py`, four `test_web_event_*id_first/preservation` files,
eight Product ID-first test files and `tests/test_web_itemcode_result_identity.py`.
Merge only `tests/test_bundle_recheck_flow.py` with the committed checked-all cases using the commonbb12059base.
Keep `web/app.py`, `web/bundle_runner.py`, `web/static/bundles.html`, `tests/test_web_bundle_import_ui.py` and `tests/test_bundle_manual_checked_validation.py` from the shipped candidate unless a concrete combined test proves a required scoped change.

- [ ] Confirm elevated read-only candidate clean/HEAD/remotes and exact147-entry prior freeze. Completed evidence may establish baseline; do not rerun an unchanged full as a setup ritual.
- [ ] Compare normalized source against the161-entry verified original manifest; reject unexplained drift, exclude user files.
- [ ] Port the exact allowlist with apply_patch; resolve the test-only overlap without dropping either behavior. Record hashes/provenance and inspect the actual candidate diff.
- [ ] Syntax/collection and focused checked-all/consumer/Item Code identity tests. Existing tests already establish RED→GREEN independently; add RED first only for a newly exposed product defect, not a fabricated failure for a mechanical port.

### Task 2: Verify exact combined source

- [ ] Read-only fresh-context whole-delta review with explicit scope and baseline; no reviewer writes or duplicate reviewers.
- [ ] Freeze every candidate code/test/static/build dependency plus the absolute durable logged runner; use new manifest/run-dir, never overwrite retained freezes.
- [ ] Run scoped regression with writable per-command TEMP/TMP. Require wrapper/raw/signedexit0, finished/passed, JUnit aggregate=actual collection, failures/errors/skips0, evidence_errors[], freeze match.
- [ ] After scoped gates and no matching runner/pytest, run one necessary final full on the combined source. Verify actual count rather than adding2715and checked-all counts. No overlapping full or source edits while frozen. Native interruption without actual testcase failure requires user direction before restart.

### Task 3: Build, verify and deliver

- [ ] Recheck remote refs/latest version/tag; do not force if changed. Select next free version (currently0.1.41).
- [ ] Read current build/release verifier/install docs; validate absolute candidate cache target/reparse points and no test using it before build. `scripts/build_local_installer.ps1 -Version <verified-free-version> -SkipTests` only for exact source with completed full.
- [ ] Verify tree/artifact/privacy/checksum/runtime version, source/static/helper digests; retain all evidence.
- [ ] Packaged executable smoke with fresh isolated userdata, free port8000, Hidden background launch and exact owned PID/path/starttime cleanup. No real Aztek. Do not silently install the same Inno AppId over the user's active installation. User-applied install/reopen/draft preservation remains explicit until actually verified.
- [ ] Selective code/test/verification-doc commit, normal fast-forward source push; established Local release docs/tag/stable GitHub Release workflow, no PR/issue closure.
- [ ] Download published Setup and sidecar, compare digest/size against actual local build; only then claim publication complete. Record any unverified installed-state boundary clearly.

## Execution record

User already chose to proceed with the stated delivery sequence; no additional feature or platform decision is introduced by this plan. Agent executes inline and records any material deviation in `.superpowers/sdd/2026-10-24-id-first-combined-release/progress.md`.
