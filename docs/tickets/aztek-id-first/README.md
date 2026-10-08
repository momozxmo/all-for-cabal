# Issue #13 — ชุด tickets ที่เผยแพร่

วันที่: 2026-10-01
Parent: https://github.com/momozxmo/all-for-cabal/issues/13
สถานะ: ผู้ใช้อนุมัติ implementation 2026-10-01; #14 verified ใน working diff;
#15 ย้าย header/Item search-add, Item card Qty/Tier/current draw ID และ Reward tab/picker/fetch/add แล้ว;
Item-card และ Reward-picker slices verified ใน working diff;
Reward card Qty/Tier/current-rate/default-Tier verified ใน working diff;
Create-action scoped/preflight verified ใน working diff;
Bundle scoped confirmation verified ใน working diff; target 33 passed in 718.83s ดู coverage;
Saved Item-detail readback verified เฉพาะ slice: target 88 passed in 239.57s; full 1,858 passed ดู coverage;
Saved Bundle-card readback verified: target 123 passed in 369.10s; full 1,893 passed ดู coverage;
Repeated-occurrence create/readback mapping: final3 target 346 passed in 2055.62s;
full 1,915 passed, 1 warning in 2677.59s (exit 0); hash 6 source/test files คงเดิม ดู coverage;
M TH write matcher จำกัด captured POST/host/path/main-frame แล้ว;
RED wrong-operation/iframe → GREEN 2; target1 16 passed;
target2 37 passed in 481.36s (exit 0);
write-contract-full1 1,927 passed, 2 warnings in 2797.33s (exit 0);
JUnit failures/errors/skipped 0 ทั้งสองชุด; hash 3 source/test files ตรง freeze หลัง target/full;
warnings เป็น process-local development secrets และ Tkinter Variable cleanup/main thread; ไม่อ้าง warning-free;
Standards/Spec static review 0 scoped finding; full 1,915 เป็นฐานก่อน matcher;
Full 1,927 เป็นฐานก่อน saved-header identity fix: แยก Item-picker IDs ใน form ออกจาก header นอก form;
RED late-picker false alarm → GREEN 1 passed; guards1 10 passed (exit 0), JUnit failures/errors/skipped 0;
Target1/Full1 หยุดหลัง fixture mismatch/report guard issue ไม่ใช้เป็นผลผ่าน;
แก้ helper ให้ header อยู่นอก form ตาม DOM โดยคง assertions; diagnose3 1 passed;
Target2: 133 passed in 423.18s (exit 0), JUnit failures/errors/skipped 0 และ hash3filesตรง;
Full2: 1,937 passed, 1 warning in 2945.52s (exit 0), JUnit failures/errors/skipped 0;
hash3filesตรงหลัง target/full; warningเดิมprocess-local development secrets;
Standards/Spec 0 scoped finding ของ header fix; หลักฐาน/สถานะปัจจุบันดู coverage;
Shared response matching/confirmation ของ flow อื่น/อีกสามเกม และ live repeated-row evidence ยังเหลือ;
#16 เริ่ม header/readiness slice หลังอ่าน empty ItemCode create ทั้งสี่เกม;
Guards2 18 passed, targeted regression768 passed in143.52s exit0/JUnit0 failures/errors/skips;
Standards/Spec0 scopedfindingและsource/test3hashesตรงfreeze ดู coverage;
Header limit/type ย้าย per-user/code-wide limits และ redeem_type ด้วย verified IDs ทั้ง4เกมแล้ว;
Regression2 798 passed in241.59s exit0/JUnit0 failures/errors/skips; source/test4hashesตรงfreeze;
Standards/Spec re-review0 residualscopedfindings; preview guards/lazy options ดู coverage.
Full1,937 เป็นฐานก่อน ItemCode slices; fullรอบใหม่ไว้ท้ายงาน16.
Calendar slice ใช้ stable start_at/end_at และ scoped runtime-ARIA popovers; อ่านทั้ง4เกม/2fields;
Regression2 854 passed in328.35s exit0/JUnit0 failures/errors/skips; hash4filesตรงfinalfreeze;
Standards/Spec re-review0 residualscopedfindings; liveauditเป็นmetadata-only ไม่สร้าง/กรอกจริง.
Reward Set names/per-user/limit/counters/code-type/FIX serial ใช้ indexed ID-first และ scoped ordinal-tab แล้ว;
Guard/error cases ผ่าน; regression2 892 passed in479.69s exit0/JUnit0 failures/errors/skips;
hash4filesตรงfinalfreeze; Standards/Spec0 findings ดู coverage (ไม่อ้างfullใหม่/typecheck).
SERVER prefix/amount ใช้ scoped indexed ID-first; metadata ครบทั้ง4เกม/ชุด0และ1;
RED1→GREEN1 และ guards22 passed; Standards/Spec static review0 scoped findings.
SERVER regression914 passed in561.50s exit0/JUnit0 failures/errors/skips;
hash4filesตรงfreeze; related suiteไม่ใช่fullใหม่ และ892เดิมเป็นฐานก่อน incrementนี้.
Bundle pickerผูกstable Reward ID pair + scoped no-ID/ARIA relation/exact row/badge readback;
Unselected/owner metadataครบ4เกม/ชุด0และ1; selected/change liveเฉพาะM TH225954ฟอร์มไม่บันทึก.
Guards1 30 passedก่อนscopefix; Guards2หลังowning-form guard31 passed in129.53s exit0/JUnit0 failures/errors/skips.
Finalreviewสองแกน0 finding; related regressionหลังpicker945 passed in699.80s exit0.
JUnit0 failures/errors/skips; source/test4hashesตรงfinalfreezeหลังจบ ไม่อ้างfullใหม่/typecheck.
งานต่อ16 create/confirmation/fullท้ายticket; #17–#19 ยังไม่ implement.
Full suite ฐานก่อน Confirmation: 1,811 passed, 1 warning in 1765.81s (exit 0);
Confirmation compatibility/URL-ID cases 5 passed in 111.45s;
Full ฐานก่อน Saved Item-detail confirm-full1: 1,837 passed, 1 warning in 2231.61s (exit 0);
Full ฐานก่อน Saved Bundle-card id-readback-full1: 1,858 passed, 1 warning in 2402.84s (exit 0);
Full ฐานก่อน occurrence increment card-readback-full1: 1,893 passed, 1 warning in 2550.49s (exit 0);
Final occurrence-target-final3: 346 passed (exit 0), JUnit failures/errors/skipped 0;
occurrence-full-final3: 1,915 passed, 1 warning (exit 0), JUnit failures/errors/skipped 0;
ผลจบ final2 เรียกคืนไม่ได้หลังหยุด จึงไม่อ้างผลฐานเป็นผล increment;
Live test 1 Bundle ตาม coverage ใช้สิทธิ์แล้ว: HTTP 200, Bundle 225954;
M TH POST /cabalm/warehouse/bundles บน admin-api-v2 ยืนยันจาก request จริง;
อ่าน saved Bundle/Item เดิมแบบ read-only ตรงตามค่าทดสอบ; automated reader ถูก Target closed;
readonly reader รอบใหม่หมดเวลารอ manual login: reader_complete=false และ allowed Bundle writes=0;
headed รอบ 2 ผู้ใช้แจ้งเข้าแล้ว แต่ utility ready gate ยังไม่ผ่านที่ existing URL; ยังไม่ได้ exercise production reader;
รอบ 4 exercise production reader แล้ว แต่ false alarm Bundle ID เปลี่ยน (report4);
หลัง fix ผู้ใช้อนุญาตอ่านเฉพาะ Bundle 225954/Item 224375 แล้ว แต่ auto-review ยังบล็อกสิทธิ์ระดับ origin;
ผู้ใช้สั่งทำต่อหลังถามสิทธิ์ทั้งเว็บไซต์ แต่ scoped retry ยังถูกบล็อก จึงหยุด live reads;
ผู้ใช้ยืนยัน origin-level แล้ว: headerอ่านได้; reader7สำเร็จหลัง bounded version-load retry1;
complete=true/matches_approved_item=true, allowed Bundle writes0, ไม่แก้ timeout/auto-retryของshipping reader;
ยืนยันเฉพาะ minimal Bundle225954/Item224375 MTH ไม่ใช่RecheckเทียบExcelหรือทุกเกม/state;
ห้ามรัน probeสร้างซ้ำ/ลบ one-write marker; MTH matcher/minimal savedreader verifiedแล้ว;
เกม/stateอื่นและlive repeated-row evidenceยังไม่ยืนยัน;
Standards/Spec ของ slice ที่ย้ายไม่มี actionable finding ค้างหลังแก้และตรวจซ้ำ.
ผลและงานที่เหลือดู coverage; ไม่ถือว่าทั้ง #15 เสร็จ.
Review base: `19eb84e` + working diff ตามผู้ใช้ยืนยัน.
หลักฐานและช่องที่ยังไม่มี ID: [coverage](coverage.md). ยังไม่ commit/Setup/push.
Remote issues ยังไม่ปิด; งานถัดไป #15 Bundle/Recheck และ #16 Item Code ตาม dependencies.

