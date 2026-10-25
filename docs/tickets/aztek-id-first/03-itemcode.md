# 03: Item Code — ID-first และ shared widgets ผ่านหลาย Reward Set

> สำเนาขอบเขตและ acceptance ต้นฉบับของ ticket ไม่ใช่สถานะปัจจุบันหรือการปิด issue
> ดู [สิ่งที่ส่งมอบแล้วและส่วนที่ยังไม่ยืนยัน](verification-current.md); ไม่ติ๊ก checkboxes เหมารวมจากผล release

## Parent

https://github.com/momozxmo/all-for-cabal/issues/13

## What to build

ผู้ใช้กรอก/สร้าง Item Code เดิมครบชื่อ ประเภท limits สถานะ วันเวลาและหลาย Reward Set ผ่าน ID-first พร้อม widget drivers สำหรับ date/switch/select/Bundle picker ที่ Event/Product ใช้ร่วมได้ ใช้ no-ID exceptions เฉพาะส่วนภายใน widgets ที่พิสูจน์แล้ว และรักษา consumer ที่ยังไม่ย้าย

## Acceptance criteria

- [ ] มี evidence ต่อ control/game/state สำหรับ header, switches, date triggers, reward fields, tabs, picker และ create/confirm พร้อม gap/exception
- [ ] เปิด active Reward Set และรอ mount ก่อนใช้ ID ของชุดนั้น ไม่กรอกหลายชุดลงชุดแรก และการเลือก Bundle ใช้ business ID ที่ตรงจริง
- [ ] ตั้งวันเวลาและวินาที 59 ตามค่าที่ขอ พร้อมอ่านกลับ; scoped calendar/time exception ไม่หยิบปฏิทินหรือช่องของ field อื่น
- [ ] Shared widget drivers ใช้ ID-first/contract checks และปรับแบบ compatible; Event/Product แบบเดิมยังผ่าน regression ก่อนย้าย consumer
- [ ] ID หาย/ซ้ำ/ผิดชนิดและ fallback หลายเป้าหมายแจ้งช่องและหยุด ไม่กรอกบางส่วนแล้วกดสร้างต่อ
- [ ] Preview submit 0; synthetic create/confirm ครบหลาย reward และหลัง locator failure ไม่ submit ซ้ำหรือทิ้งคิว/checkpoint
- [ ] API/runner จริงกับ synthetic pages ทดสอบ text/class/layout mutation, lazy mounts, portal สองตัวและ active-tab sequencing โดย traffic จริงไม่หลุด
- [ ] User-visible result/errors และ scope/limits/ชื่อ/วันที่จาก import เดิมคงเดิม พร้อม coverage/gap ของ flow นี้

## Blocked by

- https://github.com/momozxmo/all-for-cabal/issues/14 — ID-first lookup path ที่ compatible.
