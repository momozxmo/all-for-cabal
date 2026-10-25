# Local release v0.1.41 — combined candidate

Build date: 2026-10-25 (Asia/Bangkok). Status: stable/latest published and public downloads verified.
Source snapshot: `2b071e4e821fe429c7e30ed4b322b9768fcd1f81`.

## Scope

- รวม ID-first Event/Product/Item Code ล่าสุดเข้ากับปุ่ม “ตรวจเองครบแล้ว — สร้างทุกบันเดิลต่อเนื่อง” ที่ส่งมอบใน0.1.40
- คงผล Recheck จริง/history และสิทธิ์ส่งต่อแยกจากการทำคิวต่อเนื่อง;ไม่ข้าม incomplete/save-failure/uncertain/no-ID safety gates
- คง source quantities/document/workspace/group identity ใน Finder/Shop → Bundle → Item Code/Event/Product
- Item Code result identity ไม่ยืม nested Bundle/Reward IDs;คง saved-with-unknown-ID warning และไม่ submit ซ้ำ
- Atomic Create guard หยุดเมื่อปุ่ม/ฟอร์มถูกซ่อนหลัง actionability trial ก่อน activation;ไม่เพิ่ม guessed locator/schema fallback
- ไม่รวม NewItem12,การสร้างข้อมูล Aztek จริงหรือการเปลี่ยน business rules/schema

## Exact combined-source verification

- Full: **2,749 passed, 1 warning in7200.96s**, wrapperexit0/statusfinishedpassed/raw+signedpytestexit0.
- JUnit aggregate and actual:2749tests/0failures/0errors/0skips; evidence_errors empty.
- Freeze161 matched before/after and independent verification. ManifestSHA256:25D59F304CA23E64F56E98309B1C481B4822432BD385100F4D6D5C0FA93FF669.
- JUnitSHA256:A3590F97CF22020BBA346844AD715D44F15FF32AEF4433A978C540FF631BC51C.
- Full started2026-10-24T15:47:15.750980Z,ended2026-10-24T17:47:20.796658Z. No arithmetic on historical2715/2113 snapshot counts.
- Warning remains process-local development secrets in a local-runtime test; not warning-free or a production secret leak.
- Integration scoped92passed692.47s before review fix. Review Critical0/Important1/Minor1; Important reproduced2failed24.55s → minimalfix →44passed371.43s → exact combined full above.
- Review documentation observations were reconciled25October: current [status entry point](tickets/aztek-id-first/verification-current.md), preserved dated history and precise LF+TrimEnd provenance wording in [combined scope/evidence](id-first-combined-release-20261024.md). No source/test change or rerun for trailing blank-line differences.
- Original dirty worktree and user CONTEXT/item_finder hashes preserved. No runtime data/secrets staged.

## Packaging and delivery gates

Version0.1.41 remained free at pre-build remote recheck. Build uses the exact full-passed source with SkipTests; no dependency upgrades.
Buildsession44416 completedexit0 (transcript build-cache/build-v041-20261025.log).
Release tree/artifact privacy passed; only reviewed public workbook template and public certifi CA bundle are allowed. CA bundle equals the installed dependency and contains no private key.
Embedded code equals compiled tested source for all six changed modules, retained Bundle/API/Finder modules and separate update helper; all19static files match source SHA256. Runtime and Setup ProductVersion are0.1.41.
Isolated packaged smoke passed health, Local session/bootstrap, all tool pages, checked-all UI/opt-in, zero-rate import and empty history. Only the owned process was stopped after path/starttime checks; port8000 is free. No Aztek request/create invoked.
Setup: `All for Cabal Web Setup-0.1.41.exe`,279151780bytes.
SHA256: `D2CD801DB6D522FE7712711F09F5334F5D209D6F1290F7BEA5F7B12AE98AB5B8`; generated sidecar matches.
Source freeze161 and original user hashes independently matched again after build. No full rerun for documentation.
Source code commit2b071e4 and verification docs5613f75 were fast-forward pushed to origin/main. Local docs commit/tag target9cd45afda66ca8ed4e7235dfe53947d92ce7af51 was atomically fast-forward pushed to local-release/main withv0.1.41.
Stable/latest [v0.1.41](https://github.com/momozxmo/tool-cabal-local/releases/tag/v0.1.41) published2026-10-24T18:11:47Z;notdraft/notprerelease.
Public Setup and sidecar downloaded into build-cache/release-v041-published-download-20261025. Actual279151780bytes/SetupSHA256 above match local build;sidecar102bytes/SHA256E503D9E23E3F210AEE77958C66C50A05669F7CA67245F989330831516170814C matches local sidecar byte-for-byte and contains the correct Setup digest/name. GitHub normalized asset spaces to dots;sidecar text retains original spaced filename.
The first atomic Local-docs push accidentally targeted source origin and was wholly rejected (non-fast-forward);neither main nor tag changed there. Both refs verified before correcting remote to local-release;no force used. Source and Local repositories contain only their intended changes.

## Boundaries

- No live Aztek login/probe/create/edit/upload/delete or issue closure.
- Synthetic verification does not establish every live DOM/schema/navigation variant. At release time issues13/19 were still open;the subsequent25October [acceptance audit](tickets/aztek-id-first/acceptance-v041.md) evaluates their original bounded criteria independently of this historical release boundary.
- No automatic overwrite/install or closure of the user's app. Actual user-applied update/reopen/draft/queue preservation remains unverified.
- Signing and clean-VM installation are not verified.
