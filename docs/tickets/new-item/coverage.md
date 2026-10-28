# New Item #12 — สถานะพัฒนาและหลักฐาน

อัปเดต28ตุลาคม2026. **พัฒนาและตรวจเกณฑ์22ข้อในเครื่องครบแล้ว แต่ยังไม่รวมในSetup0.1.42/ยังไม่เผยแพร่หรือปิด#12**. [สรุปผลสุดท้ายที่อ่านง่าย](acceptance-final-20261028.md)

## ล่าสุด28ตุลาคม — หลังได้create receiptครบ4เกม

Manualผลสร้างGENERALครบMTH224846/PC TH224862/PC SEA224863/M SEA224864 พร้อมอ่านsavedค่ากลับตรง; สิทธิ์สร้างทดสอบใช้ครบ ห้ามทำซ้ำ. [ที่มา/ข้อจำกัด](live-three-probe-20261027.md). ไม่อ้างHTTPcount/statusที่ไม่ได้รับหรือallvariants/Premium

ต่อadapterGENERALทั้งสี่เกมและUIเลือก/ยกเลิก/อ่านกลับ/handoffในเครื่อง: REDAPI3+UI6→GREEN59passed340.07s/native+wrapper0/JUnitactualunique59/0/0/0/freeze183ตรง/originalhashตรง/evidence_errors[]. [ผลตรวจเฉพาะส่วน](../../../build-cache/new-item-four-game-green1-20261028-verification.json). การปฏิเสธสามเกมในเทสต์เก่าแทนด้วยpositivecontract3กรณีตามหลักฐานใหม่; MTHเดิมและbehavior35กรณีรักษาครบตามmapping ไม่อ้างoldชื่อทุกชื่อยังเหมือนเดิม

ส่วนกู้จากreceiptที่runnerเก็บเองก่อนsavedcommit: APIRED4→GREEN17 แล้ว UIRED2→GREEN52passed216.85s/native+wrapper0/JUnitactualaggregateunique52/0/0/0/freeze185ตรวจอิสระตรง/originalhashตรง/evidence_errors[]. [ผล API/UI/cohort เดิม](../../../build-cache/new-item-receipt-resolve-green2-20261028-verification.json). ไม่ยอมรับIDจากชื่อ/triple/clientproof, ผูกowner/game/attempt/revision/payload และอ่านใหม่ก่อนผ่าน. ไม่มีreceiptยังUnconfirmed; ไม่ใช่universal lost-response recovery. กู้แต่ละสมาชิกcohortแยกได้โดยไม่สร้างเพิ่ม

PC Premium: อ่านฟอร์มเปล่าหลังเลือกประเภททั้งPC TH/SEAตามสิทธิ์ผู้ใช้ ไม่บันทึก/อัปโหลด. ช่องหลักชุดเดิมและsourcebuilderส่งประเภทที่เลือกโดยตรง จึงรองรับCABALPC_PREMIUMแบบstrict type/payload/UUID/receipt/readback; MยังGENERALเท่านั้น. [ที่มาและข้อจำกัด](pc-premium-observations-20261028.md). ValidRED6failed25.56s→GREEN13passed49.15s/native+wrapper0/JUnit13/0/0/0/freeze185ตรวจอิสระตรง/originalhashตรง/evidence_errors[]. [ผลเฉพาะส่วน](../../../build-cache/new-item-pc-premium-green1-20261028-verification.json). ไม่อ้างserverจริงรับPremium/รูปหรือallvariants; unknownlayoutยังหยุดปลอดภัย

**FULL5จบ13:14:06Bangkok: 3104passed4failed1warning9761.23s/native+wrapper1**. JUnitactualaggregateunique3108/4failure/0error/0skip/freeze185/originalhashตรง/evidence_errors[]. [หลักฐานผลล้ม](../../../build-cache/new-item-full5-failure-verification-20261028.json). ทั้ง4traceคือเทสต์UIสองฟังก์ชัน×1280/390ยังหาชื่อปุ่มเก่า แต่DOMแสดงชื่อใหม่disabledถูกต้อง. แก้เฉพาะtestlocator คงdisabled/no-createassert และย้ายscreenshotสองฟังก์ชันไปtmp_pathไม่ทับหลักฐาน; โปรแกรมไม่เปลี่ยน. **UI22กรณีผ่านแล้ว176.66s/native+wrapper0/JUnit22/0/0/0/freeze185ตรวจอิสระตรง/originalhashตรง/evidence_errors[]** ตาม [ผลตรวจ](../../../build-cache/new-item-ui-label-green1-20261028-verification.json)

**FULL6จบผ่าน3108passed1warning10333.65s/native+raw+signed+wrapper0 เวลา17:47:41.844849Bangkok**. [ผลตรวจอิสระ](../../../build-cache/new-item-full6-20261028-verification.json): JUnitactualaggregateunique3108/0failure0error0skip/freeze185ตรงก่อน–หลังและตรวจอิสระ/originalhashตรง/evidence_errors[]. [retention](../../../build-cache/new-item-full6-retention-20261028.json)รักษาnf5เดิม3108ชื่อและnf4/scoped59/52/13/22ตามmappingครบ ไม่มีmissing. [เกณฑ์22ข้อ](../../../build-cache/new-item-acceptance-final-20261028-verification.json)อ้าง179distinctpassingcaseจากJUnitชุดเดียว ไม่ใช่เทสต์เพิ่ม. FreezeSHAF6FBFC96C3123974C6B67B1DF7E371DB1D81FD8D915E17EDAD5BDECE85DCB124/JUnitSHA2013DC01581C18FB6034C66C52ECFC8933CF6A2843AE0C0D74A23F7AA4032C7B. คำเตือนเดิมprocess-localdevelopmentsecretsไม่แก้ ไม่ใช่warning-free. ห้ามpoll/restartnf6/nf5/scopedที่จบแล้ว ไม่บวกยอดแทนfull ไม่Setup/commit/push/ปิด#12

