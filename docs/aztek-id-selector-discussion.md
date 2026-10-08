# Aztek ID-first locators — หลักฐานและข้อตกลง

วันที่: 2026-10-01
สถานะ: ยืนยัน Q1–Q4 และผู้ใช้ขอทำ spec พร้อมกฎ ID-first สำหรับฟังก์ชันใหม่ทุกตัวแล้ว
ข้อกำหนดสำหรับขั้นถัดไปอยู่ใน [aztek-id-selector-spec.md](aztek-id-selector-spec.md); ยังไม่อนุมัติแก้โค้ด
เผยแพร่ [GitHub Issue #13](https://github.com/momozxmo/all-for-cabal/issues/13) พร้อม ready-for-agent แล้ว

## คำขอและขอบเขตที่ทราบ

- พักงาน New Item Creation / New Item Recheck ที่ spec และ GitHub Issue #12
  ยังไม่แตก tickets หรือเริ่ม implementation; ไม่แก้สถานะ remote issue
- ผู้ใช้แจ้งว่า DEV รับรองว่า ID คงเดิม แม้ DOM/selector อื่นเปลี่ยน และขอประเมิน
  ว่า automation ทุกจุดเปลี่ยนมาใช้ ID ได้หรือไม่
- ID ในงานนี้หมายถึง HTML element `id` ไม่ใช่ Aztek Item ID, Bundle ID หรือค่า Currency
  การใช้ ID ยังเป็น selector ประเภทหนึ่ง และยังต้องตรวจชนิด element, scope และค่าที่อ่านกลับ
- ความคงที่ข้าม release เป็นคำรับรองที่ผู้ใช้ถ่ายทอดจาก DEV ไม่ใช่สิ่งที่การดู DOM ครั้งเดียวพิสูจน์ได้

## หลักฐานจากโค้ดปัจจุบัน

| ส่วน | หลักฐาน | ข้อสรุปที่ทำได้ |
| --- | --- | --- |
| Bundle RANDOM | ตัวกรอก rate หา `input[id="items.N.secret_chance"]` ก่อนชื่อเดิม | มีรูปแบบ ID-first อยู่แล้ว; จุดใน ID เป็นอักขระจริง ไม่ใช่ CSS class |
| Bundle Recheck | อ่าน `#item-game-item-id`, `#item-option`, `#duration-index` | ใช้ ID อยู่แล้วสำหรับสามคุณสมบัติ Item |
| Shared widgets | switch ใช้ label/parent; select ใช้ options/XPath; calendar ใช้ class/data-day/aria-label | ยังมีจุดผูกกับข้อความและโครงสร้าง; เปลี่ยนตาม ID ที่พิสูจน์ได้ ไม่ replace แบบเหมารวม |
| Create confirmation | หา dialog และปุ่มข้อความ “ยืนยัน” | ต้องตรวจ ID ของ action จริงก่อนเปลี่ยน ไม่ถือว่า ID ของ dialog เป็น ID ของปุ่ม |
| Product | Category/Currency ใช้ popover/label/ancestor; รูปใช้ตำแหน่ง input file | ยังมีจุดอาศัยข้อความหรือโครงสร้างและตำแหน่ง |
| New Item (หลักฐานก่อนหน้า) | ช่องหลักมี ID; Type ของ PC และ input file ไม่มี ID, M เป็น GENERAL ตายตัว | ไม่มีเหตุให้บังคับทุก element ต้องมี ID หรือสร้าง dropdown ที่ไม่มี |

- `#bundle-name, input[name="name"]` ตามด้วย `.first` เป็น union ที่คืนตาม DOM order
  ไม่รับประกันว่าจะลอง ID ก่อน name ต้องแยก ID-first ออกจาก “มี ID อยู่ใน selector”
- Product Currency/Category ที่เลือกด้วย option value หรือ data-value ใช้ ID ของข้อมูลธุรกิจ
  ไม่ใช่ HTML element ID; การเลือกข้อมูลด้วย server ID ยังจำเป็น แม้เปลี่ยน locator ของช่องแล้ว
- Item Finder ใช้ helper จากโมดูล desktop เดิมจริง การตรวจเฉพาะโฟลเดอร์ web จะไม่ครอบคลุม
  การค้นหา อ่านตารางและเปลี่ยนหน้า ส่วน GUI desktop เก่าอื่นไม่ได้ถูกเรียกแทน web runner ทั้งชุด

### ตำแหน่งโค้ดสำหรับตรวจต่อ

- Item Finder: `item_finder.py:2545` ช่องค้นหา, `:2608` ปุ่มค้นหา, `:2710` ตำแหน่งคอลัมน์,
  `:2738` เปลี่ยนหน้า; `web/search_runner.py:147` ใช้ helper จาก root
- Bundle: `web/bundle_runner.py:154` name union, `:166` first select, `:188` first switch,
  `:399` quantity ตาม name/index, `:420` Tier ตาม card ancestor, `:493` exact rate ID
- Currency/EXP: `web/bundle_runner.py:245` tab text, `:260` combobox/popover,
  `:327` Qty placeholder, `:334` ปุ่มเพิ่มตามข้อความ
- Bundle Recheck: `web/bundle_recheck.py:45` card hierarchy/name suffix และ `:55` rate ยังอ่าน name,
  `:98` Item detail IDs; ID-first ของการสร้างไม่ได้แปลว่าตัวอ่านใช้ ID ตามแล้ว
- Item Code/Event: `web/itemcode_runner.py:27`, `web/event_runner.py:25` date label XPath;
  `web/activity_runner.py:82` เพิ่ม reward และ `:102` ปุ่มสร้างตามข้อความ
- Product: `web/product_runner.py:75` Category text, `:91` Currency ancestor,
  `:220` date label XPath, `:267` language tab/TinyMCE, `:298` file input ตามตำแหน่ง,
  `:439` Bundle heading และ `:460` primary checkbox ตาม card
- Shared: `web/aztek_form.py:96` switch, `:137` select หลัง label,
  `:200` time controls, `:242` calendar; `web/create_flow.py:5` final confirmation

### ข้อจำกัดของ ID ในรายการซ้ำ

- `items.N.*`, `rewards.N.*`, `prices.N.*` ใช้ดัชนีแถว ต้องจับคู่แถวจริงและตรวจค่าหลังกรอก
  ID ไม่ได้ทำให้ตำแหน่งคงเดิมเมื่อเพิ่ม/ลบ/เรียงรายการ
- Reward Set แสดงเฉพาะแท็บที่ active ต้องเปิดแท็บและรอ mount ก่อนหา ID;
  calendar/popover/dialog/file/TinyMCE อาจมี scope แยก ไม่แทนทุกอย่างด้วย page-wide ID
- ID ที่มีจุดใช้ `[id="items.0.secret_chance"]` หรือ escape CSS ให้ถูก
  ไม่ใช้ `#items.0.secret_chance` แบบตรง ๆ เพราะเป็นความหมายของ CSS class
- ผลสำรวจโค้ดและ synthetic fixtures ไม่ยืนยันว่า ID ปรากฏครบ/unique ในทุก state หรือทุกเกม

## หลักฐานเว็บจริงที่สำรวจแล้ว

ส่วนนี้เป็น snapshot ตอนเก็บ requirements ก่อน implement (PC SEA).
หลักฐานล่าสุดระหว่าง implement #14 ทั้งสี่เกมอยู่ใน
[ID-first coverage](tickets/aztek-id-first/coverage.md); ไม่ใช้ snapshot เก่าแทนสถานะล่าสุด.

สำรวจในแท็บ Brave ใหม่ของงานนี้ รักษาแท็บผู้ใช้เดิม ไม่กรอก/upload/submit/create/delete
ขอบเขตครั้งนี้คือ CABAL PC SEA เท่านั้น แท็บสำรวจจบที่ Item list ปลอดภัย

- Item list: มี filter-option/filter-duration และ date/sort filters;
  ช่องค้นหา ปุ่มค้นหา และ pagination ไม่มี ID; Actions มี radix ID

- CABAL PC SEA Bundle list: ช่องค้นหาและปุ่มค้นหาไม่มี ID; row Actions มี ID แบบ `radix-*`
- CABAL PC SEA Bundle create: `#bundle-name` และ `#immediately-send` มีจริง
  Type combobox/select, ช่องค้นหา Item/Option/Duration, ปุ่มเพิ่ม และปุ่มสร้างไม่มี ID
  แท็บ Currency มี ID แบบ `radix-...-trigger-credit` ซึ่งเป็น ID ที่ framework สร้าง
  Credit picker มี radix IDs ของ search/options/dialog แต่ trigger และ Qty ไม่มี ID
- CABAL PC SEA Item Code create: มี ID ของ name_th/name_en/slug/desc_th/desc_en,
  redeem_type/per_player_limit/start_at/end_at และสถานะ is_enabled/is_test_mode/
  is_shown_only_winner/is_limited รวมช่อง reward รูปแบบ rewards.0.*
  ปุ่มเพิ่มของรางวัล เลือก bundle เพิ่มเงื่อนไข และสร้าง/บันทึกแล้วสร้างต่อไม่มี ID
- ปฏิทิน start_at ของ Item Code: dialog มี radix ID; ช่องเดือน/ปี ปุ่มเดือนก่อน/ถัดไป
  ปุ่มวัน และช่องชั่วโมง/นาที/วินาทีไม่มี ID มี semantic aria labels บางส่วน
  เปิดดูอย่างเดียว ไม่เลือกวันหรือกรอกเวลา
- CABAL PC SEA Event create: มี name_th/name_en/slug/per_player_limit/quantity/remaining,
  start_at/end_at/redeem_start_at/redeem_end_at และ ID ของสวิตช์สถานะ
  Redeem Type, file inputs, เพิ่ม reward และปุ่มสร้างไม่มี ID;
  editor/iframe ใช้ ID แบบ tiny-react_* ส่วน language tabs ใช้ radix ID
- Product list: ช่องค้นหาและ pagination ไม่มี ID แต่ date/status/category/sort filter มี;
  Actions มี radix ID เปิด href ฟอร์มสร้างที่พบจริงแล้ว main content ยังว่างระหว่างตรวจ
  จึงไม่ยืนยัน ID ของฟอร์มสร้าง Product จากการตรวจสดรอบนี้
- Item list ที่ตรวจไม่มี ID ที่ไม่ว่างซ้ำกัน ส่วนฟอร์มอื่นยังไม่ได้ตรวจ uniqueness อย่างเป็นระบบ
- ยังไม่ตรวจสดอีกสามเกม แถว Bundle Qty/Tier/rate ที่มีข้อมูล แถว reward/condition ที่เพิ่ม
  confirmation/success state หรือ saved-record edit; ไม่เพิ่มข้อมูลจริงเพื่อเปิด state เหล่านี้
- radix/tiny-react เป็นรูปแบบ ID ที่พบ ไม่ได้พิสูจน์ความคงที่ข้าม rerender/release

## Design tree — ยืนยันแล้ว Q1–Q4

- Q1: ขอบเขตการย้าย — automation ฝั่ง Aztek ของโปรแกรม local ที่ใช้อยู่ทั้งหมด ได้แก่ Item Finder,
  Bundle/Bundle Recheck, Item Code, Event, Product และ shared widgets ครอบคลุม PC/M TH/SEA
  รวม root helper ที่ web ใช้จริง แต่ไม่ย้าย GUI desktop เก่าอื่นทั้งชุดหรือรีแฟกเตอร์ UI ของ Tools;
  New Item คงพักไว้และนำแนวทางไปใช้เมื่อถึงงานนั้น
- Q2: ช่องที่ไม่มี ID คงที่ — ใช้ ID-first ไม่บังคับ ID-only
  จุดไม่มี ID ใช้ fallback ที่เจาะจงใน section/dialog/แถวของตัวเอง พร้อมรายการให้ DEV เพิ่ม ID
  ไม่ใช้ ID ที่ framework สร้างเองเป็นสัญญาถาวร และไม่เลือกตัวแรกเมื่อ match กำกวม
  ไม่แทรก ID ขึ้นเองฝั่ง Tools เพื่ออ้างว่าได้ความคงที่ตามสัญญาของ DEV
- Q3: ID ที่คาดไว้หาย/ซ้ำ/ผิดชนิด — หยุดรายการที่ต้องใช้ช่องนั้นพร้อมแจ้งชื่อช่อง
  ไม่ไหลไปเดาตำแหน่งอื่นหรือกดสร้างต่อ; รักษาคิว/ผลบันทึกเดิมเพื่อไม่ทำซ้ำ
- Q4: การพิสูจน์ — regression เปลี่ยน label/class/ตำแหน่งแต่คง ID แล้ว flow ยังผ่าน
  และทดสอบ ID หาย/ซ้ำต้องหยุดอย่างปลอดภัย ใช้ synthetic Aztek; ทดสอบเว็บจริงแบบ read-only
  ตรวจวันเวลา Currency, หลาย reward/Bundle, rate 0, ID ที่มีจุด และการยืนยันสร้างโดยไม่ submit จริง

## ความเข้าใจร่วมและข้อกำหนดเพิ่มเติมที่ยืนยันแล้ว

ปรับ automation ที่ใช้จริงของโปรแกรม local เป็น ID-first ตาม Q1 โดยรักษาพฤติกรรมเดิม
รวมตัวกรอก ตัวอ่านกลับ และ shared helper ไม่ถือว่าเพิ่ม ID ลง selector union แล้วได้ priority
ช่องไม่มี ID ตั้งแต่แรกใช้ fallback เฉพาะจุดที่ตรวจไว้ และทำรายการช่องที่ต้องขอ DEV เพิ่ม ID
ส่วน ID ที่กำหนดเป็นสัญญาของช่องแล้วแต่หาไม่ได้ ซ้ำ หรือผิดชนิด ให้หยุดตาม Q3
ไม่ลอง fallback กว้าง ๆ เพื่อซ่อนสัญญาที่เสีย และไม่เลือกตัวแรกเมื่อยังระบุเป้าหมายไม่ได้แน่นอน
รักษาคิว checkpoint และผลบันทึกเดิม ไม่ retry การสร้างเพียงเพราะ locator ล้มเหลว

แนวทางนี้เป็นการย้าย locator ตามขอบเขต ไม่สร้าง framework ใหม่หรือรีแฟกเตอร์ทั้งโปรเจกต์
ทดสอบ regression ตาม Q4 และตรวจช่องที่ยังไม่มีหลักฐานแบบ read-only ก่อนย้าย
การที่เปลี่ยนไปใช้ ID ได้แล้วไม่รับรองว่าพฤติกรรม widget หรือทุก DOM state คงเดิม

ผู้ใช้ขอทำ spec และเพิ่มกฎให้ทุกฟังก์ชัน Aztek ใหม่ใช้ stable ID เมื่อมีตั้งแต่เริ่ม
บันทึกกฎถาวรในคำสั่งโปรเจกต์และ [locator policy](agents/aztek-locators.md)
ไม่มีคำถามการตัดสินใจค้าง ใช้แนวทดสอบ Q4 ที่ยืนยันแล้ว
งาน New Item ยังคงพักที่ #12 โดยไม่เปลี่ยนเนื้อหา/label/สถานะ remote issue

## ข้อเท็จจริงที่ยังต้องพิสูจน์ในขั้น implement

- ความพร้อมของ Product create ที่ยังโหลด main content ไม่ได้ในรอบตรวจนี้
- ID และ uniqueness ของอีกสามเกม รวม repeated rows, dialog confirmation และ saved-record pages
- ความสัมพันธ์ของ control กับแถว/แท็บ/portal/editor และค่าที่อ่านกลับหลังใช้งาน
- รายการ stable ID ที่ DEV รับรองจริง แยกจาก framework-generated IDs; จัดทำรายการ gap
  จากหลักฐาน ไม่เดา ID ใหม่และไม่สร้างข้อมูลจริงเพื่อเปิด state โดยไม่มีคำสั่ง

## ขอบเขตการทำงานรอบนี้

แก้เอกสารและคำสั่งโปรเจกต์เท่านั้น ไม่แก้ product code ไม่ทำ Setup/commit/push/publish โปรแกรม
ไม่สร้างข้อมูล Aztek; to-spec รวมการเผยแพร่ spec ใน GitHub Issues พร้อม ready-for-agent
ไม่เพิ่ม DOM ID/selector ลง CONTEXT.md เพราะเป็นคำศัพท์เทคนิคทั่วไป ไม่ใช่ domain term ของโปรเจกต์
ยังไม่มี ADR: การย้าย locator ตามขอบเขตนี้เป็นการเปลี่ยนที่ย้อนกลับได้ ไม่จำเป็นต้องเพิ่ม ADR
