# #12 — ตรวจหน้าจอจริงแบบอ่านอย่างเดียว 27ตุลาคม2026

## ขอบเขตและผลสรุป

ผู้ใช้ยืนยัน “เอาเลย” หลังคำขออ่านหน้ารายการ ฟอร์มสร้าง และ Item ที่บันทึกแล้วของทั้งสี่เกมบน Aztek โดยไม่กรอก สร้าง อัปโหลด แก้ ลบ หรือดึง token/session. เป็นข้อยกเว้นเฉพาะการอ่านจากข้อห้าม live probe เดิม ไม่ใช่สิทธิ์สร้างจริงเพิ่มหรือเผยแพร่โปรแกรม

อ่าน saved Item และฟอร์มสร้างเปล่าครบ CabalPC TH/CabalPC SEA/CabalM TH/CabalM SEA แล้วผ่าน Brave browser API โดยไม่ใช้เมาส์หลัก. ไม่เปลี่ยนช่อง เลือกชนิด ติ๊กสวิตช์ แนบไฟล์ หรือกด Create/Save/ยืนยัน. ไม่เปิดเมนู Actions ของระเบียน ไม่ใช้ข้อมูลล็อกอินนอกเบราว์เซอร์ และไม่ยิง API โดยตรง. ไม่ได้ตรวจนับ HTTP requests จึงไม่อ้างจำนวนคำขอจากการอ่านหน้าเว็บ

การอ่านรอบนี้ยืนยัน DOM/ค่าที่แสดงเท่านั้น ไม่ได้ให้ raw GET/POST response, backend game UUID, positive create contract ของอีกสามเกม หรือหลักฐานผูก Item กับคำขอเดิมที่ตอบกลับหาย. จึงยังไม่ปลด capability สร้างอีกสามเกมหรือ positive Resolve และไม่ถือว่า #12 ครบแล้ว

Origin: `https://aztek-tools-v2.combo-interactive.com`. PC TH ใช้ลิงก์จากแถวที่เห็นจริงในรายการปัจจุบัน; อีกสาม saved paths มีหลักฐานการอ่านเดิมอยู่แล้ว ไม่ไล่เดาเลข ID

## Saved Item ที่อ่านจริงในรอบนี้

| เกม | Saved path / ID | ชื่อและค่าที่แสดง | ชนิด / แลกเปลี่ยน | รูป / แสดงบนเว็บ |
| --- | --- | --- | --- | --- |
| CabalPC TH | `/combo/cabalpc/shop/items/224861` | GM's Blessing (Lv. 5) Holy Water x3; Kind33561487 / Option3 / Duration0 | GENERAL / false | ไม่พบ Preview; display off |
| CabalPC SEA | `/combo/cabalpcsea/shop/items/224795` | Blessing Bead - AXP (600%)(1 day); Kind67113458 / Option0 / Duration9 | GENERAL / false | มี Preview; display on, quantity1, criticalว่าง, slotablefalse, favoritefalse |
| CabalM TH | `/combo/cabalm/shop/items/224846` | TEST_AFC_NEW_ITEM_20261026_C9D7; Kind33600667 / Option0 / Duration10 | GENERAL fixed text / false | ไม่พบ Preview; display off |
| CabalM SEA | `/combo/cabalmsea/shop/items/224791` | [Costume] Idol Face (30 Days); Kind33562319 / Option0 / Duration17 | GENERAL fixed text / false | ไม่พบ Preview; display off |

PC SEA224795 มีรูปและเปิด display ในการอ่านรอบนี้ ต่างจากข้อสังเกตเรื่องรูป25ตุลาคม. เก็บทั้งสอง snapshot ตามวันที่ ไม่เขียนทับประวัติ ไม่ระบุสาเหตุหรือผู้เปลี่ยน และเอเจนต์ไม่ได้แก้ระเบียนนี้

## ฟอร์มสร้างเปล่าที่อ่านครบ

Paths: `/combo/{cabalpc,cabalpcsea,cabalm,cabalmsea}/shop/items/create`.

- Name/Kind/Option/Duration/Description ยังว่าง; Tradeable และ display switch ปิด. ไม่ใช้ช่องว่างแทนค่า0
- PC TH/SEA แสดง Type combobox เป็น “เลือกหมวดหมู่” ไม่ใช่ GENERAL ที่เลือกไว้แล้ว. PC TH saved native select และ PC SEA create native select ที่อ่านมี GENERAL/CABALPC_PREMIUM; ไม่ได้กดเลือกตัวเลือก
- M TH/SEA แสดง GENERAL เป็นข้อความคงที่ ไม่มี Type select ให้เลือก
- คำแนะนำรูปบนหน้าคือ `.png/.jpg/.webp ขนาดไม่เกิน 5 MB`; เป็นข้อความ UI ไม่ใช่หลักฐานการตรวจไฟล์ฝั่ง server
- ไม่กดปุ่มสร้างเพื่อเปิด dialog เพราะสิทธิ์รอบนี้ห้ามกรอก/สร้าง. Active confirmation ของอีกสามเกมจึงยังไม่ได้พิสูจน์; หลักฐาน M TH เดิมยังใช้ตามขอบเขตเดิม

