# 04: Event — ID-first ครบวันใช้งาน/รับรางวัลและ reward

> สำเนาขอบเขตและ acceptance ต้นฉบับของ ticket ไม่ใช่สถานะปัจจุบันหรือการปิด issue
> ดู [สิ่งที่ส่งมอบแล้วและส่วนที่ยังไม่ยืนยัน](verification-current.md); ไม่ติ๊ก checkboxes เหมารวมจากผล release

## Parent

https://github.com/momozxmo/all-for-cabal/issues/13

## What to build

ผู้ใช้ fill/create Event เดิมด้วย ID-first โดยรักษาวันเวลาใช้งานและรับรางวัล quantity/remaining/limits ชื่อ ภาษา รูปและ Reward Set ใช้ shared widgets ที่พิสูจน์ใน Item Code แทนสร้าง driver ใหม่ และเห็นข้อผิดพลาดที่ปลอดภัยเมื่อระบุ control ไม่ได้

## Acceptance criteria

- [ ] ตรวจ ID/exception ตามเกมและ Event state จริง ไม่คัด ID ของ Item Code หรือ PC SEA ไปเหมารวมทุกเกม
- [ ] Header, switches, redeem type, quantity/remaining, start/end และ redeem start/end กรอกและอ่านกลับถูก control ตามข้อมูลเดิม
- [ ] ภาษาใน editor รูปหลาย input และ reward/picker จับคู่บริบทถูก ไม่ยึด radix/tiny-react ID เป็น stable contract
- [ ] หลาย Reward Set เปิดแท็บที่ถูกและใช้ control ชุดนั้น; date/time ใช้ widgets จาก 03 รวม readback และวินาทีที่ขอ
- [ ] Known ID/exception ผิด contract แสดง control และหยุด ไม่สร้างต่อหลังกรอกไม่ครบ; checkpoint/session behavior เดิมคงอยู่
- [ ] Synthetic API/runner พิสูจน์ DOM mutation, missing/duplicate/wrong-type, lazy mounts และ preview/create/confirm จำลองพร้อมจำนวน submit และไม่ปล่อย traffic จริง
- [ ] Import-to-result/UI flow และสิทธิ์/scope/ส่งต่อเดิมไม่เปลี่ยน พร้อม coverage/gap ที่ไม่อ้าง state ยังไม่ตรวจว่าครบแล้ว

## Blocked by

- https://github.com/momozxmo/all-for-cabal/issues/16 — Shared date/switch/select/picker drivers ที่ผ่าน Item Code และ compatibility tests แล้ว.