## ลำดับและผลส่งมอบ

| งาน | ผลส่งมอบที่ตรวจได้เอง | Blocked by |
| --- | --- | --- |
| [#14 Item Finder + ID-first path แรก](https://github.com/momozxmo/all-for-cabal/issues/14) | ค้น/filter/read ผลถูกต้อง และรายงาน locator error ผ่าน API/หน้าเดิม พร้อม helper ที่ปรับเล็กน้อยแบบ compatible | ไม่มี |
| [#15 Bundle สร้างและรีเช็ค](https://github.com/momozxmo/all-for-cabal/issues/15) | Item/Currency/EXP และ RANDOM สร้าง/อ่านกลับถูกแถวตาม ID-first รวม checkpoint/หยุดเมื่อปัญหา | #14 |
| [#16 Item Code + shared widgets](https://github.com/momozxmo/all-for-cabal/issues/16) | Header, limit, วันเวลา, หลาย Reward Set และ confirmation ทำงานครบ พร้อม widget drivers ที่ใช้ร่วมได้ | #14 |
| [#17 Event](https://github.com/momozxmo/all-for-cabal/issues/17) | วันใช้งาน/รับรางวัล จำนวนรวม/คงเหลือ ภาษา รูป และ reward ทำงานครบด้วย shared widgets จาก 03 | #16 |
| [#18 Product](https://github.com/momozxmo/all-for-cabal/issues/18) | Fetch/เลือก Currency/Category, หลายราคา รูป ภาษา Bundle/Primary และวันเวลา ทำงานครบด้วย widgets จาก 03 | #16 |
| [#19 ตรวจ flow รวมและ coverage](https://github.com/momozxmo/all-for-cabal/issues/19) | ยืนยันทุกเส้นทางที่ย้าย คง selection/handoff/คิวเดิม และสรุป ID/fallback/unknown/gap ให้ DEV | #15, #17, #18 |

03 ต้องเสร็จก่อน 04/05 เพราะส่งมอบ date/switch/select/picker drivers ที่สอง flow นี้ใช้จริง
05 ไม่รอ 02: Product เลือก Bundle ID ที่มีอยู่ ไม่ต้องรอการย้ายตัวสร้าง Bundle
06 ไม่ระบุ 01/03 ซ้ำ เพราะเป็น dependencies ทางอ้อมแล้ว

งานแรกไม่ใช่ framework refactor: ใช้ Item Finder เป็น flow แรกที่จบครบ และ prefactor เฉพาะ lookup/scope/readiness ที่จำเป็นก่อนให้ consumer อื่นใช้
แต่ละงานต้องมี evidence และ synthetic API/runner tests ของตัวเอง ไม่เลื่อน safety tests ไปทำเฉพาะงานสุดท้าย

## เงื่อนไขร่วม

- ใช้ stable HTML element ID เมื่อมี ตาม locator policy; exception เฉพาะ control ที่พิสูจน์ว่าไม่มี ID
- Known ID หาย/ซ้ำ/ผิดชนิด หรือ fallback กำกวม ต้องหยุดตาม spec ไม่เดาและไม่ auto-submit ซ้ำ
- ทุกงานปรับแบบ backward-compatible และรักษาพฤติกรรม/schema/API/สิทธิ์เดิมเท่าที่ทำได้
- ตรวจ page/game/state ของส่วนที่ย้ายแบบ read-only ก่อนใช้จริง; synthetic test ไม่แทนหลักฐานเว็บจริง
- ไม่สร้างข้อมูล Aztek ไม่ Setup/commit/push และไม่เริ่ม New Item #12
- เผยแพร่หนึ่ง GitHub Issue ต่อหนึ่งงาน พร้อม ready-for-agent, Blocked by ใน body และ native dependencies
  ไม่แก้หรือปิด parent #13; ตรวจ acceptance และหลักฐานก่อนถือว่า ticket เสร็จ

## สำเนาเนื้อหา tickets

1. [Item Finder](01-item-finder.md)
2. [Bundle](02-bundle.md)
3. [Item Code](03-itemcode.md)
4. [Event](04-event.md)
5. [Product](05-product.md)
6. [Cross-flow verification](06-verify.md)
