# #12 — เกณฑ์ที่ผ่านในเครื่องและขอบเขตที่ไม่อ้างเกินหลักฐาน

อัปเดต28ตุลาคม2026. ตรวจเกณฑ์22ข้อในขอบเขตlocalautomatedครบแล้ว และส่งมอบ0.1.43/ปิด#12ตามขั้นส่งมอบแยก โดยไม่อ้างทุกlivevariant. [สรุปอ่านง่าย](acceptance-final-20261028.md)

**ส่งมอบภายหลังผลพัฒนาแล้ว**: ผู้ใช้อนุญาตขั้นส่งมอบแยก; [Setup0.1.43](../../local-release-v0.1.43.md)เผยแพร่stable/latest/ดาวน์โหลดhashตรง และ#12ปิดCLOSED/COMPLETED18:22:45Bangkok. ข้อความยังไม่ส่งมอบในmilestoneเก่าด้านล่างเป็นสถานะก่อนสิทธิ์ใหม่นี้ ไม่ใช่งานค้างปัจจุบัน
อ้างอิงเกณฑ์22ข้อใน [สเปกที่อนุมัติ](../../superpowers/specs/2026-10-25-new-item-issue12-approved-spec.md)
ผลชุดทดสอบและข้อจำกัดล่าสุดอยู่ใน [coverage](coverage.md)

ปัจจุบัน28ตุลาคม: GENERALทั้ง4เกมผ่านชุดเฉพาะ59กรณี; Resolveจากreceiptที่โปรแกรมเก็บเองผ่านAPI/UI/cohort52กรณี; PC Premiumตามsourcebuilderและฟอร์มที่อ่านจริงผ่าน13กรณี. ManualGENERALreceipt/savedครบ4เกมแล้ว ไม่ขอซ้ำ/ไม่สร้างเพิ่ม. [หลักฐานและขอบเขต](coverage.md). ไม่อ้างlivePremium/รูป/ทุกvariant

FULL5จบ13:14:06Bangkokด้วย3104passed4failed1warning9761.23s/native+wrapper1/JUnit3108/4/0/0/freeze185ตรง/originalhashตรง/evidence_errors[]. ทั้ง4คือtestlocatorชื่อปุ่มเก่า; DOMจริงในtraceมีชื่อใหม่disabled. แก้เฉพาะเทสต์2ไฟล์ ไม่แก้โปรแกรม/ไม่ผ่อนdisabledหรือno-createguard แล้ว **UI22กรณีผ่าน176.66s/native+wrapper0/JUnit22/0/0/0/freeze185ตรวจอิสระตรง**; ทั้ง4caseเดิมผ่านครบ

**FULL6จบ3108passed1warning10333.65s/native+raw+signed+wrapper0 เวลา17:47:41.844849Bangkok**. ตรวจอิสระJUnitactualaggregateunique3108/0failure0error0skip/freeze185ก่อน–หลังและตรวจhashอิสระ/originalhashตรง/evidence_errors[]. [ผลตรวจ](../../../build-cache/new-item-full6-20261028-verification.json) และ [22เกณฑ์พร้อม179distinctpassingcase references](../../../build-cache/new-item-acceptance-final-20261028-verification.json) เป็นหลักฐานจากJUnitชุดเดียว ไม่บวกยอดscopedเป็นtestsเพิ่ม. ชื่อเดิมnf5ทั้งหมด3108/nf4และscopedตามmappingครบตามretention. ผลnf5คงfailed คำเตือนเดิมไม่แก้ การส่งมอบภายหลังตรวจเสร็จแล้วตามหัวเอกสาร ไม่ใช่การติดตั้งบนเครื่องผู้ใช้

Baseline27ตุลาคม21:41น.ก่อนโค้ดเพิ่ม: FULL4ผ่าน3053กรณี มีคำเตือนเดิม1รายการ9533.46s/native+wrapper0/JUnitactualaggregateunique3053/0/0/0/freeze183ตรง/originaluserhashตรง/evidence_errors[]. Aggregate build-cache/new-item-full4-20261027-verification.json และnew-item-full4-retention-20261027.json; JUnitSHA FB268F8FEC66F2C3852844A3A1F889DBA3356C69AAF8C2DA902774273155B8DD. รายละเอียดประวัติM2เสร็จแล้ว ไม่ใช่งานค้าง; FULL4ไม่ใช่ผลผ่านsourceปัจจุบัน

