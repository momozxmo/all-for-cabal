# #12 — หลักฐานจาก frontend source ที่ผู้ใช้ส่ง26ตุลาคม2026

นี่คือการอ่านโค้ดที่ผู้ใช้คัดลอกจาก Browser ไม่ได้ execute bundle, กดสร้าง, ส่ง API, ดึง session หรือทดลองรับผลจาก server หลักฐานนี้ยืนยันเส้นทางใน frontend ไม่ใช่ตัวอย่างคำตอบสร้างสำเร็จจริง

อัปเดต28ตุลาคม: ต่อมาได้รับGENERAL POSTreceiptและsaved readbackครบ4เกมตาม [manual evidence](live-three-probe-20261027.md). ผู้ใช้อนุญาตเลือกCABALPC_PREMIUMและอ่านฟอร์มเปล่า PC TH/SEAแล้ว พบช่องหลักชุดเดิมและอ่านประเภทกลับตรง; ไม่ได้สร้างPremiumจริง. [ข้อสังเกต/ขอบเขต](pc-premium-observations-20261028.md). Adapterใช้game_item_typeจากค่าที่เลือกตามbuilderเดิมและตรวจresponse/readbackให้เป็นประเภทนั้นโดยตรง; ไม่อนุมานPC payloadจากnameของinputที่ยังcamelCase. ชุดPremiumRED6→GREEN13พิสูจน์localcontractเท่านั้น ไม่ใช่livePremiumacceptance. ข้อความmissing/unsupportedในsnapshotเก่าด้านล่างไม่ใช่สถานะปัจจุบัน

## ที่มาของหลักฐาน

ผู้ใช้ส่ง CreateItemPage-D7d7ALDD.js, item.schema-DUVart2o.js, getFormDefaults-BLEJpeAg.js, gameOptionsCasing-CuUEKe4_.js, useSaveConfirm-CHRq6FLH.js, SaveChangeConfirmDialog-C4bvBd5s.js และ index-C6cDnekL.js ในแชท

- Form attachment SHA256: `41FC33A2E2222BD860B281A29F4394D34EF136AD62D7BA553D810CAD23A04512`
- Index attachment SHA256: `7B8BCF0A8FDF52EC0E7C42A4048320CD4CC1308B6B71E02968931AC5524BDFD4`
- ไม่คัดลอก bundle ดิบลง repository/fixtures: index มี authentication/header constants เก็บเฉพาะสัญญาที่ลบค่ากุญแจออก ไม่ใช้ค่าที่ฝังใน bundle ยิง API และไม่เก็บ cookie/token/session

## เส้นทางคำขอที่อ่านได้

CreateItemPage เรียก `postForm` ด้วย path `/{encodeURIComponent(game)}/game/items` และส่ง FormData จากฟอร์ม

Index export `it` คือ API client ซึ่งกำหนด base URL `https://admin-api-v2.combo-interactive.com`; `postForm` เรียก fetch ด้วย method POST และ body เป็น FormData ดังนั้นเส้นทางจาก source คือ:

`POST https://admin-api-v2.combo-interactive.com/{game}/game/items`

game มาจาก route parameter ไม่ใช่ publisher. ขอบเขต Tools ยังคงจำกัดสี่เกมที่อนุมัติ ไม่เพิ่มเกมอื่นจาก bundle

## FormData ของ CREATE

| ช่อง | การประกอบจาก source |
| --- | --- |
| `data[th][name]`, `data[en][name]` | ใช้ name เดียวกันทั้งสองภาษา |
| `data[th][detail]`, `data[en][detail]` | detail หรือข้อความว่าง |
| `data[game_item_type]` | type ที่เลือก |
| `data[game_item_id]` | ค่าที่ trim; frontend ใช้0เมื่อว่าง แต่ Tools ต้องคงกฎ missing/ready ตามสเปก ห้ามเอาพฤติกรรมนี้มาแทนค่าขาด |
| `data[is_game_stackable]` | string true เฉพาะค่าฟอร์มเป็น1 มิฉะนั้น false; ไม่ใช่สิทธิ์เพิ่มช่องนี้ให้ผู้ใช้ในเกมที่ไม่รองรับ |
| `data[game_options_1][tradeable]` | string true/false เมื่อ showTradeable เปิด |
| `data[display_options][is_tradable]` | string true/false เมื่อ showTradeable เปิด แม้ปิด displayOptionsEnabled |
| `files[th][thumbnail]`, `files[en][thumbnail]` | แนบ File เดียวกันเมื่อเลือกภาพ; เก็บ object URL เพื่อพรีวิวในหน้า ไม่ upload ทันทีตอนเลือก |

