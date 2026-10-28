# #12 — หลักฐาน backend game identity

บันทึกข้อมูลที่ผู้ใช้คัดลอกจาก Response แยกจากการอ่านหน้าจอ. ไม่ใช้ชื่อเกม/HTML ID/ItemKind เดา backend UUID และไม่ใช้ GET response แทนสัญญาสร้าง POST

อัปเดต28ตุลาคม: ตาราง/รายละเอียดGETด้านล่างยังเป็นที่มาของidentityแต่ละเกมตามเดิม. ต่อมาได้รับผลสร้างจริงแยกPC TH224862/PC SEA224863/M SEA224864ครบและค่าตรงsavedแล้วตาม [manual3-test](live-three-probe-20261027.md). จึงมีcreatebodyทั้งสี่เกมในscopeGENERAL ไม่ใช่เพียงGETidentityอีกต่อไป; ไม่ใช้GETbodyแทนPOSTและไม่อ้างPremium/allvariants/causalResolveหรือHTTPcountที่ไม่ได้รับ

| เกม | Backend game UUID | ที่มาที่ตรวจเทียบได้ | ขอบเขต |
| --- | --- | --- | --- |
| CabalM TH | `6eaad7c6-bfc8-48ce-a616-061a2cef8f41` | ผู้ใช้ส่ง receiptสร้าง224846; saved pageชื่อ/ค่า/เวลาตรงกัน | หลักฐาน POST เดิมตาม [manual probe](live-one-probe-20261026.md); สิทธิ์สร้างหนึ่งรายการใช้ครบแล้ว |
| CabalPC TH | `97ac0f24-541a-486c-9d15-e9e1397b46ae` | ผู้ใช้ส่ง Responseตามคำขอ GET ของ224861; ข้อมูลตรงกับ [saved pageที่อ่าน27ตุลาคม](readonly-observations-20261027.md) | ยืนยัน game identityจากข้อมูลอ่าน Item; ไม่ใช่หลักฐาน POST หรือ Resolve |
| CabalPC SEA | `88a51177-8468-4bbc-8117-a717de2458a2` | ผู้ใช้ส่ง GETbodyของ224795; ชื่อ/Kind/Option/Duration/ชนิด/ค่าที่แสดงและการมีรูปตรงกับ saved page27ตุลาคม | ยืนยัน game identityจากข้อมูลอ่าน Item; ไม่ใช่หลักฐาน POST หรือ Resolve |
| CabalM SEA | `5f0740de-8045-42d4-8460-b03f340f01a6` | ผู้ใช้ส่ง GETbodyของ224791; ชื่อ/Kind/Option/Duration/GENERAL/ผูกมัด/ไม่มีรูปตรงกับ saved page27ตุลาคม | ยืนยัน game identityจากข้อมูลอ่าน Item; ไม่ใช่หลักฐาน POST หรือ Resolve |

## CabalPC TH — Item224861

ผู้ใช้ส่ง JSON หลังขั้นตอนล้าง Network filterและเลือก ResponseของItemเดิมตามคำขอ GET. Agentไม่ได้อ่าน method/HTTPstatus/headersด้วยตัวเอง จึงบันทึกที่มาจากผู้ใช้ ไม่อ้างเป็น independent network capture

- Body: success=true, message=OK, resource=`data.data`; idเป็นinteger224861
- Name: GM's Blessing (Lv. 5) Holy Water x3
- Kind33561487; `game_options_1.item_option`เป็นstring3 และ `duration_index`เป็นstring0
- TypeGENERAL; is_game_stackable=false; display_options.is_tradable=false; detail/thumbnail_url=null
- created_at2026-10-27T07:20:42Z ตรงเวลา14:20:42Bangkokในแถวรายการที่อ่านจริง
- Rawbodyเก็บเฉพาะใน `build-cache/new-item-pcth-get-evidence-20261027.json`; ไม่มีheaders/token/cookies/HAR. ไม่คัดลอกtrace requestIdลงตารางสาธารณะ
- SHA256ของไฟล์หลักฐาน: `2CD9E1C224A90FB18F40A7B4E0C3FDCAD2EB3C48452DD7A751F35EB24F106778`; ตรวจว่าไฟล์ถูกGit ignoreแล้ว

ชื่อ/Kind/Option/Duration/Type/Tradeable/รูปและเวลาตรงกับรายการที่เปิดผ่าน row-owned hrefจริง `/combo/cabalpc/shop/items/224861`. จึงไม่ต้องขอ PC TH response ชุดเดิมซ้ำ

