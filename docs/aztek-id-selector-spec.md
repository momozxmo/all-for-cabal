# Aztek ID-first Automation — Specification

วันที่: 2026-10-01
ฐานข้อกำหนด: ยืนยัน Q1–Q4 และเพิ่มกฎใช้ ID สำหรับฟังก์ชัน Aztek ใหม่ทุกตัว
แนวทดสอบ: Q4 ที่ผู้ใช้ยืนยัน — synthetic Aztek และตรวจเว็บจริงแบบ read-only
สถานะ: พร้อมแตกงาน; ไม่ใช่คำสั่งเริ่ม implementation หรือสร้างข้อมูลจริง

## Problem Statement

Tools ใช้ข้อความ label, placeholder, class, ตำแหน่งแถวและ DOM ancestry ในหลาย flow ของ Aztek เมื่อเว็บเปลี่ยนข้อความหรือ layout การค้นหาและกรอกข้อมูลอาจหา control ไม่เจอ หรือเลือกผิดช่อง DEV แจ้งว่า ID ที่ดูแลจะคงเดิม แต่ปัจจุบันบาง control ไม่มี ID และบาง ID ถูก framework สร้าง การแทน selector ทุกตัวด้วย ID โดยไม่ตรวจ scope จึงไม่ปลอดภัย ผู้ใช้ต้องการลดความเปราะบางของ flow เดิม และกำหนดให้ฟังก์ชันใหม่ใช้ ID ตั้งแต่แรกเมื่อมี ID คงที่

## Solution

ย้าย Aztek automation ที่โปรแกรม local ใช้งานจริงเป็น ID-first โดยรักษาพฤติกรรมเดิม ครอบคลุม Item Finder, Bundle/Bundle Recheck, Item Code, Event, Product และ shared helpers ทั้ง CABAL PC/M TH/SEA ใช้ ID คงที่ที่ตรวจจากหน้าและสัญญาของ DEV เป็นหลัก ไม่เดาตำแหน่งเมื่อ ID ที่ควรมีหาย/ซ้ำ/ผิดชนิด

Control ที่ไม่มี ID ตั้งแต่แรกใช้ fallback เฉพาะจุดที่ตรวจแล้วและเจาะจงกับ form/แถว/dialog พร้อมรายการให้ DEV เพิ่ม ID ไม่ยึด ID ที่ framework สร้างเป็นค่าถาวร ไม่อ้างว่าทุก control ใช้ ID ได้แล้ว เก็บกฎนี้ในคำสั่งโปรเจกต์ให้ทุกฟังก์ชัน Aztek ใหม่ใช้ตั้งแต่เริ่ม รวม New Item เมื่อกลับมาทำงานนั้น โดยยังพัก spec #12 ไว้

## User Stories

