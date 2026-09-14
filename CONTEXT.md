# All for Cabal

คำศัพท์ร่วมของงานเตรียมข้อมูลจากไฟล์ WR เพื่อนำไปสร้างข้อมูลใน All for Cabal อย่างถูกเกม ถูกช่วงเวลา และตรวจสอบได้ก่อนส่งไป Aztek

## Language

**Mastercode WR**:
รูปแบบการนำเข้าไฟล์ WR บนหน้า Item Code เดิม โดยแปลงแต่ละ Master Code Block เป็นร่าง Item Code หนึ่งรายการ
_Avoid_: WR page, Item Code WR page

**Master Code Block**:
ชุดข้อมูลหนึ่ง Code ในชีท เริ่มจากหัวสีที่ลงท้ายด้วย `Code <เลข>` และมีวันที่ เกม Mastercode, Bundle ID และ Usage Limit ของชุดนั้น
_Avoid_: Sheet, tab, item table

**Mastercode**:
รหัสจากช่อง `Mastercode` ภายใน Master Code Block ซึ่งเป็นคนละค่ากับชื่อ Item Code และ Bundle ID
_Avoid_: Item Code name, Bundle code

**Bundle ID**:
เลขอ้างอิง Bundle ที่อยู่ทางขวาของช่อง Mastercode ภายใน Master Code Block
_Avoid_: Mastercode, Item ID

**Usage Limit**:
จำนวนครั้งสูงสุดที่ Mastercode ของ Master Code Block ใช้งานได้ ตามค่าจากช่อง `Limit การใช้งาน` เป็นโควตาเดียวกันทั้งระดับ Item Code และ Reward Set โดยจำนวนรวมและจำนวนคงเหลือเริ่มต้นเท่ากับค่านี้
_Avoid_: Per-user limit, item amount

**Code Window**:
ช่วงเวลาใช้งานภายในวันเดียวตามช่อง `CODE EXPIRE DATE` เริ่ม `00:00:00` และสิ้นสุด `23:59:59`
_Avoid_: Sheet date, header date

**Daily Sequence**:
ลำดับของ Master Code Block ภายในวันและเกมเดียวกัน เริ่มใหม่ที่ `1` ทุกวันต่อเกม และยึดลำดับชีทกับตำแหน่ง block ในไฟล์แม้ผู้ใช้เลือกนำเข้าเพียงบางรายการ
_Avoid_: Code number, selected row number

**Mastercode WR Name**:
ชื่อร่วมของ Item Code และ Reward Set ในรูป `<Daily Sequence>. <หัว block ถึง Code เลข> - <Mastercode>` เช่น `1. Master Code 27/08/26 - Code 1 - GC800WAG` หาก Mastercode ยังว่างให้ใช้ `[ยังไม่มี Mastercode]` และแทนที่เมื่อกรอกรหัสภายหลัง เฉพาะกรณีที่ผู้ใช้ยังไม่ได้แก้ชื่อเอง
_Avoid_: Sheet name, raw header

**Same-Day Game Overlap**:
กรณีหลายชีทมี Master Code Block ของวันและเกมเดียวกัน ลำดับจะต่อเนื่องกันและระบบต้องเตือนให้ตรวจ โดยไม่ถือว่าเป็นข้อมูลซ้ำโดยอัตโนมัติ
_Avoid_: Duplicate block

**Mastercode WR Preview**:
ขั้นตรวจข้อมูลหลังเลือกชีทและก่อนเพิ่มเข้าคิว แสดงชื่อ เกม Code Window, Mastercode, Bundle ID, Usage Limit และความพร้อมของแต่ละ Master Code Block
_Avoid_: Aztek preview, create confirmation

## การอัปเดต All for Cabal

**All for Cabal Update**:
การเปลี่ยนโปรแกรม All for Cabal ที่ติดตั้งอยู่เป็นรุ่นใหม่ผ่านคำสั่งอัปเดตในโปรแกรม โดยผู้ใช้งานเป็นคนเลือกเริ่มและสามารถใช้รุ่นเดิมต่อได้
_Avoid_: บังคับอัปเดต, อัปเดตข้อมูล Aztek

**Update Details Popup**:
หน้าต่างแสดงรายการแก้ไขและสิ่งที่เพิ่มในเวอร์ชัน All for Cabal ที่แจ้งอัปเดต ผู้ใช้สามารถเปิดดูซ้ำได้จากปุ่มในโปรแกรม
_Avoid_: ประวัติงานในคิว, Aztek log
