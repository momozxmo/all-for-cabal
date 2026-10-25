# 01: Item Finder — flow ID-first แรกและหยุดอย่างปลอดภัย

> สำเนาขอบเขตและ acceptance ต้นฉบับของ ticket ไม่ใช่สถานะปัจจุบันหรือการปิด issue
> ดู [สิ่งที่ส่งมอบแล้วและส่วนที่ยังไม่ยืนยัน](verification-current.md); ไม่ติ๊ก checkboxes เหมารวมจากผล release

## Parent

https://github.com/momozxmo/all-for-cabal/issues/13

## What to build

ผู้ใช้ค้น/filter/อ่านผลและเปลี่ยนหน้าจาก Item Finder เดิมได้ด้วย stable ID ที่พิสูจน์ พร้อมข้อความที่เข้าใจได้เมื่อ control ผิด contract แทนการเดาเลือกตัวแรก ปรับ lookup/scope/readiness ที่ใช้ร่วมเท่าที่จำเป็นโดยไม่เปลี่ยน framework เพื่อเป็น ID-first path ที่ flow อื่นนำไปใช้ได้ ตัวเรียกเดิมยังทำงานระหว่างทยอยย้าย

## Acceptance criteria

- [ ] ตรวจ control/game/state ใน flow นี้และแยก stable ID, no-ID exception และ unknown; รวม helper ที่ web เรียกจากโมดูล root จริง
- [ ] ค้น/filter Option/Duration/read detail/result/pagination ถูกต้องตาม identity/ข้อมูลเดิม ไม่ทำ occurrence หรือ source หาย
- [ ] ID lookup มี priority จริง เมื่อมี fallback node มาก่อนใน DOM ยังใช้ ID ที่ตั้งใจ; ID มี punctuation ชี้ถูก element
- [ ] Readiness มี timeout และ scope/role/type/uniqueness ชัดเจน; ID หาย/ซ้ำ/ผิดชนิดหรือ fallback กำกวมทำให้ error ที่เห็นผ่าน API/หน้าเดิม ไม่ใช้ first-match กลบปัญหา
- [ ] Prefactor เฉพาะส่วนจำเป็นแบบ compatible โดย API/consumer ที่ยังไม่ย้ายและการจับงานทับเดิมไม่เสีย
- [ ] API + runner จริงกับ synthetic Aztek ยืนยัน DOM text/class/order เปลี่ยนแต่ ID คงเดิมยังค้น/อ่านถูก; ไม่มี external traffic จริง
- [ ] ผลค้นหา selection และส่งต่อ Bundle เดิมไม่เปลี่ยน การหยุดจาก locator ไม่ทำร่างหรือคิวหาย
- [ ] กฎฟังก์ชันใหม่ในคำสั่งโปรเจกต์คงอยู่ และ coverage/gap ของ flow นี้บันทึกครบก่อนถือว่างานเสร็จ

## Blocked by

None (can start immediately after implementation is authorized).