1. ในฐานะผู้ใช้ Item Finder ฉันต้องการให้การค้นหาไม่พังเมื่อข้อความหรือ layout เปลี่ยนแต่ ID เดิมยังอยู่ เพื่อหาข้อมูลได้ต่อเนื่อง
2. ในฐานะผู้ใช้ Item Finder ฉันต้องการให้ตัวกรอง Option/Duration ชี้ถูกช่อง เพื่อไม่ค้นหาด้วยค่าที่ผิด
3. ในฐานะผู้ใช้ Item Finder ฉันต้องการให้การอ่านผลและเปลี่ยนหน้ามีเป้าหมายที่แน่นอน เพื่อไม่ดึงคอลัมน์หรือหน้าผิด
4. ในฐานะผู้สร้าง Bundle ฉันต้องการให้ชื่อ ประเภทและสถานะส่งของชี้ถูก control เพื่อรักษาข้อมูลที่ตั้งใจ
5. ในฐานะผู้สร้าง Bundle ฉันต้องการให้ Amount/Tier ผูกกับแถวถูกต้อง เพื่อไม่กรอกค่าข้ามไอเทม
6. ในฐานะผู้สร้าง RANDOM Bundle ฉันต้องการให้ rate 0 และค่าที่ระบุไปยัง draw chance จริง เพื่อไม่สับสนกับเรตแสดงผล
7. ในฐานะผู้สร้าง Currency/EXP reward ฉันต้องการให้เลือกชนิด Qty และ Tier ถูก card เพื่อรักษารางวัลที่ตั้งใจ
8. ในฐานะผู้ตรวจ Bundle ฉันต้องการให้ตัวอ่านกลับใช้ ID คงที่เช่นเดียวกับตัวกรอก เพื่อไม่สร้างถูกแต่ตรวจผิดจาก DOM เปลี่ยน
9. ในฐานะผู้ตรวจ Bundle ฉันต้องการให้การหา control ไม่ได้เป็นผลตรวจไม่ครบ ไม่ใช่ผ่าน เพื่อไม่ส่งต่อข้อมูลที่ยังพิสูจน์ไม่ได้
10. ในฐานะผู้สร้าง Item Code ฉันต้องการให้ชื่อ ประเภท limit สถานะและวันเวลายังคงกรอกถูกเมื่อ label เปลี่ยน เพื่อไม่ต้องแก้คิวใหม่
11. ในฐานะผู้สร้าง Item Code หลาย Reward Set ฉันต้องการให้เปิดแท็บและใช้ช่องของชุดนั้น เพื่อไม่เขียนค่าลงชุดแรกทั้งหมด
12. ในฐานะผู้สร้าง Event ฉันต้องการให้วันเวลาใช้งาน/รับรางวัลและจำนวนรวม/คงเหลือชี้ถูกช่อง เพื่อรักษาช่วงเวลาและโควตาเดิม
13. ในฐานะผู้สร้าง Product ฉันต้องการให้ Category/Currency ใช้ control และ option ของข้อมูลที่ถูกต้อง เพื่อไม่เลือกสกุลเงินผิด
14. ในฐานะผู้สร้าง Product ฉันต้องการให้ราคาหลายแถวและรูปแต่ละตำแหน่งยังจับคู่ถูก เพื่อไม่ใส่ไฟล์หรือราคาข้ามรายการ
15. ในฐานะผู้สร้าง Product ฉันต้องการให้ Bundle และ Primary ถูกต้อง เพื่อไม่เปลี่ยนสินค้าจากการย้าย locator
16. ในฐานะผู้ใช้ ฉันต้องการให้ปฏิทินยังตั้งวันและวินาทีได้ครบ เพื่อไม่เปลี่ยนเวลาสิ้นสุดหลังย้าย selector
17. ในฐานะผู้ใช้ ฉันต้องการให้ปุ่มสร้าง/ยืนยันชี้ที่คำสั่งใน form/dialog ที่ถูกต้อง เพื่อไม่กด action อื่น
18. ในฐานะผู้ใช้ ฉันต้องการให้ช่องที่ไม่มี ID ยังทำงานผ่านวิธีสำรองที่ตรวจแล้ว เพื่อไม่หยุดทุก flow เพียงเพราะ Aztek ยังไม่มี ID ครบ
19. ในฐานะผู้ใช้ ฉันต้องการให้ ID ที่ควรมีแต่หายหรือซ้ำทำให้หยุดอย่างเข้าใจได้ เพื่อไม่เสี่ยงกรอกผิดช่องหรือสร้างข้อมูลผิด
20. ในฐานะผู้ใช้ ฉันต้องการรักษาคิวและผลบันทึกเมื่อ locator มีปัญหา เพื่อทำต่อโดยไม่สร้างซ้ำ
21. ในฐานะผู้ใช้ ฉันต้องการให้ selector migration ไม่เปลี่ยนเกม การเลือก scope และสิทธิ์ส่งต่อ เพื่อคงพฤติกรรมที่ใช้ได้อยู่
22. ในฐานะผู้ใช้ PC/M TH/SEA ฉันต้องการให้การรองรับแต่ละเกมมีหลักฐานจริง เพื่อไม่ใช้ ID จากเกมเดียวแทนทุกเกมโดยเดา
23. ในฐานะผู้พัฒนา ฉันต้องการให้ฟังก์ชันใหม่ทุกตัวใช้ stable element ID เมื่อมี เพื่อไม่เพิ่ม selector เปราะบางกลับมาอีก
24. ในฐานะผู้พัฒนา ฉันต้องการให้ข้อยกเว้น control ไม่มี ID ถูกบันทึก เพื่อรู้ว่าต้องใช้ fallback ตรงไหนและขอ DEV เพิ่มอะไร
25. ในฐานะผู้พัฒนา ฉันต้องการแยก element ID จาก Item ID/Bundle ID และ option value เพื่อไม่สรุปว่ามี locator ID ทั้งที่เป็น ID ของข้อมูล
26. ในฐานะผู้พัฒนา ฉันต้องการใช้ ID ที่มีจุดและ ID แบบ indexed row อย่างถูกต้อง เพื่อไม่เลือก class หรือแถวผิด
27. ในฐานะผู้พัฒนา ฉันต้องการทดสอบ DOM เปลี่ยนแต่ ID คงเดิมโดยไม่สร้างข้อมูลบริษัท เพื่อพิสูจน์ความทนต่อการเปลี่ยนหน้าอย่างปลอดภัย
28. ในฐานะผู้ดูแล ฉันต้องการเห็นรายการย้ายแล้ว fallback และยังตรวจไม่ได้ เพื่อไม่เข้าใจผิดว่าครอบคลุมทุก control แล้ว
29. ในฐานะผู้พัฒนา New Item ในอนาคต ฉันต้องการให้กฎเดียวกันมีผลเมื่องานกลับมาทำ เพื่อไม่ต้องตกลง locator policy ใหม่
30. ในฐานะผู้ใช้ ฉันต้องการให้ร่างและพฤติกรรมเดิมคงอยู่ โดยไม่ยกเครื่องโปรเจกต์ เพื่อไม่เพิ่มความซับซ้อนจากงานความเสถียรนี้

