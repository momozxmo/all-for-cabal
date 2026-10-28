# #12 — ข้อยกเว้นทดสอบสร้างจริงเพิ่ม3รายการ

ผู้ใช้ตอบ “ทำเลย” ต่อคำขอชัดเจนให้สร้างไอเทมเทสเพิ่ม3รายการ PC TH/PC SEA/M SEAเกมละ1 เพื่อเก็บผลPOST. ไม่ใช่สิทธิ์สร้างทั้งคิว สร้างMTHซ้ำ หรือแก้/ลบรายการเดิม. สิทธิ์MTHหนึ่งรายการ26ตุลาคมใช้ครบแล้วและยังเป็นประวัติเดิม

| เกม | ชื่อเทส | Kind / Option / Duration |
| --- | --- | --- |
| CabalPC TH | TEST_AFC_PC_TH_20261027_C13A | 33561487 / 3 / 0 |
| CabalPC SEA | TEST_AFC_PC_SEA_20261027_C13A | 67113458 / 0 / 9 |
| CabalM SEA | TEST_AFC_M_SEA_20261027_C13A | 33562319 / 0 / 17 |

ทุกเกม GENERAL/ผูกมัด/คำอธิบายว่าง/ไม่แนบรูป/ปิดแสดงบนเว็บ. ไม่คัดลอกรูปจากPC SEAตัวอย่าง ไม่สร้างBundle/ส่งของให้ผู้เล่น/แก้หรือลบข้อมูลเดิม. ตรวจชื่อก่อนส่ง; พบชื่ออยู่แล้วหรือผลไม่แน่นอนให้หยุด ไม่ลองซ้ำหรือเปลี่ยนชื่อเพื่อหลบสถานะ

## สถานะปัจจุบัน

**ล่าสุด28ตุลาคม — รับcreate receiptครบ3รายการแล้ว** (รวมMTHเดิมเป็น4เกม). ผู้ใช้ส่งMSEAชุดใหม่messageGame item created/ID224864/UUID/ค่า/created_at02:43:05Zตรงsaved09:43:05Bangkok. Raw `build-cache/new-item-live-three1-msea-post-response-20261028.json` SHA0CCFA87BDBCF24FD154371504C6A1732E44BA8B8642DB1A90E8B76608B72E472; verifier `build-cache/new-item-live-three1-msea-post-verification-20261028.json` exit0. BodyOKก่อนหน้าเก็บแยกและไม่ใช้แทนcreate receipt. สถานะรอMethod/bodyในข้อความล่างเป็นลำดับเหตุการณ์ก่อนชุดแก้ไขนี้. HTTPstatus/countยังไม่ได้รับจึงunknown ไม่ขอbodyเดิมซ้ำ/ไม่สร้างเพิ่ม. ขอบเขตหลักฐานGENERAL/noimage/displayoff; ไม่อ้างทุกdynamicvariant/Premium/causalResolveหรือToolsadapterผ่านจากmanualproofนี้