Baselineก่อนUIประวัติ18:31น.: **FULL3ผ่าน3046กรณี คำเตือนเดิม1รายการ9193.41s/native+wrapper0**; ตรวจอิสระJUnitactual/aggregate/unique3046/0fail0error0skip, freeze183ตรง/originaluserhashตรง/retainedfull2เดิม3019+scoped527+cohort27ครบ/evidence_errors[]. Aggregate build-cache/new-item-full3-20261027-verification.json และnew-item-full3-retention-20261027.json; JUnitSHA1818153DAE65DC6C03F163D799E51AEA9BF50BE9DE2D54711D4FFA93719251E0. ส่วนรวมร่างที่รองรับตรวจครบในเครื่องแล้ว แต่ไม่ใช่#12ครบทั้งสี่เกม/ไม่ใช่รุ่นเผยแพร่. เก็บoldinterruptionและexpanded1WinError10055ตามจริง; ไม่แก้OS/ผ่อนassertion/สร้างlive/Setup/commit/push

Baselineก่อนcohort27ตุลาคม15:04น.: full2ผ่าน3019กรณี/คำเตือนเดิม1รายการ9489.02s/native+wrapper0/JUnit3019/0/0/0/freeze182+originaluserhashตรง. Full1ยัง3017passed1failed1warningตามจริง; แก้fixtureเท่านั้นจึงตรวจfull2ใหม่ ไม่บวกยอดต่างรอบ

คำว่า “ผ่านเฉพาะส่วน” หมายถึงมีโค้ดจริง/API จริงทดสอบกับฐานข้อมูลแยกและเว็บ Aztek จำลอง ไม่ใช่ server จริงยอมรับการสร้างแล้ว

หมายเหตุbaselineหลังreviewก่อนcohort: full2ยืนยันส่วนที่รองรับ ณ15:04น. ไม่ใช่#12ครบทุกข้อ; ตอนนั้นข้อ9ปฏิเสธscopeซ้ำก่อนbrowser/คงreferenceครบ. ปัจจุบันopt-in regroupผ่านfull3แล้วตามข้อ9ด้านล่าง. ก่อนcreateต้องมีผลค้น/searchtokenตรงpayload; Finderต้องsnapshotปัจจุบัน. Regressionของsourcegroup/rate/reference/order, saved-ID-no-recheckและsend-all bindingยังอยู่ครบในfull3