## Implementation Decisions

### ขอบเขตและกฎสำหรับงานในอนาคต

- ย้ายตัวกรอก ตัวค้นหา ตัวอ่านกลับและ shared widgets ที่ web/local ใช้จริง รวม helper จากโมดูล root ที่ถูกเรียกจริง ไม่เหมาว่า automation อยู่ใน web ทั้งหมด
- รองรับ CABAL PC/M TH/SEA ตาม flow ปัจจุบัน ไม่เพิ่มเกมใหม่หรือย้าย GUI desktop เก่าที่ไม่อยู่ใน runtime นี้ทั้งชุด
- ฟังก์ชัน Aztek ใหม่และส่วนที่แก้หลังจากนี้ต้องใช้ verified stable HTML element ID เป็น primary locator เมื่อมี ID ของ control นั้น กฎครอบคลุม New Item ในอนาคตแต่ไม่ทำให้เริ่มงาน #12 ตอนนี้
- บันทึกข้อบังคับในคำสั่งโปรเจกต์พร้อมเอกสาร locator policy เป็นจุดอ้างอิงถาวร ไม่ใส่คำศัพท์ DOM ทั่วไปลง domain glossary
- ไม่สร้าง framework locator/automation ใหม่ทั้งระบบ ใช้ runner และ widget helpers เดิม ปรับที่จำเป็นให้เลือก ID ก่อนจริงและตรวจเป้าหมายได้

### หลักฐานและ locator contract

- จัดรายการตาม flow/control/game/state: ความหมาย control, stable ID ที่พิสูจน์, scope, expected role/type, readiness, fallback exception ถ้าไม่มี ID และหลักฐาน/ส่วนที่ยังไม่ตรวจ
- อ้างอิง ID ที่พบจริงและสัญญา DEV ไม่เดา ID จากชื่อ field หรือใช้ placeholder เป็น identity
- แยก developer-maintained ID ออกจาก framework-generated ID เช่น radix/tiny-react และ business ID เช่น Aztek Item ID, Bundle ID หรือ Currency option value
- หาก control มี stable ID ต้อง lookup ID ก่อนทางอื่นจริง ไม่ใช้ selector union ตามด้วย first-match เพราะ DOM order ไม่รับประกัน ID priority
- ตรวจ match ที่ใช้ได้ใน intended scope ให้เป็นหนึ่งเดียว พร้อมชนิด/role ที่คาดไว้ ไม่ถือว่ามี node ID เดียวแล้วคลิกหรือ fill ได้โดยไม่ตรวจ
- ใช้ readiness/wait แบบมีขอบเขตก่อนตัดสินว่าหาย เช่นเปิดแท็บ รอ mount หรือเปิด dialog; ไม่หยุดทันทีเพียงเพราะ control ยังไม่ render และไม่วนรอไม่สิ้นสุด
- การรู้ ID ไม่ทำให้ widget interaction เดิมหายไป ยังต้องเปิด popover/tab, ขยาย card, เข้าถึง editor/frame และอ่านค่ากลับตามความจำเป็น

### กฎใช้ fallback กับการหยุด

