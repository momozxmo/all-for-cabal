# 06: ID-first — ปิด regression ทั้ง flow และสรุป coverage/gap

> ขอบเขตเดิมคงไว้; acceptance9ข้อตรวจรายข้อ25ตุลาคม2026แล้ว ดู [หลักฐานและขอบเขต](acceptance-v041.md)
> Checkboxesมาจากauditพร้อมretainedfull2749/coverage ไม่ใช่คำรับรองทุกlivevariant และไม่แทนการอ่านสถานะremoteจริง

## Parent

https://github.com/momozxmo/all-for-cabal/issues/13

## What to build

ยืนยันว่าเส้นทางผู้ใช้ Item Finder → Bundle/รีเช็ค → ส่งต่อ Item Code/Event/Product ยังคงทำงานเดิมหลังทุก slice ใช้ ID-first โดยตรวจการหยุด/กู้สถานะและไม่ส่งผลที่ยังตรวจไม่ผ่าน พร้อมรายงาน coverage และ no-ID gap สำหรับ DEV และคงกฎใช้ ID สำหรับทุกฟังก์ชันใหม่

## Acceptance criteria

- [x] รัน cross-flow ด้วย API/runner จริงและ synthetic Aztek ตลอดทางรวม DOM mutation โดยไม่มี traffic/record จริง
- [x] Selection-only handoff และไอเทมซ้ำหลาย Bundle รักษา occurrence/Amt/source; ไม่ดึงรายการที่ไม่ได้เลือก
- [x] Locator failure ก่อน submit ไม่บันทึก หลัง submit รักษา checkpoint/ID/ผลสร้าง/ผลตรวจ; retry/readback ไม่เพิ่มจำนวน submit
- [x] Recheck ที่อ่านไม่ครบไม่ผ่าน และเกณฑ์ส่งต่อเดิมไม่ถูก bypass จาก migration; การรับทราบไม่เปลี่ยนผลเป็นผ่าน
- [x] Regression ทุก flow/shared widget ผ่าน และข้อความผิดพลาด/ผลลัพธ์แสดงตามพฤติกรรมเดิมในโปรแกรม local
- [x] รายงาน coverage แยกตาม flow/control/game/state: ย้ายเป็น ID, exception, unknown พร้อม DEV gap; PC/M TH/SEA ต้องมีหลักฐานหรือระบุยังไม่พิสูจน์ ไม่อ้างเกมเดียวแทนทั้งหมด
- [x] Unknown ที่กั้นการย้ายอย่างปลอดภัยต้องรายงานว่าไม่เสร็จในส่วนนั้น ไม่ลด contract เพื่ออ้าง migration ครบ
- [x] คำสั่งโปรเจกต์และ locator policy ครอบคลุมฟังก์ชันใหม่ ไม่สร้าง framework เพิ่ม และ New Item #12 ยังไม่เริ่ม/ไม่เปลี่ยน remote issue
- [x] ไม่มี Setup/commit/push หรือข้อมูล Aztek จริงจาก ticket นี้โดยไม่มีคำสั่งแยก

## Blocked by

- https://github.com/momozxmo/all-for-cabal/issues/15 — Bundle create/readback.
- https://github.com/momozxmo/all-for-cabal/issues/17 — Event.
- https://github.com/momozxmo/all-for-cabal/issues/18 — Product.