สำหรับ branch มาตรฐานเมื่อ fieldConfig.gameOptions เป็น null:

| game | Option key | Duration key |
| --- | --- | --- |
| cabalm | `data[game_options_1][itemOption]` | `data[game_options_1][durationIndex]` |
| cabalmsea | `data[game_options_1][item_option]` | `data[game_options_1][duration_index]` |
| cabalpc | `data[game_options_1][item_option]` | `data[game_options_1][duration_index]` |
| cabalpcsea | `data[game_options_1][item_option]` | `data[game_options_1][duration_index]` |

Frontend ใช้0หาก durationIndex ว่างใน branch นี้; Tools ห้ามทำ missing Duration กลายเป็น0โดยไม่ยืนยันต้นทาง

ถ้า runtime fieldConfig มี gameOptions/displayOptions จะประกอบ key ตาม definitions และชนิดของ field ที่กรองด้วย item type ไม่ใช่ใช้ตาราง fallback นี้เสมอ จึงยังต้องยืนยัน settings/DOM ของเกมและ state เป้าหมาย ไม่อนุมาน dynamic definitions จากชื่อเกม

ปิด displayOptionsEnabled แล้วไม่ append display fields กลุ่มปกติ แต่ยังมี is_tradable ตามเงื่อนไขข้างบน. ไม่มีไฟล์แล้ว CREATE ไม่เติมช่อง thumbnail ว่าง; การเติมช่อง thumbnail ว่างในอีก builder เป็น EDIT ไม่ใช้แทน CREATE

## การยืนยันก่อนส่ง

useSaveConfirm.handleSubmit เก็บค่าที่รอและเปิด showConfirm โดยยังไม่เรียก onSubmit; handleConfirm จึงเรียก onSubmit, handleCancel ปิดโดยไม่ส่ง

CREATE dialog ใช้ชื่อ “ยืนยันการสร้าง”, ข้อความ “ต้องการสร้าง Item ใช่หรือไม่?”, ปุ่ม “ยกเลิก”/“ยืนยัน”. Manualprobe MTHเดิม/PC TH/PC SEA27ตุลาคมและM SEA28ตุลาคมพบ active role=alertdialog และปุ่มอย่างละหนึ่งจริง โดยไม่มี stable ID (radix เป็น generated ID). ขอบเขตGENERAL/noimage/displayoffที่ทดสอบ ไม่ใช่ทุกdynamicvariant

## API client และความเสี่ยงส่งซ้ำ

Client แนบ authentication/header ตามระบบเดิม แต่ไม่มีการคัดลอกค่ามาใช้ใน Tools จากหลักฐานนี้

Client จะตรวจ auth response:401 หรือ500ที่เข้าเงื่อนไข token หมดอายุและข้อความ unauthorized. หาก refresh สำเร็จ จะเรียก fetch อีกครั้งด้วย method/body เดิม ซึ่งรวม POST ได้

Tools ต้องไม่ถือว่า timeout/error หลังเริ่มส่งปลอดภัยให้ retry และต้องพิสูจน์ guard จำนวน create requests/checkpoint/หยุดคิวใน synthetic integration ก่อนเปิด adapter ไม่อ้างว่ากันส่งซ้ำแล้วจากการอ่าน source นี้

หลัง HTTP response ผ่าน client เรียก JSON.parse/schema.parse; preprocessing ที่ export `o` อาจ unwrap object ที่มี success(boolean) และ data. ค่า parse จึงไม่จำเป็นต้องเป็นรูปเดียวกับ raw HTTP body

## Positive response ที่ได้รับเพิ่ม — CabalM TH เท่านั้น

ผู้ใช้ส่ง raw body ของรายการเทส224846: `success=true`, resource=`data.data`, positive integer ID=`data.data.id`, backend game UUID=`6eaad7c6-bfc8-48ce-a616-061a2cef8f41`. ชื่อ/Kind33600667/Option0/Duration10/เวลา10:43:21Z ตรง saved page ที่อ่านกลับ. ดู [ที่มาและขอบเขต](live-one-probe-20261026.md). Raw `data.data.id` ต่างจากค่าหลัง client preprocessing ซึ่งอาจ unwrap ไปหนึ่งระดับ; ห้ามใช้ fallback หา ID แบบ recursive

## หลักฐาน GET เพิ่ม27ตุลาคม — CabalPC TH/SEA และ CabalM SEA