| กรณี | พฤติกรรม |
| --- | --- |
| มี stable ID ตาม contract และ target ถูกต้อง | ใช้ ID เป็นหลักและทำ interaction/readback เดิม |
| หน้า/state ที่พิสูจน์ว่า control ไม่มี stable ID | ใช้ exception ที่บันทึกไว้และ scoped semantic locator; target ต้องไม่กำกวม |
| stable ID หายหลังรอ readiness หรือซ้ำใน scope | หยุด operation ที่ต้องใช้ control นั้น พร้อมชื่อช่อง/flow ไม่เดาไป fallback อื่น |
| ID ชี้ผิด control หรือ role/type ไม่ตรง | หยุดเหมือน contract เสีย ไม่เขียนค่าให้ node ที่บังเอิญใช้ ID เดียวกัน |
| fallback exception หาไม่ได้/ได้หลายเป้าหมาย | หยุด ไม่เลือกตัวแรกหรือตำแหน่งลำดับเพื่อบันทึกต่อ |
| ส่วนอ่านกลับหา control ที่จำเป็นไม่ได้ | รักษาผลสร้าง แสดงตรวจไม่สำเร็จ/ไม่ครบตามพฤติกรรมเดิม ไม่ทำผลผ่านขึ้นเอง |

- Fallback เป็นข้อยกเว้นสำหรับ control ไม่มี ID ตั้งแต่แรก ไม่ใช่ทางซ่อนการเปลี่ยน contract ของ control ที่ควรมี ID
- จำกัด fallback กับ form/section/แถว/active tab/dialog ที่ถูกต้องตามหลักฐาน หลีกเลี่ยง page-wide text/first/nth guesses เมื่อมีหลาย candidate
- บันทึก gap ให้ DEV ว่า flow/control ใดต้องการ stable ID พร้อมข้อยกเว้นที่ใช้ชั่วคราว ไม่ใส่ ID ใหม่เองใน DOM แล้วอ้างว่าคงที่ตาม DEV
- รักษาร่าง checkpoint Item/Bundle ID และ Creation/Recheck Outcome เดิมเมื่อ locator ล้มเหลว ถ้า submit ไปแล้วแต่ยังยืนยันไม่ได้ไม่ re-submit อัตโนมัติ
- รายงานข้อความที่อ่านเข้าใจ เช่นหา control ใดไม่ได้/ได้หลายตัว และต้องตรวจหน้า/เชื่อมใหม่อย่างไร ไม่แสดงว่าสร้างไม่สำเร็จแน่นอนเพียงเพราะขาดคำตอบ

### รายการซ้ำและ shared widgets

- Indexed IDs ของ items/rewards/prices ต้องจับคู่แถวจริงหลังเพิ่ม/ลบ/เรียงและตรวจ business identity ที่เกี่ยวข้อง ไม่ถือว่า index เป็น identity ถาวรของรายการ
- ID ที่มีจุดหรืออักขระพิเศษใช้ exact attribute lookup หรือ escape CSS อย่างถูกต้อง ไม่ใช้รูปแบบ hash-ID ที่กลายเป็น CSS classes
- Reward Set ที่ mount เฉพาะแท็บ active ต้องเปิดและรอชุดที่ถูกก่อนหา control; ไม่ใช้ ID ของชุดก่อนแทนชุดใหม่
- Calendar trigger มี ID ไม่ได้แปลว่า month/day/time controls มี ID ใช้ contract/exception แยกภายใน picker ที่เปิดอยู่ รักษาการตั้ง seconds/minutes และ readback ให้ได้วันเวลาที่ขอ
- Currency/Category control เปลี่ยน locator ได้ แต่ตัวเลือกยังต้องใช้ business value ที่ fetch มา ไม่เปลี่ยนไปเลือกข้อความใกล้เคียงหรือแทน value ด้วย element ID
- รักษา Quantity/Tier/EXP, RANDOM draw rate vs display rate, ค่า 0, รูปแต่ละช่อง, ภาษาใน editor, Bundle list/Primary และ confirmation behavior เดิม
- Preserve selection-only handoff, duplicate occurrences และ source/reference; locator migration ไม่เปลี่ยนเกณฑ์ผ่านของ Bundle Recheck หรือเพิ่มสิทธิ์ส่งต่อ

### ผลส่งมอบ

- มีรายงาน coverage แยกย้ายเป็น ID แล้ว, no-ID exception และยังไม่มีหลักฐาน พร้อม gap สำหรับ DEV
- แยก contract ของ game/page/state ที่ต่างกันตามหลักฐานจริง ไม่ใช้ PC SEA sample ยืนยันทุก variant
- Control/state ที่ยังพิสูจน์ไม่ได้ต้องมีข้อจำกัดชัดเจน ไม่ลด safety contract หรืออ้างว่า migration ครบทั้งหมดเพื่อจบงาน
- ไม่เพิ่ม API public/schema queue/business rules โดยไม่จำเป็น ใช้ขอบเขตการสั่งงานและการป้องกันงานทับเดิม