| ข้อ | สถานะและหลักฐานที่ตรวจได้ | ส่วนที่ยังขาด |
| --- | --- | --- |
| 1 | Import/API/UI เลือก Sheet ตามชื่อ; `test_sheet_selection_keeps_names_and_does_not_change_input` | ไม่ครอบคลุม workbook จริงทุกแบบ |
| 2 | `test_template_download_roundtrip_is_a_preview_not_create`; previewไม่submit; UIสร้างทั้ง4เกมแยกการเลือก/ยืนยันอีกขั้น อยู่ในFULL6ที่ผ่าน | ไม่ใช่รุ่นเผยแพร่ |
| 3 | `test_from_finder_preserves_only_selected_missing_occurrences` และ Finder-entry UI เลือก/ยกเลิก | UI ต้นทางแบบ scoped กลุ่มยังหยุดอย่างปลอดภัย ต้องเปิดพื้นที่งานเต็ม |
| 4 | `test_missing_duration_is_not_zero`, `test_unreadable_numeric_cell_remains_an_editable_draft`; manualGENERALทั้ง4เกมค่าอ่านกลับตรง | ไม่อ้าง serverรับค่าทุกแบบ/ทุกประเภท |
| 5 | `test_implicit_general_and_bound_require_explicit_confirmation`, `test_m_premium_is_not_silently_changed`; PC Premiumใช้ชนิดที่เลือก/ผิดreceiptต้องไม่ผ่าน | มีmanualGENERAL4เกม แต่ไม่มีlivePremium/ทุกvariant |
| 6 | Reference/API/comparison: manual fill กับแก้ค่าที่ต้นทางมีอยู่แยกกัน; `test_changed_draft_does_not_make_original_difference_pass` | ไม่ส่งค่าทดลองเพิ่มไปAztek; การทดสอบToolscreateใช้เว็บจำลอง |
| 7 | UIทั้ง4เกมเลือกunchecked→ยืนยันเกม/จำนวน/ประเภท/ค่า; cancel/Escapeคืนfocus/POST0 บน1280/390. APIexplicitdecision/CASตรวจซ้ำ อยู่ในFULL6ที่ผ่าน | ไม่ใช้manualแทนToolscreateบนserverจริง |
| 8 | ค้น candidate ตามเกม+Kind/Option/Duration; ไม่เลือก ID เอง. ใช้ ID เดิมต้องอ่านใหม่; สร้างใหม่ทั้ง4เกมต้องมีผลค้น/searchtokenตรงfrozenpayloadก่อน พร้อมคำยืนยันแยก | live list variants ที่ไม่มี row-owned link ยืนยันไม่ได้จะหยุด |
| 9 | รวมตอนนำเข้าเดิมและexplicit group_identical=trueหลังเลือกยืนยัน: เกม+ค่าที่ใช้สร้างทุกช่อง/ภาพตรงกันจึง1POSTจำลองพร้อมbatch checkpointทุกสมาชิก/per-reference checks/handoff. Cohort27/GUI1280–390ทั้งหมดผ่านfull3; callerเดิมที่ไม่opt-inยังrejectduplicate | ไม่อ้างliveHTTPcountหรือการสร้างจริงทุกเกม |
| 10 | Handoffเก็บAmt/Sheet/row/position, กลุ่มตามscopeนำเข้า/Sheet, rate/tier/reference/RANDOM. ชุด18ทดสอบsend-allผูกIDกับoccurrenceและเรียงตามต้นทาง | รูปแบบเอกสารนอกfixtureยังไม่ครอบคลุม; ไม่ใช่การสร้างจริงครบสี่เกม |
| 11 | Comparison29 + reader19 + recheck API18 ทดสอบจริงตามขอบเขต DOM ที่มี | DOM live variants นอกที่สำรวจยัง unknown/safe-stop |
| 12 | run APIทั้ง4เกมหยุดเมื่อmismatch/incomplete/unconfirmed; UIคงรายการถัดไปunchecked. ต้องackล่าสุดก่อนเลือกnewscopeเอง; serverตรวจowner/game/หลังgate. ackไม่auto-nextหรือrewriteผล อยู่ในFULL6ที่ผ่าน | ไม่ใช่ระบบresumeที่replayรายการเดิม |
| 13 | lost-responseเก็บunconfirmed/ไม่retry/หยุดถัดไป; Resolveใช้server-owned receiptของattempt/game/revision/payload/IDเดิมแล้วอ่านใหม่ ผ่านAPI/UI/cohort52 | ถ้าคำตอบและหลักฐานหายทั้งหมดต้องคงUnconfirmed ไม่เดาIDจากชื่อ/triple |
| 14 | เลือกItemเดิมและสร้างใหม่ทั้ง4เกมผลิตcheckpointผ่านAPI/browserจริงในระบบจำลอง; independentDBเห็นsubmittingก่อนPOST/savedIDก่อนGET. Resolveเก็บprovenIDก่อนอ่านใหม่ อยู่ในFULL6ที่ผ่าน | ไม่อ้างToolsserveracceptanceหรือlivePremiumจากfixture |
| 15 | Handoffปฏิเสธmismatch/incomplete/unconfirmed; ackไม่เปลี่ยนผล/ID/reference. explicitremaining-newscopeหลังackได้syntheticID92 แต่originalunconfirmedไม่ถูกreplay/ส่งต่อ. ackเก่าหลังมีrecheckใหม่ใช้ไม่ได้ | continueเก็บเจตนา ไม่auto-resume; ยังไม่resolveรายการเดิมด้วยหลักฐานไม่พอ |
| 16 | เปิดใหม่เก็บID/ผลไม่ครบ ไม่สร้างซ้ำ; ขาดsavedcheckpointแต่มีcausalreceiptกู้IDเดิม/อ่านใหม่ได้ ผ่าน52รวมrestart/concurrency/cohort/session/gaterace | ถ้าไม่มีreceiptยังไม่กู้; หลายprocessไม่ใช่scopeที่รองรับ |
| 17 | Gameผูกตั้งแต่preview/confirm; run APIตรวจowner/revision/selection/เกม/หลังgateและก่อนforward; strictroute/UUID/casing/wronggame guardsทั้ง4 | unknowngame/type/layoutหยุด ไม่อ้างทุกlivevariant |
| 18 | ส่งเฉพาะoccurrenceที่เลือกไปFinderแยก ไม่เพิ่มคิวBundle; send-allไม่ขยายIDข้ามแถวที่สามค่าเหมือนกัน; GENERAL4เกมUI1280/390และregressionอยู่ในFULL6ที่ผ่าน | ผู้ใช้ยังต้องเลือกส่งต่อเอง ไม่auto-add |
| 19 | private image API/UIเดิม; ชุดcreate30พิสูจน์bytesเดิมสองfieldไทย/อังกฤษในmultipartPOSTเดียว ไม่มีแยกuploadก่อนส่ง | ไม่มีliveimageupload/pixelproof; presenceไม่เท่ากับเนื้อภาพตรง |
| 20 | Desktop1280/Mobile390 GENERALทั้ง4เกมและPC Premium: explicitcreate/confirm/cancel/readback; Resolveใช้ปุ่มอ่านอย่างเดียว/no replay/reload. อยู่ในFULL6ที่ผ่าน | ไม่ใช่accessibilityauditทุกอุปกรณ์ |
| 21 | `test_hundred_long_named_rows_scroll_inside_table_on_mobile` ตรวจ100แถวชื่อไทยยาว แก้แถวท้ายถูกID ตาราง scroll เอง ไม่มี page overflow; screenshot ตรวจแล้ว | ยังไม่ครอบคลุมทุกอุปกรณ์/ขนาดรายการ |
| 22 | FULL6ผ่าน3108passed1warning/native+wrapper0/JUnit3108/0/0/0/source185ตรง/originalhashตรง/evidence_errors[]/retentionครบ; เก็บFULL5failed/full1failed/oldinterruption/WinError10055ครบ | deep-path setup limitationเดิมยังไม่แก้ ไม่อ้างwarning-free |

ผู้ใช้ส่งGENERALreceiptครบ4เกมและsaved readbackตรงแล้ว; ไม่ขอข้อมูลเดิม/DEVหรือสร้างเพิ่มซ้ำ. Resolveเชิงบวกมีเฉพาะreceiptที่โปรแกรมเก็บเองอย่างมีcausalbindingก่อนsavedcommit ไม่ใช่การกู้ทุกกรณี. Premiumเป็นsource-backed+observedform+localtests ไม่มีlivePremiumPOST. รายละเอียดประวัติM2/รวมร่างและfinalfull6ตรวจครบแล้วในscopeที่รายงาน ส่งมอบSetup0.1.43และปิด#12ตามหัวเอกสาร. ผลเก่าทุกชุดคงตามsnapshot ไม่เปลี่ยนย้อนหลังเป็นpasssourceใหม่
รับโค้ดหรือ contract ที่ตรวจสอบได้โดยลบ cookie/token/ข้อมูลลับแล้วได้ ไม่ต้องสร้างข้อมูลจริงเพื่อเก็บหลักฐานใหม่
ไม่ลดเกณฑ์ผ่าน ไม่เปลี่ยน synthetic fixture เป็นข้อเท็จจริง live และไม่ปิด issue จากผล scoped tests
