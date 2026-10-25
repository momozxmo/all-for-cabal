# Bundle/Recheck-only delivery plan

User approved: separate WR while preserving work, verify actual delivery source, build/verify Setup, selective commit/push/publish and download/hash proof.

Base87d80e25eda871c12519fd5693568dda4650c6f2. Branch codex/bundle-recheck-v042 in managed worktree bundle-recheck-v042. Version0.1.42 is provisional until final remote recheck; latestv0.1.41 and tag0.1.42 absent at preflight.

## Constraints
- Original bundle-manual-release worktree including all WR changes remains untouched. Backup+patch manifest remains in its build-cache/wr-held-out-v042-20261025. Never apply the rejected WR rollback.
- Only port web/bundle_recheck.py, web/static/bundles.html, tests/test_bundle_recheck_reader.py and new tests/test_bundle_recheck_audit_ui.py. WR source/tests must remain Git-equal HEAD.
- No workbook inspection, real Aztek, NewItem12, user-app stop/install, dependency upgrades, force push, PR, additional issue closures, or cleanup of evidence/worktrees.
- Prior one fresh review covers unchanged Recheck code; Important was RED→GREEN/full verified. No repeated review. Old full2783 includes heldWR and is not release proof.
- Full/new build/package/public-download gates precede success claims and publication.

## Task 1: Preservation and separation
- [x] Native managed worktree created at exact base after safer-original rollback was rejected; original WR files unchanged.
- [x] Port approved four-file allowlist via apply_patch.
- [x] Three files byte-identical to reviewed fix; bundles.html identical after CRLF→LF normalization only. New raw-byte freeze required.
- [x] WR source/tests equal HEAD; source branch has only approved Recheck diff/newtest.

## Task 2: Exact final verification
- [x] New freeze includes all tracked source/tests/static and verifier/external runner. Confirm all tracked tests and new UI module frozen.
- [x] Actual collection and no existing pytest, unique durable full run with isolated command TEMP/TMP.
- [x] Verify wrapper/raw/signed0, finishedpassed, actual unique JUnit count with0fail/error/skip, evidence_errors[], freeze and original161/user hashes. Preserve warnings.

## Task 3: Setup
- [x] Recheck source/main, Local/main/latest/free0.1.42 and no active pytest/browser cache users.
- [x] Read build/privacy/installer docs; validate exact candidate-cache ancestors and no reparses before reset. Build Version0.1.42 SkipTests only exact passed bytes, command-scoped writable TEMP/TMP.
- [x] Verify privacy/tree/version/helper/embedded source including Recheck and unchanged WR baseline/allstatic/Setup SHA+sidecar.
- [x] Fresh isolated LOCALAPPDATA smoke after port8000/userapp checks; hidden process, finally stop only owned PID/path/starttime, confirm portfree. No Inno install.

## Task 4: Publish
- [ ] Selective source code/tests/docs commit(s), normal origin/main fast-forward after unchanged-remote recheck. No runtime/artifacts/heldWR staged.
- [ ] Local-docs worktree AGENTS/HANDOFF/status then notes/tag/stable GitHub Release using established local-release remote.
- [ ] Download actual published Setup/sidecar, enumerate spaces→dots filenames, hash+size equal actual build. Only then claim published; actual user update/reopen/drafts still unverified.

## Review focus
No heldWR leaks into code/build/commit. Recheck semantics must match reviewed source. Full proof belongs to release-only bytes. All data/privacy and owned-process boundaries hold. No force or duplicate finished runs.
