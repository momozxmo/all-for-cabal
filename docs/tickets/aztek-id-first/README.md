# Aztek ID-first — สถานะและชุด tickets

อัปเดตสถานะ: 25 ตุลาคม 2026

## อ่านสถานะปัจจุบันจากหน้านี้

[สรุปสิ่งที่ส่งมอบแล้ว หลักฐาน และงานที่ยังไม่ยืนยัน](verification-current.md)

- ส่งมอบชุดรวมใน [v0.1.41](https://github.com/momozxmo/tool-cabal-local/releases/tag/v0.1.41) แล้ว: Item Finder/Bundle พร้อม Event/Product/Item Code ID-first ล่าสุด และปุ่มบันเดิลต่อเนื่อง
- Full ของ source ชุดรวม: **2,749 passed, 1 warning**; ตรวจแพ็กเกจและดาวน์โหลดไฟล์เผยแพร่กลับมาเทียบขนาด/SHA-256 แล้ว
- ตรวจ [acceptance20ข้อของ#13และ9ข้อของ#19](acceptance-v041.md) พร้อม [control/game/state coverageและDEVgaps](coverage-v041.md) แล้ว ไม่ต้องรอDEVเพิ่มIDครบทุกnodeหรือสร้างข้อมูลบริษัทใหม่
- ไม่ได้หมายความว่าทุก control มี HTML ID ถาวร หรือทุก live game/state ได้รับการยืนยันแล้ว
- ยังไม่ยืนยันการอัปเดต/เปิดกลับ/ร่างและคิวบนโปรแกรมของผู้ใช้;remoteclosure#13/#19เป็นขั้นตอนที่ผู้ใช้อนุญาตแยกเมื่อครบเกณฑ์ ตรวจสถานะจริงก่อนอ้างปิดแล้ว
- ไม่มี live Aztek action เพิ่มเติม และ New Item #12 ยังพักไว้
- หลักฐานส่งมอบ: [combined source](../../id-first-combined-release-20261024.md) / [release verification](../../local-release-v0.1.41.md)

## ขอบเขตต้นฉบับของ tickets

ตารางนี้คือลำดับและขอบเขตงานที่ออก ticket ไว้ ไม่ใช่สถานะว่าแต่ละ issue ปิดแล้ว
Checkbox01–05คงต้นฉบับ;06อัปเดตจากacceptanceauditรายข้อ ไม่ติ๊กเหมารวมจากผลrelease ดูผลและข้อจำกัดจากหน้าสรุปด้านบน

| Ticket | ขอบเขตต้นฉบับ | เอกสาร |
| --- | --- | --- |
| #14 | Item Finder | [01-item-finder](01-item-finder.md) |
| #15 | Bundle และ Recheck | [02-bundle](02-bundle.md) |
| #16 | Item Code และ shared widgets | [03-itemcode](03-itemcode.md) |
| #17 | Event | [04-event](04-event.md) |
| #18 | Product | [05-product](05-product.md) |
| #19 | Cross-flow regression และ coverage | [06-verify](06-verify.md) |

## ประวัติและรายการ DOM

- [สถานะเดิมถึง 8 ตุลาคม — เก็บข้อความต้นฉบับทั้งหมด](README-history-20261008.md)
- [coverage snapshot เดิม](coverage.md): เก็บหลักฐานและข้อจำกัดของช่วงเวลานั้น ไม่ใช่สถานะ release ล่าสุด
- หลักฐาน DOM เก่าไม่ยืนยันว่าเว็บไซต์สดวันนี้ยังเหมือนเดิม และ business record ID ไม่ใช่ HTML element ID
- ข้อความเดิมว่า “ยังไม่ implement / ยังไม่ Setup / ยังไม่ commit/push” อยู่ในประวัติ ไม่ใช่งานที่ต้องเริ่มใหม่หลัง v0.1.41