หัวข้อ27ตุลาคมและตารางmilestoneด้านล่างเป็นประวัติก่อนงานเพิ่มนี้ ไม่ใช้ข้อความunsupportedสามเกมของsnapshotเก่ามานับเป็นปัจจุบัน และไม่ยกFULL4แทนsourceใหม่

หลักฐานเพิ่มหลังอ่านหน้าจอ: ผู้ใช้ส่ง GETbodyของPC TH224861/PC SEA224795/M SEA224791ครบแล้ว ชื่อ/Kind/Option/Duration/ชนิดและข้อมูลที่แสดงตรงกับItemที่อ่านจริง ดู [ตารางgame identity](backend-game-identity-20261027.md). UUIDครบทั้งสี่เกมเมื่อรวมMTHreceiptเดิม ไม่ขอGET/receiptชุดเดิมซ้ำ. GETนี้ไม่ใช่positivePOST/Resolveproofและยังไม่เปลี่ยนruntimeหรือfull4

หลังผู้ใช้อนุญาตอ่าน Aztek จริงรอบใหม่ ตรวจ saved Item/ฟอร์มสร้างเปล่าครบสี่เกมแล้ว ดู [ข้อสังเกต27ตุลาคม](readonly-observations-20261027.md). IDsช่องหลักยังเป็นชุดเดิม; ไม่กรอก/สร้าง/แก้/อัปโหลด/ลบ. Browser API ไม่มี Network response reader และ DOM ไม่ให้หลักฐาน backend UUID/คำตอบสร้างอีกสามเกม/positiveResolve จึงยังไม่ปลดส่วนที่ขาด ไม่ใช้ผลอ่านหน้าจอเป็นหลักฐาน POST. ไม่มีruntime/testเปลี่ยนหรือรันfullซ้ำ

## ปัจจุบัน21:41น. — รายละเอียดประวัติย้อนหลังผ่านรอบเต็มแล้ว

เปิดแต่ละรอบเพื่อตรวจค่าต้นฉบับ ค่าที่ส่ง ค่าที่อ่านกลับ และสาเหตุที่ไม่ผ่านได้แล้ว. ใช้ข้อมูลที่เก็บไว้ของรอบนั้น ไม่เอาผลล่าสุดไปแทนประวัติเก่า; ข้อมูลเก่าที่ไม่มีจะแจ้งว่าไม่มีข้อมูล. การเปิดประวัติไม่ส่งคำขอหรือเปลี่ยนข้อมูล และผลผ่านเก่าไม่ทำให้ส่งต่อได้เมื่อผลล่าสุดไม่ผ่าน

**FULL4 session63031/build-cache/nf4 จบ3053passed1warning9533.46s/native+wrapper0 เวลา21:40:57.570719Bangkok**. Actualcollection3053; ตรวจอิสระJUnitactual/aggregate/unique3053/0fail0error0skip, freeze183ก่อน–หลังและoriginaluserhashตรง/evidence_errors[]. JUnitSHA FB268F8FEC66F2C3852844A3A1F889DBA3356C69AAF8C2DA902774273155B8DD; freezeSHA7854CC0015A138FA596B43ED17882C794893DBFA516B0DEAE48B136D75A94458. [ผลตรวจรอบเต็ม](../../../build-cache/new-item-full4-20261027-verification.json) และ [ตรวจชื่อแบบordinal](../../../build-cache/new-item-full4-retention-20261027.json) ยืนยันกรณีเดิมfull3ทั้งหมด3046/scoped534ครบ รวม7กรณีประวัติใหม่/cohort27. คำเตือนเดิมtest_local_runtime.py:86 process-local development secretsยังอยู่ ไม่ใช่warning-free. เทียบfull3เปลี่ยนเฉพาะweb/static/new_items.jsและtests/test_new_item_ui.py ไม่มีbackend/locator/CSSเปลี่ยน. รายละเอียดประวัติM2เสร็จเฉพาะขอบเขตlocalแล้ว; อีกสามเกม/positiveResolveยังunsupported. ไม่Setup/commit/push/live/issueclosure และไม่รันชุดที่จบแล้วซ้ำเพราะเอกสาร

ก่อนรอบเต็ม ชุดregression534passed880.23s/native+wrapper0/JUnit534/0/0/0ผ่านบนsource183เดียวกัน พร้อมretained527ครบ/originalhashตรง/evidence_errors[]. ครอบคลุมNewItemทุกไฟล์และFinder/Bundle/import/auth/gatesเดิม; aggregate build-cache/new-item-history-detail-regression1-20261027-verification.json, JUnitSHA94480570AE9DA528E61A28BBE31594E03BE03BF161EAFA02EEFE5D148991FBFA

รายละเอียดTDDก่อน534จบ (ประวัติ ไม่ใช่สถานะกำลังรัน):

ผู้ใช้สั่งทำต่อหลังระบุM2เป็นงานที่เหลือ จึงเพิ่มตามข้อกำหนดประวัติเดิม: เปิดผลเปรียบเทียบของแต่ละรอบได้ ใช้snapshotของรอบนั้น ไม่ใช้รอบล่าสุดแทน; แสดงmissingmetadataตรงๆ; ackไม่กลายเป็นrecheck; historicalpassไม่ปลดล็อกlatestmismatch. RED6failed121.11s+legacyRED1failed6.52s→GREEN7passed44.46s/native+wrapper0/JUnit7/0/0/0/independentfreeze183+originalhashตรง/evidence_errors[]. Aggregate new-item-history-detail-green1-20261027-verification.json, JUnitSHA03C6D888E474B821A9A9A0E01C2689B06E36ED3D7A396F32AD7E9BB851C8882B. UI1280/390/keyboard/no request or state mutation/XSStext/imagepresencequalificationผ่านเจาะจงแล้ว; เพิ่มassertscrollคอลัมน์actualบนมือถือก่อนregressionปัจจุบัน. กำลังregression534/session29876/build-cache/nhds1; ยังไม่full4. **Full3ด้านล่างเป็นbaselineก่อนเปลี่ยนUIประวัติ ไม่ใช่fullpassของsourceปัจจุบัน**. ไม่มีbackend/locator/CSS/dependency/OS/live/Setup/commit/push/issueเปลี่ยน

