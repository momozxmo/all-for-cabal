# ID-first coverage ของชุดที่ส่งมอบ v0.1.41

วันที่สรุป: 25 ตุลาคม 2026. อ่านร่วมกับ [acceptance รายข้อ](acceptance-v041.md) และ [หลักฐาน release](../../local-release-v0.1.41.md)

## วิธีอ่าน

- **ID** = developer-maintained HTML element ID ไม่ใช่เลข Item/Bundle/UUID ของข้อมูล
- **Exception** = จุดที่ตรวจแล้วว่าไม่มี ID ถาวร จึงหาแบบจำกัด owning form/row/tab/dialog; ต้อง unique/type/role/readiness/readback ถูกต้อง ถ้ากำกวมหรือเปลี่ยน contract ให้หยุด
- **Runtime relation** = อ่าน ARIA relation ปัจจุบันใหม่ทุกครั้ง ไม่ hardcode ค่า Radix/TinyMCE
- **ไม่แตะค่าเดิม** = ไม่มี workflow กรอก control นั้นใน Tool เดิม ไม่เพิ่มฟีเจอร์หรือ schema ใต้ชื่องาน selector migration
- **Unknown** = ตัวอย่าง/state ที่ยังไม่ตรวจ ไม่ใช่ผลผ่าน และไม่ทำให้เดา locator/result route เพื่อสร้างต่อ
- หลักฐาน DOM ด้านล่างเป็นการตรวจเดิมเดือนตุลาคม ไม่ใช่การเข้า Aztek ใหม่25ตุลาคม; synthetic assertions ไม่แทนหลักฐาน DOM จริง

สี่เกมใน inventory: CabalM TH/cabalm, CabalM SEA/cabalmsea, CabalPC TH/cabalpc, CabalPC SEA/cabalpcsea. ใช้ route ของแต่ละเกมที่อ่าน/จับจริง ไม่คัด schema จากเกมหนึ่งแทนอีกเกม

## Item Finder

