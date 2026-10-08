# 02: Bundle — สร้างและรีเช็คตาม ID-first ครบ Item/Currency/EXP

## Parent

https://github.com/momozxmo/all-for-cabal/issues/13

## What to build

ผู้ใช้ fill/create Bundle และดู Bundle Recheck ผ่าน flow เดิมได้ถูกแถว ทั้ง Item, Currency, EXP และ RANDOM โดยใช้ stable ID เมื่อมี การอ่านกลับใช้หลักเดียวกับการกรอกและไม่เปลี่ยนผลผ่านเมื่อหา control ไม่ครบ Locator failure รักษา checkpoint และไม่กดสร้างซ้ำ

## Acceptance criteria

- [ ] ตรวจ ID/scope/state ของชื่อ ประเภท ส่งทันที search/add, reward card, Quantity/Tier, rate, create/confirm และ saved Bundle/Item detail พร้อม exceptions/gap
- [ ] หลาย Item/Currency/EXP เพิ่ม/ลบ/เรียงแล้ว Quantity/Tier/ID จับคู่ card จริง ไม่ใช้ดัชนีเก่าหรือหน้า-wide selector แทน identity
- [ ] RANDOM rate 0 ลง actual draw chance ไม่ใช่ display rate และตัวอ่านกลับแยกสองค่านี้ตามพฤติกรรมเดิม
- [ ] Known ID contract เสียหรือ exception กำกวมหยุดก่อนบันทึก; ใน readback ให้ตรวจไม่ครบ/ไม่สำเร็จ ไม่เปลี่ยนเป็น Recheck Outcome ผ่าน
- [ ] Document Reference, Submitted Bundle Values และ Recheck History เดิมรักษาไว้ ไม่แก้ source/เกณฑ์ส่งต่อจากงาน locator
- [ ] Preview submit 0; create/confirmation จำลองชี้ action ถูก; failure หลัง submit รักษา ID/checkpoint/ผลไม่แน่นอน ไม่ auto-resubmit
- [ ] Synthetic API/runner ครบกรณี DOM mutation, misleading fallback, repeated row, ID มีจุด, missing/duplicate/wrong-type และอ่านกลับไม่ตรง พร้อมตรวจจำนวน submit
- [ ] UI แสดงผล/ข้อผิดพลาดเดิมอย่างเข้าใจได้และ coverage/gap ครบ โดยไม่สร้างข้อมูลจริงบน Aztek

## Blocked by

- https://github.com/momozxmo/all-for-cabal/issues/14 — Item Finder และ ID-first lookup path ที่ compatible.