## Baseline18:31น. — FULL3ก่อนเพิ่มรายละเอียดประวัติย้อนหลัง

**FULL3session53296/build-cache/nf3 จบ3046passed1warning9193.41s/native+wrapper0 เวลา18:30:53.278784Bangkok**. Independentverifierexit0: JUnitactual/aggregate/unique3046/0fail0error0skip, freeze183ก่อน/หลังและตรวจอิสระตรง, originaluserhashตรง, evidence_errors[]. JUnitSHA1818153DAE65DC6C03F163D799E51AEA9BF50BE9DE2D54711D4FFA93719251E0; aggregate build-cache/new-item-full3-20261027-verification.json. Supplementalnew-item-full3-retention-20261027.jsonตรวจexactordinalชื่อscoped527ครบ/cohort27ครบ; verifierหลักตรวจfull2เดิม3019ครบ. FreezeSHA A96B902D46613553CC2375893F99F0552358F293AABD29388B1E9D11E7149D26 ตรงregression527passed876.68s. คำเตือนเดิมtest_local_runtime.py:86 RuntimeWarning/process-local development secrets ไม่ใช่warning-free/ไม่ได้แก้. Regroupที่รองรับตรวจlocalครบแล้ว; ไม่ถือว่าserverรับการสร้างจริงทุกเกมหรือทั้ง#12ครบ. NoSetup/commit/push/live/issueclosure; ไม่รันfull/scopedที่จบแล้วซ้ำเพราะเอกสาร

รายละเอียดระหว่างพัฒนาก่อนregressionจบ (เก็บผลเก่าตามจริง):

เพิ่ม strict opt-in group_identical/defaultfalse, จัดกลุ่มตามเกมและค่าทุกช่องที่ใช้สร้าง, batch CAS/commitทุกสมาชิกก่อนPOSTและก่อนอ่านกลับ, แยกผลเทียบตามreferenceเดิม และคำนวณremainingตามID. UIแสดงจำนวนItemกับจำนวนร่าง/การใช้IDร่วมกันก่อนยืนยัน และกลุ่มสร้างร่วมกันในผลตรวจ. REDก่อนแก้3failed0error13.25s; ผู้ใช้อนุญาตdiagnosticretry original3ผ่าน14.29s. Expanded1ยัง26pass1fail1warning76.39sจากWinError10055ขณะเปิดasyncio self-pipeก่อนdispatchHTTP ไม่ใช่cohortassertion; เก็บหลักฐานเดิม. หลังlocalreadinesscheckผ่าน boundedretryบนsourceเดิม expanded2ผ่าน27กรณี74.20s/native+wrapper0/JUnit27/0/0/0/independentfreeze183ตรง/JUnitSHA0B974405D26A6FB598639A41A1E878C9AB04BA3D786C60C02D10FA39F8BB7F62. ครอบคลุมloss/restart/atomicrollback/stale/concurrency/reference/selected-only/images. ต่อhistorylabelด้วยRED2failed18.68s→GREEN2passed8.92s/JUnitSHAF3D873AE5735FE9E0D032CC596D5790EB1AA8BCDBC08B9C3F05708A8F053439A/freeze183ตรง. Gridgeistตรวจconfirm1280/390และresult390แล้ว count/sharedID/perreferenceชัด คงรูปแบบเดิม ไม่ใช่all-device/accessibilityaudit. รอบเก่าค้าง/noJUnitยังinterruptedunknown ไม่เปลี่ยนย้อนหลังเป็นpass. ตอนนี้regression527กรณี/33ไฟล์session81074/build-cache/nccr1; full3ยังไม่เริ่ม. ไม่มีรีวิวซ้ำ/live/Setup/commit/push/issueclosure/OSหรือdependencychange

## Baseline27ตุลาคม15:04น. — ก่อนเพิ่มส่วนรวมร่างรอบปัจจุบัน

**full2ผ่านแล้ว27ตุลาคม15:04น.**: 3019passed1warning9489.02s/native+wrapper0/JUnitaggregate+actual+unique3019/0/0/0/evidence_errors[]. Freeze182ตรวจอิสระก่อน/หลังตรง/originaluserhashตรง; ทุก475และ3018caseเดิมยังครบ. Aggregate build-cache/new-item-full2-verification-20261027.json; JUnitSHA64D14205A038513E7241F75DB3E5FE337075FF5BC7848F3235B71A4B4B6DA3F5. คำเตือนเดิมprocess-local development secrets. Full1ยัง3017passed1failed1warning/native1; เปลี่ยนเฉพาะfixtureของno_problemให้เป็นผลผ่านครบจริง คงassert409และเพิ่มsavedไม่มีrecheckแยก ไม่เปลี่ยนโปรแกรม/ไม่บวกยอดต่างรอบ/ไม่ลบผลเก่า

รีวิวอิสระCritical0/Important8/Minor2และonefixpassผ่านแล้ว: RED9failed1passed→GREEN10, affected117/review18, หลังแก้fixtureตรวจ35แล้วfull2ผ่าน3019. Separate-sheet controlเดิมผ่านอยู่แล้ว ไม่อ้างว่าเคยล้ม. 475เป็นmilestoneก่อนreviewfix. Fullผ่านยืนยันเฉพาะโค้ดที่รองรับ ไม่เปลี่ยนส่วนunsupportedให้ครบ

