# New Item Creation / Recheck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement issue #12: selected new Items from Excel or Finder misses, explicit confirmation, durable non-replay creation, fresh Item readback and passed-only selection-controlled handoff.

**Architecture:** Add a focused New Item feature beside the existing tools. Reuse SQLAlchemy Job records for pending imports, per-Item drafts/checkpoints/history, existing user/workspace ownership, BrowserOperationGate, Aztek session service, verified locator/confirmation helpers and Sheet picker. Keep original occurrences/reference immutable and distinguish creation state from recheck outcome; no new queue framework or database engine.

**Tech Stack:** Existing Python/FastAPI/Pydantic/SQLAlchemy, openpyxl, vanilla HTML/JS and Playwright. No dependency upgrades except explicit26October approval for Pillow13.0 in this task's isolated worktree environment only; do not upgrade base Python/environment.

**Spec:** [Approved issue #12 snapshot](../specs/2026-10-25-new-item-issue12-approved-spec.md), canonical https://github.com/momozxmo/all-for-cabal/issues/12. Q1–Q24/test seams are already confirmed; do not repeat the requirements interview.

## Global Constraints

DELIVERED28October2026: userseparatelyauthorizedSetup/commit/push/publish/close#12aftergates. v0.1.43stable/latestpublished18:19:35Bangkok/publicSetup+sidecardownload18:21hash+sizematchbuild/API/notesmatch/updaterdiscoveryavailable043verified. Source394af564/docs323e394normalpush/publicdocs-tag32661245atomicpush; issue#12CLOSED/COMPLETED18:22:45readbackconfirmed. [Deliveryevidence](../../local-release-v0.1.43.md). NoextraAztek/userappinstall/stop/WR/workbook/reset/evidencecleanup. Earlierno-releaseauthorityconstraintsbelowarehistoricalbeforethisexplicitgrant; local/fullproof unchanged, no rerunfordocs.

FINAL LOCAL COMPLETION28October17:47:41.844849Bangkok: Tasks1–5 implemented and original22acceptancecriteria verified within documentedlocal/synthetic-boundaryscope. FULL6 session48422/nf6 FINISHED3108passed1warning10333.65s/native+raw+signed+wrapper0/JUnitactualaggregateunique3108/0/0/0/independentfreeze185+originalhashmatch/evidence_errors[]. Aggregate new-item-full6-20261028-verification.json/JUnitSHA2013DC01581C18FB6034C66C52ECFC8933CF6A2843AE0C0D74A23F7AA4032C7B. Retention allnf5old3108/nf4old3053with5aliases/scoped59with2aliases+52+13+22missing0. Acceptance-final verification maps22criteria to179distinctpassingcases fromsameJUnit, NOTadditionaltests. [Readable delivery status](../../tickets/new-item/acceptance-final-20261028.md). Existingdevelopmentsecretwarningretained, no source/test/dependency editsafterfullpass/docs-onlyalignment. No morefull/scoped/reviewloopsforevidencealreadycomplete. NoSetup/install/commit/push/publish/issueclosure; preserveallworktrees/evidence/uncommittedchanges underexistinguserconstraint.

The original task checkboxes and dated execution notes below preserve planning/intermediate state, not new pending implementation work. Hypothetical testmodule/functionnames inoriginalplan were implemented throughactualAPI/browserseams andcurrent179-case trace instead; no claimthatnonexistenttestcommandsran. Remainingboundaries: noall-livevariants/Premiumlivecreate/imagepixelacceptance, prooflessUnconfirmedstaysunresolved, singlelocalprocessnotmultiworker. Those areexplicitqualification/no-guessrules, notpermissiontoexpandlivework. Integration/release requiresseparatehumanchoice; retainnamedbranch/worktreeas-is.

### Historical execution checkpoints — superseded by final local completion above

CURRENT FULL6 session48422/nf6 running since28October14:55:19.920416Bangkok/07:55:19.920416Z afterUI22GREEN176.66s/nativewrapper0/JUnit22/0/0/0/independentfreeze185/originalhashmatch. Actualcollection3108/allnf5names3108retained; freezeF6FBFC96C3123974C6B67B1DF7E371DB1D81FD8D915E17EDAD5BDECE85DCB124 matchesGREEN22. OnlytwoUItestfileschangedfromnf5; production/dependenciesunchanged. Runner33388/pytest4540/exactstart+commandsverifiedread-onlyelevated; noexistingpytest/uniquepathscheckedbeforelaunch. No frozenedits/overlap/stop/restart/reviewer/live/Setup/commit/push/issueaction. Verifyafterfinish via cohortverifier -RunLeaf nf6 -EvidenceName new-item-full6-20261028 -ExpectedCount3108 -RetainJUnit build-cache/nf5/junit.xml; preserve actualwarnings. FULL5isfailedhistory, notcurrentrunningorpassed.

SUPERSEDING28October13:14: FULL5 FINISHED3104passed4failed1warning9761.23s/nativewrapper1/JUnit3108/4/0/0/freeze185+originalhashmatch/evidence_errors[]. All4actualtraces show old exactcreatebuttonlabel missing, actualnewlabelbuttondisabled; no productionregression established. Failureaggregate saved beforeediting. CorrectedONLYtwoUItestfiles/currentaccessiblelabel+retaineddisabled/no-createguard/unique screenshots; product/dependenciesunchanged. Focused22 UIcases session42826/nulg1 running; mustgreenbeforenecessaryfull6, no overlaps/review/live/release. FULL5staysfailed; oldrunningentrybelowishistorical.

CURRENT FULL5 launched once28October10:31:16.617794Bangkok/03:31:16.617794Z: session60817/runbuild-cache/nf5/actualcollection3108. RunnerPID23412 created10:31:16.446202/pytestPID12608 created10:31:16.620648, exactabsolutecommandscheckedread-onlyelevated. Freeze185SHA5B81466501A2FAA337963E747769086CB3557ED97792AEF2AD4E435AD627C74E matchesfinalPremiumGREEN13source. Noexistingpytest/allnewpathsabsentbeforelaunch; sameapprovedisolatedvenv/externalrunner/scopedTEMP/TMP restoredfinally. No source/test/dependency edits/overlap/rerun/stop. Finalwrapper/status/native/JUnit/freeze/originalhash/retentionverificationpending via build-cache/verify-new-item-full5-20261028.ps1; notwhole#12passed/releaseauthority.

Current28October: GENERAL four-game extension RED→GREEN59; retained-response Resolve API/UI RED→GREEN52 (22 API/3 UI/27 cohort); observed PC Premium type-only forms plus existing source builder → strict Premium support RED6→GREEN13. Each final scope has wrapper/native0, actual/aggregate/uniqueJUnit with nofailure/error/skip, independentfreeze and protectedoriginal hashes matching. Premium supports PC only, never silently converts toGENERAL. No live Premium create/receipt/image or allvariant claim. Resolve covers server-owned retained causal proof only; entirely lost proof staysUnconfirmed/no replay. Supersedes earlier GENERAL-only/Premiumblocked and Resolve/UIpending snapshots below. Actual full-suite collection3108 verified exit0; final full5 still pending, no full-pass/Setup/commit/push/issueclosure claim. Preserve evidence and one existing final review; no re-review loop.

Current27October21:41Bangkok: Task4 historicalcomparisonUI/M2 completed forSUPPORTEDLOCALscope after RED6+legacy1→GREEN7→regression534→FULL4. Session63031/nf4 FINISHED21:40:57.570719Bangkok/3053passed1warning9533.46s/native+wrapper0/JUnitactualaggregateunique3053/0/0/0/independentfreeze183+originalhashmatch/evidence_errors[]. Freeze7854CC0015A138FA596B43ED17882C794893DBFA516B0DEAE48B136D75A94458; JUnitFB268F8FEC66F2C3852844A3A1F889DBA3356C69AAF8C2DA902774273155B8DD. Aggregates new-item-full4-20261027-verification.json and new-item-full4-retention-20261027.json verify allold3046/scoped534/history7/cohort27retained. OnlyJSrendering+existingUItestfilechangedfromfull3; original attempts remain immutable, missing legacy metadata stays missing, oldpasscannotunlocklatestmismatch. Existingprocess-localdevelopmentsecretswarningretained. WholeTasks3–5/#12 remain partial forother3writes/positive lost-ID Resolve. No newreviewer/live/build/commit/push/issue/OS/dependencyaction; no rerunfordocs.

Baseline27October18:31Bangkok (before historicalcomparisonUI): Full3 FINISHED3046passed1warning9193.41s/native+wrapper0/JUnitactualaggregateunique3046/0/0/0, independentfreeze183/originaluserhashmatch, full2old3019/scoped527/cohort27namesretained/evidence_errors[]. Aggregate build-cache/new-item-full3-20261027-verification.json plus retention JSON. Explicit final-payload regroup supported locally after RED3→GREEN3/expanded27/historyRED2→GREEN2/scoped527/finalfull; no frozen reference/history rewrite or unselected draft inclusion. Full2/Full1/environmentfail/interruption evidence retained honestly, not rerun for documentation. Atthisbaseline M2wasdeferred; supersededbyusercontinuationandfull4above. Other3writes/positive lost-ID Resolve remainunsupported. One prior reviewer only, no re-review/live/build/commit/push/closure or dependency/OS change.

- Support exactly CabalPC TH, CabalPC SEA, CabalM TH, CabalM SEA using existing game mappings; exclude HOF.
- PC: GENERAL/CABALPC_PREMIUM. M: GENERAL only; reject unsupported type rather than silently convert.
- Template columns: Name, ItemKind, Option, Duration, Item Type, Tradeable, Description. Choose game at import.
- Missing Option/Duration are missing, never inferred zero. Explicit numeric0/false are real values.
- Missing type/tradeable default GENERAL/bound, with per-field provenance and explicit confirmation. Ambiguous Itemmove/Yes-No columns never imply Tradeable.
- Optional description/image; display-on-web off. No automatic Excel image extraction, image reuse from other tools or pixel-equivalence claim.
- Preserve filename/Sheet/row, every occurrence, group/workspace identity, Amt and original blanks. Amt never determines create count.
- Creating successfully is not recheck-passed. Known difference wins over incomplete; both remain visible. No acknowledge-to-pass bypass.
- Persist a submitting checkpoint before the possible first write. Lost response/ID or interruption after that checkpoint stays Unconfirmed Item Creation; no automatic retry/reset/replay.
- Authority update25October: user personally completed login and explicitly authorized read-only inspection of four-game create forms/existing Items. No fill/upload/create/edit/delete; no session extraction. Tests still use synthetic browser traffic only; unexpected external requests must fail.
- Read docs/agents/aztek-locators.md before automation edits. Known stable ID missing/duplicate/wrong-type stops; no broad guessed fallback or framework-generated IDs.
- Current v0.1.42 source/release/evidence remain intact; WR stays parked, original dirty worktree/workbook remain read-only.
- This approval resumes #12 locally. No Setup/release/push/remote issue mutations, issue closure or user-app installation/stop without separate authority. Plans remain uncommitted pending review.
- Preserve existing auth, owner checks, size limits, update/concurrency gates and explicit user consent. Use fresh isolated test DB/TEMP, never installed runtime.
- Authority26October: user explicitly permits Pillow13.0 dependency and installation only in a separate worktree environment for private local image validation. Base Python/packages stay unchanged; no Setup or Aztek upload.
- Execution starts only after plan review. Reuse a suitable isolated managed worktree at exact verified source commit, following using-git-worktrees; never reset this published candidate or old evidence.

## Evidence and implementation boundary

Retained evidence inspected read-only: original docs/new-item-dom-observations.md (2026-10-01, four empty create forms) and current Finder/Recheck readers/tests. Copy only the public sanitized observations into this feature's evidence document at Task2; do not copy sessions, user data or dirty CONTEXT/item_finder.

Verified create IDs: item-name, item-game-item-id, item-detail, item-option, duration-index, game-tradeable, display-option-enable.
PC type and upload control have no stable ID in the retained observations; M GENERAL is fixed text. Scope/type/uniqueness must be pinned by evidence, not guessed.
Existing saved Item reader proves only a subset. The observations do NOT prove create POST method/host/path/body/result-ID schema, Item confirmation, saved type/name/tradeable/description/image coverage across four games.

Evidence update26October after user-supplied frontend source: [frontend-contract-20261026.md](../../tickets/new-item/frontend-contract-20261026.md) establishes client POST host/path, FormData builder, standard game casing and confirmation source flow. It does not establish raw successful POST body/status/ID or positive resolve proof; dynamic fieldConfig/active dialog DOM are still scoped. Frontend auth refresh can resend a POST, so strict at-most-one request guard/checkpoint tests remain necessary. The old observation statement above is historical, not a claim that no source has now been read. No write adapter enabled until remaining evidence gate is met.

**Gate:** Tasks2/3 must inventory retained evidence per game/page/state before shipping their adapter. Missing evidence blocks only the affected automation capability: report unsupported and preserve drafts, never invent endpoint/ID/schema, fake a runner result or weaken passed criteria. Local import/reference/history/UI can proceed. If required evidence cannot be obtained without new live authority, stop that slice and request direction; do not claim all #12 implemented.

Later26October evidence supersedes the missing-MTH-response statement above: user supplied raw success/data.data.id224846/gameUUID6eaad7c6-bfc8-48ce-a616-061a2cef8f41 matching the one authorized manual test's saved fields/time. Active MTHconfirmation observed. One-create authority fully consumed; no replay/extra write. Task3 now proceeds only with an MTH contract-bound API/checkpoint slice offline; other games reject writes before browser and create UI remains disabled. Resolve proof/other-game UUIDs and unknown states remain unproved. Task3 brief/ledger record API/CAS interface adaptation; not completion of the whole task.

## Review Focus

Evidenceupdate27October: user-suppliedGETbodiesforPC TH224861/PC SEA224795/M SEA224791nowcompletebackendgameUUIDidentityforallfourwithretainedMTHPOSTreceipt224846. See docs/tickets/new-item/backend-game-identity-20261027.md. This supersedesoldermissing-UUIDnotesonly; doesnotproveother3createPOST/activeconfirmationorcausalResolve. No repeatGET/oldMTHreceiptrequests; no livewritepermissioninferred. No production/testchangeorfullrerunfromthisdocumentationupdate.

1. Explicit0/false versus blank/unreadable, including parser and browser serialization: Task1/2 tests.
2. Concurrent clicks, draft edits after confirmation and process death after submit starts: Task3/4 tests; at most one submit.
3. Same search triple but different name/type/tradeable/description/image, plus repeated occurrences across Bundles: Task1/3/4 tests.
4. Cross-owner, stale history/game/ID and schema ambiguity never enabling create/handoff: Task2/3/4 tests.
5. Four-game unavailable controls, keyboard/mobile long rows and image-presence-only claims: Task2/5 tests.

## File map and stable contracts

Create:
- web/new_item_import.py — new template + legacy-plan parser adapter, missing/provenance preservation.
- web/new_item_domain.py — typed draft/reference/occurrence/comparison DTOs and strict create-identity grouping.
- web/new_item_store.py — owned Job-backed repository, revisions, atomic submission claim, append-only attempts.
- web/new_item_routes.py — feature routes; register_new_item_routes(router, *, require_user, get_db), invoked once at module setup after existing dependencies are defined, not once per create_app.
- web/new_item_reader.py — evidence-backed fresh saved-Item readback, no mutation.
- web/new_item_runner.py — four-game adapters, search/create/checkpoint orchestration.
- web/static/new_items.html, web/static/new_items.js — focused UI, existing console/Sheet-picker/workspace patterns.
- docs/tickets/new-item/coverage.md — evidence matrix, exceptions/unknowns, acceptance results.

Modify only required seams: web/app.py (route registration/static page), web/item_service.py (selection-only Finder integration if needed), web/static/index.html + existing console navigation; do not restructure old tools or change Bundle reference semantics.

Domain DTOs (TypedDict; JSON-safe, no live session material):
- Occurrence: occurrence_id, workspace_id(optional), group_key, filename, sheet, row, amount, position, original.
- Draft: draft_id, revision, game, values{name,kind,option,duration,item_type,tradeable,description,image_key}, confirmed_fields, occurrences.
- FrozenItem: draft_id, revision, game, submitted_values, references (one per occurrence), occurrences, payload_hash.
- ActualItem: game, item_id, values, readable_fields, image_present(optional), evidence.
- Recheck: outcome(passed/mismatch/failed), incomplete, differences, per_occurrence, reference, submitted_values, actual, image_status.
- Creation: state(draft/confirmed/submitting/saved/unconfirmed/skipped), item_id(optional), evidence. Creation state is not Recheck.outcome.

Repository stores Job.tool new_item_import for preview, new_item for draft/creation; Job.config has schema_version1, queue_id, draft/frozen values; Job.result has creation/recheck; Job.log contains immutable attempts. Existing Job fields suffice: no new DB engine/table/reset required. Do not persist cookies/tokens/upload paths in history. Store referenced optional uploads separately under owner-scoped private storage, not history JSON or Git. Builder choice: accept only PNG/JPEG/WebP up to5MB locally, check real content type/size, owner and immutable content SHA; this follows retained UI guidance, not a claim about Aztek server validation. Record image digest as strict grouping identity.

Public routes under /api/new-items:
GET /template; POST /import (preview only); POST /import/apply (pending_id, selected_sheets, game); POST /from-finder (workspace_id, selected_missing_indexes, game, snapshot_token from current workspace GET); GET /drafts; PATCH /drafts/{id}; POST /confirm (selected{id,revision}, game); POST /search (confirmed IDs, read-only); POST /run (confirmed IDs/revisions, explicit per-row create_new plus current owned search_id); POST /{id}/use-existing separately; POST /{id}/recheck; POST /{id}/acknowledge (skip/continue); GET /history; POST /handoff (selected passed IDs + occurrence IDs).
Add POST /drafts/{id}/image (owner/revision-bound optional upload, immutable digest/key) and POST /{id}/resolve (candidate Item ID plus retained submission proof; fresh readback, no create). Recovery may select candidates only when evidence binds the exact game/record; name or triple alone is insufficient. Ambiguity preserves unconfirmed.
All requests validate owner/game/revision/selection server-side; no client-supplied passed flag or arbitrary actual/reference override. Import requests use multipart file/mode(template or legacy plan mode)/game; apply returns drafts. Errors: foreign or missing owned record404, stale revision/conflicting claim409, invalid input400/422 consistent with existing API.

### Task 1: Import, editable drafts and immutable references

**Files:** Create domain/import/store/routes modules; modify app registration; tests/test_new_item_import_api.py, tests/test_new_item_reference_api.py.

**Interfaces:** read_new_item_workbook(path: str, mode: str) -> dict; new_item_template_bytes() -> bytes; freeze_draft(draft: Draft) -> FrozenItem; NewItemRepository(session) provides owned preview/draft CRUD and revision checks. Later tasks consume FrozenItem, never mutable current draft.

- [x] Write public API tests for sheet preview/search/selection, new-template roundtrip, legacy-plan rows, Finder misses only, ownership and unchanged workbook bytes. Assert no browser job/submits.
- [x] Pin reference values: original duration absent + confirmed9 -> reference9/provenance manual while original stays blank; original9 + edited0 -> reference9/submitted0. Explicit Option/Duration0 and tradeablefalse survive; missing remains not-ready.
- [x] Pin group identity: all submitted fields/game/image identity equal -> one create group, all occurrences/Amt/positions retained. Any create field differs -> separate groups. Display Name not Sheet label; no suffix trimming.
- [x] Name behavioral tests test_missing_duration_is_not_zero, test_manual_fill_preserves_blank_original, test_edit_does_not_rewrite_reference, test_grouping_preserves_each_occurrence. Their core assertions after real import/edit/confirm API calls are:

```python
assert blank["ready"] is False
assert explicit_zero["values"]["duration"] == "0"
assert filled["original"]["duration"] is None
assert filled["reference"]["duration"] == "9"
assert edited["reference"]["duration"] == "9"
assert edited["submitted_values"]["duration"] == "0"
assert [row["amount"] for row in grouped["occurrences"]] == ["2", "3"]
```
- [x] Run RED: python -B -m pytest tests/test_new_item_import_api.py tests/test_new_item_reference_api.py -q (fresh test temp). Confirm assertion/product failure, not setup error.
- [x] Implement minimal authenticated routes and Job-backed storage; use existing per-sheet parsers for legacy input, explicit template parser for new columns. Confirm defaults, unsupported M Premium and ambiguous Itemmove.
- [x] Run GREEN plus existing import/Finder handoff regressions. Record actual commands/counts/nativeexit and hashes; do not rerun completed release suites as a baseline.

### Task 2: Evidence-backed readback and New Item Recheck

**Files:** Create reader module/coverage report; domain comparison; tests/test_new_item_recheck_api.py, tests/test_new_item_reader.py with provenance-tagged fixtures.

**Interfaces:** async read_saved_new_item(page, *, game: str, item_id: str, detail_url: str) -> ActualItem; compare_new_item(frozen: FrozenItem, actual: ActualItem, *, expected_item_id: str) -> Recheck. No shared Bundle comparison rule changes.

- [x] First inventory exact create/saved/success contracts per game and link retained evidence. Mark unavailable fields/contracts explicitly. Never elevate existing synthetic fixture values into live facts.
- [x] RED tests: each required name/type/kind/option/duration/tradeable/game/ID difference -> mismatch; missing -> not passed; difference plus missing -> mismatch with incomplete true. Description checked when sent; image presence separate, no pixel claim.
- [x] Route all synthetic Aztek traffic; unexpected external requests fail. Misleading controls/changed labels cannot override stable IDs; missing/duplicate/wrong-type ID stops without POST.
- [x] Name tests test_each_property_difference_is_mismatch, test_difference_and_unreadable_both_visible, test_missing_false_is_not_false, test_image_presence_is_not_pixel_proof. Pin these API/reader result assertions for the matching scenarios:

```python
assert changed["outcome"] == "mismatch"
assert mixed["outcome"] == "mismatch" and mixed["incomplete"] is True
assert missing["outcome"] != "passed"
assert missing["actual"]["values"].get("tradeable") is None
assert image["image_status"] == "present_not_content_verified"
```
- [x] Implement fresh readback only where evidence supports it. Wrong game/ID/route/header stops before pass. Unsupported coverage fails/incomplete instead of filling values from the submitted form/search result.
- [x] Run GREEN: python -B -m pytest tests/test_new_item_reader.py tests/test_new_item_recheck_api.py tests/test_bundle_recheck_id_first.py -q. Record exact supported/blocked matrix. Included in scoped137 and latest218 with comparison/draft/auth/limits/startup regressions; see ledger.

### Task 3: Search decisions, atomic create checkpoint and stopped queue

**Files:** Create runner module; extend store/routes; tests/test_new_item_create_flow.py, tests/test_new_item_concurrency.py.

**Interfaces:** async run_new_items(game, items: list[FrozenItem], storage_state, *, on_checkpoint, browser_gate) -> list[dict]; repository claim_submission(owner_id, draft_id, revision, payload_hash) -> FrozenItem is an atomic conditional transition confirmed -> submitting committed BEFORE possible write. Read-only use_existing is distinct from create_new.

- [ ] Evidence gate from Task2 first: no create adapter enabled without observed exact write/success/confirmation contract. No guessed REST endpoint/schema or wildcard POST response capture.
- [ ] RED real API/runner tests using synthetic pages: search triple returns multiple IDs -> no automatic choice; use_existing -> zero create submits and fresh readback; explicit create_new required. Cancel -> zero submits and drafts unchanged.
- Verified read-only subset26October: search/use-existing RED18→GREEN18; UI RED3→API+UI GREEN24; boundaries4passed. POST /search accepts confirmed selected IDs/revisions/game; POST /{id}/use-existing accepts current owned candidate/token and performs fresh readback, never create. Stored creation.source=existing distinguishes known existing record from new creation. Candidate links must be read from the row. Full create_new/atomic submitting/queue boxes remain unchecked.
- Later MTH-only slice verified after actual raw receipt: run API explicitcreate decision/CAS/durablecommit-before-firstPOST/exact mainframe multipart matcher/ID-before-freshreadback/stop-next all implemented. Missing-route RED1→GREEN14; image-prefix RED→fix; concurrentPOST RED→latch-after-await fix; GREEN30. Scoped latest464passed624.51s wrapper0/JUnit464/0/0/0/source44match/originaluserhashmatch; old396allretained+create30+wholeAPIextra38. See create-mth-slice-20261026.md and ledger. Whole-task boxes stay unchecked: other three games unsupported, no positive resolve proof/fullcreateUI/finalfull/freshreview. No new live writes, build/commit/push/issue closure.
- [ ] RED race tests: two requests and edited revision after confirm -> at most one submit; stale/foreign/game-mixed IDs rejected. Claim failure cannot click.
- [ ] RED checkpoint tests: server accepted write then response/ID lost, browser disconnect, ambiguous success/nested other-record ID -> unconfirmed, stop next Item and persist evidence. No auto retry, even if confirmation handler times out.
- [ ] Name tests test_lost_response_never_replays, test_concurrent_requests_submit_once, test_use_existing_requires_readback, test_stale_revision_cannot_submit. Use real HTTP/runner and only existing routed-browser Aztek boundary patterns, with these observable assertions:

```python
assert first["creation"]["state"] == "unconfirmed"
assert total_create_requests == 1
assert second_request.status_code == 409
assert stale_request.status_code == 409
assert use_existing_create_requests == 0
assert unexpected_external_requests == []
```
- [ ] Implement with existing BrowserOperationGate/session/ID-first create activation + scoped confirmation helpers, strict main-frame operation matcher. Persist item_id immediately when proven; then Task2 readback. Only passed+complete advances next confirmed Item.
- [ ] GREEN: python -B -m pytest tests/test_new_item_create_flow.py tests/test_new_item_concurrency.py tests/test_bundle_recheck_flow.py -q; assert unexpected network empty and exact total submit counts.

### Task 4: Durable recovery/history and passed-only handoff

**Files:** Store/routes; minimal existing Finder integration; tests/test_new_item_recovery_api.py, tests/test_new_item_handoff.py.

**Interfaces:** append_recheck(owner_id, draft_id, result: Recheck) -> dict; recover_interrupted() preserves submitting as unconfirmed; handoff_passed(owner_id, selected_ids: list[str], occurrence_ids: list[str]) -> dict produces existing Finder result shape, never adds Bundle queue.

- [x] RED reopen a new app instance on the same isolated DB after submitting: no POST, no reset to draft, prior references/game/ID/history survive and log contains no credentials.
- [ ] RED saved ID but failed readback -> recheck adds one immutable attempt with zero extra create submits. Acknowledge skip/continue keeps original outcome and handoff restriction; remaining selected jobs require explicit continued scope.
- [x] RED handoff verifies latest passed+complete record and each selected occurrence server-side, reads wrong-owner/game/stale result as rejection. IDs and per-Bundle Amt/position remain separate; no unselected found/missing rows or auto-add.
- [ ] RED resolve tests: supplied candidate belongs to another game/has ambiguous triple-only evidence -> retain unconfirmed; exact independently proven identity -> fresh readback/history only. Cross-owner image key, spoofed MIME, oversized upload and changed image digest cannot be confirmed/reused.
- Verified partial slice26October: acknowledgement RED6→GREEN6, local private images RED13→GREEN19withack, UI/remove RED6→GREEN27; current media17+ack6+UI5 included in340passing scoped selection. Owner/revision/hash/MIME/byte/pixel/animation guards and no-ack-to-pass covered. Resolve/queue still pending; combined boxes stay unchecked rather than claim Task4 complete.
- [ ] Name tests test_restart_keeps_unconfirmed, test_recheck_is_read_only, test_acknowledge_cannot_unlock_handoff, test_selected_occurrences_keep_amounts. After reopening isolated DB and exercising actual routes:

```python
assert restored["creation"]["state"] == "unconfirmed"
assert after_create_requests == before_create_requests
assert len(after_attempts) == len(before_attempts) + 1
assert rejected_handoff.status_code in (400, 409)
assert [row["amount"] for row in selected_handoff] == ["2", "3"]
assert automatic_bundle_adds == []
```
- [ ] Implement durable continuation and pass-only result mapping using existing Finder/Bundle handoff schema; do not let request payload invent reference/actual/passed.
- [ ] GREEN: python -B -m pytest tests/test_new_item_recovery_api.py tests/test_new_item_handoff.py tests/test_web_finder_bundle_handoff_ui.py tests/test_bundle_recheck_flow.py -q.

### Task 5: Complete operator UI and final regression

**Files:** New Item HTML/JS, existing navigation/Finder selected-miss action/app page; tests/test_new_item_ui.py; coverage/handoff docs.

**Interfaces:** /new-items uses Task1–4 APIs. Existing Sheet picker controls preview selection; UI renders original/submitted/actual/provenance and creation/recheck separately, no hidden auto-run on reload.

Verified MTH-only continuation26October: UI explicitunchecked create scope/count/game/values/description, cancel/Escapefocus, busy/doubleclick/lostToolsHTTP response, freshsaved result and selectedFinderhandoff at1280/390. Same-owner/game problems require current acknowledgement before explicitnewscope, never auto-next/replay. Source51/scoped475passed683.62s wrapper0/JUnit475/0/0/0/allold464retained/originaluserhashmatch. UI game label fixed after observedRED+DOMdiagnosis. Whole-task/finalfull/freshreview boxes stay incomplete because other three games and positive unconfirmedResolve proof are missing; user reports no other-game data, do not ask for same data or extra live records. No commit/push/Setup/issue change.

- [ ] RED browser tests at Desktop1280x900 and Mobile390x844: import -> select named Sheets -> edit missing fields/confirm defaults -> select Items -> explicit count/game confirmation -> result -> selected passed-only Finder handoff.
- [x] Pin Tab/Space/Enter, dialog cancel/focus return, Thai/long names/large lists, per-table scrolling without whole-page overflow. Supported workflow only: separate UI2cases log/JUnitpassed (wrapper output unavailable),100rows/mobile screenshot inspected; no create end-to-end claim.
- [ ] Pin mismatch + incomplete warning always visible, image-presence label, unconfirmed recovery guidance without “create again”, game switching in other tool cannot mutate queued Item.
- [ ] Name tests test_mobile_import_to_selected_handoff, test_keyboard_cancel_returns_focus, test_incomplete_warning_survives_mismatch, test_reload_does_not_submit. Observable browser assertions use Playwright expect, for example:

```python
expect(page.get_by_text("ยังตรวจไม่ครบทุกส่วน", exact=True)).to_be_visible()
expect(page.get_by_role("button", name="ยืนยันสร้าง", exact=True)).to_be_focused()
assert page.evaluate("document.documentElement.scrollWidth <= innerWidth") is True
assert create_requests_after_reload == create_requests_before_reload
```
- [ ] Implement UI using existing console/Sheet-picker style and row editing. No new UI framework or long textarea-only draft editing. Keep optional image owner-isolated.
- [ ] GREEN focused UI plus existing Finder/Bundle/ItemCode/Event/Product regressions, then one necessary final full on exact frozen source with durable runner/nativeexit/JUnit/independent source hashes. No live Aztek, user-app install or release build.
- [ ] Native execution recommendation: one fresh final branch reviewer after task verification, fix findings by valid RED -> minimal fix -> GREEN; no repeated reviewer loops. Commit/push/Setup/publication remain separately gated, not implied by spec.
- [ ] Map all22 acceptance items in coverage.md to concrete passing evidence or explicit unsupported blockers. Never mark #12 complete while required automation coverage is missing.

## Acceptance trace

| Spec acceptance | Task |
| --- | --- |
| 1–6,9–10 | 1 |
| 7–8,12–13,17 | 3 (+1 readiness) |
| 11,19 | 2 |
| 14–16,18 | 4 |
| 20–21 | 5 |
| 22 | 5 with existing pipeline regressions |

## Self-review and execution handoff

- All42 user stories and22 acceptance criteria map to tasks; no original reference mutations, auto replay/handoff or WR work added.
- Fixed DTO names/signatures are shared across tasks. New API names are builder choices following existing conventions, not a previously approved upstream Aztek contract.
- Five Review Focus classes each have a named task/test. Missing real create/result evidence remains an explicit automation gate; Task1 does not depend on gaining live access.
- Plan reviewed locally against full GitHub spec/comments (none), current ownership/storage/BrowserOperationGate and retained create observations. Tests in this plan are prospective, not executed/passing claims.
- Recommended execution: **Native** in this chat, task-by-task TDD, because tasks share immutable reference/checkpoint interfaces; one fresh final reviewer, no per-task agent overhead.
- Historical milestone before read-only search/use-existing (superseded by the latest entry below): User approved Native execution. Task1 API/drafts/reference, Task2 comparison/reader/recheck API and Task4 history/startup recovery/selected handoff plus local private images/acknowledgement implemented. Supported-only Task5 UI + Finder selected-miss entry verified; Create stays disabled. Latest scoped340passed215.89s wrapper0/JUnit340/0/0/0/source26match, not full suite. Separate Tab/100rows2cases log/JUnitpassed, wrapper output unavailable after truncation. Retained scoped1 remains338passed2dev-fixture-failed; diagnosed path-sensitive setup limitation and used fresh short basetemp without assertion/source changes. Earlier305/363 are historical snapshots, not additive/current full evidence. Create contract/search/use-existing/resolve/queue/complete create UI/finalfull/fresh review pending. No commit/push/issue mutation/live write. See coverage.md, acceptance-current.md and ledger for current boundaries.
- New latest26October: Task3 read-only search/use-existing and Task5 corresponding UI verified: scoped396passed500.40s wrapper0/JUnit396/0/0/0/source43match. Includes all NewItem tests (also Tab/100rows) and existing Finder ID-first/handoff/import/auth/limits/plan/dev-script/startup regressions. Store actual row links and owned revision/payload-bound search token; explicit ID choice, no automatic selection/create; fresh identity/readback and CAS, source=existing checkpoint, passed-only handoff. Screens1280/390/candidate/confirmation inspected; preserved existing console styling (Gridgeist brand-derived). Previous340/305/363 are milestones, not current-source full results. Create-write contract/resolve/write queue/finalfull/freshreview still pending; no final completion/commit/push/Setup/livewrite/issue closure. Source and evidence unchanged after scoped396 except docs.
