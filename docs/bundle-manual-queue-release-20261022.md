# Checked-all Bundle release candidate

User approved a separate checked-all button, then the established Setup/commit/push workflow when verified.
Candidate branch:codex/bundle-manual-release; base:bb12059f118e691279222c0766eaee16e25b4fa1.
The remote source main was19eb84e at preflight; latest stable installer wasv0.1.39. Intended next version0.1.40, recheck before publication.

## Exact scope

- web/app.py: StrictBool manual_checked defaultfalse, create-only opt-in to runner.
- web/bundle_runner.py: confirmed saved+knownID may continue nonpassed Recheck for this invocation; actual outcome/history/replay protection retained.
- web/static/bundles.html: one-shot checked-all button/confirmation, action and game lock during request, uncertain-write lock, no automatic handoff override.
- Preserve the three already-approved Bundle identity edits (submitted workspace/group snapshots and result fallback after queue removal/reload).
- tests/test_bundle_recheck_flow.py: port only manual-checked API/UI/safety tests onto clean committed fixture. No inherited Shop/consumer pipeline extension.
- tests/test_web_bundle_import_ui.py and new tests/test_bundle_manual_checked_validation.py: cancellation/reload scope/keyboard/responsive/uncertain guards/request validation.

No unrelated dirty Event/Product/Item Code migration, Product visibility guard, userCONTEXT/item_finder edit, runtime data, journal or capture copied into candidate.
The existing committed checkpoint foundation bb12059 remains the baseline; do not claim the excluded ongoing migrations ship in this release.

## Gates

Original feature snapshot:445passed2434.66s and incremental review0/0/0. Those do not prove this clean candidate.
Original Product full:2701passed2environment failures; unchanged devscript suite7passed after command-scoped writableTEMP/TMP. Original full is still failed.
Candidate scoped verification and one necessary final full pending. Use writable TEMP/TMP for each command, restored in finally.
No Setup/commit/push/publication until exact candidate passes. No live Aztek action. All UI/runner tests intercept external traffic.
Retain source freezes/status/logs/JUnit and check wrapper/raw/signed exits, actual counts, evidence_errors and freeze drift.

Release workflow: build Setup, release_verify + checksum, safe isolated installed health/version/data preservation checks, selective commit/source push, team release metadata/tag/assets, download/hash verify. Never overwrite unrelated user work or silently update the user's active installation.

## Fresh candidate review

Independent read-only reviewer found Critical0/Important0/Minor0 against the clean candidate diff, including the test port and three Bundle identity fixes. No code changes requested; reviewer did not execute tests.
Ruling: test success is established by runner/JUnit, not reviewer inspection. Cost if wrong: no release without that evidence.
Ruling: live Aztek, excluded migrations, Setup/install/reopen/publication/download checks remain separate gates or explicit exclusions; no such coverage claimed by this review. Cost if wrong: synthetic tests cannot prove external compatibility or installed state.
Ruling: previous full environment failures do not establish this candidate's pass/fail; it receives its own full using scoped writable TEMP/TMP.
Ruling: cross-tab/editor mutations during active requests remain inherited and outside this bounded change; server checkpoint/replay protection remains active. Cost if wrong: recovery may require history; no broader UI locking claim.
UI pixel review is not supplied by the reviewer. Candidate UI tests render the same production files at360/768/1280/1600 and save screenshots at360/1280; execution evidence remains pending until the scoped run finishes.

Source freeze prepared147 paths:build-cache/release-v040-freeze-20261022.json. Full collection2113 confirmed; do not confuse this intentionally isolated candidate with the2703-test ongoing-migration snapshot.

## Candidate execution

Scoped run19148 finishedexit0:51passed270.05s; JUnitaggregate+actual51/failures0/errors0/skips0.
Artifact:build-cache/rc-scoped-20261022.xml; SHA256AA15869ABF48E8A8C9F06D20E0D08A5D90690FA7B8B5FAB2DDA95A615CE08507.
Includes the seven unchanged developer-script cases using per-command writableTEMP/TMP.

Necessary final full started2026-10-22T12:23:27.955709Z (19:23:27Bangkok), session94249,
runner31560/pytest35504, collection2113 confirmed. Run-dirbuild-cache/release-v040-full1-20261022,
freeze147build-cache/release-v040-freeze-20261022.json verified0drift at launch.
Command uses the existing durable runner from original checkout/scripts/run_pytest_logged.py with candidate cwd;
the runner itself is included in the freeze. TEMP/TMP scoped to candidate/build-cache/rc-full-system-temp-20261022 and restored by wrapperfinally.
Do not edit frozen files, start another full, stop this one, overwrite logs or infer pass from running status.