- ส่งจาก New Item→Finder→ส่งทั้งหมด ยึด ID ของ occurrence ที่เลือก ไม่ขยายข้ามรายการแค่เพราะสามค่าเหมือนกัน; Finderเดิมที่ไม่ผูกIDยังทำงานเดิม
- กลุ่มจากการนำเข้าใช้scopeของชุดนำเข้า/Sheet ไม่ใช้IDร่าง, เก็บเรต/tier/Document Reference/RANDOMและลำดับแถวเดิม
- ถ้าปิดโปรแกรมหลังเก็บIDแต่ก่อนตรวจครบ เปิดใหม่ยังมีID/ผลตรวจไม่ครบ ต้องตรวจอ่านอย่างเดียวหรือรับทราบก่อนเลือกชุดใหม่ ไม่สร้างรายการเดิมซ้ำ
- ค่าที่แก้บนหน้าจอแต่ยังไม่กดบันทึกต้องบันทึกร่างก่อนยืนยัน; Finderselectionต้องมีsnapshotตรงปัจจุบัน และcreateต้องมีผลค้นItemเดิม/searchtokenที่ตรงกับfrozenpayload
- ร่างที่เดิมต่างกันแต่แก้จนค่าที่ใช้สร้างเหมือนกัน: ปฏิเสธscopeที่ซ้ำก่อนเปิดbrowser เก็บร่าง/referenceครบ. **ยังไม่รองรับรวมร่างที่ยืนยันแล้วภายหลังโดยอัตโนมัติ**; เลือกสร้างหนึ่งรายการแล้วค้น/เลือกใช้IDเดิมกับร่างอื่นเอง ไม่อ้างเกณฑ์9ครบ
- Minorที่พักไว้: UIประวัติรอบเก่าแสดงเวลา/ผลแต่ยังไม่เปิดรายละเอียดเปรียบเทียบทั้งหมด ข้อมูลเต็มยังเก็บและอ่านทางAPIได้

ยังไม่เปิดcreateอีกสามเกม/positiveResolveเมื่อIDหาย, ไม่มีการทดสอบlive/สร้างเพิ่ม, ไม่มีSetup/commit/push/issueclosure. รายงาน reviewer/RED/GREEN/คำตัดสินอยู่ในledger .superpowers/sdd/2026-10-25-new-item-creation-recheck/

## ความคืบหน้า26ตุลาคม

