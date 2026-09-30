# ส่งต่องาน All for Cabal

Snapshot: 2026-09-30 — อ่านแล้วตรวจสถานะ Git จริงก่อนแก้ไฟล์เสมอ
ใช้ `git status --short --branch`, `git remote -v` และ `git log -5 --oneline`
เพื่อยืนยัน checkout/branch และแยกไฟล์ผู้ใช้ที่แก้ค้างออกจากงานใหม่

## สถานะล่าสุด

- งาน Bundle Recheck #9–#11 เสร็จใน source commit `71fffad` รวมการอ่านกลับ,
  history/retry และการยืนยันก่อนส่งต่อ; รวมการแก้ selector เรท RANDOM แบบ ID
- รุ่นเผยแพร่: [v0.1.38](https://github.com/momozxmo/tool-cabal-local/releases/tag/v0.1.38)
  หลักฐาน build/test/hash อยู่ใน [local-release-v0.1.38.md](local-release-v0.1.38.md)
- เพิ่มคำสั่งเตรียมเครื่องและเปิดโหมดพัฒนาแยกข้อมูลจากโปรแกรมที่ติดตั้งไว้:
  [MULTI_COMPUTER_DEV.md](MULTI_COMPUTER_DEV.md)
- Launcher source commit `673bd82`: เลือก Default/Chrome/Edge/Firefox,
  จำตัวที่เปิดสำเร็จล่าสุด และขอ bootstrap token ใหม่ทุกครั้ง
  รายละเอียดการใช้และข้อจำกัดร่าง/คิวอยู่ใน [LOCAL_INSTALL.md](LOCAL_INSTALL.md#เลือกเบราว์เซอร์)
- ทดสอบเฉพาะ Launcher/local access: **36 passed**;
  Chrome/Edge จริงแบบ headless ด้วยโปรไฟล์ชั่วคราวผ่าน bootstrap และหน้า
  account/bundles/itemcodes/events/products; session แรกยังอยู่หลังเปิดตัวที่สอง
  Firefox ไม่ติดตั้งบนเครื่องนี้ ตรวจการเรียก executable ด้วย test double เท่านั้น
- Full build-time suite: **1,662 passed, 2 warnings in 532.93s**;
  warnings เป็น development secrets และ pytest cache เขียนไม่ได้
  แพ็กเกจจริงผ่าน bootstrap, ทุกหน้าเครื่องมือ และ shortcut ซ้ำ ด้วย runtime แยก
  updater ดาวน์โหลด v0.1.38 กลับจาก GitHub แล้ว size/hash ตรงกับ build
- ตรวจคำสั่งเตรียมเครื่องจริงและรันซ้ำบน Windows นี้ผ่าน; `.venv` ใช้ Python 3.12.9,
  FastAPI 0.128.7, Starlette 0.52.1 และ Playwright 1.63.0
- Full suite หลังเพิ่มตัวเลือกเบราว์เซอร์ใน `.venv`: **1,662 passed, 2 warnings in 580.74s**;
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
- รุ่น v0.1.38 ยังไม่ทดสอบติดตั้งบน clean VM หรือสร้างจริงบน Aztek
  การติดตั้งอัปเดตและร่าง/คิวบนเครื่องผู้ใช้ต้องตรวจหลังผู้ใช้เลือกอัปเดตเอง

## เวลาอัปเดต handoff นี้

แก้สถานะข้างบนให้เป็น snapshot ใหม่ก่อนส่งงานข้ามเครื่อง:
ระบุ commit/issue ที่เกี่ยวข้อง, งานค้างที่ทำต่อได้, ผลทดสอบและข้อจำกัด
เก็บเฉพาะสถานะปัจจุบันและลิงก์หลักฐาน ไม่สะสมประวัติแชทหรือ secrets