User confirmed quota reset and the authorized elevated read-only probe succeeded before candidate creation;
approval quota waiting is no longer the active blocker. No build/commit/push/publication yet.

Release verification ruling: latest v0.1.39 workflow explicitly did not install over or close the user's app.
Preserve that boundary for0.1.40: verify packaged executable against isolated runtime data and Setup metadata/hash;
do not silently apply an Inno installer sharing the same AppId to the user's active installation.
If actual installation/reopen cannot be isolated without changing the user's installation/registry, report it as unverified
rather than claim installed success or broaden permission. User-applied update/reopen/draft preservation remains a separate check.

## In-progress failure observation (2026-10-22T13:07Z)

Full session94249 remains running. Stdout reports four failures at41% in
tests/test_web_finder_id_first.py::test_api_search_persists_correct_item_for_each_verified_game
for CabalM TH, CabalM SEA, CabalPC TH and CabalPC SEA. Latest progress observed45%;
JUnit/final tracebacks are not yet available. Freeze147 still matches with0drift.
This is not a final count or a root-cause diagnosis. Do not stop the run or edit frozen files.
Wait for completion and inspect actual failure details before classifying environment/fixture/product
and deciding whether an in-scope fix is authorized. Release gates remain unmet; no Setup/commit/push.
User notified of this new material failure observation once; unchanged pending state stays quiet.

## Final full result and scoped diagnosis (2026-10-22)

Session94249 finished with wrapper exit1, statusfinished/verificationfailed, raw+signed pytest exit1.
Ended2026-10-22T13:16:58.729653Z. Summary:2109passed4failed1warning in3207.02s.
JUnit aggregate and independently counted actual:2113tests/4failures/0errors/0skips.
evidence_errors=[]; freeze147 matched before/after and independent post-run check0drift.
JUnit SHA256:B6BE8B32E92A3EFA7ADD63196A0E47F20759EAD5432036672F69F3BFEA7191BB.
Status SHA256:97D7B44EBBC62BD14971C226F920BC57EAA8765DF4247481D0238E9915ACC9CC.
All four failures are the previously observed Finder parameter cases at test_web_finder_id_first.py:245:
document_reference is None although the selected Item's other fields are correct.

Tight repro, unchanged source: pytest
"tests/test_web_finder_id_first.py::test_api_search_persists_correct_item_for_each_verified_game[CabalM TH]"
-q -p no:cacheprovider --basetemp=build-cache/finder-diagnosis-red1-temp-20261022
--junitxml=build-cache/finder-diagnosis-red1-20261022.xml --tb=short:
1failed7.44s with the same TypeError. The PowerShell shell returned0 because finally restored env;
the pytest verdict is established by output/JUnit, not that shell exit.

Ranked predictions shown before the probe: dropped criteria metadata during result conversion;
loss at API/persistence boundary; incomplete fixture input. Source tracing finds imported references
in item_service, but committed item_finder.App._search_all copies a fixed criteria key list that omits
document_reference. HeadlessFinder binds this shared engine method; search_runner's result mapper
then reads item.get('document_reference') and emits None. Candidate Bundle API diff does not alter
this path. HEAD has the identical omission, so it is a baseline Finder defect, not a Bundle-button regression
or a TEMP/browser environment failure.

Single-variable diagnostic probe: only in the disposable Python process, recompile that engine method
with document_reference added to its copied keys and bind it to HeadlessFinder. No source/test files
or original user files edited. Same real API/runner + synthetic browser test:1passed7.57s, session54230exit0;
build-cache/finder-diagnosis-probe-20261022.xml independently1/0/0/0.
This proves the missing propagation at the engine boundary; it is not a release candidate fix or full pass.

The required one-line change already exists in the original checkout's explicitly excluded user-owned
item_finder.py diff. Incorporating it would expand the approved isolated six-file Bundle release scope.
Stop before copying/staging it; request permission to include only this reference-propagation line,
then targeted Finder verification, fresh review as needed and a new exact-source full before release.
No source fix, new full, Setup, commit, push or live Aztek action performed during this diagnosis.
Automatic monitor is removed because progress now requires a new scope decision, not more polling.

## Approved Finder prerequisite follow-through

User replied "ทำต่อเลย" after the scope question, authorizing the single-line prerequisite.
Only candidate item_finder.py now includes document_reference in the criteria metadata copy list.
Original user checkout files remain untouched. Existing four public API tests remain unchanged.
The failed full and diagnostic artifacts above are preserved and do not become passing evidence.
Fresh freeze:build-cache/release-v040-freeze2-20261022.json,147paths; compared to the first freeze,
only item_finder.py differs. Target Finder regression is running session51398,26collected,
run-dirbuild-cache/release-v040-finder-target1-20261022. An initial invocation rejected a missing
new manifest before creating a run-dir or launching pytest; the actual target started only after the freeze existed.
Independent read-only incremental review requested for this one-line prerequisite.
After targeted/review gates, one necessary exact-source final full is required before packaging.