- ล่าสุดหลัง464: UIสร้างเฉพาะMTH พร้อมเกม/จำนวน/ชื่อ/ค่า/คำอธิบายก่อนส่ง, cancel/Escapeคืนfocus, controlsbusy, doubleclick/Toolsresponseหาย/reloadไม่ส่งซ้ำ, ผลผิด/ไม่ครบ/unconfirmedยังแสดงและหยุด. รับทราบไม่auto-next ต้องเลือกnewscopeเอง และserverตรวจack owner+เกมหลังlatestcheck/หลังgate. **475passed683.62s wrapper0/JUnitaggregate+actual+unique475/0/0/0/source51ก่อน-หลังตรง/originaluserhashตรง/old464ครบ**; build-cache/new-item-create-ui-scoped1-20261026/verification.json, JUnitSHA D5A0C1AA0C62FA3CE0400C437CA89D14BBF238845104D9E758C4EC95EDA90B93. ภาพ1280/390ตรวจแล้ว. ไม่มีlive traffic/writeเพิ่ม ไม่ใช่finalfull/review; อีกสามเกมผู้ใช้ไม่มีข้อมูลจึงคงunsupportedwrite ไม่ขอข้อมูล/สร้างเพิ่มซ้ำ. PositiveResolveกรณีAztekไม่คืนIDยังขาด
- ผู้ใช้อนุญาตmanualสร้างไอเทมเทส1รายการ: CabalM TH `TEST_AFC_NEW_ITEM_20261026_C9D7` ID224846 บันทึก/อ่านกลับตรงและค้นชื่อพบ1รายการ. ต่อมาผู้ใช้ส่ง raw response `success=true`/`data.data.id=224846` และ MTHgameUUID/ค่า/เวลา ตรงกันตาม [หลักฐานและที่มา](live-one-probe-20261026.md). ใช้สิทธิ์ครบแล้ว ห้ามสร้างเพิ่ม/ส่งซ้ำ/ลบ. HTTPcountของmanualprobeยังไม่ยืนยันอิสระ; นี่ไม่ใช่การรันToolscreateadapter/full#12
- หลักฐานจาก JavaScript: POSTไป `https://admin-api-v2.combo-interactive.com/{game}/game/items`, FormData/รูปสองภาษา, casingใน branchมาตรฐาน และconfirm flow ตาม [contract](frontend-contract-20261026.md). ณmilestone26ตุลาคมมีpositivePOST/UUIDเฉพาะMTH; ต่อมาGET27ตุลาคมยืนยันUUIDครบ4เกมแล้วตามตารางidentityด้านบน. PositivePOSTอีกสามเกมและresolveยังขาด ไม่ต้องถามDEVหรือส่งJS/GET/receiptเดิมซ้ำ
- Milestoneก่อนUIใหม่: [MTHcreate/checkpoint API](create-mth-slice-20261026.md) ผ่าน **464passed624.51s wrapper0/JUnitaggregate+actual+unique464/0/0/0/source44ก่อน-หลังตรง/originaluserhashตรง**; `build-cache/new-item-create-scoped1-20261026/verification.json`, JUnitSHA DB75685B57621CF5A0986B53C69CBD657CD1D96EACFCB42D6BE9A54D9C1EF6EE. รวมold396ครบ+create30+APIเดิมเพิ่ม38 ไม่ใช่426หรือfinalfull. ณsnapshot464ปุ่มUIยังปิด ภายหลังเพิ่มMTHUIแล้วตาม475หัวข้อแรก ไม่ใช้464แทนsource51ปัจจุบัน
- ต่อส่วนอ่านอย่างเดียว: มี API/หน้า UI ค้น Item เดิมจากร่างที่ยืนยันแล้วตามเกม+Kind/Option/Duration, เก็บ candidate ที่ผูก owner/revision/payload/search token. ไม่กรองด้วยชื่อหรือเลือก ID อัตโนมัติ; ผู้ใช้เลือกเองและยืนยันก่อนอ่านรายละเอียดใหม่เพื่อเทียบ reference
- ใช้ลิงก์จริงในแถวตารางที่อ่านได้ ไม่ประกอบลิงก์ไปเปิดจากตัวเลขเอง; missing/foreign/duplicate link หยุด. เก็บ checkpoint `source=existing` และแสดง “ใช้ Item เดิม — ไม่ได้สร้างใหม่”; mismatch/incomplete ยังบล็อก handoff. ไม่ใช้ขั้นนี้แก้ unconfirmed/submitting หรือสร้าง Item ใหม่
- API RED18failed5.21s→GREEN18passed57.66s; UI RED3failed93.69s(missing controls)→API+UI GREEN24passed83.29s wrapper0; แยก pagination/empty/ปิดกั้นPOST/ผลค้นหาเปลี่ยนระหว่างอ่าน4passed16.99s wrapper0. ตรวจภาพ1280/390/candidate/dialog/cancel-focus/no-page-overflowแล้ว
- Milestoneก่อนเพิ่มcreate adapter: **396passed500.40s wrapper0/JUnitaggregate+actual396/0failures/0errors/0skips/source43ก่อน-หลังตรง**. รวม New Itemทุกไฟล์กับ Finder ID-first/handoff/import/auth/limits/plan/dev-script/startup เดิม; `build-cache/new-item-existing-scoped1-verification.json`, JUnitSHA B31F246FF3793ABB9CDAD8E3500BCD1071A3C38D6F020F3D28A03FA40F024366. ไม่ใช่ sourceล่าสุด/final full suite/fresh review และไม่ทำให้ #12ครบ
- ล่าสุด: แนบรูปส่วนตัวกับร่างในเครื่อง, เปิดดู/ถอดการผูกกับร่าง/เก็บ digest เพื่อแยกกลุ่มได้แล้ว; รับเฉพาะ PNG/JPEG/WebP ภาพนิ่ง ≤5,000,000bytes และ20ล้านพิกเซล ตรวจเนื้อไฟล์จริง/owner/revision/hash ไม่อ้างว่า Aztek รับรูปแล้ว. ถอดรูปไม่ลบไฟล์ต้นฉบับหรือ bytes ที่เก็บไว้
- ปุ่มรับทราบ/ข้ามบันทึกประวัติเท่านั้น; mismatch/incomplete/unconfirmed และข้อห้ามส่งต่อยังอยู่. API continue เป็นเจตนาของผู้ใช้ ไม่ใช่เริ่มคิวต่อ
- ผู้ใช้อนุญาต Pillow13.0 เฉพาะ environment แยก `build-cache/new-item-media-venv-20261026`; base Pillowยัง11.1.0 ไม่มีอัปเกรด Python/environment เดิม
- Milestoneรูป/รับทราบก่อนเพิ่มเลือก ID เดิม: **340passed215.89s wrapper0/JUnitaggregate+actual340/0failures/0errors/0skips/source26ก่อน-หลังตรง**; `build-cache/new-item-media-ack-scoped2-verification.json`, JUnitSHA48B990BD20D50F3E96206E847AA9C808AAB4DE7701BD5617ED8D552CB6B944FB. ไม่ใช่ final full suite หรือ sourceล่าสุด
- Milestoneแยกตรวจ Tab/Space/Enter/Escape/focus และ100แถวชื่อไทยยาวบนมือถือ: log2passed4.68s/JUnitactual2/0/0/0; wrapper output ของรอบเก่ากู้ไม่ได้หลัง tool truncationจึงไม่อ้าง wrapper0รอบนั้น. หลัง UIเปลี่ยน กรณีทั้งสองรวมอยู่ใน396ล่าสุดที่มี wrapper0แล้ว; screenshot `build-cache/new-item-hundred-rows-mobile.png` ตรวจ ไม่มี whole-page overflow
- รอบก่อน `new-item-media-ack-scoped1` ยังคง338passed2failed219.12s wrapper1: fixture setup_dev สองกรณีล้มที่พาธยาว. ใช้ interpreter/TEMP/assertions เดิม เปลี่ยนเฉพาะ basetempใหม่สั้นแล้วสองกรณีเดิมผ่าน ก่อนตรวจ340ใหม่; ไม่แก้ Windows/settings/setup scripts และไม่อ้าง deep-path setup หายแล้ว
- Milestones305/363ด้านล่างเป็นประวัติก่อนรูป/รับทราบ ไม่บวกยอดกับชุดล่าสุด
- มีหน้า `/new-items` แบบใช้ APIจริง: เลือกSheet/แก้ทีละแถว/ยืนยันdefaultร่าง/ดูผล/เลือกpassedไปFinder. เลือกสร้างใหม่ได้เฉพาะMTHในworking treeพร้อมยืนยันอีกครั้ง อีกสามเกมปุ่มสร้างยังปิดพร้อมเหตุผล ไม่ใช่Setupที่เผยแพร่แล้ว
- ส่งต่อเป็นงาน Finder แยกเฉพาะที่เลือก ไม่แก้พื้นที่ต้นทาง ไม่เพิ่มคิว Bundle; เก็บ Amt/Sheet/row และแยก group key ที่ซ้ำข้ามพื้นที่งาน
- UI7 + handoff13 ผ่าน20กรณี39.64s wrapper0/JUnit20/0/0/0; ตรวจภาพ Desktop1280x900/Mobile390x844, keyboard cancel/focus, overflow, reload ไม่ส่ง POST, mismatch กับ incomplete แสดงพร้อมกัน
- UI milestone หลักฐาน `build-cache/new-item-ui-green3-verification.json`; ชุดรวมก่อน mode fix ผ่าน363กรณี624.59s wrapper0/JUnit363/0/0/0/source19ตรง ไม่รันซ้ำ
- Legacy Shop/ItemCode ส่งต่อผิดเป็น Event: RED2failed1passed5.44s → เก็บ source mode ผ่าน preview/ร่าง → GREEN3passed5.72s; ไม่เปลี่ยน parser เดิม
- Finder มีปุ่มเพิ่มเฉพาะรายการที่ไม่พบและเลือกไว้เป็นร่าง พร้อมยืนยัน/ยกเลิก; รักษาเกมเดิม ไม่สร้างบน Aztek. RED2 → GREEN2passed2.75s; การค้นหาแบบ scoped กลุ่มยังปิดปุ่มนี้พร้อมเหตุผล ให้เปิดพื้นที่งานเต็มก่อน
- Milestoneหลังแก้ mode และเพิ่ม Finder entry ก่อนแนบรูป: **305 passed185.23s / wrapper0**, JUnit aggregate+actual305/0failures/0errors/0skips/source21filesก่อน-หลังตรง. หลักฐาน `build-cache/new-item-handoff-ui-scoped2-verification.json`; SHA256 JUnit 2B0F0720A3F8E4C0A8532089862CA8CD7549CECDFEF382F299D077B8B6E86390. ชุดเฉพาะ ไม่ใช่ full suite
- ดู [เกณฑ์22ข้อที่ผ่านเฉพาะส่วน/ยังขาด](acceptance-current.md) โดยไม่รวมยอด363กับ305เป็นจำนวน tests ของ source เดียว
- สิทธิ์สร้างจริง1รายการใช้ครบแล้ว ไม่มีสิทธิ์สร้างเพิ่ม/แก้/ลบ และยังไม่ commit/push/Setup/ปิด #12

