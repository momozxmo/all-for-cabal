# Local release v0.1.40

Build date: 2026-10-22. Release source is the commit containing this document,
based on ID-first checkpoint `bb12059f118e691279222c0766eaee16e25b4fa1`.

## Scope

- เพิ่มปุ่ม “ตรวจเองครบแล้ว — สร้างทุกบันเดิลต่อเนื่อง” พร้อมยืนยันครั้งเดียวสำหรับคิวและเกมปัจจุบัน
- ทำต่อเมื่อยืนยันว่าบันทึกสำเร็จและมี Bundle ID แม้ Recheck ไม่ผ่านครบ โดยเก็บผลตรวจจริงไว้
- ยังคงหยุดเมื่อกรอกไม่ครบ บันทึกไม่สำเร็จ ผลสร้างไม่แน่นอน หรือไม่มี ID; ไม่เปิดโหมดถาวรหลัง reload
- ปุ่มสร้างเดิมยังหยุดตาม Recheck ตามเดิม และไม่อนุมัติส่งผลที่ไม่ผ่านไป Event/Product อัตโนมัติ
- คง workspace/group identity ของรายการที่ส่งสร้าง และส่งต่อ Document Reference จาก Finder ไม่ให้หาย

ไม่รวม dirty Event/Product/Item Code migrations และ Product visibility guard ที่ยังพัฒนาแยกอยู่

## Verification

- Fresh exact-source full: **2,113 passed, 1 warning in 3168.61s**; wrapper exit0,
  status finished/passed, raw/signed pytest exit0, JUnit aggregate/actual2113/0/0/0,
  evidence_errors empty. Source/tests/assets/build freeze147 matched before/after and before packaging.
- JUnit SHA256: `19EA54DCE0F61E444385B0FAE21A1A7E8EFC67135A0B893B681F57E47E8237B9`.
- Warning remains process-local development secrets in a test; not a production secret leak.
- Finder prerequisite: existing four-game RED cases → actual-source GREEN, targeted26passed201.07s.
  Scoped51 passed and independent reviews found no remaining Critical/Important/Minor findings;
  overlapping targeted counts are not added to full total.
- Build: `scripts/build_local_installer.ps1 -Version 0.1.40 -SkipTests` after that exact full.
  PyInstaller, update helper, privacy checks, Inno Setup and checksum completed with exit0.
- Runtime and Setup product version `0.1.40`; helper present. Packaged `bundles.html`, `index.html`,
  `bundle_import.js` and `workspace-ui.css` SHA256 match source.
- Packaged executable smoke passed with fresh isolated runtime: health0.1.40, Local session/bootstrap,
  all tool pages, checked-all UI, zero-rate import and empty Recheck history.
  Only its own process was stopped, checking PID/path/starttime; port8000 was released.

## Artifact

- Local Setup: `All for Cabal Web Setup-0.1.40.exe`
- Size: **279,146,982 bytes**
- SHA256: **31ABC0280BC9D055142884369C6A4E243E6DBCBC89807B10C44FE82BB6DD28FF**
- Published stable/latest at [GitHub Release v0.1.40](https://github.com/momozxmo/tool-cabal-local/releases/tag/v0.1.40),
  2026-10-22T14:42:28Z. Source code commit: `2ff80782182f0dfca87e2df83aa2cb01ba712a34`;
  Local release docs/tag commit: `c76a99d10909c99109148a5f6a6daad185924258`.
- Downloaded both public assets without download authentication; Setup size/hash match the local build
  and downloaded sidecar. Published filename is `All.for.Cabal.Web.Setup-0.1.40.exe`.
- Sidecar SHA256: `BB2A60AFE08AB267BA7D9D147079A14FE093826319311E571CC89F7B6B881242`.

## Boundaries

- No real Aztek login/probe/create/update/delete or issue closure performed.
- No user installation closed or overwritten; original user source/runtime preserved.
- Actual user update/reopen and browser drafts/queues preservation await user-applied update checks.
- Setup is unsigned; clean-VM installation is not verified.
- Prior failed full remains failed; this fresh full is the passing release evidence.
