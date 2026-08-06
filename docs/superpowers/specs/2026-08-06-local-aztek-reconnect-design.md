# Local Aztek Reconnect Design

## เป้าหมาย

ทำให้การเชื่อม Aztek แบบ Local ใช้ได้กับทุกเกมโดยไม่ผูกกับเซิร์ฟเวอร์แรกในรายการ และลดการกรอกรหัส IPA ซ้ำเมื่อ SSO session เดิมยังใช้ได้ โดยโปรแกรมยังคงไม่ถาม ไม่อ่าน และไม่เก็บรหัสผ่าน IPA/Aztek

## ปัญหาที่ตรวจพบ

- ตัวเชื่อมเปิดและตรวจซ้ำกับ URL ของ `CabalM TH` เพราะเลือก `GAME_NAMES[0]` แม้ผู้ใช้กำลังทำงานกับเกมอื่น เช่น `CabalM SEA`
- เมื่อบัญชีไม่มี session ที่ใช้ได้กับ URL ตรวจดังกล่าว การตรวจรอบสุดท้ายกลับไปหน้า Login และ Local แสดง `ยังเข้าสู่ระบบ IPA/Aztek ไม่สำเร็จ`
- ทุกครั้งที่เชื่อมใหม่ Playwright สร้าง browser context ว่าง จึงไม่สามารถใช้ SSO cookie ที่โปรแกรมเก็บแบบเข้ารหัสไว้แล้ว และผู้ใช้ต้องกรอก IPA ใหม่เสมอ

## แนวทางที่เลือก

ใช้ URL กลาง `https://aztek-tools-v2.combo-interactive.com/init` สำหรับทั้งการเปิด Login และการตรวจซ้ำหลัง Login พร้อม seed browser context ด้วย storage state เดิมที่ถอดรหัสในหน่วยความจำเท่านั้น

แนวทางนี้ถูกเลือกแทน:

1. persistent Chromium profile ซึ่งลดการ Login ซ้ำได้ แต่เก็บ browser profile และ cookies แบบอ่านได้บนดิสก์
2. context ว่างทุกครั้งแบบปัจจุบัน ซึ่งปลอดภัยแต่บังคับกรอก IPA ทุกครั้งและยังผูกการตรวจเข้ากับเกมแรก

## การไหลของข้อมูล

1. API อ่าน Aztek session เดิมของผู้ใช้ได้แม้สถานะเป็น `expired` โดยถอดรหัสเฉพาะในหน่วยความจำ
2. ถ้ามี state เดิม ให้ส่งเป็น `storage_state` ตอนสร้าง Playwright context
3. เปิด `/init` กลาง
4. ถ้า state เดิมยังผ่าน SSO ให้ยอมรับหน้า Aztek ที่ authenticated โดยไม่บังคับให้เห็นหน้า Login ก่อน
5. ถ้า state เดิมใช้ไม่ได้หรือไม่มี state หน้า IPA/Aztek Login จะเปิดตามปกติ และระบบรอจนผู้ใช้ Login แล้วกลับเข้า Aztek
6. เปิด `/init` ซ้ำใน context เดิมเพื่อยืนยันว่า session อยู่รอดในการนำทางใหม่
7. เมื่อผ่านเท่านั้นจึง export `context.storage_state()` ตรวจ validation เข้ารหัส และแทน session เดิมด้วยสถานะ `active`

รหัสผ่าน IPA/Aztek จะไม่ผ่าน API และไม่ถูกบันทึก โปรแกรมเก็บเฉพาะ cookies/localStorage ที่ Playwright export และเข้ารหัสด้วยกุญแจ Local เดิม

## การจัดการข้อผิดพลาด

- ถ้าผู้ใช้ปิดหน้าต่าง หมดเวลา Login ไม่สำเร็จ หรือ state ใหม่ไม่สมบูรณ์ ให้เก็บ record เดิมไว้เหมือนเดิม
- ถ้า seed เดิมหมดอายุ ให้แสดงหน้า Login แทนการล้มทันที
- การกด `ตัดการเชื่อมต่อ` ยังคงลบ session record จึงไม่มี seed ในการเชื่อมครั้งถัดไป
- ไม่เปลี่ยนการทำงานของ Hosted mode หรือ bookmark pairing

## การทดสอบ

- ยืนยันว่าการเปิดและ probe ใช้ `/init` กลางทั้งสองครั้ง ไม่ใช้ URL ของเกมแรก
- ยืนยันว่า encrypted state เดิมถูกส่งให้ browser context และ session ที่ยัง valid เชื่อมสำเร็จโดยไม่ต้องผ่านหน้า Login
- ยืนยันว่า state เดิมที่ถูก redirect ไป Login ยังรอผู้ใช้ Login แล้วกลับ Aztek
- ยืนยันว่า context ว่างไม่ยอมรับหน้า Aztek ชั่วครู่ก่อน redirect ไป IPA
- ยืนยันว่า capture ล้มเหลวไม่แทนหรือลบ session เดิม
- รัน focused tests และ full `tests` suite

## เกณฑ์สำเร็จ

- ผู้ใช้เชื่อมได้โดยไม่ขึ้นกับเกมที่กำลังทำงาน
- ถ้า SSO เดิมยัง valid การกดเชื่อมใหม่ไม่ถาม IPA
- ถ้า SSO หมดอายุจริง ผู้ใช้ Login ใหม่ได้ใน Chromium เดิมและเชื่อมสำเร็จ
- งานค้นหา Preview และ Create ใช้ session ใหม่ได้ตาม flow เดิม