## Testing Decisions

Q4 ยืนยันให้ใช้ synthetic Aztek สำหรับ regression และอ่านเว็บจริงแบบ read-only แนวนี้ใช้ public API/runner และขอบเขตจำลองเว็บ Aztek เดิมเป็น seam หลัก ไม่สร้าง test seam ให้ทุก helper

- ใช้ API และ runner จริงกับ browser ที่ intercept traffic Aztek แล้วตอบ DOM/response จำลอง ตรวจค่าที่กรอก ค่าที่อ่าน ผลที่ผู้ใช้เห็น จำนวน submit และคิว/history ไม่ fake runner result ให้ผ่าน
- Prior art คือ routed API/runner ของ Bundle Recheck, fixture อ่าน Item detail, activity readiness, Product popover และ rate-zero tests เดิม ใช้ชุดเหล่านี้ต่อยอด แต่ไม่ถือว่า mock assertions เดิมพิสูจน์เว็บจริงครบ
- ทดสอบ locator behavior ใน synthetic DOM เมื่อ ID คงเดิมแต่ label/placeholder/class/DOM nesting/ตำแหน่งอื่นเปลี่ยน ให้เป้าหมายหลักยังถูกต้องตาม scope ที่กำหนด
- ทดสอบ ID-first โดยมี fallback control ที่ดูเหมือนถูกแต่ล่อให้เขียนผิด ถ้ามี stable ID ต้องใช้ตัว ID โดยไม่ขึ้นกับ DOM order
- ใน control ไม่มี ID การเปลี่ยนส่วนที่ fallback อาศัยจนหาไม่ชัดต้องหยุดอย่างปลอดภัย ไม่สัญญาว่า fallback จะทนได้เท่า ID
- API/runner test traffic ต้องถูกจำลองทั้งหมด request ที่ไม่คาดไว้ต้องล้มเหลว ไม่ปล่อยออกไป Aztek บริษัทโดยบังเอิญ
- อ่านสดก่อน implement เพื่อพิสูจน์ ID และ scope ที่ยังขาดโดยไม่กรอก/upload/submit/edit/delete ข้อมูลจริง การทดสอบบันทึกจริงต้องมีคำสั่งผู้ใช้แยก

### Acceptance Criteria

1. ฟังก์ชัน Aztek ใหม่ทุกตัวมี verified stable ID เป็น primary เมื่อ control มี ID และมีหลักฐาน/exception ชัดเจนเมื่อไม่มี
2. Text/label/placeholder/class/ตำแหน่งเปลี่ยนแต่ stable ID เดิมใน scope ถูกต้องแล้วกรอก/อ่านได้ตรงช่อง; scope ที่เสียต้องหยุด ไม่บังคับให้ผ่านด้วยความกำกวม
3. ID กับ fallback node สลับ DOM order แล้ว target ยังคงเป็น ID ที่ระบุ
4. ID ที่มีจุดเลือกได้ถูกต้อง ไม่ไปเขียน node ที่ตรงชื่อ CSS class
5. Known stable ID หาย/ซ้ำ/ผิดชนิดหลัง readiness ต้องแจ้ง control และไม่ submit สร้าง; exception ที่มีหลายเป้าหมายก็ต้องหยุด
6. Lazy-mounted control ที่มี ID หลังพร้อมใช้งานทำงานได้ตาม timeout ไม่เกิด false failure ก่อน mount และไม่วนรอไม่สิ้นสุด
7. Known no-ID control ใช้ fallback ที่ระบุและ scoped ได้ ไม่ใช้ framework-generated ID เป็น permanent contract
8. ฟอร์มสองชุด/hidden duplicate/portal สองตัวไม่ทำให้กรอกชุดผิด; ambiguity ใน intended scope ไม่ถูกแก้ด้วย first-match
9. Item Finder ค้น/filter/read pagination ถูกต้องหลังย้าย ไม่ทำ occurrence หรือรายการที่ผู้ใช้เลือกหาย
10. Bundle หลาย Item/Currency/EXP จับคู่ Quantity/Tier ถูก card และ RANDOM rate 0 ลง draw chance ไม่ลง display chance
11. เพิ่ม/ลบ/เรียง repeated rows แล้วค่าลงแถวจริงตาม identity ไม่ตาม index เก่าที่ cached
12. Item Code/Event หลาย Reward Set เปิดแท็บที่ถูกและไม่เขียนค่าซ้ำลงชุดแรกทั้งหมด
13. Date/time picker ตั้งวันและเวลาได้ตรง รวมเวลาสิ้นสุดวินาที 59 ตามข้อมูลที่ขอ; อ่านกลับแล้วไม่ตรงต้องรายงานไม่ครบ/หยุดตาม flow เดิม
14. Product Category/Currency ใช้ fetched business values, ราคาหลายแถว รูป ภาษา Bundle และ Primary คงพฤติกรรมเดิม
15. Preview/fill ที่ไม่บันทึกมีจำนวน submit 0; confirmation จำลองชี้ dialog/action ถูก ไม่คลิก action ของฟอร์มอื่น
16. Locator failure ก่อน submit ป้องกันบันทึก; failure หลัง submit รักษา checkpoint/ID/ผลตรวจและไม่เพิ่ม submit จากการกู้
17. Recheck actual ที่หา control ไม่ได้ไม่กลายเป็น passed และไม่ส่งต่อผลนั้นตามเงื่อนไขเดิม
18. Coverage ของ PC/M TH/SEA มีหลักฐานต่อ variant/state ที่ย้าย หรือระบุยังไม่พิสูจน์ ไม่อ้าง PC SEA แทนทุกเกม
19. Regression ของ API/runner/shared widgets เดิมผ่าน โดยคิว เกม สิทธิ์และ selection-only handoff ไม่เปลี่ยน
20. คำสั่งโปรเจกต์มี policy สำหรับฟังก์ชันใหม่ และรายงาน gap/exception/unknown ครบจุดที่ไม่มี stable ID ในขอบเขตที่ย้าย

