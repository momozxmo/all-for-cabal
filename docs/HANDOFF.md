# ส่งต่องาน All for Cabal

Snapshot: 2026-09-30 — อ่านแล้วตรวจสถานะ Git จริงก่อนแก้ไฟล์เสมอ
ใช้ `git status --short --branch`, `git remote -v` และ `git log -5 --oneline`
เพื่อยืนยัน checkout/branch และแยกไฟล์ผู้ใช้ที่แก้ค้างออกจากงานใหม่

## สถานะล่าสุด

- งาน Bundle Recheck #9–#11 เสร็จใน source commit `71fffad` รวมการอ่านกลับ,
  history/retry และการยืนยันก่อนส่งต่อ; รวมการแก้ selector เรท RANDOM แบบ ID
- รุ่นเผยแพร่: [v0.1.37](https://github.com/momozxmo/tool-cabal-local/releases/tag/v0.1.37)
  หลักฐาน build/test/hash อยู่ใน [local-release-v0.1.37.md](local-release-v0.1.37.md)
- เพิ่มคำสั่งเตรียมเครื่องและเปิดโหมดพัฒนาแยกข้อมูลจากโปรแกรมที่ติดตั้งไว้:
  [MULTI_COMPUTER_DEV.md](MULTI_COMPUTER_DEV.md)
- ตรวจ setup จริงและรันซ้ำบนเครื่อง Windows นี้ผ่าน; `.venv` ใหม่ใช้ Python 3.12.9,
  FastAPI 0.128.7, Starlette 0.52.1 และ Playwright 1.63.0
- Full suite ใน `.venv` ใหม่: **1,648 passed, 2 warnings in 580.93s**;
  warnings เป็น AnyIO deprecated alias และกรณีทดสอบ process-local secrets
  isolated Local migration/session/API smoke ผ่านทุกหน้าเครื่องมือ
  ยังไม่ได้รันคำสั่งบนคอมอีกเครื่องหรือ clean VM
- ณ snapshot นี้ไม่มีงานแก้โค้ดที่ต้องเริ่มต่ออัตโนมัติ รับคำขอถัดไปจากผู้ใช้

## ขอบเขตและจุดที่ยังไม่ยืนยัน

- ใช้ภาษาไทยในการคุยกับผู้ใช้ คง workflow ที่มีอยู่ และเลือกวิธีเรียบง่าย
- สร้างข้อมูลจริงบน Aztek และ build/commit/push/publish ได้เมื่อผู้ใช้สั่งชัดเจนเท่านั้น
- รักษาไฟล์แก้ค้างของผู้ใช้; stage เฉพาะไฟล์ของงาน เก็บข้อมูลลับ/ข้อมูลผู้ใช้ไว้นอก Git
- Recheck ที่ไม่มีข้อมูลต้นทางหรืออ่าน exact currency code ไม่ได้ยังเป็นผลบางส่วน
  ไม่เปลี่ยนให้ผ่านโดยเดา; การยืนยันทำต่อไม่เปลี่ยนผลตรวจ
- รุ่น v0.1.37 ยังไม่ทดสอบติดตั้งบน clean VM หรือสร้างจริงบน Aztek
  การติดตั้งอัปเดตและร่าง/คิวบนเครื่องผู้ใช้ต้องตรวจหลังผู้ใช้เลือกอัปเดตเอง

## เวลาอัปเดต handoff นี้

แก้สถานะข้างบนให้เป็น snapshot ใหม่ก่อนส่งงานข้ามเครื่อง:
ระบุ commit/issue ที่เกี่ยวข้อง, งานค้างที่ทำต่อได้, ผลทดสอบและข้อจำกัด
เก็บเฉพาะสถานะปัจจุบันและลิงก์หลักฐาน ไม่สะสมประวัติแชทหรือ secrets
