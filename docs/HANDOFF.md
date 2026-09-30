# ส่งต่องาน All for Cabal

Snapshot: 2026-10-01 — อ่านแล้วตรวจสถานะ Git จริงก่อนแก้ไฟล์เสมอ
ใช้ `git status --short --branch`, `git remote -v` และ `git log -5 --oneline`
เพื่อยืนยัน checkout/branch และแยกไฟล์ผู้ใช้ที่แก้ค้างออกจากงานใหม่

## สถานะล่าสุด

- ผู้ใช้อนุมัติ Setup/commit/push ทั้ง source main และ Local Release;
  กำลังเตรียม v0.1.39 จาก 4 งานด้านล่าง ยังไม่ติดตั้งทับโปรแกรมผู้ใช้
- Item Finder แยก “ส่งเฉพาะที่เลือก (N)” และ “ส่งทั้งหมด (N)”;
  การส่งจาก Product ใช้ขอบเขตกลุ่มที่แสดง ทั้งรีวิวและส่งเข้าคิว
  Regression: `tests/test_web_finder_bundle_handoff_ui.py` รวมไอเทมซ้ำหลาย Bundle
- Bundle มี “Clear ข้อมูล” ล้างข้อความ/พรีวิว/ข้อความแจ้งผล คืน focus
  และคงคิวเดิมไว้; ทิ้งผลพรีวิวที่ตอบกลับหลัง Clear ด้วย revision เดิม
- Bundle RANDOM รองรับเรต `0–100` ทั้งไอเทมและ Currency ตั้งแต่ import,
  preview, queue, API จนกรอก stable ID บน Aztek; ศูนย์ไม่ใช่ช่องว่าง
  การนำเข้ายังบังคับผลรวม `100%` และปฏิเสธค่าติดลบ/เกิน 100/ทศนิยมเกิน 3 ตำแหน่ง
- Currency บนหน้า Bundle แสดงชื่อเต็มแยกบรรทัดและ wrap ชื่อยาว;
  แก้ CSS เฉพาะ `body[data-btype] .rwrow` คงค่าคิว/API และพฤติกรรมเดิม
  Regression: `tests/test_web_bundle_rewards_ui.py` ครอบคลุม FIXED/RANDOM,
  Credit/Debit/Player EXP, จำนวน/Rarity/เรต 0, Keyboard/visible focus,
  เลือกและลบแถว และ Overflow ที่ 360/768/1280/1600px
- Full suite รอบก่อน release: **1,701 passed, 1 warning in 653.30s**
  (`python -X utf8 -B -m pytest tests -q --basetemp=<leaf ใหม่ใน build-cache>`)
  warning เดิมเรื่อง process-local development secrets
- คง Document Reference จากเอกสารต้นฉบับไว้ครบ;
  หากเลือกส่งเพียงบางรายการ Bundle Recheck อาจรายงานรายการขาดตามเอกสาร
- รุ่นเผยแพร่ก่อนงานนี้: [v0.1.38](https://github.com/momozxmo/tool-cabal-local/releases/tag/v0.1.38)
  หลักฐานอยู่ใน [local-release-v0.1.38.md](local-release-v0.1.38.md)
  รวม Bundle Recheck #9–#11, stable ID เรท RANDOM และตัวเลือกเบราว์เซอร์ Launcher แล้ว
- เตรียมเครื่อง/เปิดโหมดพัฒนาแยกข้อมูลจากโปรแกรมที่ติดตั้ง:
  [MULTI_COMPUTER_DEV.md](MULTI_COMPUTER_DEV.md)
  Launcher ใช้ Default/Chrome/Edge/Firefox และขอสิทธิ์เข้าเว็บใหม่ทุกครั้ง;
  ร่าง/คิวในเบราว์เซอร์ไม่ย้ายตาม ดู [LOCAL_INSTALL.md](LOCAL_INSTALL.md#เลือกเบราว์เซอร์)

## ขอบเขตและจุดที่ยังไม่ยืนยัน

- ใช้ภาษาไทย คง workflow และเลือกวิธีเรียบง่าย
- สร้างข้อมูลจริงบน Aztek และ build/commit/push/publish เมื่อผู้ใช้สั่งชัดเจน
- รักษาไฟล์แก้ค้างของผู้ใช้; stage เฉพาะงาน เก็บข้อมูลลับ/ข้อมูลผู้ใช้ไว้นอก Git
- Recheck ที่ต้นทางไม่ครบหรืออ่าน exact currency code ไม่ได้ยังเป็นผลบางส่วน;
  ไม่เดาให้ผ่าน และการยืนยันทำต่อไม่เปลี่ยนผลตรวจ
- ยังไม่ทดสอบติดตั้งบน clean VM หรือสร้างจริงบน Aztek สำหรับงานแก้ใหม่นี้
  การติดตั้งอัปเดตและร่าง/คิวต้องตรวจหลังผู้ใช้เลือกอัปเดตเอง

## เวลาอัปเดต handoff นี้

ก่อนส่งข้ามเครื่อง ให้ระบุสถานะปัจจุบัน commit/issue งานค้าง ผลทดสอบ ข้อจำกัด
และลิงก์หลักฐาน โดยไม่สะสมประวัติแชทหรือ secrets