Incremental independent reviewer:Critical0/Important0/Minor0 for the authorized one-line prerequisite.
Read-only HEAD-blob/current-file comparison confirmed no other item_finder.py changes.
Ruling on declined items: test outcomes require runner/JUnit evidence, not static review;
live Aztek remains unauthorized; packaging/reopen/data-preservation/release readiness remain later gates;
previously reviewed Bundle scope need not be re-reviewed unchanged; original user-worktree changes
are not staged or modified. No excluded behavior is being claimed covered by this incremental review.
Original CONTEXT.md and item_finder.py hashes rechecked unchanged from recorded user-owned hashes.
Remote read-only recheck:origin/main19eb84e11f8c37e03249ffdfc93ea9e920fca48b,
local-release/main92e8ee8f39b5ae2603be8c357754a371ec3c5a64,lateststablev0.1.39;
v0.1.40 tag absent at this preflight. Recheck again before publishing.

Finder target session51398 finishedexit0:26passed201.07s; statusfinished/verificationpassed,
raw+signedpytestexit0/JUnitaggregate+actual26/0/0/0/evidence_errors[]/freeze147matchedbefore-after.
JUnit SHA256:85AF2FD2809293E6DA0A2DE0E828A35590D64F4FA56968C7BC61C2C8B843BD29.
All four formerly failing game cases pass on actual candidate source, not an in-memory probe.
Do not add this26 to the final full total or convert the first failed full to pass.

Necessary final full2 started2026-10-22T13:25:42.617660+00:00; session77349,
runnerPID16520/pytestPID28200; collection2113 confirmed.
Run-dirbuild-cache/release-v040-full2-20261022,freeze147build-cache/release-v040-freeze2-20261022.json.
Command-scopedTEMP/TMP=candidate/build-cache/rc-full2-system-temp-20261022,restoredfinally.
Same durable logged runner absolute path as full1; no concurrent full and no source changes until completion.
No Setup/commit/push/publication yet. Resume the single automatic follow-through monitor for this active run;
stay quiet on normal progress and notify only material changes, final results, or required action.
Active follow-through monitor:bundle-setup-follow-through,every10minutes,samechat.
Previous product-option-final-full monitor remains deleted; no duplicate monitor was created.

## Final full2 verified / packaging started

Session77349 finishedexit0,statusfinished/verificationpassed,raw+signedpytestexit0.
2113passed1warning in3168.61s; ended2026-10-22T14:18:34.775484Z.
JUnitaggregate+independentactual2113/0failures/0errors/0skips,evidence_errors[],
freeze147matchedbefore-after and independentprebuildcheck0drift.
JUnit SHA256:19EA54DCE0F61E444385B0FAE21A1A7E8EFC67135A0B893B681F57E47E8237B9.
Status SHA256:FB1B557AB817F44279E2B5FB36EC6341039E6DA1600A61FDD6E2DA4EDB321220.
One warning remains process-local development secrets in test_local_runtime.py; no warning-free claim.
User notified of full pass once. No further full is required for documentation-only edits.

Prebuild remote refs unchanged and v0.1.40 tag absent/lateststablev0.1.39.
Build started session17576 using scripts/build_local_installer.ps1 -Version0.1.40 -SkipTests,
exactsourcefull2pass, command-scopedbuildTEMP/TMP restoredfinally. Transcriptbuild-cache/build-v040-20261022.log.
Candidate browser-cache absolute target validated within candidate, no reparse point, no active tests.
Build reuses already-satisfied dependencies and downloads its own Chromium. No user installation invoked.
Do not rerun build while this session is running or overwrite its eventual artifacts.
Packaging/smoke/sourcecommit/push/publication/downloadhash gates remain pending.

Build session17576 finishedexit0; Inno successfulcompile250.969s. Setup279146982bytes,
SHA25631ABC0280BC9D055142884369C6A4E243E6DBCBC89807B10C44FE82BB6DD28FF,sidecarmatched.
Independent release_verify(package/artifacts)exit0,runtime0.1.40,SetupProductVersion0.1.40,
updatehelperpresent,4staticSHA matched source,signatureNotSigned. No installer invoked.
Isolated packaged smoke script build-cache/release-smoke-v040.ps1 completedexit0:
health0.1.40,Localsession/bootstrap,alltoolpages,checked-allUI,zero-rateparser,emptyhistory.
Only ownedPID/path/starttime was stopped and port8000 released; no real Aztek request/create.
Actual user install/reopen/drafts remain unverified. Source commit/push/publication/downloadhash next.
