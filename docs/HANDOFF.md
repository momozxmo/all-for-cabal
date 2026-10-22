# ส่งต่องาน All for Cabal

Snapshot: 2026-10-08 — อ่านแล้วตรวจสถานะ Git จริงก่อนแก้ไฟล์เสมอ
ใช้ `git status --short --branch`, `git remote -v` และ `git log -5 --oneline`
เพื่อยืนยัน checkout/branch และแยกไฟล์ผู้ใช้ที่แก้ค้างออกจากงานใหม่

## สถานะล่าสุด

- 2026-10-22: ส่งมอบ Setup v0.1.40 สำหรับปุ่มตรวจเองครบแล้ว—สร้างทุกบันเดิลต่อเนื่องตามสิทธิ์ผู้ใช้
  ใช้ clean release candidate แยกจาก dirty migrations; source `2ff8078`, Local docs/tag `c76a99d`
  Full exact-source2,113 passed1warning3168.61s/JUnit2113/0/0/0/exit0/evidence_errorsว่าง/freeze147ตรง
  Build/privacy/helper/staticSHA/runtime0.1.40 และ packaged smoke ข้อมูลทดสอบแยกผ่าน
  เผยแพร่ stable/latest และดาวน์โหลด Setup+checksum กลับมาแล้ว size/SHA256ตรงbuild
  ดู [หลักฐานv0.1.40](local-release-v0.1.40.md) และ [scope/evidence ledger](bundle-manual-queue-release-20261022.md)
  ไม่ติดตั้งทับ/ปิดแอปผู้ใช้ ไม่สร้างAztekจริง และไม่ปิด#13/#19/NewItem12
  การอัปเดตจริง/เปิดกลับ/ร่างและคิวต้องตรวจหลังผู้ใช้เลือกอัปเดตเอง; dirty Event/Product/ItemCode migrations ไม่รวมรุ่นนี้
- 2026-10-08 ผู้ใช้อนุมัติ commit จุดพักงาน ID-first ปัจจุบันเท่านั้น ไม่ push/Setup/publish
  ไม่รวม CONTEXT.md, เอกสาร New Item และไฟล์อื่นนอกงาน; #15/#16 ยังไม่ปิด และ #17–#19 ยังเหลือ
  Pre-commit picker guards รอบใหม่31 passed/129 deselected in127.73s; staged Python syntax20filesผ่าน
  Regression945ข้างล่างเป็นผลก่อนหน้านี้ที่ตรวจhashตรง ไม่ใช่fullใหม่; ข้อมูล runtime/ไฟล์อัปโหลดไม่เข้าcommit