ผู้ใช้อนุมัติแผนและให้ทำต่อแบบ Native ในแชทนี้ และต่อมาอนุญาตอ่านฟอร์มกับ Item เดิมทั้งสี่เกม โดยล็อกอินเองแล้ว
สิทธิ์เดิมห้าม live writes ต่อมาได้รับข้อยกเว้นmanualcreate1testตามหัวข้อบนและใช้ครบแล้ว; ไม่อนุญาตรายการที่สอง/แก้/ลบ/อัปโหลดหรือทั้งคิว และยังไม่อนุญาต commit/push/Setup/ปิด #12
สเปก: [สำเนา issueที่ยืนยันแล้ว](../../superpowers/specs/2026-10-25-new-item-issue12-approved-spec.md)
แผน: [งาน5ส่วน](../../superpowers/plans/2026-10-25-new-item-creation-recheck.md)

## ทำในเครื่องแล้ว

- APIนำเข้า workbookแบบเลือกSheet, templateใหม่และadapterเอกสารแผนเดิม; previewไม่สร้างหรือเพิ่มร่างเอง
- ร่างผูกเกม/ผู้ใช้, ต้นฉบับและoccurrence/Amt/ตำแหน่งไม่หาย; ค่า0/falseไม่ใช่ช่องว่าง
- ค่าGENERAL/ผูกมัดที่ต้นทางไม่มีต้องยืนยัน; M Premiumไม่เปลี่ยนเงียบเป็นGENERAL
- แก้ร่างมีrevision/CAS, กดapplyพรีวิวพร้อมกันเพิ่มร่างได้ครั้งเดียว, clientแก้original/ผลผ่านเองไม่ได้
- referenceที่ต้นทางมีอยู่ไม่เปลี่ยนตามร่าง; ช่องเดิมว่างใช้ค่าผู้ใช้เติมพร้อมprovenance
- รวมรายการเมื่อคุณสมบัติสร้างเหมือนกันทั้งหมดและคงทุกต้นทาง; same tripleแต่ชื่อ/type/tradeable/descriptionต่างไม่ยุบ
- ตัวเปรียบเทียบNew Itemตามreferenceทุกoccurrence แยกmismatchจากincomplete, ตรวจgame/Item IDกับcheckpointที่ให้แยก, ไม่ถือค่าร่าง/ผลค้นเป็นactual
- ตัวอ่าน Item เดิมตรวจชื่อ/Kind/Option/Duration/Type/Tradeable/Description จาก ID และขอบเขตฟอร์มที่ตรวจไว้
- API ตรวจซ้ำใช้เกมและ Item ID จาก checkpoint ที่เก็บไว้เท่านั้น ไม่รับ actual/reference/ผลผ่านจาก client และไม่สร้าง Item
- ประวัติตรวจซ้ำเก็บแต่ละครั้งแยกกัน ไม่เขียนทับครั้งก่อน; ผลตรวจไม่เปลี่ยนสถานะว่าบันทึก Item แล้ว
- เปิดแอปใหม่แล้วงานที่ค้างตอนส่งบันทึกจะเป็น “ยังยืนยันการสร้างไม่ได้”; เก็บ ID/หลักฐาน/ผลตรวจเดิม ไม่เริ่มสร้างหรือเปิด browser เอง และกู้ซ้ำแล้วไม่เพิ่มประวัติซ้ำ
- รูปบน Aztek ตรวจได้เพียง presence ไม่อ้างเนื้อภาพตรงกัน; รูปในร่างมี private upload UI/API แล้ว แต่ยังไม่ส่งขึ้น Aztek
- รับทราบ/ข้ามผ่านAPI/UIพร้อมhistoryCAS ไม่เปลี่ยนresult/creationID/reference/สิทธิ์ส่งต่อ ไม่เดินคิวเอง; MTHnewscopeเลือกเองหลังackล่าสุดเท่านั้นและserverบล็อกก่อนbrowser/หลังgateหากยังไม่ack
- ค้นหา/เลือก Item เดิมผ่าน API/UI แบบ explicit, ใช้ BrowserOperationGateและตรวจสถานะใหม่หลังรอ, fresh readbackและCASก่อนบันทึก checkpoint. ผลค้นหาเก่าหรือร่างเปลี่ยนไม่สามารถทับผลล่าสุด; serverไม่รับ URL/actual/passed ที่ clientแต่งเอง