ผู้ใช้ส่ง bodyของItem224861ตามคำขอ GET: `data.data.game_id=97ac0f24-541a-486c-9d15-e9e1397b46ae`; ชื่อ/Kind33561487/Option3/Duration0/TypeGENERAL/เวลา07:20:42Zตรงกับ saved pageและแถวรายการที่อ่านจริง. ดู [game identityและขอบเขต](backend-game-identity-20261027.md). ไม่ต้องขอPC THชุดเดิมซ้ำ; ไม่ใช้ GETนี้แทนpositivecreate POSTหรือResolveproof

ต่อมาผู้ใช้ส่งPC SEA224795: `data.data.game_id=88a51177-8468-4bbc-8117-a717de2458a2`; ชื่อ/Kind67113458/Option0/Duration9/GENERAL/displayquantity1และการมีรูปตรงกับ saved page27ตุลาคม. เวลาcreated_at07:05:35Zของ22ตุลาคมมาจากbody ไม่ได้ยืนยันเวลาในUIแยก. ไม่ขอPC SEAชุดเดิมซ้ำ และไม่ยกGETเป็นPOSTacceptance

ได้รับM SEA224791เพิ่มแล้ว: `data.data.game_id=5f0740de-8045-42d4-8460-b03f340f01a6`; ชื่อ[Costume] Idol Face (30 Days)/Kind33562319/Option0/Duration17/GENERAL/ผูกมัด/ไม่มีรูปตรงกับ saved page. created_at21ตุลาคม06:33:33Zมาจากbody ไม่ได้ยืนยันเวลาUIแยก. BackendUUIDครบ4เกมแล้ว ไม่ขอGETเดิมซ้ำ แต่ไม่ยกผลอ่านเป็นผลสร้างหรือResolve

## จุดที่ยังยืนยันไม่ได้

Updateหลังmanualprobe27ตุลาคม: PC TH224862และPC SEA224863activealertdialog/POSTreceiptยืนยันแล้วสำหรับGENERAL/noimage/displayoffตาม [manual3-test](live-three-probe-20261027.md); ยังไม่ถือเป็นToolsadapteracceptanceหรือpositiveResolve และไม่อ้างHTTPcountที่ไม่ได้ยืนยัน

- Create page onSuccess ไม่รับ/อ่าน ID; invalidate รายการ แสดงข้อความสำเร็จ แล้วกลับหน้ารายการ
- Create ใช้ schema export `a` ที่ไม่ได้กำหนด field ID ของคำตอบอย่างเฉพาะเจาะจง. Schemaรายละเอียดที่มี id เป็นอีก operation ไม่ใช่หลักฐาน POST response
- BackendUUID/activeconfirmation/positivecreatebodyในscopeGENERALครบสี่เกมแล้ว: MTH224846/PC TH224862/PC SEA224863/M SEA224864. M SEAได้รับชุดแก้ไขGame item created28ตุลาคมตรงsavedและเวลาแล้ว ไม่ใช้bodyOKก่อนหน้าแทนPOST. HTTPstatus/countที่ไม่ได้รับยังunknown. อีกเกณฑ์ที่ยังขาดคือproofสำหรับresolve Unconfirmedที่ผูกกับwriteเดิม. RawPOSTมาจากผู้ใช้ตามคำขอเลือกPOST ส่วนGETbodyสามเกมเป็นคนละoperation ไม่ใช้แทนPOSTproof
- HTTP2xx, toast, ชื่อ, triple, การพบแถวเพิ่ม หรือ ID ของ nested record อย่างเดียวไม่ใช้แทนหลักฐานสร้างสำเร็จและ identity

ไม่ต้องขอresponse/JavaScriptเดิมซ้ำสำหรับทั้งสี่เกมที่ยืนยันแล้ว. ส่วนที่ยังขาดใช้หลักฐานเดิมหรือbackendcontractโดยไม่ส่งheaders/cURL/HAR/ความลับ. สิทธิ์MTHเดิมและข้อยกเว้นmanual3รายการใหม่ตาม [งบทดสอบ](live-three-probe-20261027.md) ใช้ครบแล้ว ไม่มีสิทธิ์สร้างเพิ่ม/ทำซ้ำเพื่อเก็บตัวอย่าง

เมื่อผู้ใช้สร้างงานจริงตามปกติในอนาคต อาจใช้ response ของรอบนั้นเป็นหลักฐานได้ ไม่ขอให้สร้างระเบียนทิ้งเพิ่มเพื่อเก็บตัวอย่าง. หากจะให้อัตโนมัติสร้างจริง ต้องได้รับสิทธิ์เฉพาะเกม/ข้อมูล/จำนวนใหม่ก่อน ไม่อนุมานจากสิทธิ์อ่านหรือการส่ง source