## Out of Scope

- การบังคับให้ทุก DOM node มี ID ทั้งที่ Aztek ยังไม่ได้กำหนด
- การใช้ business ID หรือ framework-generated ID แทน stable element ID โดยไม่ตรวจ
- การเดา ID, inject ID ฝั่ง Tools เพื่ออ้างความคงที่ หรือใช้ broad fallback เมื่อ contract เสีย
- การสร้าง framework automation/locator ใหม่ทั้งระบบ รีแฟกเตอร์ UI หรือย้าย GUI desktop เก่าทั้งชุด
- เปลี่ยนกฎธุรกิจของ Item Finder/Bundle/Item Code/Event/Product หรือเกณฑ์ Recheck/สิทธิ์ส่งต่อ
- เปลี่ยนเว็บ Aztek ฝั่ง DEV เอง การติดต่อ/ส่งข้อความให้ DEV โดยไม่มีคำสั่ง; งานนี้จัดรายการ gap เท่านั้น
- การเริ่ม implementation New Item หรือแก้เนื้อหา/label/สถานะ GitHub Issue #12
- การสร้าง/แก้/ลบข้อมูลจริงบน Aztek เพื่อทดสอบโดยไม่มีคำสั่งผู้ใช้แยก
- Setup, commit, push, publish โปรแกรม และ deployment จากการทำ spec นี้

## Further Notes

- DEV รับรองว่า ID ที่ดูแลจะคงเดิมตามที่ผู้ใช้แจ้ง การสำรวจ DOM ครั้งเดียวไม่พิสูจน์ความคงที่ข้าม release
- Live audit 2026-10-01 ตรวจ PC SEA Item/Bundle/Item Code/Event และ Product list พบ ID ของช่องหลัก แต่ search/add/create/picker บางจุดไม่มี ID; radix/tiny-react เป็นรูปแบบที่พบ ไม่ใช่ stable contract
- Product create เปิด href จริงแล้ว main content ยังว่างในช่วงตรวจ จึงยังไม่ยืนยัน controls ของฟอร์มนี้จากการตรวจสด
- อีกสามเกม, populated repeated rows, confirmation/success และ saved-record states ยังต้องพิสูจน์ ก่อนย้ายต้องแยกข้อเท็จจริงจาก fixtures กับหลักฐานเว็บจริง
- ID-first ช่วยลดความเปราะบางของ target lookup แต่ไม่ได้รับรอง widget semantics, mounting, validation หรือการจับคู่แถวอัตโนมัติ
- ขั้นนี้เขียน spec และกฎโปรเจกต์เท่านั้น การเผยแพร่ ready-for-agent ไม่ใช่การอนุมัติบันทึก Aztek หรือเริ่ม implementation โดยอัตโนมัติ