ข้อด้านบนเป็น API/domain/reader และUIในworking tree: MTHมีflowสร้างจำลองครบถึงselectedhandoffแล้ว แต่ยังไม่รองรับสร้างครบทั้งสี่เกม. Manualprobe1รายการแยกจากToolsadapterและใช้สิทธิ์ครบแล้ว
Checkpointจากการเลือก Itemเดิมและสร้างใหม่MTHผ่าน run API/browserจำลองจริงแล้ว ไม่ใช่ fake runner/storage checkpointล้วน. ไม่ยกผลจำลองเป็นข้อเท็จจริง live หรืออ้างทั้งสี่เกมพร้อมแล้ว

## หลักฐานที่มีและสิ่งที่ยังขาด

Retained2026-10-01: docs/new-item-dom-observations.md ในoriginalworktree (อ่านอย่างเดียว)
ยืนยันemptycreateformทั้งPC/M TH/SEA ไม่กรอก/upload/submit. ไม่ใช่หลักฐานPOSTหรือsaved-result

| ส่วน | สิ่งที่พบ | ข้อจำกัด |
| --- | --- | --- |
| ชื่อ/Kind/Option/Duration/Description | item-name/item-game-item-id/item-option/duration-index/item-detail | อ่าน create/saved อย่างละหนึ่งตัวอย่างต่อเกมแล้ว; description ตัวอย่างว่าง ไม่อ้างทุกรูปแบบ |
| Tradeable/display | game-tradeable/display-option-enable | saved ตัวอย่าง Tradeable=false; true ยังเป็น synthetic coverage |
| PC Type | GENERAL/CABALPC_PREMIUM, ไม่มี stable ID | label-owned select; ต้องรอ options โหลดจริง ไม่เติม GENERAL เอง; saved Premium ยังไม่สุ่มอ่าน |
| M Type | GENERAL คงที่ | อ่าน saved ทั้ง M TH/SEA แล้ว; รูปแบบเปลี่ยนเป็น select ต้องหยุด |
| รูป | hiddenfileinputไม่มีID, UIแนะนำPNG/JPG/WebP<=5MB | ไม่ยืนยันชนิด/responseที่serverรับ, ไม่มีpixelproof |
| createendpoint/payload/confirmation | frontend POST/admin-api-v2/FormData; MTHactivealertdialogและmanualsaveยืนยันแล้ว | อีกสามเกม/dynamic fieldConfig/unknownstateยังไม่ครอบคลุม |
| create result-ID/resolve proof | ผู้ใช้ส่ง MTHsuccess raw `data.data.id=224846`/gameUUID/ค่า/เวลาตรงsavedpage; GETของPC TH/SEAและM SEAยืนยันbackendUUIDครบ4เกมแล้วตามตารางidentity | ยังไม่มีpositivePOST/activeconfirmationของอีกสามเกมหรือpositiveResolveproofของwriteที่คำตอบหาย; ไม่ยกGETแทนPOST/ไม่recursive-ID fallback |
| existing saved Item | ตัวอย่าง PCSEA224795/PCTH224794/MTH224801/MSEA224791 | หนึ่งตัวอย่างต่อเกม ไม่ใช่ทุก live variant; รูปตรวจ presence เท่านั้น |
| ค้นหา Item เดิม/ลิงก์ในแถว | reuse HeadlessFinder ID-first main/form/search/table/pagination contract เดิม; detail href ต้องอ่านจากแถว ID เดียวกันและตรงเกม/path/ID ที่ทราบ | main/form/table/top-search/Next/record link ไม่มี stable ID ตาม exception เดิม; DEV ยังควรให้ stable ID. ไม่อนุมาน href เมื่อเป็น button/หาย/กำกวม; stateนอก contractหยุด ไม่อ้าง live variants ครบ |

ผู้ใช้ตอบว่าไม่มีrequest/response/savedItemหลักฐานเพิ่มใน25ตุลาคม2026
หลังผู้ใช้ล็อกอินเอง ได้อ่าน DOM ตามสิทธิ์เฉพาะแล้ว ดู [หลักฐานอ่านอย่างเดียว](readonly-observations-20261025.md)
ตอนauditเดิมยังไม่ทราบ createendpoint/payload/confirmation/result-ID; ต่อมาผู้ใช้ส่งsourceจริงและMTHreceiptยืนยันส่วนที่ระบุด้านบนแล้ว ไม่ได้ใช้เพียงชื่อไฟล์มาเดาcontract. อีกสามเกม/unknownstate/resolveยังไม่ครบ
การอ่าน assetโดยไม่มี credentials เคยหยุดที่Sign In;26ตุลาคมไฟล์รุ่นปัจจุบันตอบ403/HTML Sign Inเช่นกัน ก่อนผู้ใช้ส่งsourceเอง ไม่มีการดึงcookie/sessionหรือหลบgate

## ประวัติการทดสอบช่วงแรก (ไม่ใช่สถานะปัจจุบัน)

รายการในหัวข้อนี้เป็นcheckpointก่อนเพิ่มMTHcreate/UIและก่อนรีวิว27ตุลาคม เก็บไว้เพื่อย้อนตรวจ ไม่ใช้ข้อความงานค้างเก่าให้นับงานซ้ำ สถานะปัจจุบันอยู่หัวเอกสารและ acceptance-current.md

