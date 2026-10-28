# PC Premium — อ่านฟอร์มโดยไม่บันทึก28ตุลาคม2026

ผู้ใช้อนุญาตเฉพาะเลือกCABALPC_PREMIUMในฟอร์มสร้างเปล่าของPC TH/SEAและอ่านช่องที่เปลี่ยน ห้ามกดสร้าง/ยืนยัน/แนบไฟล์/แก้รายการเดิม. เปิดแท็บงานBrave3ใหม่ PC TH1412036007 และPC SEA1412036010 แยกจากแอป/แท็บผู้ใช้. เลือกเพียงType ไม่กรอกช่องอื่น ไม่กดCreate/Confirm/Save และไม่อัปโหลด

ทั้งสองเกมก่อนเลือกพบTypebuttonrolecomboboxไม่มีstableID ภายในowningmain/formที่มีitem-nameหนึ่งตัว; native selectมีตัวเลือกว่าง/GENERAL/CABALPC_PREMIUM. เลือกจากactivepopupจริงแล้ว native selectและtriggerอ่านกลับCABALPC_PREMIUMตรงกัน

หลังเลือกทั้งสองเกมยังมีช่องชุดเดียวกัน:

ภาพมีplaceholderตัวอย่างHP Potion/7199/100/0 แต่DOM.valueของName/Kind/Option/Durationยังว่างจริงทั้งหมด ไม่คัดลอกplaceholderไปเป็นค่าร่างหรือdefault

| ช่อง | Stable ID / ชนิด | ค่าที่อ่าน |
| --- | --- | --- |
| ชื่อ | item-name / input name=name | ว่าง |
| ItemKind | item-game-item-id / input name=game_item_id | ว่าง |
| คำอธิบาย | item-detail / textarea name=detail | ว่าง |
| Option | item-option / input name=game_options_1.itemOption | ว่าง |
| Duration | duration-index / input name=game_options_1.durationIndex | ว่าง |
| Tradeable | game-tradeable / button rolecheckbox | false |
| Web display | display-option-enable / button roleswitch | false |
| รูป | inputtypefileไม่มีstableID | valueว่าง/ไม่เลือกไฟล์ |

ไม่พบช่องสร้างเพิ่มหลังสลับPremium; มีinputcheckboxไม่มีIDที่เป็นคู่ควบคุมของTradeable/displayตามRadix ไม่นำมาแทนstableID. Generatedradix IDsไม่ใช้เป็นcontract. ชื่อinputยังcamelCaseแม้gameเป็นPC จึงใช้กฎFormData snake_caseจากfrontend sourceที่ผู้ใช้ส่ง ไม่อนุมานpayloadจากinputname

ขอบเขต: นี่ไม่ใช่ผลserverรับPremiumจริง ไม่ใช่PremiumPOSTreceipt/activeconfirmation/live savedPremiumหรือทุกdynamicvariant. สัญญาPOST/clientbuilder/responseIDเป็นของgameเดียวกันที่มีGENERALreceiptแยกแล้ว และsourceส่งgame_item_typeจากค่าที่เลือกโดยตรง. เปิดadapterPremiumได้เฉพาะรูปแบบที่พิสูจน์นี้ โดยexactmultipart/expectedtype/UUID/ID/snapshotต้องตรง; layout/fields/responseอื่นหยุด ไม่guessหรือretry. SyntheticPremiumfixturesต้องอ้างว่าsource-backed+observedform ไม่ใช่live-createproof. สิทธิ์สร้างจริงยังใช้ครบ ไม่มีสิทธิ์สร้างPremiumเพื่อเก็บตัวอย่าง