หลักฐานเดิม: [coverage8Oct](coverage.md#หลักฐาน-item-finder-14) list/detail และ completed-empty แยกสี่เกม; saved detail เป็นเพียงตัวอย่างที่ตรวจ ไม่รับรองทุก record

| Control/state | ID / exception | ขอบเขตและการตรวจ |
| --- | --- | --- |
| Item identity/name/detail | item-name, item-game-item-id, item-option, duration-index, item-detail | owning detail form; type/unique; detail business identity ต้องตรงแถวค้น |
| Web/trade/drill/quantity/critical | display-option-enable, game-tradeable, displayOptions-is_slotable, displayOptions-quantity, displayOptions-critical | อ่านเฉพาะ state ที่มี control; false/hidden/late มี readiness; ไม่ใช้ hidden checkbox แทน ID switch |
| Option/Duration filters | filter-option/filter-duration มี ID จริง | คง Python filtering หลังอ่านครบทุกหน้า ไม่เพิ่ม interaction ใหม่เพียงเพราะมี ID |
| Search/results/pagination/Preview | no-ID exceptions: search form/input/submit, table/columns, exact Next, explicit completed-empty, img Preview | ต้องได้ target/header/state เดียว; blank/loading ไม่เป็น completed-empty; duplicate/missing ผิด contract หยุดและรักษา imported draft |

DEV gap: maintained search/result/pager/ready-empty/image IDs. Unknown: records/layouts นอก sampled list/detail states; ไม่เพิ่ม date/sort/favorite/Actions interaction ที่ Tool เดิมไม่ได้ใช้

## Bundle create และ saved Recheck

หลักฐาน header/create/readback/Item/Currency/EXP/repeated cards: [coverage เดิม](coverage.md). Create metadata ตรวจสี่เกม; populated card/readback บาง state มาจาก M TH/PC SEA เท่านั้น ไม่อ้างเป็น four-game live repeated-row proof

| Control/state | ID / exception | ขอบเขตและการตรวจ |
| --- | --- | --- |
| Name / delivery | bundle-name / immediately-send | unique owning form; typed ID; state/readback |
| Type / Item search-add | audited no-ID type block/native select, Item tab/current panel, exact search/result business ID/own Add | one active panel; exact ID ไม่จับเลขที่เป็น prefix/suffix; missing/ambiguous หยุด |
| Item/Currency/EXP cards | no-ID card/expander/Qty/Tier; business identity + occurrence + current index | หลัง add/remove/reorder ต้อง remap card และตรวจทุกค่าท้ายฟอร์ม; current indexes ซ้ำ/merged occurrence หยุด |
| RANDOM draw | items.N.secret_chance | เลือก exact literal ID/current row; แยก items.N.chance display rate และคงค่า0 |
| Reward picker/fetch | audited no-ID tab/panel/trigger/search/listbox/option/Qty/Add | current ARIA relation ทั้งสองทาง; bounded readiness; unknown code/display-name collision ไม่เลือก first |
| Create / confirmation | audited no-ID submit ใน owning form; active alertdialog/current title-description relation/Confirm-Cancel | Create metadataสี่เกม; Bundle confirmation live เดิม M TH เป็นหลัก ส่วน synthetic compatibility ไม่กลายเป็นหลักฐาน live อีกสามเกม |
| Saved Bundle/Item identity | audited no-ID header marker แยกจาก picker IDs; Item detail IDs ตามตาราง Finder | header/URL เปลี่ยนหรือ card เปลี่ยนระหว่างอ่านหยุด; unknown property เป็น partial/failed ไม่เป็น passed |
| Queue/history/consumer handoff | local API/UI/checkpoint เดิม;ไม่ใช่ Aztek HTML ID | explicit checked-all continuation ไม่เปลี่ยน actual Recheck และไม่ให้สิทธิ์ handoff ใหม่; replay409; read-only retryไม่สร้างซ้ำ |

DEV gap: stable form/header/card/occurrence/expander/Qty/Tier/type/picker/submit/confirm IDs และ explicit readiness; exact Currency/EXP keys แยก display text. Unknown: live repeated-row variants, layouts และ exact option keys บาง state ที่ยังไม่มี metadata. ไม่มีข้ออนุญาตสร้าง Bundle เพิ่ม

## Item Code

หลักฐาน header/limit/calendar/reward/picker/create/confirmation แยกสี่เกมใน retained coverage ต้นฉบับ; [coverage8Oct](coverage.md) มีลำดับก่อนหน้า. Selected Bundle/change ของ Item Code มี live proofเฉพาะ M TH ใน state ที่บันทึกไว้; ไม่เทียบเท่า all-game selected-state proof

| Control/state | ID / exception | ขอบเขตและการตรวจ |
| --- | --- | --- |
| Header/type/per-user/date triggers | name_th/name_en/slug/redeem_type/per_player_limit/start_at/end_at | one main form anchored name_th; native select ไม่มี ID เป็น exception เฉพาะ parent ของ trigger; type คง ALL |
| Code-wide limit | is_limited, quantity, remaining | quantity/remaining เมื่อ limited เท่านั้น; enabled/typed/unique/readback |
| Reward names/limit/count/type/codes | rewards.N.name_th/name_en/per_player_limit/is_limited/quantity/remaining/is_generate_code/serial/prefix/amount | เปิดและรอ active indexed set; FIX textarea, SERVER prefix optional/amount required; native select scopedกับtrigger |
| Add/tab owner | no-ID form/Add/tablist/ordinal tab | active fields mountก่อนtabได้ ต้องรอrelation/ordinalชัด;ไม่เลือกจากชื่อรางวัลที่แก้ได้ |
| Bundle picker | no-ID reward owner/Bundle section/trigger/search/result/selected badge/change | ผูกกับ verified reward ID pair; current dialog relation; exact requested business ID;ห้ามwalkออกform |
| Create/Confirm | no-ID owning-form submit และ verified alertdialog/title/description/actions | audited per-game operation path/mainframe;หนึ่งsubmit/confirmation;broken relationไม่เขียน |
| Own result | conservative own-record identity ไม่ใช้ nested Reward/Bundle IDs | สี่เกมใช้ strict guardsร่วม; flat numeric/numeric URL compatibility ไม่ใช่ live schema ใหม่; unknownยังเตือนและไม่re-submit |

is_enabled/is_test_mode/is_shown_only_winner และ header desc IDs ที่เคยอ่านพบ แต่ไม่มี requested autofill ใน workflow นี้ ให้คงค่าเดิม ไม่เพิ่มinteractionใหม่. DEV gap: form/tab/picker/calendar/create/confirm IDs. Unknown: other response envelopes/created navigation และ all-live selected variants;ไม่เดา slug/UUID/numeric saved URL

## Event

Independent Event field/reward/picker metadata สี่เกม ไม่ยก Item Code มาเป็นหลักฐานแทน. retained event-reward-*-20261009 / event-bundle-selected-live-20261015 / per-game follow-ups และ confirmation/response records เดิมเป็นหลักฐานเฉพาะ sampled states

| Control/state | ID / exception | ขอบเขตและการตรวจ |
| --- | --- | --- |
| Header/counters | slug/name_th/name_en/per_player_limit/quantity/remaining | one main form anchored name_th; numeric counters แยก header/reward; zero/default behaviorเดิม |
| Event/claim dates | start_at/end_at/redeem_start_at/redeem_end_at | four own triggers; exact seconds/readback ไม่ยืม calendar ข้างเคียง |
| Redeem type | no-ID trigger/native select WINNER/ALL | owning redemption section+direct label owner;ambiguous/role/typeผิดหยุด |
| Reward names/descriptions/limit/counts | rewards.N.name_th/name_en/desc_th/desc_en/is_limited/per_player_limit/quantity/remaining | active indexed fields; descriptions textareaไม่ใช่header editor;onlylimitedcountsเมื่อขอ |
| Reward Add/tabs | no-ID section/Add/ordinal tabs ไม่มีpermanent panel relation | ตรวจ unique owning section/tab/aria-selected และรอ mountก่อนfill |
| Bundle picker | no-ID owner/trigger/search/result/badge/change; runtime dialog relation | selected badge/row มีหลักฐานสี่เกมตามfollow-up; index1 PCSEAและselected-statefollow-upsมีขอบเขตตามบันทึก ไม่ใช่ทุกrepeatedstate |
| Create/Confirm/result | audited owning submit/dialog/actions + independently captured path/strict own UUID+submitted slug | สี่เกมมีown-response samples;wrong host/path/method/frame/negative/nested IDไม่รับ;no-responseไม่สร้างซ้ำ |
| Header status/media/editor/language | no requested header image/rich-editor workflowในToolเดิม | preserve ไม่เขียน/ไม่สลับภาษา/ไม่upload; sentinelsตรวจสองภาษา×สี่เกม8cases ไม่อ้างเป็นlive hidden-file DOM contract |

Event header language/media live auditเดิมเป็น AX-only: ยืนยันว่ามีlanguage/image/details sections แต่ยังไม่รับรอง hidden file/inactive panel contracts. ส่วนนี้ไม่ถูกย้ายเป็นautofillที่ไม่เคยมี. DEV gap: form/redeem owner/Add/tabs/picker/calendar/create/confirm และ media wrappersถ้าจะเพิ่มworkflowภายหลัง. Unknown response/navigation/layout variants remain safe-stop/unknown ไม่แต่งfallback

## Product

Independent create forms สี่เกมอ่านแล้ว17Oct ไม่ใช้ข้อความเก่า Productblank1Octเป็นcurrentstatus. retained product-id/options/media/popup/populated/display/bundle/confirmation audits แยกสี่เกมและstateตามชื่อด้านล่าง

| Control/state | ID / exception | ขอบเขตและการตรวจ |
| --- | --- | --- |
| Names | th_name/en_name | one main form; IDชนะname/label/outside decoys;late mount bounded |
| Category/Currency | no-ID trigger/dialog/search/options; actual opaque business UUID/value | Categoryอยู่Generalsection;Currencyอยู่currentpricerow;optionidentityexact/uniqueและatomicvisibilitycheck |
| Prices/Add/remove | name-only prices.N.original_price/prices.N.price; no-ID row/actions | remap current rowsหลังremove/reindex/reorder;zeroคงอยู่;Currencyกับราคาownrow;ambiguousหยุด |
| Display/limits/date triggers | is_enabled/is_test_mode/is_hidden/position/show_at/hide_at/purchase_limit_type/limit_per/limit_reset_interval_days/limit_reset_at | typedID;limitfieldsmountเมื่อขอ;defaultsคงเดิม;date/numericreadbackผิดเป็นincomplete |
| Images/languages/editor | no-ID label-owned Thumbnail/Banner file input; runtime tab/panel/iframe relations | ownsection/TH-EN panel;readback filename/type/size/content;unrequestedoptionalmediaไม่แตะ;ไม่มีglobalnth |
| Bundle/Primary | no-ID picker/search/results/selected card; bundle-primary-N มีIDจริง | remapPrimaryIDไปcurrentcard/businessBundle;preserveexistingprefix/order/choices;conflictหยุด ไม่ลบหรือreorderของผู้ใช้เอง |
| Create/Confirm/result | no-ID owningform submit/dialog/actions;independentlycapturedpaths/strictUUID+submittedownname | สี่เกมมีresponse/selectedsampleหลักฐาน;previewsubmit0;hidden-after-trialหยุด;unknownsavedURLไม่ถูกเดา |

Tagsไม่ใช่workflowปัจจุบัน ไม่เพิ่มจากmetadata. PrimaryมีIDแล้วไม่ควรขอเพิ่มซ้ำ. DEV gap: Category/Currency/options/pricerow/actions/image/language/editor/Bundlepicker/form/Create/Confirm IDs และselected UUID/state contract. Unknown: filled multiple-price live preservation/dragreorder/uploadbehavior/selected Bundleremovalและotherlivevariants. Synthetictestsครอบคลุมlistedbehaviorแต่ไม่รับรองliveทั้งหมด

## Shared calendar และการหยุด

start/end triggers มีIDไม่ได้แปลว่าcalendar internalsมีID. ItemCode/Event/Productใช้ scoped current dialog/listbox, Year/Month selects, day data-day, hour exact unique option และminute/second inputsตามaudit. Internalsไม่มีmaintainedID;runtimeARIAอ่านใหม่. Set seconds/minutesและreadbackค่าที่ขอ รวม23:59:59. Invalid/ambiguous/never-matchingreadbackไม่เป็นsuccess. DEVgap:calendarroot/year/month/previous-next/day/hour/options/minute/second IDs

## Unknown ไม่ถูกซ่อนเพื่อปิดงาน

- ยังไม่รับรองทุก live DOM/state/response/navigation variant. Unknownที่หยุดmigration/อ่านครบไม่ได้ยังเป็นunsupported/incompleteในส่วนนั้น
- Seven saved-record readbacksและeightselectedProductoptionUUIDequalitiesมีหลักฐานเดิมแล้ว ไม่อ้างว่ายังไม่มีทั้งหมด และไม่ตีความเป็นcreate-time redirectsหรือallvariants
- Actualuserinstall/reopen/draftpreservation,cleanVMและsigningไม่ใช่acceptanceของ#13/#19 และยังไม่ยืนยัน. NewItem12นอกscope
- No-ID gapsเป็นupstreamwish-list ไม่ใช่รอDEVเป็นprerequisite. หากมีfuturecontrol/variantต้องสืบหลักฐานและใช้policyเดิม ไม่ลดguard
- การปิดงานตามเกณฑ์เดิมคือboundedID-first+syntheticverification+honestcoverage/gap ไม่ใช่คำรับรองทุกnodeมีIDหรือทุกระบบผ่านliveend-to-end

## Integrity catalogue ของ retained audits

อ้างอิงไฟล์ใน build-cache ของ original codex-web-auth worktree เก็บเดิม ไม่คัดrawบริษัท/session/media/DBเข้าสู่Git. Hashesใน [machine-readable acceptance](acceptance-v041.json) ตรวจไฟล์ยังอยู่และคงหลักฐานที่อ้างอิง ไม่ใช่newliveaudit

- product-id-dom-audit-20261017.json — 4990 bytes; SHA256 38C819D3BB9F3B7D7D535E475093742F2BE4341F52B87CF7420F68235FA1DC2A
- product-media-dom-audit-20261017.json — 2623 bytes; SHA256 C8A4061D0F3242E77507C2887D9295CAFB6637DDC0EAA898B255DF5D77E2DEBB
- product-popup-dom-audit-20261017.json — 4140 bytes; SHA256 7F2C9D93E54C5E4BF25623B7F9F3E63D2724E908CAFB09DC940B8D34E59FA473
- product-populated-draft-dom-audit-20261017.json — 5484 bytes; SHA256 B27AD5102B6125D9A3B55EEBB9569925DB8461BB69FA536D616D557587423273
- product-display-date-dom-audit-20261017.json — 5435 bytes; SHA256 C336C6F8175ABEF56DF3BBCBC76F26ECE8D54C00A62E32A2944B0345F5AA985C
- product-bundle-dom-audit-20261020.json — 3278 bytes; SHA256 B1144200E8733825922550D36D6DB830960F6ECDDD5EC8BA897342EE6485BD85
- product-confirmation-api-blocked-audit-20261020.json — 16060 bytes; SHA256 429168B781C484DF07130D5154E3376585DF5BBC92B3836127C91F59C035A5DB
- event-reward-live-20261009.json — 3837 bytes; SHA256 F141D5409E428172B432361174E9F29148732E3E1BEF67EB75073E292297CE6F
- event-reward-scope-live-20261009.json — 2022 bytes; SHA256 459CA29172FC7EF7CE704244D71738FE8F3A2EA78594D23FF0756A9400579507
- event-reward-hidden-live-20261009.json — 1416 bytes; SHA256 C95A273E9F616B739C12AD2107B133B2D41CCCE9297F3C90B2D38B6A657F00E4
- event-bundle-selected-live-20261015.json — 5747 bytes; SHA256 503B0704BA843C1A6485BBB2E2B46E8344235385322656C7A831FFB152523B9B
- event-language-image-readonly-20261016.json — 2573 bytes; SHA256 E4C858F2D5D0B6527291AA78C53A59EB49DD8DE7ADCB913DC060CEDBFEFE7BF4
- saved-record-readback-7-20261022.json — 7439 bytes; SHA256 513BA29B741A50DD1A6A4719CE1BD423C17E6331238889B78F5E01C8D8204DCB