## HTML IDs และข้อยกเว้นที่สังเกต

IDs หลักที่แสดงบนฟอร์มทั้งสี่เกมยังเป็นชุดเดิม:

| ช่อง | HTML ID |
| --- | --- |
| Name | `item-name` |
| ItemKind | `item-game-item-id` |
| Description | `item-detail` |
| Option | `item-option` |
| Duration | `duration-index` |
| Tradeable | `game-tradeable` |
| Display enable | `display-option-enable` |

M SEA/PC SEA create มี DOM count1 ต่อ IDทั้งเจ็ดที่ตรวจ. PC TH saved ตรวจ count1 ของหกช่องหลักที่สอบถาม; ไม่ยกผลนี้เป็นการตรวจ hidden duplicates ทุกสถานะของทุกเกม

ข้อยกเว้นไม่มี stable ID ที่อ่านได้: PC Type combobox/native select, file input, Create/Save button, saved ID header และ Preview image. File input ที่อ่านไม่มีทั้ง id/name. Generated radix IDs ของเมนูไม่ใช่ stable IDs ที่ใช้แทนสัญญา DEV ได้

PC SEA saved display ที่เปิดอยู่แสดง IDs เพิ่ม `displayOptions-quantity`, `displayOptions-critical`, `displayOptions-is_slotable`, `displayOptions-favorite`. ไม่ได้ toggle หรือแก้ค่า ไม่อ้างสำรวจ dynamic display fields ครบทุกชนิด

HTML `item-game-item-id` เป็นช่อง ItemKind ไม่ใช่ Aztek Item record ID หรือ backend game UUID. ไม่ใช้ ID ของช่องกรอก/ชื่อเกมใน sidebar มาเดา UUID

## ข้อจำกัดเครื่องมือและสิ่งที่ไม่ได้ทำ

- Tab capability ที่มีคือ pageAssets; export รองรับ image/font/stylesheet/video ไม่ใช่ response body ของ Fetch/XHR หรือ script source. Dev API ให้ console logs ไม่ใช่ Network reader
- การตรวจ DOM ที่ทำไม่ให้ backend game UUID. ใน M TH/M SEA/PC SEA create ที่สอบถาม ไม่มี inputชื่อ `game_id`/`data[game_id]` หรือ `data-game-id` attribute. ไม่ขยายข้อสรุปเป็นการค้นทุก runtime/internal state
- ไม่อ่าน cookies/localStorage/sessionStorage, auth headers, credentials, framework internals หรือ session files; ไม่ดัดแปลง fetch/ฉีด script เพื่อดัก response และไม่ใช้ช่องทางอื่นหลบข้อจำกัด
- การโหลด PC TH ครั้งแรก/Playwright helper เคย timeout; เปลี่ยนมาเข้ารายการผ่าน Shop→Item แล้วเปิดลิงก์จริง224861 อ่านสำเร็จ. ไม่ถือ timeout เป็น product test failure หรือหลักฐานว่า224794ถูกลบ. ไม่ reload/ลองเลขระเบียนเป็นชุด

## สถานะงานหลังตรวจ

หลังการอ่านหน้าจอ ผู้ใช้ส่ง GETbodyของPC TH224861เพิ่มและยืนยันbackendgameUUIDได้จาก bodyกับชื่อ/ค่า/เวลาในหน้าItem ตาม [ตารางหลักฐาน](backend-game-identity-20261027.md). เป็นหลักฐานจากผู้ใช้คนละขั้น ไม่ใช่Browserเริ่มอ่านNetworkได้แล้ว และไม่เปลี่ยนขอบเขตการตรวจDOMด้านบน

โค้ดไม่เปลี่ยนจาก [FULL4ที่ตรวจผ่าน](coverage.md); ไม่รันทดสอบเต็มซ้ำเพราะเอกสาร. ไม่แพ็ก SetupเฉพาะMTHแทนเป้าหมายครบสี่เกม ไม่ commit/push/publish/install หรือปิด #12

สิ่งที่ยังต้องยืนยันคือ contract คำตอบสร้าง/ตัวเกมของอีกสามเกม และหลักฐาน Resolve ที่ยืนยันตัวรายการของคำขอเดิมได้. การพบชื่อ/Kind/Option/Duration ตรงกันหรือการเปิด saved page ได้ไม่พิสูจน์ว่าคำขอที่ค้างสร้างรายการนั้น. คง Unconfirmed และห้ามส่งซ้ำ แทนการเดาว่ากู้สำเร็จ