- PC THสร้างแล้ว ID[224862](https://aztek-tools-v2.combo-interactive.com/combo/cabalpc/shop/items/224862) เวลา27ตุลาคม23:26:52Bangkok. กดCreateหนึ่งครั้งเปิดactive rolealertdialogที่ title/promptตรงItem และปุ่มยกเลิก/ยืนยันอย่างละ1 ไม่มีstableID; เก็บcheckpointก่อนกดยืนยันหนึ่งครั้ง. พบtoastสำเร็จ/row-ownedhrefใหม่ และค้นชื่อเดิมหลังสร้างพบ1รายการเท่านั้น
- เปิดsaved pageจากลิงก์จริง อ่านชื่อ/Kind33561487/Option3/Duration0/GENERAL/ผูกมัด/descriptionว่าง/ไม่มีPreview/displayoffตรงค่าที่อนุญาตทั้งหมด ไม่กดSave/แก้/ลบ. ภาพผลแสดงในแชทแล้ว
- **ได้รับPOST ResponseของPC THแล้ว**: success=true/messageGame item created/resource`data.data`/ID224862/UUID97ac0f24-541a-486c-9d15-e9e1397b46ae/name/Kind33561487/Optionstring3/Durationstring0/GENERAL/ผูกมัด/noimage/descriptionnull ตรงsavedpage. created_at16:26:52Zตรงเวลา23:26:52Bangkokที่อ่านจากแถวจริง. ภาพNetworkของผู้ใช้แสดงitems200fetch; Methodไม่ได้อยู่ในภาพและไม่มีHTTPcountที่ยืนยัน จึงคงcountunknown ไม่อ้างHTTP-level at-most-once
- Rawbody `build-cache/new-item-live-three1-pcth-post-response-20261027.json`, SHA256 B510C24297480180CC0AF2C1904FFBAE9233D4E0C16C20D228FAA3167247C521; verifier `build-cache/new-item-live-three1-pcth-post-verification-20261027.json` exit0. เป็นหลักฐานmanualPC THสำหรับGENERAL/noimage/displayoff ไม่ใช่ToolsadapterทุกvariantหรือpositiveResolve
- **PC SEAสร้างแล้ว ID[224863](https://aztek-tools-v2.combo-interactive.com/combo/cabalpcsea/shop/items/224863)** เวลา27ตุลาคม23:40:03Bangkok. ก่อนสร้างค้นชื่อเทสไม่พบ โดยOption/Durationfilterว่าง; อ่านฟอร์มGENERAL/Kind67113458/Option0/Duration9/ผูกมัด/คำอธิบายว่าง/ไม่แนบรูป/displayoffตรงทุกช่อง. เก็บcheckpointก่อนCreate1ครั้งและก่อนยืนยัน1ครั้งในactivealertdialog. พบtoastสำเร็จและrow-ownedhrefใหม่ จากนั้นค้นชื่อเดิมพบ1รายการเท่านั้น เปิดsavedpageอ่านค่ากลับตรงทั้งหมดและแสดงภาพแล้ว ไม่กดบันทึกแก้ไข
- **PC SEAได้รับPOSTreceiptแล้ว**: success/Game item created/data.data.id224863/UUID88a51177-8468-4bbc-8117-a717de2458a2/ค่าและเวลา16:40:03Zตรงsaved23:40:03Bangkok. Raw `build-cache/new-item-live-three1-pcsea-post-response-20261027.json` SHA5024D878EA5FC49B6E30F90B9564D70F6474A79155D7CEB066211EA7ABB0C097; verifier `build-cache/new-item-live-three1-pcsea-post-verification-20261027.json` exit0. Status/countไม่ได้ส่งจึงยังunknown ไม่ขอbodyเดิมซ้ำ ไม่สร้างPC SEAซ้ำ และไม่อ้างHTTP-at-most-once
- **28ตุลาคม — M SEAสร้างแล้ว ID[224864](https://aztek-tools-v2.combo-interactive.com/combo/cabalmsea/shop/items/224864)** เวลา09:43:05Bangkok. ใช้ชื่อ/ค่าเดิมที่อนุญาตในTab1412035963Brave3ใหม่ หลังพบTab1412035751เดิมปิดไป; ก่อนหน้านี้navigateMSEAไม่ได้executeเพราะapproval-review quota ไม่ใช่safetydenial/createfailure. ค้นชื่อเดิมไม่พบ/อ่านGENERAL/Kind33562319/Option0/Duration17/bound/blankdetail/noimage/displayoffตรง และผู้ใช้ยืนยันNetworkพร้อมในแท็บใหม่แล้ว. Durablecheckpointก่อนCreate1ครั้งและก่อนยืนยัน1ครั้งในactivealertdialog ไม่มีการส่งซ้ำ. พบrow-ownedhref224864แล้วเก็บIDก่อนค้นชื่อซ้ำ พบ1รายการเท่านั้น เปิดsavedอ่านค่ากลับตรงทุกช่องและแสดงภาพ ไม่กดSave/แก้/ลบ. **รอPOSTbody/Status/count**; สิทธิ์manual3รายการใช้ครบแล้ว ห้ามสร้างเพิ่มหรือสร้างทั้งสี่รายการซ้ำ. ชื่อยังมี20261027ตามpayloadที่อนุญาต แม้created_atจริง28ตุลาคม

Checkpointส่วนตัว `build-cache/new-item-live-three1-20261027.json` เก็บงบหนึ่งรายการต่อเกม/ชื่อ/ค่า/สถานะ/ID/จำนวนUIclicksแยกกัน. ก่อนปุ่มที่อาจส่งคำขอครั้งแรกต้องเก็บcheckpointก่อน; หากผลหายให้ถือว่าอาจสร้างแล้ว ไม่กลับเป็นplanned

28ตุลาคมได้รับbodyของM SEA224864แล้ว: success=true/messageOK/resource data.data/UUID/ชื่อ/Kind/Option/Duration/GENERAL/bound/noimage/blankdetail/created_at02:43:05Zตรงsaved09:43:05Bangkok. Raw `build-cache/new-item-live-three1-msea-user-response-20261028.json` SHA5F37B0E601D6E4FE52DCD32D7429902D8E4E91E11AB4805E097322BA28EE8CB9; body-verifierexit0. **ยังไม่จัดเป็นPOSTreceipt**: messageOKและgame_options_2คล้ายGETdetailที่ส่งก่อนหน้า ต่างจากGame item createdในPC TH/PC SEA; ไม่ตัดสินว่าเป็นGETแน่นอนจากshapeอย่างเดียว. ขอผู้ใช้ยืนยันMethod/ชื่อแถว/Statusก่อน; หากเป็นGETเลือกPOSTitemsเดิม ไม่สร้างใหม่. Operation/status/countยังunknown; bodyนี้ยืนยันrecordidentityแต่ไม่ปลดPOSTadaptergate

Browserไม่อ่านNetwork responseโดยตรง จึงต้องให้ผู้ใช้เปิดDevTools Networkในแท็บเดียวกับที่ทดสอบก่อนส่ง และส่งเฉพาะResponsebody/Status/จำนวนPOSTที่เห็น ไม่ส่งHeaders/token/cURL/HAR. การตอบรับสิทธิ์สร้างไม่เท่ากับยืนยันว่าNetworkพร้อม; ไม่สร้างก่อนเตรียมการเก็บหลักฐานเพื่อเลี่ยงสร้างทิ้งโดยไม่ได้receipt

ไม่มีHTTP-level at-most-once claimจากmanualUI. กดแต่ละขั้นครั้งเดียว; หากfrontendส่งซ้ำหรือจำนวนระเบียนผิดคาดให้หยุดและรายงาน ไม่ลบเพื่อซ่อนผล. ไม่แก้runtime/test/sourcefreezeจากการเตรียมmanualprobe และยังไม่ถือเป็นToolsadapteracceptanceหรือpositiveResolveproof
