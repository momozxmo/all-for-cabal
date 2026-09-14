# All for Cabal Update — ผลตรวจ 2026-09-14

Checkout: `.worktrees/codex-web-auth`, branch `codex/local-windows-installer`
จุดเริ่มต้น: `5cfa892a12202f4b40b84375069c1c31ef11fba6`

## Automated tests

- Full suite: **1,455 passed, 1 warning**, 315.17 วินาที ก่อนแก้ข้อพบจากรีวิว
- หลังแก้รีวิว: **39 passed** ครอบคลุม Local update UI/API, helper, launcher, browser gate และ Local access
- `python -m compileall -q local_app web` และ `node --check web/static/updates.js`: ผ่าน
- เทสต์ใหม่ตรวจผ่านพฤติกรรม UI/API และขอบระบบไฟล์/เวลา/เครือข่าย/process ไม่เรียกสร้างข้อมูลจริงบน Aztek
- Warning เดิมจากการทดสอบ development settings ไม่ใช่ updater failure

## Code review

Standards: ไม่พบการละเมิดมาตรฐานที่เขียนไว้ พบ reliability 2 ข้อและแก้แล้ว:
ปุ่มลองใหม่หลัง handled error และแท็บปิดผิดปกติค้างกั้นอัปเดต

Spec: พบ 3 ข้อและแก้แล้ว: กดไว้ก่อนระหว่างดาวน์โหลดยังติดตั้งต่อ,
ปุ่มลองใหม่ และการไม่อ่านผลครั้งก่อนหลังเปิดใหม่ การตรวจซ้ำไม่พบ findings เดิมค้าง

การนำแท็บไม่ตอบสนองออกต้องยืนยันว่าปิดแท็บและจัดการงานแล้ว Backend ไม่ยอมนำ
แท็บที่กลับมาเชื่อมต่อออกเอง ไม่ทิ้งร่างจากแท็บที่เงียบโดยอัตโนมัติ

## Windows integration smoke

พื้นที่ทดสอบแยก: `<project-root>/.codex-tmp/u` ไม่ใช่โฟลเดอร์ production
ใช้ Inno Setup จริงที่มี AppId ทดสอบเฉพาะ ไม่มี shortcut หรือ uninstall registry
ใช้ข้อมูลจำลองที่ `u/userdata/AllForCabalWeb` และไม่ใช้ session Aztek ของผู้ใช้

1. PyInstaller build โปรแกรมและ standalone helper ผ่าน; release tree scan ผ่าน
2. ติดตั้ง Setup ทดสอบ **0.1.31** ใน `u/installed` สำเร็จ (exit 0)
3. เปิด source Local runtime harness จากโค้ดชุดเดียวกัน อ่านเลขรุ่นจากแพ็กเกจ
   ที่ติดตั้งไว้ โดยแทนเฉพาะ GitHub transport ด้วยแพ็กเกจ **0.1.32** ที่สร้างแยก
4. เปิด Bundle จริงด้วย Chromium และสร้างร่าง `Windows smoke draft preserved`
5. checksum จำลองไม่ตรง: ไฟล์ถูกปฏิเสธ รุ่น **0.1.31** ยังตอบ health และร่างยังอยู่
6. กดใหม่หลังหน้าโหลดเสร็จและยืนยันงานว่าง: download → prepare → install สำเร็จ
7. `LocalServer.install_update` หยุด server จริง แล้วเปิด helper ที่ build แล้ว;
   helper รอ parent ออก เรียก Setup จริง และเปิด **packaged Launcher 0.1.32**
8. helper รายงาน `success`, health คืน `all-for-cabal-local` และ version `0.1.32`
9. หน้า Bundle โหลดกลับและร่างเดิมยังอยู่; config bytes เดิมและแถว AztekSession
   จำลองในฐานข้อมูลยังถอดรหัสเป็นข้อมูล fixture เดิมได้

หลักฐานเฉพาะเครื่อง: `u/windows-update-passed.png`, `u/base-package.log`,
`u/target-package.log`, `u/userdata/AllForCabalWeb/updates/result.json`
ไฟล์เหล่านี้เป็น artifact ทดสอบ ไม่รวมใน commit/Release

ข้อจำกัด: การส่งคำสั่งเริ่มอัปเดตใช้ source runtime harness ไม่ใช่ UI ของ
packaged Launcher รุ่นเริ่มต้นทั้งชุด เครือข่าย GitHub ถูกแทนด้วย transport
ทดสอบ การทดสอบนี้ไม่ใช่ clean VM Windows ที่ไม่มีเครื่องมือพัฒนา
ก่อนแจกวงกว้างยังควร smoke บนเครื่องสะอาดพร้อม Release จริง

## สถานะส่งมอบ

โค้ดและคู่มือผ่านขั้นตรวจเพื่อสร้าง Release v0.1.31 ตามคำสั่งผู้ใช้แล้ว
การเผยแพร่ใช้ Setup ที่สร้างจาก source snapshot `eddcdd3`
ผู้ใช้เดิมต้องลง Setup ที่เพิ่ม updater อีกครั้งก่อนอัปเดตผ่านโปรแกรมได้