ข้อจำกัด: bodyนี้ไม่พิสูจน์ HTTPstatusหรือ schemaของcreate POST, active confirmation หรือว่า Itemใดเกิดจากคำขอที่ตอบกลับหาย. ยังไม่เปิดสร้างอีกสามเกม/positiveResolveจากข้อมูลนี้เพียงอย่างเดียว. ไม่มี runtime/testเปลี่ยน ไม่มีการสร้างจริงเพิ่มหรือรันfullซ้ำ

## CabalPC SEA — Item224795

ผู้ใช้ส่ง bodyตามคำขอ GETของItemเดิม ไม่ใช่ผลสร้างใหม่. Agentไม่ได้อ่าน method/HTTPstatus/headersด้วยตัวเอง และไม่ดาวน์โหลดรูปจากURLในbody

- success=true, message=OK, resource=`data.data`; idเป็นinteger224795 และ game_id=`88a51177-8468-4bbc-8117-a717de2458a2`
- Name: Blessing Bead - AXP (600%)(1 day); TypeGENERAL; Kind67113458; item_optionเป็นstring0; duration_indexเป็นstring9
- is_game_stackable=false; display_options: favoritefalse/quantity1/is_slotablefalse/is_tradablefalse; detail=null
- thumbnail_urlไม่ว่าง สอดคล้องกับ Previewที่อ่านพบในหน้าItem27ตุลาคม. ไม่ได้ตรวจว่าURLหรือเนื้อภาพตรงกัน และไม่ใช้presenceแทนpixel proof
- created_at2026-10-22T07:05:35Z เท่ากับ14:05:35Bangkokจากbodyนี้; รอบอ่านหน้าจอไม่ได้ยืนยันเวลาแถวของระเบียนนี้แยกต่างหาก จึงไม่อ้างว่าtimestampตรงกับUI
- Rawbody: `build-cache/new-item-pcsea-get-evidence-20261027.json` ในGit-ignored build-cache; ไม่มีheaders/token/cookies/HAR และไม่คัดลอกtrace requestIdลงตารางสาธารณะ
- ตรวจไฟล์หลักฐานแล้ว SHA256=`8B8BD61004366A090EEDB0B50C3E04AA62BCB09D3DCAAA2FB07A9374D07F80FA`; รายงาน `build-cache/new-item-pcsea-get-verification-20261027.json` แยกความถูกต้องของbodyออกจากPOSTproofและการเทียบรูป/เวลาในUI

ไม่ต้องขอPC THหรือPC SEAชุดเดิมซ้ำ. ต่อมาได้รับM SEAตามหัวข้อถัดไปแล้ว; positivecreate POST/activeconfirmationของอีกสามเกมและpositiveResolveยังเป็นคนละเกณฑ์ ไม่ปลดจากGETbodyนี้

## CabalM SEA — Item224791

ผู้ใช้ส่ง bodyตามคำขอ GETของItemเดิม ไม่ใช่ผลสร้างใหม่. Agentไม่ได้อ่าน method/HTTPstatus/headersด้วยตัวเอง

- success=true, message=OK, resource=`data.data`; idเป็นinteger224791 และ game_id=`5f0740de-8045-42d4-8460-b03f340f01a6`
- Name: [Costume] Idol Face (30 Days); TypeGENERAL; Kind33562319; item_optionเป็นstring0; duration_indexเป็นstring17
- is_game_stackable=false; display_options.is_tradable=false; detailและthumbnail_url=null. สอดคล้องกับการอ่านค่าผูกมัดและไม่พบPreview ไม่อ้างรายละเอียดรูป/การรับไฟล์ของserver
- created_at2026-10-21T06:33:33Z เท่ากับ13:33:33Bangkokจากbody; ไม่ได้ยืนยันเวลาแถวในUIแยก จึงไม่อ้างtimestampUIตรงกัน
- Rawbody: `build-cache/new-item-msea-get-evidence-20261027.json` ในGit-ignored build-cache; ไม่มีheaders/token/cookies/HAR และไม่คัดลอกtrace requestIdลงตารางสาธารณะ
- SHA256=`7EC8A00750D1C95587E8C1A28B92B42C95135C3407E75DC8AB06E3E9452FC49B`; รายงาน `build-cache/new-item-msea-get-verification-20261027.json` ตรวจbody/เวลาUTC→ไทย/UUIDทั้งสี่ไม่ซ้ำและsource183ยังตรงFULL4 โดยไม่อ้างPOSTproof

ตอนนี้ backend game UUIDครบทั้งสี่เกมตามหลักฐานแต่ละoperationในตาราง ไม่ต้องขอGET/receiptชุดเดิมซ้ำ. การสร้างของอีกสามเกม/activeconfirmationและการกู้ที่ผูกกับคำขอเดิมยังไม่ถูกพิสูจน์จากGETเหล่านี้ ไม่มีการสร้างจริงเพิ่มหรือเปลี่ยนruntime/test
