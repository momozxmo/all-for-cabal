# 05: Product — ID-first ครบ Currency/ราคา/รูป/Bundle/Primary

> สำเนาขอบเขตและ acceptance ต้นฉบับของ ticket ไม่ใช่สถานะปัจจุบันหรือการปิด issue
> ดู [สิ่งที่ส่งมอบแล้วและส่วนที่ยังไม่ยืนยัน](verification-current.md); ไม่ติ๊ก checkboxes เหมารวมจากผล release

## Parent

https://github.com/momozxmo/all-for-cabal/issues/13

## What to build

ผู้ใช้ fetch options, fill และ create Product เดิมได้ผ่าน ID-first ตั้งแต่ Category/Currency ที่ fetch จริง หลายราคา รูป ภาษา วันเวลาและ Bundle/Primary ใช้ shared widgets จาก 03 และรักษาการเลือก option ด้วย business value ไม่เปลี่ยนเป็นเดาข้อความ

## Acceptance criteria

- [ ] พิสูจน์ Product create ที่ตรวจสดรอบก่อนยัง blank ให้ได้ก่อนย้ายส่วนที่ยังไม่มีหลักฐาน พร้อม ID/exception/scope ของแต่ละเกมและ state
- [ ] Fetch/เลือก Currency และ Category คง actual option values ไม่สับสน element ID กับ server ID หรือเลือก purchase-limit select ผิด
- [ ] หลาย price row เพิ่ม/ลบ/เรียงแล้ว Qty/ราคา/Currency ถูกแถว; รูปและภาษา editor ถูกตำแหน่ง/บริบทที่พิสูจน์ ไม่ cached index เก่า
- [ ] Date/time/limits/switches ใช้ shared widgets จาก 03 พร้อม readback; หลาย Bundle และ Primary ไม่เปลี่ยนจากที่ผู้ใช้เลือก
- [ ] Known stable ID/exception กำกวมหรืออ่านค่ากลับไม่ครบแสดงปัญหาและหยุด ไม่ทำ partial form เป็นสำเร็จหรือกดสร้างต่อ
- [ ] Synthetic API/runner ตรวจ DOM mutation, misleading fallback, missing/duplicate/wrong-type และหลาย price/Bundle พร้อม submit/checkpoint ที่ไม่สร้างซ้ำ
- [ ] Preview submit 0 และฟอร์ม/UI/validation/ภาพที่ส่งจริงยังตรงพฤติกรรมเดิม พร้อม coverage/gap; ไม่สร้างข้อมูล Aztek จริง

## Blocked by

- https://github.com/momozxmo/all-for-cabal/issues/16 — Shared date/switch/select/picker drivers ที่ compatible.