- Task1 RED22(404จริง)→GREEN22; concurrency/typeRED4→GREEN27; sizeRED1→scoped115passed21.29s(exit0)
- Task2 purecomparisonRED28→localcombinedGREEN56passed11.10s(exit0); ไม่ใช่API/runnercreate/readbackผ่าน
- ช่องExcelอ่านเป็นวันที่ทำpendingJSONล้ม: RED1→normalizeเป็นค่าที่แสดงและแก้ได้, ห้ามเดา0. ค่าoriginalตัวเลขอ่านไม่ได้แก้แล้วต้องใช้manualreferenceไม่ใช่impossiblereference: RED1→minimalfix
- Latestlocal scoped3: **145passed27.48s**, wrapperexit0/JUnitaggregate+actual145/0failures/0errors/0skips; build-cache/new-item-local-scoped3-verification.json. JUnitSHA DACE8BC34E5E5722D13E0253A209AB4A073093E9A1C64D106126F58B995630AE. Source9files snapshotในbuild-cache/new-item-local-source-snapshot1.json
- Reader RED19 → URL host fix → พบ fixture ไม่ระบุ UTF-8 (วิเคราะห์ DOM ยืนยัน windows-1252) → แก้เฉพาะ fixture: GREEN3 **19 passed27.70s / wrapper0**. GREEN1/2 ที่ไม่ผ่านเก็บไว้ ไม่เปลี่ยนเป็นผ่าน
- Recheck API RED16 → GREEN1 **16 passed23.91s / wrapper0**; เพิ่ม RED2 **2 failed1 passed** ยืนยันว่าต้องแจ้ง control ที่ผิดและบล็อก POST จากหน้าเอง แล้วแก้เฉพาะสองจุด → scoped readback **137 passed174.49s / wrapper0**
- Restart recovery RED2failed2passed → GREEN4passed1.57s / wrapper0; สถานะ/เกม/ID/reference/ประวัติเดิมคงอยู่, ไม่เปิด browser, ไม่แตะเครื่องมืออื่นหรือเดา schema ที่ไม่รู้จัก
- ล่าสุดหลังเชื่อม recovery: **218 passed189.64s / wrapper0**, JUnit aggregate+actual218/0failures/0errors/0skips; source/test14filesก่อน-หลังตรง. รวม New Item, Bundle ID-first, auth, request limits และ startup งานค้นหาเดิม. หลักฐาน `build-cache/new-item-recovery-scoped1-verification.json`; JUnitSHA F8C9780374336D20093F1C9FBF400FB9BE9EBFC879ED89023F420B69B6FEC0AC. เป็น scoped regression ไม่ใช่ full suite หรือ #12 เสร็จ
- รักษาlog/JUnitทุกรอบในbuild-cache, original/release/WRเดิมไม่เปลี่ยน
- ณcheckpoint218ยังไม่มี full suite, UIสร้างครบ flow หรือ fresh final review. ภายหลังMTHUI/reviewfixผ่านเฉพาะส่วนและfull1เริ่มแล้วตามหัวเอกสาร; ยังไม่มีcommit/push/Setup/ปิด#12
- Task2 reader/comparison/APIผ่านตามcoverageของcheckpointนั้น. ส่วนMTHcreate/checkpoint/UI/คิวที่เลือกเพิ่มภายหลังดูสถานะ27ตุลาคม; อีกสามเกมและpositiveResolveยังขาด ไม่ถือTask3–5ครบทั้งสเปก

## ประวัติหลักฐานที่เคยขาดก่อนเปิดขั้นสร้าง — สถานะปัจจุบันอยู่หัวเอกสาร

บรีฟDEVเดิมเป็นประวัติ: [รายการคำถามเดิม](dev-create-contract-request.md). ผู้ใช้ถามDEVไม่ได้; ไม่ขอส่งบรีฟ/JS/receiptเดิมซ้ำหรือสร้างข้อมูลจริงเพิ่ม

Method/host/path/FormData/confirm source และ MTHrawresponse-ID/gameUUIDมีหลักฐานแล้ว. อีกสามเกม/unknownstate/resolveยังไม่ครบตาม [contract](frontend-contract-20261026.md); ปิดเฉพาะcapabilityที่ขาด ไม่เรียกทั้งหมดว่าไม่มีหลักฐาน
รับได้จากโค้ด create/save ที่ตรวจสอบได้ หรือ request/response ตัวอย่างที่ลบ cookie/token/ข้อมูลลับแล้ว ไม่จำเป็นต้องสร้าง Item จริงเพื่อเก็บใหม่
Source frontendที่มีแล้วไม่ระบุIDของPOSTอย่างเฉพาะเจาะจง: ไม่ใช้schemaรายละเอียดหรือผลจำลองมาแทนข้อเท็จจริงของserver
จึงยังไม่เปิดสร้างครบทั้งสี่เกมหรือส่งมอบSetup ไม่อ้างว่าผู้ใช้กดใช้งาน #12 ครบแล้ว และไม่ปิดissue. MTHUIที่ทดสอบเป็นโค้ดรุ่นพัฒนา ไม่ใช่สิทธิ์ให้เอเจนต์สร้างจริงเพิ่ม

การผ่านเทสต์domainไม่ทำให้ #12 เป็นcomplete และไม่ทำให้มีสิทธิ์บันทึกAztekจริง

## ประวัติการต่อสิทธิ์อ่าน25ตุลาคม

ผู้ใช้อนุญาตอ่านฟอร์ม/Itemเดิมทั้ง4เกมแล้วด้วยคำตอบ“ทำต่อเลย”ต่อคำถามสิทธิ์เฉพาะนั้น
พยายามเปิดฟอร์มPCSEAที่มีhrefในหลักฐานเดิม1ครั้ง แต่ไปSSOที่dex.combo-interactive.com
auto-reviewบล็อกเพราะเป็นคนละoriginที่ยังไม่ได้อนุญาต ไม่ใช่ผู้ใช้กดปฏิเสธ
ณ ตอนนั้นยังไม่ได้อ่าน DOM ใหม่ จึงหยุดเฉพาะส่วนที่ติด SSO ไม่ใช้ช่องทางอื่นหลบ gate
ต่อมาผู้ใช้แจ้ง “เข้าแล้ว”; พบ dashboard ที่ล็อกอินแล้วและอ่าน DOM ทั้งสี่เกมสำเร็จตามหลักฐานด้านบน
เหตุการณ์ SSO เดิมไม่ใช่ blocker ปัจจุบัน แต่สิทธิ์อ่านไม่รวมการบันทึก Item