- งานปัจจุบัน: Aztek ID-first ยืนยัน Q1–Q4 และกฎสำหรับทุกฟังก์ชันใหม่แล้ว
  spec อยู่ใน [aztek-id-selector-spec.md](aztek-id-selector-spec.md)
  เผยแพร่ [GitHub Issue #13](https://github.com/momozxmo/all-for-cabal/issues/13)
  พร้อม ready-for-agent แล้ว ตรวจเนื้อหาตรงกับไฟล์ในเครื่อง
  AGENTS.md ชี้ [locator policy](agents/aztek-locators.md) สำหรับงาน Aztek ใหม่/แก้ไขทุกครั้ง
  ผู้ใช้อนุมัติและเผยแพร่ [6 tickets #14–#19](tickets/aztek-id-first/README.md) ตาม to-tickets
  ทุกงานมี ready-for-agent และ native blockers; ลำดับเริ่มที่ #14 Item Finder
  ผู้ใช้อนุมัติ implementation; #14 Item Finder verified ใน working diff
  #15 ย้าย header/Item search-add, Item card Qty/Tier/current draw ID และ Reward tab/picker/fetch/add แล้ว
  Item-card และ Reward-picker slices verified ใน working diff
  Reward card Qty/Tier/current-rate/default-Tier verified ใน working diff
  Create-action scoped/preflight verified ใน working diff
  Bundle scoped confirmation verified ใน working diff; target 33 passed in 718.83s ดู coverage
  Saved Item-detail readback verified เฉพาะ slice: target 88 passed in 239.57s; full 1,858 passed ดู coverage
  Saved Bundle-card readback verified: target 123 passed in 369.10s; full 1,893 passed ดู coverage
  Repeated-occurrence create/readback mapping verified: target 346 passed; full 1,915 passed
  ใช้ fill-local node/control binding + business identity, อ่าน current draw ID และตรวจท้ายฟอร์ม
  exact draw ID ต้องไม่ซ้ำใน owning form; current row index ต้องไม่ชนกันทั้ง FIXED/RANDOM
  Reward Recheck จับคู่หนึ่งต่อหนึ่ง; เกณฑ์เทียบเดิมและกฎ API ห้าม Item ID ซ้ำใน Bundle เดียวคงเดิม
  รอบปัจจุบัน: M TH write matcher จำกัด POST + API host/path ที่จับจริง + owning main frame แล้ว
  RED wrong-operation/iframe จับ ID ผิดก่อนแก้; GREEN 2 และ targeted รอบแรก 16 passed
  Standards/Spec static review 0 finding ค้างเฉพาะ increment นี้; target2 37 passed in 481.36s (exit 0)
  write-contract-full1: 1,927 passed, 2 warnings in 2797.33s (exit 0)
  Target2/full1 JUnit failures/errors/skipped 0; hash 3 source/test files ตรงกับ freeze หลังทั้งสองชุด
  Warnings: process-local development secrets เดิม และ Tkinter Variable cleanup/main thread warning
  Tkinter warning ไม่ได้แก้ใน Bundle increment นี้; ไม่อ้างว่า warning-free หรือผ่าน typecheck
  Full 1,915 เป็นฐานก่อน matcher; Full 1,927 เป็นฐานก่อน header identity fix ด้านล่าง
  รอบปัจจุบัน: saved Bundle header identity แยกจาก Item-picker IDs ภายใน form แล้ว
  RED late-mounted picker ทำให้แจ้ง Bundle ID เปลี่ยนผิด; GREEN 1 passed หลังแก้
  เพิ่ม initial picker/เลขตรง Bundle, missing header และ real header/URL mutation guards
  Guards1 10 passed in 23.16s (exit 0), JUnit failures/errors/skipped 0
  Target1 พบ failures เพราะ fixture helper เก่าวางหัว Bundle/ID ใน form แล้วหยุด (ไม่มีผลจบ)
  Diagnose2 RED reader เดิม; แก้เฉพาะ _saved_page ให้ header อยู่นอก form ตาม DOM แล้ว diagnose3 GREEN 1 passed
  Assertions/wrong ID cases คงเดิม; Standards/Spec follow-up 0 scoped finding
  Full1 เริ่มจาก guard ของ temporary command ที่ไม่ stop เมื่อ JUnit หาย จึงหยุดทันที ไม่ใช้เป็นผลผ่าน
  Target2 reader/Recheck/API: 133 passed in 423.18s (exit 0), JUnit failures/errors/skipped 0
  Full2: 1,937 passed, 1 warning in 2945.52s (exit 0), JUnit failures/errors/skipped 0
  Warning เดิม process-local development secrets; ไม่มี Tkinter warning รอบนี้ ไม่อ้างว่าแก้แล้ว
  Target2/full2 จบแล้ว; source/test 3 files ตรง freeze หลังทั้งสองชุด; syntax/diff check ผ่าน
  Shared response matching/confirmation ของ flow อื่น/อีกสามเกม และ live repeated-row behavior ยังเหลือ
  #16 เริ่ม header/readiness slice หลังอ่าน empty create ของ Item Code ทั้งสี่เกมแล้ว
  name_th/name_en/slug ใช้ scoped ID-first + shape/readback; READY_SELECTOR ใช้ name_th ID
  Guards2 18 passed; target2 regression768 passed in143.52s exit0/JUnit0 failures/errors/skips
  Standards/Spec0 scopedfinding; source/test3hashesตรงfreezeหลังtarget2 ดู coverage
  Full1,937 เป็นฐานก่อน ItemCode slice; fullรอบใหม่ไว้ท้ายงาน16 ไม่อ้างsourceใหม่ผ่านfullแล้ว
  #16 header limit/type: per_player_limit/is_limited/quantity/remaining/redeem_type ย้าย ID-first แล้ว
  อ่าน limit-on/native-select metadata ทั้ง4เกม; native no-ID exception จำกัด parent ของ ID trigger
  รอ requested option; switch trial+atomic guard ป้องกัน disabled→submit; preview submit0
  Regression2 798 passed in241.59s exit0/JUnit0 failures/errors/skips; source/test4hashesตรงfreeze
  Standards/Spec re-review0 residual scopedfindings; ดูหลักฐาน/RED-GREEN ใน coverage
  #16 calendar slice ย้าย start_at/end_at ID-first และ scoped ARIA-linked dialog/hour listbox
  อ่านทั้ง4เกม/2fields; เดือน/ปี/วัน/เวลาใช้ verified no-ID exceptions และ exact readback
  Regression2 854 passed in328.35s exit0/JUnit0 failures/errors/skips; source/test4hashesตรงfinalfreeze
  Standards/Spec re-review0 residual scopedfindings; metadata-only live audit ไม่อ้าง livefillผ่าน
  #16 Reward slice ย้าย names/per-user/limit/counters/code-type/FIX serial เป็น indexed ID-first
  อ่าน metadata reward0/1 ทั้ง4เกม; M TH reward2/back-tab เพิ่ม; no-ID add/ordinal-tab scope ดู coverage
  Guards2 35 passed/Tab1 2 passed; error RED2→GREEN5 สำหรับ disabled add/tabไม่active
  Named error คง cause/non-submit guard ไม่ retry action; Standards/Spec re-review0 findingค้าง
  Regression2 892 passed in479.69s exit0/JUnit0 failures/errors/skips; source4hashesตรงfinalfreeze
  Regression1หยุดก่อนerrorfix ไม่ใช้เป็นผลผ่าน; fullใหม่ไว้ท้าย16 ไม่อ้างtypecheck
  #16 SERVER prefix/amount ย้าย scoped indexed ID-first แล้ว; อ่าน metadata ทั้ง4เกม/ชุด0และ1
  Prefix optional/readback และ amount requirednumber คงเดิม; RED1→GREEN1, guards22 passed
  Standards/Spec static review0 scoped findings; regression SERVER914 passed in561.50s exit0
  JUnit0 failures/errors/skips และ source/test4hashesตรงfreeze; related suite ไม่ใช่fullใหม่
  #16 Bundle picker ย้าย stable Reward ID pair + scoped no-ID/ARIA relation/exact row/badge readback
  Unselected/owner metadataครบ4เกม/ชุด0และ1; selected/change liveเฉพาะM TH225954บนฟอร์มไม่บันทึก
  Guards1 30 passed ก่อนscopefix; Specพบoutside-form escapeแล้ว REDยืนยัน/เพิ่มowning-form guard
  Guards2หลังscopefix31 passed in129.53s exit0/JUnit0 failures/errors/skips; finalreviewสองแกน0 finding
  Related regressionหลังpicker945 passed in699.80s exit0/JUnit0 failures/errors/skips
  Source/test4hashesตรงfinalfreezeหลังจบ; related suiteไม่ใช่fullใหม่ ซึ่งไว้ท้าย16
  งานต่อ16: create/confirmation/fullท้ายticket; #17–#19 ยังไม่ implement
  ส่วนที่เหลือ15ยังรอ endpoint/contracts/state evidence ของเกมอื่น ไม่ถือ15เสร็จ
  Review base `19eb84e` + working diff; ไม่แก้ parent #13 ไม่ Setup/commit/push
  ID-first scope/evidence/DEV gaps อยู่ใน [coverage](tickets/aztek-id-first/coverage.md)
  Full regression ฐานก่อน Confirmation: **1,811 passed, 1 warning in 1765.81s** (exit 0)
  Confirmation compatibility/URL-ID cases: 5 passed in 111.45s; review ซ้ำสองแกน 0 finding ค้าง
  Full ฐานก่อน Saved Item-detail `confirm-full1`: **1,837 passed, 1 warning in 2231.61s** (exit 0)
  Source/test 4 files คง hash เดิมในรอบ Confirmation; ไม่มี live submit/Setup verification
  Full ฐานก่อน Saved Bundle-card `id-readback-full1`: **1,858 passed, 1 warning in 2402.84s** (exit 0)
  Source/test 3 files ที่แก้คง hash เดิมตลอดชุดเต็ม; syntax/diff check ผ่าน ดู coverage
  Full ฐานก่อน occurrence increment `card-readback-full1`: **1,893 passed, 1 warning in 2550.49s** (exit 0)
  Focused occurrence/collision regression: 24 passed in 289.93s; collision-only 2 passed in 13.89s
  `occurrence-target-final3`: 346 passed in 2055.62s (exit 0); JUnit failures/errors/skipped 0
  `occurrence-full-final3`: 1,915 passed, 1 warning in 2677.59s (exit 0)
  JUnit failures/errors/skipped 0; warning เดิมเรื่อง process-local development secrets
  เก็บ stdout log/JUnit ใน build-cache; รอบ final2 ผลจบเรียกคืนไม่ได้หลังหยุด จึงไม่อ้างว่าผ่าน
  รอบ final1 หยุดหลังพบ collision gap; ไม่ใช้เป็นผลผ่านของ increment
  Source/test 6 files hash ตรงกับก่อนหยุด หลัง target และหลัง full; syntax/diff check ผ่าน
  Standards/Spec 0 finding ค้างเฉพาะ increment นี้
  ผู้ใช้อนุมัติ live test เพียง 1 Bundle: CabalM TH, ชื่อ AFC-IDFIRST-TEST-*, FIXED,
  Item ID 224375 Qty 1 Tier Common และปิดส่งทันที ใช้ Playwright แยกเพื่อจับ Method/URL
  Live test ส่งเพียง 1 write แล้ว: HTTP 200, Bundle 225954 ชื่อ AFC-IDFIRST-TEST-20261008-035003
  ยืนยันเฉพาะ M TH: POST https://admin-api-v2.combo-interactive.com/cabalm/warehouse/bundles
  อ่านหน้า saved Bundle/Item เดิมผ่าน Brave แบบ read-only: 1 Item 224375, Qty 1, Tier Common,
  FIXED, ส่งทันที false; ItemKind 5468/Option 255/DurationIndex 0 ตรงกับ saved Item detail
  Playwright reader รอบนี้จบไม่ครบเพราะ Target closed; ไม่อ้าง automated live recheck ผ่าน
  ภาพ/readonly verification อยู่ build-cache/approved-bundle-probe-verified.jpg และ
  approved-bundle-probe-readonly-verification.json; report เดิมคง error/response ไว้
  one-write marker ถูกใช้แล้ว: ห้ามรัน approved-bundle-probe.py ซ้ำ/ลบ marker หรือสร้างเพิ่ม
  M TH matcher syntheticverifiedแล้ว; reader7อ่าน minimal saved recordสำเร็จ ดู header increment ด้านล่าง
  endpoint เกมอื่นยังไม่มี live write evidence; readonly Playwright reader รอบใหม่หมดเวลารอ manual login
  reader_complete=false, bundle_writes_allowed=0; ไม่ใช้ exit 0 ของ utility เป็นผลอ่านผ่าน
  bounded read-only diagnostic ยืนยันว่า stored session พาไป dex SSO; headed รอบ 2 ผู้ใช้แจ้งเข้าแล้ว
  utility ยังไม่ผ่าน ready gate และจบ timeout ที่ existing URL; ไม่ได้เรียก production reader จึงไม่อ้างว่า reader/DOM เสีย
  ผลแยกใน approved-bundle-readonly-reader-report2.json; ไม่มีสิทธิ์สร้าง/แก้ไข/ลบ Bundle
  รอบ 3 จบก่อนอ่านสำเร็จ; รอบ 4 เริ่ม production reader แล้ว แต่หยุด Bundle ID เปลี่ยนระหว่างอ่าน
  report4 reader_started=true/reader_complete=false และ Bundle writes allowed=0
  DOM ที่อ่านก่อนถูกบล็อก: header ID 225954 อยู่นอก form; Item-picker ID หลายรายการอยู่ใน form
  ยืนยัน original main-wide ID regex จับทั้งสองส่วน จึงแก้ locator เฉพาะ Bundle header
  ผู้ใช้ยืนยันอ่านเฉพาะสองรายการแล้ว แต่ auto-review ยังบล็อกเพราะเครื่องมือขอสิทธิ์ระดับ origin
  ผู้ใช้สั่งทำต่อหลังถามสิทธิ์ทั้งเว็บไซต์; scoped retry ยังถูก auto-review บล็อกเช่นเดิม หยุด live reads
  ขอ explicit origin-level approval ผ่านตัวเลือกอีกครั้ง; ไม่อ่านรายการนอกสองรายการเดิมหรือเปลี่ยนข้อมูล
  ผู้ใช้ยืนยัน origin-level แล้ว: scoped Brave read header225954 สำเร็จ (markerนอกformไม่มี HTML ID)
  Report5 version-load error/report6 spinner ไม่ครบ; เก็บหลักฐานไว้ ไม่ใช้ utility exit0เป็นผลผ่าน
  Reader7 สำเร็จหลัง retry navigation1ครั้งเฉพาะ observed Aztek version-load error
  reader_complete=true/matches_approved_item=true, Item224375 Qty1 Common Kind5468 Option255 Duration0
  ไม่มี rewards/unsupported และ header count1; allowed Bundle writes0, ไม่มี blocked_other_records
  shipping reader ไม่เพิ่ม auto-retry/ไม่เปลี่ยน timeout; retryมีเฉพาะ temporary readonly utility
  หน้าต่าง probeปิดเฉพาะของตัวเอง; ไม่มี reader/test processค้าง ไม่ต้อง loginรอบนี้เพิ่ม
  ไม่อ้าง RecheckเทียบExcelผ่าน (minimalprobeไม่มีDocument Reference); เหลือstate/เกมอื่นของ15
  Header/Item-add/Item-card/Reward-picker/Reward-card ของ #15 verified เฉพาะส่วนนี้;
  Python syntax 5 files/diff check ผ่าน; targeted Bundle/Recheck 167 passed in 665.72s
  Create-action รอบล่าสุด syntax 4 files/diff check ผ่าน; focused 25 cases และ final readiness 5 cases ผ่าน
  Standards/Spec review เทียบฐานที่ผู้ใช้ยืนยัน ไม่พบ finding ค้างของ #14 หลังแก้ไข
  Standards/Spec incremental review ของ #15 ไม่มี finding ค้างหลังแก้ regression; งานที่เหลือดู coverage
  Remote issues ยังไม่ปิด; create header ทั้ง 4 เกม และ saved Item/Currency/EXP preflight ดู coverage
  Create submit อ่านสดครบ 4 เกม 2026-10-02; ผู้ใช้เปิด confirmation M TH ค้างไว้ให้ตรวจแล้ว
  กล่อง/action ไม่มี stable ID; ARIA runtime relation ดู coverage. Bundle ใช้ scoped resolver แล้ว
  Shared helper default สำหรับ Item Code/Event/Product ยังไม่ย้าย; popup อีกสามเกมยังไม่มี live evidence
  พักขั้น tickets/implementation ของ New Item ตามคำสั่งผู้ใช้
- New Item Creation / New Item Recheck: ยืนยัน Q1–Q24 และ test seams แล้ว
  spec รองรับ CABAL PC/M ทั้ง TH/SEA อยู่ใน [new-item-spec.md](new-item-spec.md)
  เผยแพร่ [GitHub Issue #12](https://github.com/momozxmo/all-for-cabal/issues/12)
  พร้อม ready-for-agent แล้ว ตรวจเนื้อหาตรงกับ spec ในเครื่อง
  ยังไม่อนุมัติ implementation และไม่สร้างข้อมูลจริง/Setup/commit/push โปรแกรม
- Setup/commit/push ทั้ง source main และ Local Release สำเร็จสำหรับ v0.1.39;
  source งานแก้ `d1a3d18`, Local docs/tag `92e8ee8`
  production updater จำลองรุ่น 0.1.38 พบ/ดาวน์โหลด 0.1.39 แล้วเป็น `ready`;
  ขนาดและ SHA-256 ตรงกับ build โดยไม่ติดตั้งทับหรือปิดโปรแกรมเดิม
- Item Finder แยก “ส่งเฉพาะที่เลือก (N)” และ “ส่งทั้งหมด (N)”;
  การส่งจาก Product ใช้ขอบเขตกลุ่มที่แสดง ทั้งรีวิวและส่งเข้าคิว
  Regression: `tests/test_web_finder_bundle_handoff_ui.py` รวมไอเทมซ้ำหลาย Bundle
- Bundle มี “Clear ข้อมูล” ล้างข้อความ/พรีวิว/ข้อความแจ้งผล คืน focus
  และคงคิวเดิมไว้; ทิ้งผลพรีวิวที่ตอบกลับหลัง Clear ด้วย revision เดิม
- Bundle RANDOM รองรับเรต `0–100` ทั้งไอเทมและ Currency ตั้งแต่ import,
  preview, queue, API จนกรอก stable ID บน Aztek; ศูนย์ไม่ใช่ช่องว่าง
  การนำเข้ายังบังคับผลรวม `100%` และปฏิเสธค่าติดลบ/เกิน 100/ทศนิยมเกิน 3 ตำแหน่ง
- Currency บนหน้า Bundle แสดงชื่อเต็มแยกบรรทัดและ wrap ชื่อยาว;
  แก้ CSS เฉพาะ `body[data-btype] .rwrow` คงค่าคิว/API และพฤติกรรมเดิม
  Regression: `tests/test_web_bundle_rewards_ui.py` ครอบคลุม FIXED/RANDOM,
  Credit/Debit/Player EXP, จำนวน/Rarity/เรต 0, Keyboard/visible focus,
  เลือกและลบแถว และ Overflow ที่ 360/768/1280/1600px
- Full suite รอบก่อน release: **1,701 passed, 1 warning in 653.30s**
  (`python -X utf8 -B -m pytest tests -q --basetemp=<leaf ใหม่ใน build-cache>`)
  warning เดิมเรื่อง process-local development secrets
- คง Document Reference จากเอกสารต้นฉบับไว้ครบ;
  หากเลือกส่งเพียงบางรายการ Bundle Recheck อาจรายงานรายการขาดตามเอกสาร
- รุ่นเผยแพร่ล่าสุดที่บันทึกไว้: [v0.1.39](https://github.com/momozxmo/tool-cabal-local/releases/tag/v0.1.39)
  หลักฐาน build/test/hash และ updater อยู่ใน [local-release-v0.1.39.md](local-release-v0.1.39.md)
  รวม Bundle Recheck #9–#11, stable ID เรท RANDOM และตัวเลือกเบราว์เซอร์ Launcher แล้ว
- เตรียมเครื่อง/เปิดโหมดพัฒนาแยกข้อมูลจากโปรแกรมที่ติดตั้ง:
  [MULTI_COMPUTER_DEV.md](MULTI_COMPUTER_DEV.md)
  Launcher ใช้ Default/Chrome/Edge/Firefox และขอสิทธิ์เข้าเว็บใหม่ทุกครั้ง;
  ร่าง/คิวในเบราว์เซอร์ไม่ย้ายตาม ดู [LOCAL_INSTALL.md](LOCAL_INSTALL.md#เลือกเบราว์เซอร์)
- งานต่อ: ส่วนที่เหลือของ15 (เกม/stateอื่นและshared response matching) ไม่สร้างเพิ่ม;
  shared response matching และ live popup อีกสามเกมยังเหลือของ #15
  ก่อนถือว่า ticket เสร็จ; ไม่เริ่ม New Item #12

## ขอบเขตและจุดที่ยังไม่ยืนยัน

- ใช้ภาษาไทย คง workflow และเลือกวิธีเรียบง่าย
- สร้างข้อมูลจริงบน Aztek และ build/commit/push/publish เมื่อผู้ใช้สั่งชัดเจน
- รักษาไฟล์แก้ค้างของผู้ใช้; stage เฉพาะงาน เก็บข้อมูลลับ/ข้อมูลผู้ใช้ไว้นอก Git
- Recheck ที่ต้นทางไม่ครบหรืออ่าน exact currency code ไม่ได้ยังเป็นผลบางส่วน;
  ไม่เดาให้ผ่าน และการยืนยันทำต่อไม่เปลี่ยนผลตรวจ
- ยังไม่ทดสอบติดตั้งบน clean VM; live test ที่อนุมัติ 1 รายการสร้างแล้วเป็น Bundle 225954
  การติดตั้งอัปเดตและร่าง/คิวต้องตรวจหลังผู้ใช้เลือกอัปเดตเอง

## เวลาอัปเดต handoff นี้

ก่อนส่งข้ามเครื่อง ให้ระบุสถานะปัจจุบัน commit/issue งานค้าง ผลทดสอบ ข้อจำกัด
และลิงก์หลักฐาน โดยไม่สะสมประวัติแชทหรือ secrets
