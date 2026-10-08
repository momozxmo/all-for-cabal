# ID-first coverage

Snapshot: 2026-10-08. Review base: `19eb84e` + working diff.
Implementation: #14 Item Finder verified ใน working diff. #15 กำลังทำ:
ย้าย header/Item search-add, Item card Qty/Tier/current draw ID และ Reward tab/picker/fetch/add แล้ว;
Item-card และ Reward-picker slices verified ใน working diff.
Reward card Qty/Tier/current-rate/default-Tier verified ใน working diff;
Create-action scoped/preflight slice verified ใน working diff (full 1,811 passed).
Bundle scoped confirmation verified ใน working diff (full 1,837 passed; ดูท้ายเอกสาร).
Saved Item-detail readback verified ใน working diff (full 1,858 passed; ดูท้ายเอกสาร).
Saved Bundle-card readback verified ใน working diff (full 1,893 passed; ดูท้ายเอกสาร).
Repeated-occurrence create/readback mapping: final3 target 346 passed; full 1,915 passed (1 warning).
M TH write matcher จำกัด captured POST/host/path/main-frame แล้ว; target37/full1,927 passed เป็นฐานก่อน headerfix.
Saved-header ID scopefix: target133/full1,937 passed (1 warning), JUnit failures/errors/skipped0;
hash3filesตรง freezeหลังทั้งสองชุด; Standards/Spec0scopedfinding ดู incrementท้ายเอกสาร.
Shared response matching/confirmation ของ flow อื่น/อีกสามเกม และ live repeated-row evidence ยังเหลือ.
#16 header/readiness และ limit/type slices verified targeted798; ดู increment ท้ายเอกสาร.
#16 calendar slice verified targeted854; ตรวจทั้ง4เกม/2fieldsแล้ว ดู incrementท้ายเอกสาร.
#17–#19 ยังไม่ implement. New Item #12 คงพักไว้. Remote issues ยังไม่ปิด.
Live ตรวจอ่านอย่างเดียวโดยปกติ; ข้อยกเว้นคือ test 1 Bundle ที่ผู้ใช้อนุมัติท้ายเอกสาร.
ไม่มีสิทธิ์ write เพิ่มเติมหรือ Setup/commit/push/publish.
Approved live write ใช้แล้ว: M TH Bundle 225954, HTTP 200; อ่าน saved record ตรงตามค่าทดสอบ.
Actual write endpointยืนยันเฉพาะMTH; automated reader7สำเร็จสำหรับminimal recordหลัง readonlyversion-load retry1.
Reportเก่าTargetclosed/IDcollision/version-errorคงไว้; ไม่อ้างว่าExcelRecheckหรือทุกgame/stateผ่าน.

## หลักฐาน Item Finder (#14)

ตรวจในแท็บสำรวจ Brave แยกจากแท็บผู้ใช้: list และ saved Item อ่านอย่างเดียว.
ค้นข้อความทดสอบเพื่ออ่าน empty state เท่านั้น ไม่กดสร้าง/บันทึกฟอร์ม.
Host: `https://aztek-tools-v2.combo-interactive.com`.

| เกม | List ที่ตรวจ | Saved Item ที่ตรวจ | State |
| --- | --- | --- | --- |
| CabalM TH | `/combo/cabalm/shop/items` | `/combo/cabalm/shop/items/224375` | Web เปิด; ไม่มี Preview |
| CabalM SEA | `/combo/cabalmsea/shop/items` | `/combo/cabalmsea/shop/items/224371`, `/224358` ภายใต้ path เดียวกัน | Web ปิด / Web เปิดพร้อม Preview |
| CabalPC TH | `/combo/cabalpc/shop/items` | `/combo/cabalpc/shop/items/224351` | Web เปิดพร้อม Preview |
| CabalPC SEA | `/combo/cabalpcsea/shop/items` | `/combo/cabalpcsea/shop/items/224352` | Web เปิดพร้อม Preview |

ทั้งสี่เกมมี list/detail contract ด้านล่างจริง แต่ไม่ได้อ้างว่าได้ตรวจทุก record/state.
Completed-empty ตรวจครบทั้งสี่เกมด้วยคำค้นทดสอบเดียวกัน: ไม่มี table และมีข้อความ
`ไม่พบ Item ที่ตรงกับเงื่อนไข`; เปลี่ยนเกมจากปุ่มเกมจริงบน Item list ไม่แก้ record.
Uniqueness ตรวจตอนใช้งานใน intended scope ทุกครั้ง รวม hidden duplicate.
DOM live audit ตรวจ duplicate IDs ในฟอร์ม M SEA 224358 ไม่พบ; ไม่ใช้ sample นี้รับรอง record อื่น.

### Stable IDs ที่ย้ายแล้ว

Scope: `main` ที่ไม่กำกวม → `form:has([id="item-name"])` ที่ไม่กำกวม.
ID lookup เป็น exact attribute (`[id="..."]`) ไม่ใช่ selector union/first-match.

| Control | HTML element ID | ชนิดที่ตรวจ | State/read policy |
| --- | --- | --- | --- |
| ชื่อ | `item-name` | input text | ใช้ระบุฟอร์ม |
| ItemKind | `item-game-item-id` | input text | รอ numeric value นิ่ง; เทียบกับแถวผลค้นหา |
| ItemOption | `item-option` | input text | เทียบกับแถวผลค้นหา |
| DurationIndex | `duration-index` | input text | เทียบกับแถวผลค้นหา |
| คำอธิบาย | `item-detail` | textarea | อ่าน value |
| แสดงผลบนเว็บ | `display-option-enable` | button, role=switch | ต้องมี aria-checked true/false |
| แลกเปลี่ยนได้ | `game-tradeable` | button, role=checkbox | อยู่ใน Game parameters; ไม่อาศัยตำแหน่งเก่า |
| จำนวนแสดงผล | `displayOptions-quantity` | input text | มีเมื่อ Web เปิด; ปิดแล้วไม่บังคับอ่าน |
| คริติคอล | `displayOptions-critical` | input text | มีเมื่อ Web เปิด |
| เจาะรูได้ | `displayOptions-is_slotable` | button, role=checkbox | มีเมื่อ Web เปิด; ต้องอ่านสถานะได้ |

ช่องเลขข้างต้นรับ input text/number ใน runtime เพื่อคง compatibility; live ที่เห็นเป็น text.
ไม่มีการย้าย ID ที่ไม่ใช้จริง เช่น favorite. ไม่ใช้ hidden native checkbox ของ Radix.

### No-ID exceptions และ DEV gaps

| จุด | ขอบเขต/หลักฐานที่ใช้ | เมื่อ contract เสีย | ID ที่ขอ DEV เพิ่ม |
| --- | --- | --- | --- |
| Main/detail form | main เดียว; form มี item-name เดียว | หาย/ซ้ำ → หยุด | Item page/form wrapper |
| Search form/input | main → form ที่มี input placeholder ตรง `ค้นหา Item...`; input text เดียว | หาไม่ได้/ซ้ำ/ผิด type → หยุดก่อนค้น | Search form + input |
| Search submit | button type=submit เดียวใน search form | หาไม่ได้/ซ้ำ → หยุด | Search action |
| Result table | table เดียวใน main; map หัวคอลัมน์ Aztek Item Id/ชื่อ/ItemKind/ItemOption/DurationIndex | header ขาด/ซ้ำ/แถวผิดรูป → หยุด | Results table/columns + loading/ready state |
| Completed empty | ทั้งสี่เกมแสดง p ข้อความตรง `ไม่พบ Item ที่ตรงกับเงื่อนไข` และไม่มี table | empty ที่ไม่ยืนยันหรือสอง state พร้อมกัน → หยุด | Explicit empty-result status |
| Next page | button ข้อความตรง `Next ›` ภายใน main; disabled = สุดท้าย | ซ้ำ/เปลี่ยนหน้าไม่สำเร็จ → หยุด | Pagination Next |
| Saved image | img alt=Preview ภายใน detail form; 0 = ไม่มี, 1 = รอ load แบบ bounded | มากกว่า 1/ยังโหลดไม่เสร็จ → หยุด | Saved-image Preview |

Option/Duration บน list มี `filter-option`/`filter-duration` จริงทั้งสี่เกม แต่ Finder
คงกรองด้วย Python หลังอ่านครบทุกหน้า เพื่อไม่เปลี่ยน behavior pagination เดิม.
ไม่เพิ่ม interaction กับ date/sort filters หรือ Actions (radix IDs) ที่ flow นี้ไม่ได้ใช้.
ไม่มี business ID, radix/tiny-react ID หรือ Tools-injected ID ที่อ้างเป็น stable element ID.

### Readiness / root callers / safety

- `web/aztek_locator.py`: bounded 5s lookup, unique target และ tag/role/input type checks;
  known ID เสียไม่เปลี่ยนไป fallback. IDs ที่มี punctuation ใช้ exact literal attribute.
- `web/search_runner.py`: override เฉพาะ web path ของ root engine:
  apply filters, table/detail readiness/read และ scoped pager. Root search/filter/deep business checks ยังใช้เดิม.
- Table ต้องมีแถวที่นิ่งหรือ completed-empty ที่ตรวจไว้; blank/loading colspan ไม่ใช่ผลสำเร็จ.
- `item_finder.py`: optional detail-reader/error hook สำหรับ web; desktop caller เก่ายังใช้ path เดิม.
  ส่ง Document Reference จาก imported criterion ต่อไปถึงผลค้นหา.
- Locator error ไปถึง coordinator เป็น `aztek_locator_changed` และ UI alert ไม่ถูก done ทับ.
  ร่างต้นฉบับ/เซสชัน/คิวไม่ถูกลบ; ไม่ submit สร้าง record หรือกู้ด้วยการสร้างซ้ำ.

## การพิสูจน์ / ข้อจำกัด

`tests/test_web_finder_id_first.py` ใช้ API/runner จริงและ Playwright กับ synthetic Aztek;
unexpected traffic abort. ครอบคลุม ID priority/DOM nesting/label ลวง, missing/hidden duplicate/
wrong role/type/state, lazy switch, reordered columns, scoped pagination และ slow/unknown loading.
ทดสอบ API ทั้ง 4 เกม, import สอง sheet ที่ใช้ Item เดียวกันต่าง Amount/source/reference,
ส่งเฉพาะที่เลือกและส่งทั้งหมด รวม UI error ผ่าน Keyboard ที่ 1280/390px และ page overflow.
มี focused browser-level test ของ lookup ID ที่มีจุด ไม่อ้างว่าทุก consumer ย้ายแล้ว.

Regression เดิมยังตรวจ selection-only/multi-group handoff, authentication และ browser busy/cancel.
RED ก่อนแก้ยืนยัน premature loading, wrong search type, duplicate Preview และ error→done overwrite.
Full suite เมื่อจบ #14: **1,727 passed, 1 warning in 830.69s** (2026-10-01).
Warning เดิมใน local runtime test: process-local development secrets; ไม่ใช่ locator failure.

```powershell
python -X utf8 -B -m pytest tests -q -p no:cacheprovider --basetemp=build-cache/id-first-full1
```

ใช้ global Python/Playwright 1.60 ที่มี Chromium ตรงกับเครื่อง ไม่ติดตั้ง dependencies เพิ่ม.
Python syntax check 6 files และ inline JavaScript syntax check 2 scripts ผ่าน;
`git diff --check` ผ่าน. UI failure flow ตรวจจริงที่ 1280/390px รวม Enter key และ overflow.

### Standards review

เทียบ `19eb84e` + working diff เฉพาะงานนี้: แก้ loading readiness และ ambiguous Preview
แล้วเพิ่ม regression ก่อนแก้. รีวิวซ้ำไม่พบ finding ค้างที่ต้องแก้ใน #14.

### Spec review

แก้ premature loading, search input type, Preview uniqueness และ coverage/gap ที่ขาดแล้ว.
Public import/runner/handoff tests ยืนยัน source/Amount/reference/selection;
punctuation lookup มี focused browser test. รีวิวซ้ำไม่พบ residual finding ของ #14.
Findings สองด้านตรวจแยกกัน; full suite ข้างต้นเป็นหลักฐานสุดท้ายก่อนถือว่า verified.

Unknown: live delayed/broken image, lazy/duplicate/error states ที่ต้อง
จำลองเพื่อไม่แก้ production DOM, ส่วนที่เหลือของ #15 และทุก flow #16–#19/New Item. ไม่มี live submit confirmation/success
หรือ clean-VM/installer verification ในงานนี้. Static type checker ยังไม่มีใน runtime/config ปัจจุบัน;
ใช้ Python syntax check กับ test suite แต่ไม่อ้างว่าเป็น typecheck.

## Preflight #15 — Saved RANDOM Currency

ระหว่างรอ regression #14 อ่าน PC SEA saved RANDOM Bundle
`/combo/cabalpcsea/shop/bundles/225735` จาก href จริงใน list และกดขยายทั้งหมดเท่านั้น.
ไม่ได้กดเพิ่ม/ลบ/เรียง/บันทึก/ทดสอบส่ง/คัดลอก Bundle.

- Saved form มี `bundle-name` input และ `immediately-send` button role=switch.
- 11 WALLET cards (Limited Orb) มี draw IDs `items.0.secret_chance` ถึง
  `items.10.secret_chance`; display IDs เป็น `items.<current-index>.chance` แยกกัน.
  ทั้งสองเป็น input number. อ่าน expanded cards ไม่ infer ว่า index จะคงหลัง reorder.
- Quantity มี name `items.<current-index>.quantity` แต่ไม่มี ID.
  Tier เป็น button role=combobox พร้อม native select ที่ไม่มี ID/name ภายใน card เดียวกัน.
- ไม่พบ data-rfd/data-rbd draggable identity ใน sample นี้; expander ใช้ aria-label
  `ขยาย` เมื่อพับ และ `ย่อ` เมื่อเปิด พร้อม aria-expanded (ตรวจ attribute จริงเพิ่มในรอบ Item-card).
- Tab IDs เป็น radix-generated ไม่ใช้เป็น permanent ID contract.
- Record ถูกล็อกและมี action บันทึกเป็นฉบับร่าง; ไม่ใช้ sample นี้รับรอง create/confirmation,
  Item/EXP card หรือเกมอื่น. Header/type/add evidence เพิ่มเติมอยู่ใน incremental ด้านล่าง;
  saved-read mapping ยังต้องตรวจและย้ายในงาน #15.

## #15 incremental — Header และ Item search/add

ยังไม่ถือว่าทั้ง ticket เสร็จ. ตรวจ create page ทั้ง 4 เกมผ่านปุ่มเกมและ href จริง:
`/combo/{cabalm,cabalmsea,cabalpc,cabalpcsea}/shop/bundles/create`.
อ่าน control และเปิดแท็บเท่านั้น ไม่กรอก เพิ่ม ลบ เรียง บันทึก หรือยืนยันสร้างบนเว็บจริง.

| Control | หลักฐาน/locator ที่ย้าย | Readiness และขอบเขต |
| --- | --- | --- |
| ชื่อ Bundle | `bundle-name`, input text; พบทั้ง 4 เกม | unique ภายใน `main form`, bounded visible |
| ส่งทันที | `immediately-send`, button role=switch; พบทั้ง 4 เกม | unique, aria-checked ต้อง true/false, อ่านค่ากลับ |
| ประเภท Bundle | ไม่มี stable ID; label ประเภท Bundle กับ combobox/native select ใน block เดียวกัน | รอ trigger visible, native select attached และ options แบบ bounded; ไม่เลือก select หน้า-wide |
| แท็บ/ค้นหา Item | tab/panel IDs เป็น radix-generated; role=tab Item, active tabpanel และ textbox ค้นหาชื่อ Item... ไม่มี stable ID | form เดียว, tab selected, unique active panel/search text input |
| แถวผล/เพิ่ม | ไม่มี stable ID; ID เป็น business ID ใน span, result div มีปุ่มเพิ่มเป็น direct child | exact ID ไม่จับ 91 เป็น 910; descendant ภายใน panel เท่านั้น, one-ID/one-button; รอผล 5s |

DEV gap: เพิ่ม stable IDs ให้ type trigger/native select, Item tab/panel/search,
result-row identity และ Add. ไม่มี ID ที่เดาหรือ inject เพิ่มใน production DOM.
ตรวจ type block/native select ไม่มี ID และอยู่กับ label/combobox ใน parent เดียวกัน
ครบทั้ง 4 create pages. PC TH ขณะ form เพิ่ง mount เคยเห็น native select options ยังว่าง;
จึงไม่ถือว่า trigger visible แปลว่า options พร้อมแล้ว (มี bounded readiness regression).
Broken known ID/ambiguous exception หยุดด้วย named locator error ก่อน save;
batch ระบุ fields_complete=false และไม่จอง creation checkpoint ก่อนผ่านการกรอก.

`tests/test_web_bundle_id_first.py` ใช้ runner และ `/api/bundles/run` จริงกับ
isolated synthetic traffic (unexpected requests abort): misleading controls นอก form,
missing/hidden duplicate/wrong role/type/state, lazy type/options, exact/missing/duplicate
Item และ missing-own-Add ไม่ยืมปุ่ม sibling, delayed search, preview writes=0,
queue failure ไม่ submit/ไม่ทำรายการถัดไป/ไม่จอง checkpoint และ session เดิมยัง active.
ทดสอบ header เก่าที่ fake CSS probes ถูกแทนด้วย real browser runner coverage.
Fixture `test_bundle_recheck_flow.py` ปรับให้มี main/form, stable switch ID,
type block และ Item tab/panel ตาม DOM จริง; คง assert create/checkpoint/recheck/replay เดิม.

Standards/Spec incremental review: แก้ ancestor escape, native-type readiness
และ premature search miss ด้วย regression ก่อนแก้; ไม่พบ residual finding ใน slice.
Verification หลังแก้ fixture: **93 passed in 222.00s** รวม 22 tests ใหม่,
Bundle/zero-rate และ 5 API create/checkpoint/recheck/replay cases เดิม.
Full suite รอบใหม่: **1,743 passed, 1 warning in 967.94s** (exit 0, 2026-10-01).
Warning เดิมที่ test_local_runtime.py:86 เรื่อง process-local development secrets.
รอบแรกหยุดเมื่อพบ fixture ไม่ตรง contract ไม่อ้างว่ารอบนั้นผ่าน.
Python syntax 4 files และ git diff --check ผ่าน.

```powershell
python -X utf8 -B -m pytest tests -q -p no:cacheprovider --basetemp=build-cache/bundle-id-full2
```

ผลนี้ verified เฉพาะ incremental header/Item-add รวม regression เดิม;
ไม่ถือว่าทั้ง #15 เสร็จ และไม่ใช่หลักฐานสร้างจริง/Setup/installer verification.

### งานที่ยังเหลือใน #15

- Reward card identity/mapping หลัง add/remove/reorder และ occurrence-aware mapping
  เมื่อมี Item ID เดียวกันหลายรายการ; Item-card slice ล่าสุดอยู่ด้านล่าง.
- Reward tabs/picker/Qty/Tier ของ Currency/EXP และ shared card numbering.
- Create/confirm exception scope และ saved Bundle/Item readback ID-first.
- Synthetic malformed/repeated-card/readback/checkpoint cases และ UI coverage ตาม AC.
- ตรวจ saved states ของเกม/ชนิดที่ยังไม่พบแบบ read-only; ยังไม่มี live submit verification.

หลักฐานถัดไป: M SEA saved FIXED Bundle `/combo/cabalmsea/shop/bundles/225800`
มี 10 ITEM cards; เปิดขยายทั้งหมดอย่างเดียว. Quantity name เป็น items.0.quantity ถึง
items.9.quantity, input number ไม่มี ID; Tier เป็น button combobox/native select ไม่มี ID/name.
Card root ของ sample นี้เป็น grandparent ของ expander โดยมี Item ID และ Quantity/Tier
อยู่ในการ์ดเดียวกัน; ไม่ถือว่า ancestry นี้พิสูจน์ทุกชนิดหรือหลัง reorder แล้ว.

M SEA EXP picker preflight บน saved sample เดียวกัน: active tabpanel มี combobox,
Qty input number และ Add ไม่มี stable ID. เปิด picker แล้วพบ aria-controls ชี้ dialog
ใน portal ตรงกัน; dialog/search/option IDs เป็น radix-generated. ใช้ความสัมพันธ์ runtime
นี้กำหนด scope ได้ แต่ไม่ hardcode generated ID เป็น permanent contract. Search เป็น input
role=combobox placeholder ค้นหา…; option แสดง Player Experience - SEA. เปิด/ปิดด้วย Escape
เท่านั้น ไม่เลือกหรือเพิ่ม; จำนวน Item เดิมยัง 10. Saved EXP card ของ M SEA ยังไม่ได้ตรวจ.

## #15 incremental — Item card Quantity/Tier/actual draw rate

Item ใช้ exact business Item ID ใน label/p ภายใน card ของ form เดียวกัน แทน index
จากรายการที่ส่ง. ตรวจหนึ่ง card/หนึ่ง Item ID/หนึ่ง ITEM badge, expander role/type/state
และโครงสร้างก่อนคลิกหรือกรอก; Qty เป็น input number ไม่มี stable ID.
Tier ไม่มี stable ID: ตรวจ visible combobox แล้ว native select attached/options แบบ bounded
และอ่านค่ากลับ. Header/Tier ใช้ bounded-option helper เดียวกัน โดยไม่เพิ่ม framework.

RANDOM derive current index จาก quantity name ของ Item ที่จับคู่แล้ว และใช้ literal
`items.<current-index>.secret_chance` ภายใน card นั้นเท่านั้น. ID หาย/ซ้ำ/ผิดชนิดไม่ fallback
ไป randomRate/display chance; numeric/string 0 และค่าทศนิยมยังลง draw chance.
ในรอบ Item-card นี้ Reward picker/card mapping/default blank-Tier และ rate discovery ยังเป็น legacy;
Reward picker ถูกย้ายเพิ่มใน increment ถัดไปด้านล่าง ส่วน card/rates ยังไม่ย้าย.
ไม่อ้างว่า slice นี้ทำให้ Currency/EXP หรือทั้ง #15 เป็น ID-first ครบแล้ว.

### Live evidence และ DEV gaps

- PC SEA saved RANDOM `/combo/cabalpcsea/shop/bundles/225766` มีหนึ่ง ITEM card.
  อ่านอย่างเดียวและพับ/กางกลับเท่านั้น: expander type=button, implicit button role,
  aria-label=`ขยาย`/`ย่อ` ตาม state; grandparent card มีหนึ่ง ITEM span,
  Item ID label ตามด้วย p, quantity name `items.0.quantity`, Tier combobox/native select
  ไม่มี ID, draw/display IDs `items.0.secret_chance`/`items.0.chance` แยกกันเป็น number.
- M SEA saved FIXED `/combo/cabalmsea/shop/bundles/225800` ตรวจสดซ้ำ: 10 ITEM cards,
  แรกเปิดใช้ label `ย่อ`; อีก 9 พับใช้ `ขยาย` และ Item ID/Qty/Tier ยังไม่ mount.
  Card scope และ label/p ของรายการที่เปิดตรงกัน; ไม่กรอก เพิ่ม ลบ เรียง หรือบันทึก.
- M TH saved FIXED `/combo/cabalm/shop/bundles/225824` อ่านเพิ่ม: 4 ITEM cards,
  แรกเปิดและอีก 3 พับ. มีหนึ่ง form/หนึ่ง ITEM badge ต่อ card, expander implicit button
  type=button และ labels ตาม state; card ที่เปิดมีหนึ่ง Item ID label/p, quantity
  name `items.0.quantity` input number, Tier button/native select ไม่มี ID (Common value=0).
  ไม่กรอก เพิ่ม ลบ เรียง หรือบันทึก; ไม่ใช้ sample FIXED ยืนยัน RANDOM ของ M TH.
- Fixture รอบแรกใช้ `ขยาย/ย่อ` เป็นค่าคงที่ผิดจาก attribute จริง จึงแก้ fixtures และ
  เพิ่ม RED/GREEN สำหรับ dynamic label. Full suite `bundle-cards-full1` ถูกหยุดเพื่อแก้
  หลักฐานนี้ ไม่อ้างว่ารอบที่หยุดผ่าน.
- DEV gap: ต้องการ stable card identity/expander/Quantity/Tier IDs. การตรวจนี้ยังไม่พิสูจน์
  populated create/reorder/remove จริง, PC TH saved Item cards หรือ M TH RANDOM.

### Safety และข้อจำกัด

Synthetic public runner ทดสอบสอง Item ที่เว็บกลับลำดับและ reindex, lazy card/options,
late+collapsed mount, actual label states, rate 0/decimal กับ display chance ไม่เปลี่ยน,
Currency amount เดิมไม่ถูกเขียนทับ, missing/hidden-duplicate/wrong-type draw IDs,
ambiguous card identity/Tier, wrong card kind/expander role/type, และ decoy expander.
Preview decoy regression เคยทำ synthetic POST ก่อนแก้; หลังแก้ต้องหยุดก่อนคลิกและ writes=0.
Private/fake selector tests 10 ตัวถูกแทนด้วย real public-runner coverage; create/checkpoint/
Recheck/replay assertions เดิมคงไว้ โดย fixture เพิ่ม actual ITEM badge/expander/Tier trigger.

Item ID ซ้ำภายใน Bundle ที่แยก occurrence ไม่ได้จะหยุดก่อนกรอก card values/บันทึก;
ไม่รวม/ทิ้ง/แก้ Document Reference หรือ Submitted Bundle Values เอง. ยังไม่ถือว่ารองรับ
occurrence-aware repeated Item matching ครบ AC. Source/history/checkpoint/queue gates ไม่เปลี่ยน.

Full suite ของ Item-card slice: **1,755 passed, 1 warning in 1101.91s** (2026-10-01).
Warning เดิมใน local runtime test เป็น process-local development secrets.

```powershell
python -X utf8 -B -m pytest tests -q -p no:cacheprovider --basetemp=build-cache/bundle-cards-full2
```

Standards review: 0 actionable findings ค้างใน slice หลังแก้และตรวจซ้ำ.
Spec review: 0 actionable findings ค้างใน slice หลังแก้และตรวจซ้ำ; งานที่ยังไม่ย้าย
และ repeated occurrence ยังเป็นข้อจำกัดของ ticket ไม่ใช่ AC ที่เสร็จแล้ว.
Python syntax 4 files และ git diff --check ผ่าน. ไม่มี live create/installer verification.

## Preflight ถัดไป — M TH saved Currency/EXP

อ่าน saved FIXED Bundle `/combo/cabalm/shop/bundles/225272` จาก href จริงในผลค้นหา EXP.
เปิดการ์ดที่พับและเปิด/ปิด Player Exp. picker เท่านั้น ไม่เลือก เพิ่ม กรอก ลบ เรียง หรือบันทึก.

- 3 cards: Ark Gem `WALLET_CREDIT` จำนวน 2, Leaf Gem `WALLET` จำนวน 190,
  Player Experience `PLAYER_EXPERIENCE` จำนวน 2. แต่ละ card มีชื่อ/ชนิดและ expander
  type=button, implicit button role, ไม่มี stable ID; labels `ขยาย`/`ย่อ` ตาม state.
- Qty เป็น input number name `items.0.quantity` ถึง `items.2.quantity`, ไม่มี ID.
  Tier มี visible button role=combobox และ native select ไม่มี ID/name; Common value=0.
  การ์ดแสดงชื่อรางวัล ไม่แสดง exact Currency code; จึงไม่ถือว่าอ่าน code ได้ครบจากชื่อ.
- Player Exp. active panel มี picker button role=combobox, Qty number placeholder=Qty,
  Add type=button ทั้งหมดไม่มี stable ID. Panel/tab IDs เป็น radix-generated.
- เปิด picker แล้วมี dialog, search input role=combobox, listbox และ option
  Player Experience. IDs เป็น radix-generated; search aria-controls ชี้ listbox ปัจจุบัน.
  Picker trigger ที่เห็นก่อนเปิดมี aria-controls ว่าง จึงไม่อ้างว่าทุกเกม/state มี contract นี้.
- คืนแท็บ Item หลังอ่านเสร็จ. Sample นี้พิสูจน์เฉพาะ saved FIXED M TH;
  ไม่รับรอง RANDOM EXP, populated create/reorder/remove หรือเกมอื่น.

ขั้นถัดไปหลัง preflight นี้คือ Reward tab/picker/add ตาม increment ด้านล่าง;
หลังส่วนนี้ verified ให้ย้าย Reward card mapping/default-Tier/rates ก่อน save/saved recheck.

## #15 incremental — Reward tab/picker/fetch/add

ย้ายเฉพาะการเลือก/ค้นหา/เพิ่ม Credit, Debit, Mileage และ Player Exp. กับ explicit fetch catalog.
ไม่มี stable element ID ของ controls ที่ใช้ใน slice นี้ จึงใช้ documented no-ID exceptions:

| Control | Scope/exception ที่ตรวจ | เมื่อ contract เสีย |
| --- | --- | --- |
| Reward tab | main form เดียว → exact role=tab/name, type=button | หาย/ซ้ำ/ผิดชนิด → หยุด |
| Active panel | tab aria-controls ปัจจุบัน → literal ID; role=tabpanel, active, aria-labelledby ตรง nonempty tab ID | association/active state ไม่พร้อมหลัง bounded wait → หยุด |
| Picker trigger | unique button role=combobox/type=button ภายใน panel | สถานะเริ่มไม่ใช่ false หรือเปิดไม่สำเร็จ → หยุด |
| Portal dialog | picker aria-controls หลัง expanded=true → exact runtime ID ใน popper wrapper, role=dialog | หาย/ซ้ำ/ผิด role → หยุด |
| Search/listbox | unique input text role=combobox ใน dialog → aria-controls listbox ภายใน dialog เดียวกัน | association/role/type กำกวม → หยุด |
| Option | exact option text ใน listbox ที่เปิด; รวม hidden duplicates | หาย/ซ้ำ/ผิดชนิด → หยุดก่อนเลือกหรือ Add |
| Qty/Add | unique number input placeholder=Qty, exact Add button type=button และ implicit/explicit button role ใน active panel | type/role/uniqueness/readback เสีย → หยุดก่อน Add/save |

Generated IDs ใช้เฉพาะความสัมพันธ์ที่อ่านใหม่จาก control ปัจจุบัน ไม่ hardcode เป็น stable ID.
Tab/panel/picker/search association, options และ closure/selected-label มี bounded readiness 5s.
Qty ต้องอ่านค่ากลับตรง. Fetch อ่านเฉพาะ options ใน dialog ของแท็บนั้น รอตัวเลือกก่อนรายงาน
และคืนแท็บ Item; ยังคง deduplicate ชื่อเพื่อ display แต่การเลือกชื่อซ้ำจริงจะหยุด ไม่เลือกตัวแรก.
DEV gaps: stable IDs สำหรับ tab/panel/picker/search/listbox/option/Qty/Add และ explicit catalog-ready/empty.

### Live evidence / unknown

- M TH saved FIXED `/combo/cabalm/shop/bundles/225272`: ตรวจทั้ง 4 reward tabs;
  tab → panel reverse association, picker หลังเปิด → dialog → search/listbox ตรงกัน.
  ก่อนเปิด trigger aria-controls ว่าง แต่หลังเปิดมีค่า runtime. อ่านและ Escape เท่านั้น.
- Create ทั้ง 4 เกม `/combo/{cabalpc,cabalpcsea,cabalmsea,cabalm}/shop/bundles/create`:
  ตรวจทั้ง 4 reward tabs/pickers ต่อเกม ผ่านปุ่มเกมจริง → href สร้าง Bundle ใน list;
  control ไม่มี stable ID, Qty number/Add type=button, dialog/search/listbox ใช้ runtime
  relationships แบบเดียวกัน. เปิด/ปิดเท่านั้น ไม่กรอก เลือก เพิ่ม หรือบันทึก.
- หลักฐานนี้ยืนยันเฉพาะ empty create/open-picker states ที่ตรวจ ไม่รับรอง populated create,
  search-filter/selection/add จริง, duplicate/lazy/error states หรือทุก saved-record variant.
  M SEA EXP saved preflight เดิมยังเป็นหลักฐานเฉพาะที่บันทึกไว้.
- ชื่อ trigger หลังเลือกเทียบ exact fetched option text เพื่อหยุดเมื่ออ่านกลับผิด.
  Post-selection label behavior พิสูจน์ด้วย synthetic runner เท่านั้น ยังไม่มี live selection;
  หาก live แสดงชื่อย่อ/ซ่อน code ต่างจาก option ขณะนี้จะหยุดก่อน Add ไม่เดาชื่อให้ผ่าน.
  Empty catalog ที่ไม่มี readiness evidence ยังไม่รับรองเป็นผลสำเร็จ.

### Verification / scope

Public runner/fetch/API ใช้ traffic จำลองทั้งหมดและ abort unknown requests.
RED ยืนยัน outside matching option ถูกคลิก, wrong selected label ยังถูกเพิ่ม, submit Add
ถูกกลืนเป็น failure ทั่วไป, delayed state/label/associations false-fail, None==None association
และ wrong Add role ถูกยอมรับ รวม premature empty catalog. แก้แล้วมี regressions คงไว้.
Negative cases ยังตรวจ zero writes/no Add/session active; create failure ไม่จอง uncertain creation.
Standards และ Spec correction review: 0 residual actionable findings ใน increment นี้.

Focused Reward checks ก่อน association รอบสุดท้าย: 19 passed; API failures: 2 passed.
Association รอบสุดท้าย: 6 passed in 39.11s. Targeted run ระหว่างแก้ source มี 118 passed/1 failed
ที่ test_preview_does_not_tour_every_reward_tab เพราะ inspect source ใช้ line cache เก่า;
fresh isolated rerun ผ่าน 1 test (0.07s). ไม่อ้างว่ารอบที่ failed ผ่าน.
Full suite `bundle-reward-full1` หยุดที่ 4% เพื่อแก้ review findings; ไม่ใช่ผลผ่าน.
Full suite ใหม่ `bundle-reward-full2` ผ่านจาก source ที่ตรึงแล้ว:
**1,777 passed, 1 warning in 1162.65s** (exit 0, 2026-10-01).
Warning เดิมที่ `tests/test_local_runtime.py:86` เรื่อง process-local development secrets.

```powershell
python -X utf8 -B -m pytest tests -q -p no:cacheprovider --basetemp=build-cache/bundle-reward-full2
```

ณรอบ Reward-picker นี้ #15 ยังเหลือ Reward card fields, repeated occurrences,
save/confirmation และ saved readback ID-first; Reward card fields ย้ายเพิ่มใน increment ด้านล่าง.
Document Reference/Submitted Bundle Values/history/queue gates ไม่เปลี่ยน.

## #15 incremental — Reward card fields (verified ใน working diff)

Live read-only M TH saved FIXED `/combo/cabalm/shop/bundles/225272` (2026-10-01):
ขยายการ์ดเดิมโดยไม่กรอก/เพิ่ม/ลบ/เรียง/บันทึก พบ Ark Gem/WALLET_CREDIT,
Leaf Gem/WALLET และ Player Experience/PLAYER_EXPERIENCE.
Card scope เป็น grandparent ของ expander ตาม slice เดิม; header p และ label/p ภายใน body
แสดงชื่อเดียวกัน. Currency ใช้ label `ชื่อ`; EXP ใช้ `ชื่อ Monarchy`.
Qty เป็น input number name `items.<current-index>.quantity` ไม่มี ID;
Tier เป็น button type=button/role=combobox และ native select ไม่มี ID/name, Common value=0.

Documented no-ID exception สำหรับการจับคู่: exact display name จาก fetched value
(`slug - ชื่อ` ตัดเฉพาะ slug ที่ตรงรูปแบบ) + exact badge ของชนิดรางวัล ภายใน main form
และ card expander ที่ตรวจแล้ว; header/body name ต้องตรงกันและมีหนึ่ง target.
ชื่อซ้ำชนิดเดียวกันหรือ identity/control กำกวมให้หยุด ไม่ยึด list index เป็น identity.
Quantity/Tier อ่านกลับภายในการ์ดนั้น; actual draw ID ใช้ `items.<current-index>.secret_chance`
จาก quantity name ของการ์ดที่จับคู่แล้ว ไม่ใช้ display `chance` และไม่ fallback เมื่อ ID เสีย.
Default Common ต้องจำกัด scope กับ reward cards ไม่แก้ native select ของฟอร์มอื่น.

Implementation ใน working diff จับคู่ Qty/Tier ของ Credit/Debit/Mileage/EXP ตาม identity นี้
และหา actual draw ID จาก current index ใหม่ก่อนกรอก พร้อมอ่านค่ากลับทุกช่อง.
Common เติมเฉพาะ Reward ที่ยังว่างและไม่ได้ระบุ Tier; native Tier ที่เลือกไว้แล้วคงเดิม
โดยไม่ต้องมีตัวเลือก Common ที่ไม่ได้ขอ. RANDOM Reward ที่ไม่ระบุ Tier/rate คง draw default เดิม;
explicit rates รวม numeric/string 0 ใช้เส้นทางตรวจและกรอกเดิม.
กรณีหลาย requested Reward มี effective `(kind, display-name)` เดียวกันหยุดก่อนกรอก card fields
แม้ Aztek รวมเป็นการ์ดเดียว หรือเป็นคนละ code แต่ซ่อน code เหลือชื่อเดียวกัน.
ยังไม่ถือว่ารองรับ occurrence-aware repeats ครบ; ไม่เปลี่ยน/รวมรายการต้นฉบับเพื่อแก้ความกำกวม.
รอการ์ด lazy mount และกางหลัง identity ปรากฏแบบ bounded; expander ที่กางช้ารอสูงสุด 5s.

ตัด positional Qty/Tier/rate fallback และ page-wide default-Tier sweep ที่ไม่ต้องใช้แล้ว.
Default อยู่ใน mapped card fields แทน. ย้าย 5 private/fake blank-Tier tests และ 2 raw no-ID
private rate cases ไปยัง approved public runner/real browser seam; ไม่เพิ่ม private seam ใหม่.

Synthetic runner/API ใหม่ตรวจการ์ด 4 reward kinds ที่ reorder, index เปลี่ยนหลังกรอก Qty,
ชื่อไทย/quotes, ambiguous/hidden duplicate cards/Qty/Tier/rate, ID หาย/ผิด type,
readback ไม่ตรง, nonblank Tier, rate 0/default, late collapsed EXP และ session/save gate.
Traffic จำลองทั้งหมด unknown abort; API contract failures ไม่จอง uncertain creation และ writes=0.
RED/GREEN ยืนยัน positional wrong-card writes, numeric0 ถูกข้าม, slow expansion false-fail,
unrequested Tier overwrite, Thai option lookup, merged duplicate overwrite, unrequested Common,
late collapsed fields และ absent-rate behavior regression; คง regression ป้องกันไว้.
Correction checks ก่อน cleanup ผ่าน 5 tests in 30.93s; Python syntax 5 files ผ่าน.
Standards/Spec correction review หลัง cleanup: 0 residual actionable findings ใน increment นี้.
Targeted Bundle/Recheck ชุดใหม่ผ่าน **167 tests in 665.72s** (exit 0) จาก source ที่ตรึงแล้ว:

```powershell
python -X utf8 -B -m pytest tests/test_web_bundle_id_first.py tests/test_web_bundle.py tests/test_web_bundle_bulk.py tests/test_web_bundle_zero_rate.py tests/test_bundle_recheck_flow.py -q -p no:cacheprovider --basetemp=build-cache/reward-card-target1
```

Full suite รอบ Reward-card `reward-card-full1` ผ่าน **1,798 tests, 1 warning in 1322.08s**
(exit 0, 2026-10-01). Warning เดิมที่ `tests/test_local_runtime.py:86` เรื่อง
process-local development secrets; ไม่ใช่ locator failure.

```powershell
python -X utf8 -B -m pytest tests -q -p no:cacheprovider --basetemp=build-cache/reward-card-full1
```

Verification นี้ครอบคลุม increment และ regression เดิม ไม่ใช่ live submit/Setup verification
และไม่ถือว่าทั้ง #15 เสร็จ. Python syntax 5 files และ git diff --check ผ่าน.

DEV gaps: stable card/reward identity, Quantity/Tier IDs และ exact currency/Monarchy code ใน card.
ยังไม่พิสูจน์ populated create/reorder/delete/selection จริง, Mileage saved card,
Reward RANDOM และ saved Reward ทุกเกม; synthetic evidence จะระบุแยกหลังทดสอบ.
ผล full suite 1,777 ด้านบนเป็นฐานก่อน increment นี้ ไม่ใช่ผลของ source รอบนี้.
ณรอบ Reward-card งานถัดไปของ #15 เป็น save/confirmation, saved readback ID-first และ full occurrence mapping;
Document Reference/Submitted Bundle Values/Recheck History/checkpoint/queue gates คงเดิม.

## Bundle create action — 2026-10-02

Increment นี้ย้ายเฉพาะ target ปุ่มสร้างและ preflight ก่อนจอง checkpoint;
ไม่เปลี่ยน shared `web/create_flow.py` หรือเกณฑ์ตรวจผลบันทึก.

### หลักฐานอ่านสดและ DEV gap

สำรวจ Brave ในแท็บงานแยก เปิดเกมจาก header แล้วอ่าน create page ของ
PC TH/SEA และ M TH/SEA ทั้งสี่เกม:
`/combo/{cabalpc,cabalpcsea,cabalmsea,cabalm}/shop/bundles/create`.
ไม่กรอก/select/upload/Add/Save/Create/Confirm หรือสร้างข้อมูลจริง.

- แต่ละหน้ามี `main form` หนึ่งชุดและปุ่มข้อความตรง `สร้าง Bundle` หนึ่งตัว.
  ปุ่มไม่มี HTML ID, type=`submit`, role attribute ว่าง (native button), enabled;
  native `button.form` ผูกกับฟอร์มที่ครอบปุ่มจริง.
- `บันทึกและสร้างต่อ` เป็นอีก action type=`button` ไม่มี ID; ไม่ใช้แทนปุ่มสร้าง.
- No-ID exception: exact create text ภายใน unique main form พร้อม type/role,
  visibility/readiness/uniqueness และ native form-owner validation.
  ปุ่ม/ฟอร์มซ้ำรวม hidden duplicate หรือผิดชนิดหยุด ไม่เลือก first-match.
- DEV gap: stable HTML ID ของ create submit action. ไม่เดา ID จากข้อความ.
- ผู้ใช้เปิด confirmation ของ M TH ค้างไว้ให้ตรวจ (2026-10-02); Tools อ่านอย่างเดียว:
  `div[role="alertdialog"][data-state="open"]`, ไม่มี stable ID.
  `aria-labelledby` เชื่อม H2 `ยืนยันการสร้าง`, `aria-describedby` เชื่อม P
  `ต้องการสร้าง Bundle ใช่หรือไม่?` ผ่าน runtime radix IDs.
  ปุ่ม `ยืนยัน`/`ยกเลิก` ไม่มี ID, type=`button`, role attribute ว่าง, enabled;
  confirm target หนึ่งตัวและไม่มี nested dialog. ไม่ยึด literal radix IDs เป็น contract.
- DEV gap เพิ่ม: stable Bundle confirmation dialog/action IDs.
  Confirmation อีกสามเกมและ success state ยังไม่ตรวจ; Tools ไม่คลิกสร้างหรือยืนยัน.
  Confirmation fixture ด้านล่างยังเป็น synthetic regression ของ legacy behavior
  ไม่ใช่หลักฐานว่าการย้าย confirmation เสร็จแล้ว. แท็บที่ผู้ใช้เตรียมคงเปิดไว้.

### พฤติกรรมและการตรวจ

- `_save` ใช้ action ที่ scoped แทน page-wide contains-text/first และไม่ใช้ปุ่ม legacy
  เป็นทางสำรองเมื่อ contract ปัจจุบันเสีย.
- ตรวจ enabled แบบมีขอบเขต 5 วินาที แล้วตรวจ main form/target/type/role/form-owner
  ซ้ำหลังรอ ป้องกัน control เปลี่ยนระหว่าง mount. ปุ่มที่พร้อมช้าภายใน timeout ทำงานได้.
- `run_many` preflight ก่อนจอง `creation_uncertain`/checkpoint. Missing/ambiguous/
  disabled/wrong-type action ที่ตรวจได้ก่อนเริ่มสร้างไม่ล็อก draft เป็น uncertain.
  หลังเริ่มบันทึกยังรักษา reservation/ID/recheck และไม่ auto-resubmit ตาม flow เดิม.
- Public runner/API tests ตรวจ outside decoy, missing/duplicate/hidden duplicate,
  wrong type/role/form owner, disabled/late enabled, late type/role/owner/button/form
  mutation, verified response ID, 2xx ไม่มี ID, non-2xx, redirect และ dropped response.
  ทุก request ถูก intercept; unexpected traffic abort. Preview ยังคง submit 0.
- แทน private/FakePage save tests 7 ตัวและ fake unverified-created queue test 1 ตัว
  ด้วย public runner/API coverage; queue gate/replay ยังทดสอบผ่าน routed API เดิม.
  ปรับ synthetic create fixture ให้ type=`submit` ตรงกับหลักฐานสด.
- RED ยืนยัน outside action ถูกเลือก, pre-click ambiguity/disabled ถูกจอง uncertain,
  wrong form-owner ถูกคลิก และ late-ready type/form ambiguity ไม่หยุด. GREEN หลังแก้.
- Focused run `create-final-target1`: 25 passed in 235.53s ก่อน final form revalidation;
  final readiness mutation run `create-final-ready1`: 5 passed in 37.34s หลังแก้ครบ.
  `create-target1` (5 files) หยุดก่อนจบเพื่อแก้ review ไม่ใช่ผลผ่าน.
- Standards/Spec re-review: 0 residual actionable findings เฉพาะ increment นี้.
  Python syntax 4 files/diff check ผ่าน.
- Full `create-target-full1`: **1,811 passed, 1 warning in 1765.81s** (exit 0).
  Warning เดิมที่ `tests/test_local_runtime.py:86` เรื่อง process-local development secrets.
  Source คงที่ระหว่างชุดเต็ม; มีเพียงการเก็บหลักฐาน DOM/แก้เอกสารและลบ whitespace EOF.

```powershell
python -X utf8 -B -m pytest tests -q -p no:cacheprovider --basetemp=build-cache/create-target-full1
```

### ส่วนที่เหลือ

ณจบรอบ Create-action: confirmation ยังใช้ shared legacy helper ที่มี broad first-match;
รอบถัดไปด้านล่างย้าย scoped Bundle confirmation โดยคง flow อื่นไว้.
Response matching, live evidence อีกสามเกม และการย้ายร่วม flow อื่นยัง pending ไม่อ้างว่าปลอดภัยครบ.
Saved readback ID-first และ full repeated-occurrence mapping ยังเหลือ.
ผล full 1,798 ด้านบนเป็นฐานก่อน increment นี้ ไม่ใช่ผลของ source ปัจจุบัน.
ยังไม่ถือว่า #15 เสร็จ; ไม่ Setup/commit/push/publish และคงพัก #12.

## Bundle confirmation — 2026-10-02

อ่าน popup ที่ผู้ใช้เปิดค้างไว้อีกครั้งบน M TH โดยไม่คลิก/กรอก/reload/ปิด dialog.
หลักฐานตรงกับรายการในรอบ Create-action: DIV alertdialog/data-state=open,
H2/P เชื่อมผ่าน live ARIA IDs และปุ่ม native type=button ไม่มี developer ID.
ใช้ exact Bundle heading/description ภายใน unique active alertdialog เป็น no-ID exception.
ตรวจ role/tag/type, hidden duplicates, native form owner, nested dialog และ ARIA relation
ว่าชี้ node เดียวภายใน dialog จริง ไม่ยึด literal runtime Radix ID.
รอ mount/enabled แบบ bounded แล้วตรวจ contract/URL ซ้ำก่อนคลิก.

Shared helper รับ optional confirmation resolver เฉพาะ Bundle; flow อื่นยังใช้ legacy behavior.
Listener เปิดก่อน Create; หากรับ write response แล้วจะไม่กดยืนยันเพิ่ม.
Lookup/click error ไม่ทิ้ง write proof ที่รับแล้ว; dropped response ยังเก็บ numeric Bundle ID
จาก URL ที่ตรง origin/game/bundles path เดิมก่อนรายงานข้อผิดพลาด.
Non-2xx ไม่ถูก URL override และ foreign-game URL ไม่ใช่ proof ของรายการนี้.
กรณีไม่มี popup จริงบนหน้า direct-write เก่าคง return shape เดิม;
กรณี popup มีแต่ contract เสียหยุดและเก็บ uncertain checkpoint/replay gate.
ข้อความขาด write proof ระบุให้ตรวจบนเว็บก่อนและห้ามสร้างซ้ำ ไม่สรุปว่าไม่สร้างแน่นอน.

Synthetic public runner/API เพิ่ม outside action/other-record dialog decoys,
duplicate/hidden action/dialog, wrong action/dialog type/role, ARIA หาย/ซ้ำ/ข้าม scope,
nested dialog/form owner, mount ช้า, enabled แล้วเปลี่ยน contract/page,
response races, dropped-response same/foreign-game redirect และ replay protection.
ปรับ routed Recheck fixture เป็น observed alertdialog/ARIA shape; ไม่ใช่ live write evidence.

RED: outside confirm action ถูกกด; lost response + saved URL ทำ ID หาย;
legacy no-popup/dropped-response โยน exception แทนผลเดิม. GREEN ตรวจหลังแก้.
`confirm-target1`: 27 passed, 1 failed in 551.32s; failure เป็น test fixture เปลี่ยน
ไป GAME เดิม ไม่ใช่การเปลี่ยนเกมจริง. แก้ fixture เป็นเกมอื่นและตรวจซ้ำ; ไม่อ้างว่ารอบนี้ผ่าน.
`confirm-green3`: 3 passed in 78.46s สำหรับ same/foreign-game URL และ page-change.
`confirm-green4`: 5 passed in 111.45s สำหรับ compatibility/URL-ID/page-change/direct proof.
Standards/Spec re-review: 0 residual actionable findings หลังแก้ทั้งสอง compatibility regressions.
`confirm-target2`: **33 passed in 718.83s** (exit 0) หลังแก้ครบ,
รวม observed dialog contracts, compatibility, checkpoints และ Recheck queue gate.
Python syntax 4 files/diff check ผ่าน.
Full `confirm-full1`: **1,837 passed, 1 warning in 2231.61s** (exit 0).
Warning เดิมที่ `tests/test_local_runtime.py:86` เรื่อง process-local development secrets.
Source/test 4 files คง hash เดิมระหว่างชุดเต็ม; มีเพียงการปรับเอกสารสถานะ.
ผล full 1,811 ด้านบนเป็นฐานก่อน increment นี้ ไม่ใช่ผล source ปัจจุบัน.

```powershell
python -X utf8 -B -m pytest tests/test_web_bundle_id_first.py tests/test_bundle_recheck_flow.py -k 'confirmation or lost_response_retains or a_missing_write_response or checkpoint_recheck' -q -p no:cacheprovider --basetemp=build-cache/confirm-target2
python -X utf8 -B -m pytest tests -q -p no:cacheprovider --basetemp=build-cache/confirm-full1
```

Unknown/gaps: popup อีกสามเกม, success/live write endpoint ยังไม่ตรวจสด;
DEV gap stable confirmation dialog/action IDs คงเดิม. Broad write-response matcher ยัง pending.
Saved readback ID-first และ repeated-occurrence mapping ยังเหลือ; #15 ยังไม่เสร็จทั้งหมด.
ไม่ Setup/commit/push/publish, ไม่สร้างข้อมูลจริง และยังพัก New Item #12.

## Saved Item-detail readback — 2026-10-02

ย้ายเฉพาะการอ่าน ItemKind/Option/Duration ของ Item ใน Bundle ที่บันทึกแล้ว;
saved Bundle-card reader (จำนวน/Tier/reward/rate) ยังไม่ย้าย ไม่ถือว่าทั้ง #15 เสร็จ.
อ่านสด PC SEA `/combo/cabalpcsea/shop/items/224352` อีกครั้ง:
main เดียว → form ที่มี `item-name`; ทั้งสี่ IDs เป็น input text ที่มองเห็นได้.
หลักฐานอีกสามเกมจาก #14 ด้านบนยังเป็นฐาน contract ไม่ใช่การตรวจสดซ้ำรอบนี้.
Saved Bundle PC SEA `/combo/cabalpcsea/shop/bundles/225766` ที่อ่านสดมี
actual `items.0.secret_chance` และ display `items.0.chance` แยกกันจริง;
การย้ายตัวอ่านเรทของการ์ดเป็นงานถัดไป ไม่อ้างว่าได้นำหลักฐานนี้ไปใช้ครบแล้ว.
อ่าน saved M TH `/combo/cabalm/shop/bundles/225272` เพิ่มแบบ read-only:
WALLET_CREDIT/WALLET/PLAYER_EXPERIENCE สามการ์ด; กางด้วย `ขยายทั้งหมด`
(button type=button ไม่มี ID) โดยไม่เปลี่ยนค่า/บันทึก. การ์ดที่พับไม่มี Qty control.
หลังขยายมี `items.0–2.quantity` เป็น input number ไม่มี ID และ Tier native select
กับ trigger button role=combobox ไม่มี ID; EXP ใช้ label `ชื่อ Monarchy`.
นี่เป็นหลักฐานสำหรับ saved-card slice ถัดไป ไม่ยืนยันว่ารองรับทุก game/state แล้ว.

ตัวอ่าน Item ใช้ unique main/form/name marker และ exact attribute IDs
`item-game-item-id`, `item-option`, `duration-index`; ตรวจ input text/number,
visibility, uniqueness และรอค่าตัวเลขนิ่งแบบ bounded โดยรับ `0` เป็นค่าจริง.
Known ID หาย/ซ้ำ/ผิดชนิด/ถูกซ่อนหยุด ไม่ใช้ name/label หรือ ID นอกฟอร์มทดแทน.
No-ID business identity ใช้ข้อความ numeric ID เดียวภายใน main;
รอ mount/visibility 5s และตรวจ expected ID/path/visibility ซ้ำหลังค่าพร้อม.
Identity เก่าที่ซ่อนอยู่/หลาย ID/ID หายระหว่างอ่านไม่ใช่หลักฐานว่าตรวจผ่าน.
Exception/gap: main/form/heading/record-ID text ยังไม่มี developer-maintained ID
ตามหลักฐาน #14; ขอ page/form/record-identity IDs และ explicit ready state จาก DEV.

Synthetic routed public reader/API ตรวจ misleading outside ID/name, missing,
duplicate, wrong-type, hidden control, delayed values/identity และ identity mutation.
Failure หลังสร้างเก็บ Bundle ID 42, failed/incomplete Recheck history,
Document Reference และ replay gate; ไม่ส่ง write เพิ่มและไม่ทำรายการถัดไป.
Schema/เกณฑ์ comparator/source/reference เดิมไม่เปลี่ยน; login redirect ยังคงหยุด.
RED รอบแรก 15 failed; identity regressions 3 failed ก่อนแก้ตาม review.
GREEN รอบแรก 85 passed in 224.45s ก่อนเพิ่ม identity cases/history assertions.
Standards/Spec re-review: 0 residual actionable findings เฉพาะ increment นี้.
Target `id-readback-green2`: **88 passed in 239.57s** (exit 0) หลังแก้ครบ.
Python syntax 3 files และ default `git diff --check` ผ่าน.
Full `id-readback-full1`: **1,858 passed, 1 warning in 2402.84s** (exit 0).
Warning เดิมที่ `tests/test_local_runtime.py:86` เรื่อง process-local development secrets.
Source/test 3 files ที่แก้คง SHA-256 เดิมตั้งแต่เริ่มจนจบชุดเต็ม;
ระหว่างรันมีเพียงอ่าน DOM/ปรับเอกสาร ไม่แก้ production/test source.
ผล full 1,837 ด้านบนเป็นฐานก่อน increment นี้ ไม่ใช่ผลล่าสุด.

```powershell
python -X utf8 -B -m pytest tests/test_bundle_recheck_reader.py tests/test_bundle_recheck_flow.py -q --tb=short -p no:cacheprovider --basetemp=build-cache/id-readback-green2
python -X utf8 -B -m pytest tests -q --tb=short -p no:cacheprovider --basetemp=build-cache/id-readback-full1
```

งานต่อ: saved Bundle-card scope/current-index mapping/ID-first draw readback,
full repeated-occurrence create mapping, response matcher และ popup อีกสามเกม.
ไม่ Setup/commit/push/publish และไม่สร้าง/แก้ข้อมูลจริง; New Item #12 ยังพัก.

## Saved Bundle-card readback — 2026-10-02

Scope: #15 เฉพาะ saved-card reader; comparator/source/queue schema ไม่เปลี่ยน.
อ่านสด PC SEA Bundle 225766 ยืนยัน actual draw ID `items.0.secret_chance`
กับ display `items.0.chance` แยกกัน; Quantity `items.0.quantity` เป็น name ไม่ใช่ ID.
ใช้ unique main/form กับ stable `bundle-name` input text; Bundle identity numeric เดียว
ที่มองเห็นได้ และตรวจ URL/identity/marker ซ้ำหลังอ่าน Item details.
Snapshot เดียวผูก badge/business identity/Qty/Tier/current index/draw ID ต่อ occurrence;
รอ mount/options/numeric values แบบ bounded และสอง snapshot ตรงกันก่อนอ่าน details.
Snapshot เปลี่ยนระหว่างอ่าน → หยุดตรวจ ไม่คืนข้อมูลเก่าหรือทำผลผ่านขึ้นเอง.
RANDOM อ่าน exact attribute ID ของ draw ตาม Qty index ปัจจุบัน; เรท 0 ใช้ได้.
Known ID หาย/ซ้ำ/ผิดชนิด/ถูกซ่อนจะไม่ใช้ name, display chance หรือ ID นอกการ์ดแทน.

No-ID exceptions จาก PC SEA 225766/M TH 225272 ที่ตรวจไว้: Type/Tier label block
พร้อม visible button type=button role=combobox + native select-one เดียว;
Qty input number/name ในการ์ด, card expander, badge/Item ID/ชื่อ/ชื่อ Monarchy และ count.
กางเฉพาะ expander ของการ์ดที่ตรวจ shape/form owner/readiness แล้ว;
final click locator คง type=button ระหว่างรอ ป้องกัน submit-type mutation.
DEV gaps: stable form/record/card/expander/count/type/quantity/tier IDs + explicit ready state.
ยังไม่อ้างว่า evidence ของสองเกมครอบคลุมทุก variant/state.

Public reader/API synthetic regressions: outside decoys, repeated IDs/current indices,
draw-vs-display/zero, missing/duplicate/wrong-type/hidden targets, lazy hydration,
nested count, marker mutation และ card mutation ระหว่าง fresh detail reads.
API card failure เก็บ Bundle ID 42, failed/incomplete history, Document Reference
และ replay gate; ไม่ทำรายการถัดไปหรือเพิ่ม submit เพื่อแก้ locator.
RED ทั้ง scope/draw/semantic/readiness/unsafe-submit/count/marker/native-select ก่อนแก้.
Standards/Spec final static re-review: **0 residual findings เฉพาะ increment นี้**.
Target `card-readback-final1`: **123 passed in 369.10s** (exit 0).
Full `card-readback-full1`: **1,893 passed, 1 warning in 2550.49s** (exit 0).
Warning เดิมที่ `tests/test_local_runtime.py:86` เรื่อง process-local development secrets.
ผลก่อน freeze `target2` 112 passed เป็นฐานก่อนเพิ่ม cases/fixes สุดท้าย ไม่ใช่ผล final.
Syntax 4 files/default diff check ผ่าน; SHA-256 ของ source/test 4 files ตรงกับก่อนเริ่ม
final target/full และจบชุดเต็ม ระหว่างรันเปลี่ยนเฉพาะเอกสารส่งต่อ/coverage.

```powershell
python -X utf8 -B -m pytest tests/test_bundle_recheck_id_first.py tests/test_bundle_recheck_reader.py tests/test_bundle_recheck_flow.py -q --tb=short -p no:cacheprovider --basetemp=build-cache/card-readback-final1
python -X utf8 -B -m pytest tests -q --tb=short -p no:cacheprovider --basetemp=build-cache/card-readback-full1
```

งานต่อหลังตรวจรอบนี้: full repeated-occurrence create mapping, broad response matcher,
popup อีกสามเกม และ #16–#19; ไม่ถือว่าทั้ง #15 หรือ #13 เสร็จ.
ไม่มี Setup/commit/push/publish/live write; New Item #12 ยังพัก.

## Repeated-occurrence create mapping — 2026-10-02

Scope: #15 ต่อจาก saved-card slice; ไม่มี public API/schema/business-rule changes.
ฟอร์มที่มี repeated business identity จับการ์ดใหม่จาก DOM delta หนึ่งรายการต่อ Add
และตรวจว่าการ์ดเดิมยังเป็น node เดิม; รันไทม์ binding นี้ไม่ใช่ stable Aztek ID.
Qty/Tier/draw control อยู่ในการ์ดที่ตรวจ identity/kind/scope แล้ว; ใช้ node-specific
control handles และ poll native Tier จากการ์ดเดิมเมื่อรอ options เพื่อไม่ retarget ตาม nth.
อ่าน Qty index ปัจจุบันก่อน exact draw ID `items.<current>.secret_chance`; display chance ไม่เปลี่ยน.
Exact draw ID ต้อง unique ใน owning form และอยู่ใน owning card; current row index
ต้องไม่ซ้ำระหว่าง created occurrences ทั้ง FIXED/RANDOM ก่อนถือว่ากรอกครบ.
Merged/deleted/replaced/ambiguous cards หยุดก่อนสร้าง ไม่เดาจับคู่จากลำดับใหม่.
ตรวจท้ายฟอร์มกัน input ภายหลังเปลี่ยน Qty/Tier/rate ที่กรอกไว้ก่อนหน้า.

Reward Recheck ใช้ one-to-one assignment ตาม identity และ known Qty/Tier/rate เดิม;
คง mismatch/unknown/partial criteria, source/reference และ consume submitted diagnostic rows ทีละ occurrence.
API เดิมห้าม Item ID ซ้ำใน Bundle เดียว: คง rejection นี้และทดสอบว่าไม่เปิด browser/ไม่ส่ง request.
Repeated Item tests ใช้ public runner; repeated Currency/EXP ใช้ runner/API ตาม flow ที่มีอยู่.

Synthetic public cases: repeated Item + four reward kinds, zero/default Common,
prepend/reindex ระหว่าง Add และระหว่าง input/native option readiness, mixed Item+repeated rewards,
ชื่อ Currency เดียวต่าง kind, merged/deleted/replaced cards, previous-row value mutation,
API retryability ก่อน submit และ create/recheck/history/replay ทั้ง correct กับผิด Qty/Tier/rate/จำนวน.
RED พบ duplicate rejection ใน runner, previous Quantity corruption, dynamic nth retarget,
Tier-options readiness reorder, false mismatch ของ reward readback และ current-index collision ก่อนแก้.
Static Standards/Spec reviews ตรวจ source increment; final target/full ผ่านแล้ว.
Focused occurrence/collision: **24 passed in 289.93s**; collision-only RED 2 → **2 passed in 13.89s**.

Freeze source/test 6 files ก่อน final target/full; เปลี่ยนเฉพาะเอกสารระหว่างรัน.
`occurrence-target-final3`: **346 passed in 2055.62s** (exit 0); JUnit failures/errors/skipped 0.
SHA-256 ทั้ง 6 source/test files ตรงกับก่อนเริ่มหลัง target จบ.
`occurrence-full-final3`: **1,915 passed, 1 warning in 2677.59s** (exit 0).
JUnit failures/errors/skipped 0; warning เดิมใน test_local_runtime.py เรื่อง process-local development secrets.
SHA-256 ทั้ง 6 source/test files ตรงกับ freeze หลัง full; syntax 3 files/default diff check ผ่าน.
Standards/Spec 0 finding ค้างเฉพาะ source increment ที่รีวิวไว้; source ไม่เปลี่ยนหลังรีวิว.
ไม่ถือว่าทั้ง #15 หรือ #13 เสร็จ: live repeated-row states, write matcher และ popup อีกสามเกมยังไม่ยืนยัน.
2026-10-08: ผลจบ final2 เรียกคืนไม่ได้หลังหยุด; source/test 6 files SHA-256 ตรงกับ freeze เดิม.
รอบ final3 เก็บ stdout log/JUnit ใน build-cache เพื่อมีหลักฐานหลัง process จบ.
รอบ final1 หยุดหลังพบ collision gap; ไม่ใช่ผลผ่านของ source ล่าสุด.
Syntax 3 files/default diff check ผ่านก่อน freeze; warning CRLF เดิมไม่ใช่ diff error.

Live exceptions/evidence ใช้ card contract ที่อ่านไว้ก่อนหน้า; ยังไม่ทำ live Add/delete/reorder หรือ submit.
DEV gap: stable per-occurrence card identity/ready state เพื่อรองรับ DOM replacement อย่างชัดเจน.
อีกส่วนของ #15: shared response matcher และ popup evidence อีกสามเกม; #16–#19 ยังไม่ implement.
อ่าน DOM M TH `/combo/cabalm/shop/bundles/create` ที่ผู้ใช้เปิด popup ค้างไว้ซ้ำแบบ read-only:
form ไม่มี action/method attributes; browser defaults คือ URL `/create` + GET ไม่ใช่หลักฐาน
ปลายทาง write ของ SPA. Submit และ confirm buttons ไม่มี stable ID; popup ใช้ runtime Radix
ARIA linkage และ confirm `type=button` ไม่มี owning form. ไม่กด/ปิด popup และไม่อ่าน secrets.
ก่อนย้าย broad response matcher ต้องมี endpoint/method evidence หรือ DEV contract;
ไม่อ้าง synthetic POST `/shop/bundles` ว่าเป็น endpoint เว็บจริงที่ยืนยันแล้ว.
ไม่มี Setup/commit/push/publish/live write; New Item #12 ยังพัก.

### Approved one-record live probe — 2026-10-08

ผู้ใช้อนุมัติเพียง 1 Bundle: CabalM TH, FIXED, AFC-IDFIRST-TEST-*;
Item ID 224375 Qty 1 Tier Common, immediately_send=false และ Playwright แยกจากร่างผู้ใช้.
ตัวตรวจชั่วคราวอยู่ build-cache/approved-bundle-probe.py (ignored): ฟอร์มต้องเริ่มว่างและมี 1 card ก่อน arm,
อนุญาตคำขอ write ที่มีชื่อทดสอบเพียงครั้งเดียวและสร้าง exclusive marker ก่อนส่ง;
กัน write อื่น/การส่งซ้ำและ WebSocket, credentials อยู่ใน memory ไม่บันทึก payload/header/token.
ยังไม่มี allowed write/Bundle ID. รอบ 2026-10-02 session ส่งไปหน้า SSO ก่อนกรอก;
รอบ 2026-10-08 Chromium และ HTTP HEAD timeout, DNS ชี้ network ภายในและ TCP443 ไม่สำเร็จ.
รอเครื่องเข้าถึงเครือข่ายบริษัท ก่อนเปิด Chromium ให้ผู้ใช้ล็อกอินเองและตรวจครั้งเดียวต่อ.
ต่อมา 2026-10-08 TCP443 เข้าถึงได้และ headed Chromium เปิดหน้า Login ได้.
พบ SSO ส่ง POST ไป `https://dex.combo-interactive.com/auth/ldap/login` ซึ่ง guard เดิมบล็อก;
หยุดรอบนั้นโดย marker ยังไม่มี แล้วอนุญาตเฉพาะ endpoint/method นี้ช่วงรอ manual login
ก่อนอ่าน authentication body. เปิดรอบใหม่รอผู้ใช้ล็อกอิน; ยังไม่ใช่ผลสร้าง/endpoint Bundle proof.
แก้เฉพาะ ignored temporary probe ไม่เปลี่ยน production source/test ที่ผ่าน final3.
รอบถัดมาผู้ใช้พบ `ERR_BLOCKED_BY_CLIENT`: sanitized report ระบุ guard บล็อก
`POST https://dex.combo-interactive.com/approval` หลังเข้าสู่ระบบ; ไม่มี allowed Bundle write/marker.
เพิ่มเฉพาะ path `/approval` ของ dex ในช่วง manual login แล้วเปิด Chromium ใหม่.
Offline debug harness `build-cache/check-probe-auth-guard.py` รัน guard จริงโดยไม่มี network:
RED พบ authentication body ถูกอ่านเมื่อ path ไม่อยู่ใน allowlist; หลังแก้ SSO approval ผ่าน
โดยไม่อ่าน body และ unrelated writes/post-login approval ยังถูกบล็อก (exit 0).
นี่เป็นผลตรวจ temporary guard ไม่ใช่หลักฐานว่า login/create/readback สำเร็จแล้ว.
ตรวจ marker/report ทุกครั้งก่อนรัน; หากส่งแล้วแต่ผลไม่แน่นอน ให้อ่านผลเดิม ไม่สร้างใหม่.
ไม่ขยายอนุมัติเป็นเกมอื่น/หลาย Bundle หรือ Setup/commit/push/publish; New Item #12 คงพัก.

### Approved probe result — 2026-10-08

ส่ง Bundle write **เพียง 1 ครั้ง**; marker `approved-bundle-probe-write-spent.marker` มีแล้ว.
ห้ามรัน create probe ซ้ำ/ลบ marker/สร้าง test เพิ่มจากสิทธิ์นี้; read/reconcile record เดิมได้.

- Request: `POST https://admin-api-v2.combo-interactive.com/cabalm/warehouse/bundles`.
- Response: HTTP 200; extracted Bundle ID `225954`; runner saved=true.
- Exact name: `AFC-IDFIRST-TEST-20261008-035003`.
- Saved URL: `https://aztek-tools-v2.combo-interactive.com/combo/cabalm/shop/bundles/225954`.
- Live evidence จำกัด CabalM TH; ไม่ extrapolate endpoint/method ของอีกสามเกม.
- Guard บล็อก analytics POST อื่น; ไม่มี write ซ้ำที่อนุญาต.

Playwright probe อ่าน saved Bundle ไม่จบเพราะ `Target page, context or browser has been closed`;
ยังไม่ทราบเหตุปิดจากหลักฐานนี้ และ screenshot ตอน error ล้มเหลวเพราะ target ปิดแล้ว.
คง report/error เดิมไว้ ไม่อ้างว่า automated live reader/recheck ผ่าน และไม่สร้างใหม่.

เปิด saved URL เดิมผ่าน Brave ในแท็บใหม่แบบ read-only แล้วตรวจได้:
ชื่อ exact ตามด้านบน, FIXED, immediately-send aria-checked=false, รายการ Item 1 รายการ,
Item ID 224375 (Raw Stone Of Dimension), Quantity 1, Tier Common (native value 0).
Card แสดง ItemKind 5468/Option 255/DurationIndex 0/Critical —;
อ่าน saved Item URL `/combo/cabalm/shop/items/224375` ด้วย stable IDs item-game-item-id,
item-option และ duration-index ได้ 5468/255/0 ตรงกัน.
ไม่มี workbook reference ใน minimal probe นี้ จึงไม่อ้างผล Recheck เทียบเอกสาร Excel.

ภาพหลักฐานใหม่: `build-cache/approved-bundle-probe-verified.jpg` (ไม่ใช่ screenshot blank เก่า);
ผล readonly แยกใน `build-cache/approved-bundle-probe-readonly-verification.json`.
แท็บ saved Bundle คงไว้ให้ผู้ใช้; ปิดเฉพาะแท็บ Item detail ที่เปิดตรวจเอง ไม่แก้ฟอร์ม/ข้อมูล.
ณ จบรอบ live probe production source/test ยังไม่เปลี่ยน; final3 เป็นผล source ตอนนั้น.
งานต่อคือจำกัด response matcher ตาม endpoint/operation ที่มีหลักฐานจริงพร้อม synthetic public cases;
ณ จบรอบ live probe matcher ยัง broad; ดู increment ถัดไปสำหรับผลล่าสุด.
Remaining #15/#16–#19 ไม่ถือว่าเสร็จจาก live test นี้.

### M TH write-operation contract increment — 2026-10-08 (synthetic verified; live reader pending)

เปลี่ยนเฉพาะ M TH predicate ใน BundleBuilder._save ให้รับ POST จาก captured HTTPS
admin-api-v2 host และ exact path /cabalm/warehouse/bundles ของ owning main_frame.
Worker-owned request ที่ไม่มี frame proof ไม่ match; query ไม่ใช้เป็น identity ของ endpoint.
อีกสามเกมรักษา legacy compatibility predicate จนมี endpoint evidence ไม่อ้าง migration ครบ.
ไม่เปลี่ยน shared create_flow/helper consumers, schemas, document criteria หรือ queue rules.

Public runner RED1: unrelated draft operation ตอบก่อน create แล้ว code เดิมรับ ID 999 แทน 777.
หลังจำกัด endpoint GREEN1 1 passed; RED2: iframe ส่ง API เดียวกันตอบก่อนแล้ว code ยังรับ ID 999.
หลังผูก main_frame GREEN2 2 passed (21.91s).
Case variations: wrong operation/UI host/external host/other game/PUT/PATCH/GET,
correct/error/no-ID response; API dropped write ต้อง creation_uncertain/pending และ replay 409.
Repeated M TH reward fixture และ queue/recheck flow fixture ใช้ captured endpoint โดย traffic ทั้งหมด intercepted.
Target1 16 passed in 195.05s; -k ของรอบนี้ deselect flow suite จึงยังไม่ใช่ผล flow รอบใหม่.
Target2 รวม flow/checkpoint/URL-ID cases และ missing-response API case:
37 passed, 149 deselected in 481.36s (exit 0); JUnit failures/errors/skipped 0.
write-contract-full1: 1,927 passed, 2 warnings in 2797.33s (exit 0).
JUnit tests=1927, failures/errors/skipped=0; target2 JUnit failures/errors/skipped=0.
Hash ทั้ง 3 source/test files ตรงกับ write-contract-freeze.json หลัง target2 และ full1.
Warnings: process-local development secrets เดิม และ PytestUnraisableExceptionWarning
จาก Tkinter Variable.__del__ (main thread is not in main loop) ระหว่าง local release test.
ไม่แก้ Tkinter warning ใน Bundle increment และไม่อ้างว่า warning-free.
Standards/Spec static reviewers 0 scoped finding; source ไม่เปลี่ยนหลังรีวิว.
ไม่มี typechecker config ใน checkout; syntax 3 files/default diff check ผ่าน.
ตรึง shipping source/test 3 files ก่อน final verification; แก้เฉพาะเอกสารและ ignored
read-only debug utilities ระหว่างรัน; ไม่มี shipping source/test เปลี่ยน.

Readonly utility `build-cache/approved-bundle-readonly-probe.py` ใช้ project read_saved_bundle
อ่านเฉพาะ existing ID 225954; บล็อก writes/WebSocket ทั้งหมด ยกเว้น manual SSO login ระหว่างรอ.
ไม่มี authorization/guard arm สำหรับสร้าง; user credentials ไม่ถูกอ่าน/logged/persisted.
รอบ readonly reader จบด้วย Manual login timed out; reader_complete=false,
bundle_writes_allowed=0 ตาม approved-bundle-readonly-reader-report.json.
Final URL เป็น existing Bundle แต่ยังไม่มี ready-control proof; ไม่อ้างว่าสาเหตุคือ session หมดอายุ.
Utility จับ error และ exit 0 จึงไม่ใช้ exit code เป็นผล automated reader ผ่าน.
Bounded read-only ready-state diagnostic ใช้ stored session เดิมใน context แยก,
บล็อกทุก write/WebSocket; final URL เป็น https://dex.combo-interactive.com/auth/ldap/login.
ยืนยันว่ารอบตรวจนี้ต้องผ่าน SSO อีกครั้ง ไม่ใช่ DOM contract proof หรือหลักฐานเวลาหมดอายุ session.
Headed รอบ 2 ผู้ใช้แจ้งเข้าแล้ว แต่ utility ยังไม่ผ่าน extra ready gate (visible bundle-name),
จบ timeout ที่ existing URL; actual production reader ยังไม่ถูกเรียกในรอบนี้.
ไม่มี DOM/screenshot ตอนรอจาก process นั้น จึงไม่อ้างว่าผู้ใช้ login ไม่สำเร็จหรือ stable ID เสีย.
Report2 แยกจากผลแรก; allowed Bundle writes=0 และ reader_complete=false.
Brave read-only inspection ยังพบ exact URL/heading และ bundle-name มี layout rects ไม่มี hidden ancestor.
เตรียม temporary utility สำหรับรอบถัดไปให้รอ saved heading ตาม production reader,
บันทึก sanitized URL transitions/reader_started/ready DOM counts และ screenshot เมื่อไม่ ready;
Utility รูปแบบใหม่ syntax ผ่าน; เปิดรอบ 3 แล้ว, sanitized URL เปลี่ยนจาก existing Bundle ไป dex SSO.
รอ manual login; ยังไม่มี actual reader result รอบ 3 จึงไม่ใช้เป็นผล live reader ผ่าน.
Report3/screenshot reader3 แยกจากหลักฐาน error รอบแรก/รอบ 2.
One-write budget เดิมยัง spent; New Item #12 พัก; ไม่มี Setup/commit/push/publish.

### Saved Bundle header identity increment — 2026-10-08 (verified scoped increment)

Readonly report4 exercise production `read_saved_bundle` แล้ว: reader_started=true,
reader_complete=false, error "Bundle ID เปลี่ยนระหว่างอ่านรายละเอียด" ทั้งที่ final URL ยังเป็น 225954.
Allowed Bundle writes=0; utility exit 0 ไม่ใช่ผลอ่านผ่าน.
DOM inspection ก่อนการอ่านถูกบล็อกยืนยัน header ID 225954 อยู่ด้านนอก form ในกลุ่มหัวข้อ
แก้ไข Bundle (nested span ภายใน p); ไม่มี developer-maintained HTML ID ของ marker/header.
Item picker ภายใน form มีหลาย ID markers เช่น 224529 และโหลดขึ้นระหว่างอ่าน Item detail ได้.
Original main-wide numeric-ID semantic locator จึงนับ header กับ Item results รวมกัน.

No-ID exception ของ **Bundle header เท่านั้น**: intersect numeric-ID text locator ภายใน unique
main กับ `:not(form *)`; initial/final uniqueness, visibility, expected business ID และ URL guard
ยังคงเดิม. ไม่เลือก first-match ไม่ใช้ exact expected text เพื่อซ่อน wrong/duplicate header.
Unknown/ambiguous header layouts ยังคงหยุด; DEV gap ขอ stable saved-record header ID.
Item-detail identity matcher และ comparator/source/queue/write permissions ไม่เปลี่ยน.

Public synthetic reader RED1 มี nested header และ Item-picker ID ที่ mount ระหว่าง GET Item detail:
ล้มด้วย error เดียวกับ report4; GREEN1 หลัง fix: 1 passed in 2.61s (exit 0).
Additional cases: picker IDs ตั้งแต่เริ่มรวมเลขเท่ากับ Bundle, missing header ที่มี picker เลขตรง,
real header wrong/duplicate/hidden/removed/moved into form และ changed URL ระหว่างอ่าน.
Traffic ทั้งหมด routed เป็น synthetic GET; unexpected requests abort ไม่มี traffic ออก Aztek จริง.
Target1 รัน Bundle/Recheck reader, API flow และ ID-first runner แต่พบ failures แล้วหยุด; ไม่มีผลจบ.
Guards1 แยกยืนยัน 10 cases: 10 passed, 32 deselected in 23.16s (exit 0);
JUnit failures/errors/skipped 0; hashes 2 files ตรง freeze หลัง guards.
Diagnose1 correct API flow แยก: 1 passed in 18.75s. Diagnose2 saved-reader [none-passed]
ล้มเพราะ fixture `_saved_page` เก่าวางหัว/Bundle ID ทั้งหมดใน form; ไม่ใช่ actual picker contract proof.
ปรับ fixture helper ให้ supplied heading+ID อยู่ด้านนอก form และการ์ดอยู่ด้านในตามหลักฐาน DOM.
Preserve supplied ID รวม wrong_bundle_id=43; assertions/outcome expectations ทั้งแปด callers คงเดิม.
Production source ไม่เปลี่ยนเพิ่ม. Diagnose3 reader เดิม: 1 passed in 5.12s (exit 0).
Standards/Spec follow-up ของ fixture correction 0 scoped finding (static only).
Full1 temporary queued command เริ่มหลัง target1 ถูก interrupt เพราะ missing-JUnit error ไม่ terminating;
หยุด full1 ทันที ไม่ใช้ผล partial เป็น proof และไม่ใช้ temp/log เก่าทับรอบใหม่.
Target2 ตรวจ reader/Recheck/API ใหม่: 133 passed in 423.18s (exit 0);
JUnit tests133/failures0/errors0/skipped0; hash3filesตรง freeze หลังจบ targeted suite.
Target2 unified exec session 64439 จบแล้ว; full2 session 96941 เริ่มหลัง target2 ผ่านแล้ว
มี ErrorActionPreference=Stop/explicit file existence/positive tests count และ failures/errors/skipped=0
ก่อนเริ่ม พร้อม hashes3filesตรง freeze. Full temp leaf ใหม่ต้องยังไม่ exist.
Full2: 1,937 passed, 1 warning in 2945.52s (exit 0);
JUnit tests1937/failures0/errors0/skipped0; hash3filesตรง freeze หลัง full เช่นเดียวกับ target2.
Warningเดิมprocess-local development secrets; ไม่มี Tkinter warningรอบนี้ ไม่อ้างว่าแก้root causeแล้ว.
Syntax3filesและdiffcheckผ่าน; ไม่มี typecheckerconfig ไม่อ้างtypecheckผ่าน.
write-contract-full1 1,927 passed เป็นฐานก่อน source ล่าสุดนี้ ไม่ใช่ผล fullล่าสุด.
Standards/Spec reviewers 0 scoped finding (static only). Hash 3 shipping source/test files
ตรึงใน `build-cache/bundle-record-id-freeze.json`; logs/JUnit RED/GREEN แยกจากผลเก่า.

Live reread รอบล่าสุดถูก auto-review ปฏิเสธการเข้าถึง origin เพราะ scope กว้างกว่ารายการที่อนุญาต.
ผู้ใช้ยืนยันอ่านเฉพาะ Bundle 225954 กับ Item 224375 แล้ว; scoped retry ยังถูก auto-review บล็อก
เพราะสิทธิ์ที่ browser tool ขออยู่ระดับ origin แม้ action จำกัดสองรายการ. หยุดการอ่านสดตรงนี้;
ผู้ใช้สั่งทำต่อหลังถามสิทธิ์ทั้งเว็บไซต์; retry อ่านเฉพาะหัว Bundle เดิมยังถูก auto-review ปฏิเสธเช่นเดิม.
ขอ explicit origin-level approval ผ่านตัวเลือกอีกครั้ง เพราะ browser API ขอสิทธิ์ระดับเว็บไซต์;
ขอบเขต actions ยังคงอ่านเฉพาะสองรายการ ไม่เปลี่ยนข้อมูล ไม่อ่านรายการอื่น.
ยังไม่ข้ามผ่าน browser/probe ช่องทางอื่น และยังไม่อ้าง automated live recheck ผ่านหลัง fix.
ผู้ใช้ยืนยัน origin-levelโดยชัดเจนแล้ว: scoped Brave read header225954สำเร็จ
(headingแก้ไข Bundle, markerนอกformหนึ่งรายการ ไม่มี developer-maintained HTML ID).
Readonly report5: started=true/complete=false, wait_for timeout5000ms; finalstateไม่มีform/heading.
ภาพ final-state5แสดง Aztekโหลดเวอร์ชันล่าสุดไม่สำเร็จ; report6/final-state6เป็นspinnerไม่มีform.
ไม่สรุปว่า IDcontractเสียจากสองภาพนี้; allowed Bundle writes0ทั้งสองรอบ ไม่ใช้utility exit0เป็นผลผ่าน.
Reader7 (unifiedexec30328) สำเร็จแล้ว: reader_complete=true/matches_approved_item=true.
Public shipping readerถูกเรียกจริง มี initial version-load timeoutแล้ว temporaryutility
retry navigationได้1ครั้งเฉพาะ visible observed version-load error; shipping sourceไม่เปลี่ยนเพิ่ม.
Actualตรง literalที่อนุมัติ: Item224375 Qty1 TierCommon Kind5468 Option255 Duration0,
rewards[]/unsupported[]/complete=true, finalheader count1/headingแก้ไขBundle/bundle-name1/form1.
Allowed Bundle writes0 และไม่มี blocked_other_records; one-write markerเดิมยังอยู่.
Report7/reader7.jpg/reader7-final-state.jpgแยกจากreports4–6ที่ล้ม; ไม่ทับหลักฐานerrorเก่า.
ยังไม่อ้างRecheckเทียบExcelผ่านเพราะminimalprobeไม่มีDocument Reference; ไม่ใช้1rowMTHแทนทุกgame/state.
Window/probe processปิดเฉพาะของตัวเอง; full2/target2/reader7จบแล้ว ไม่มีงานรอSSOรอบนี้.
Source/test3filesคงhashเดิมผ่าน targeted/full; NewItem12ยังพัก; งาน15ส่วนที่เหลือยังไม่เสร็จ.
One-write budget spent ตามเดิม; ไม่มี creation/edit/delete เพิ่ม ไม่มี Setup/commit/push/publish.

### Item Code header/readiness increment — 2026-10-08 (partial #16)

Live audit ผ่าน Brave หลังผู้ใช้อนุญาต origin-level สำหรับอ่านหน้าสร้าง Item Code ทั้งสี่เกม:
`/combo/cabalm/itemcodes/create`, `/combo/cabalmsea/itemcodes/create`,
`/combo/cabalpc/itemcodes/create`, `/combo/cabalpcsea/itemcodes/create`.
ใช้เมนู/ลิงก์สร้างจริง; direct navigation ครั้งแรกที่เพิ่ม `/shop/` ผิดได้ 404
และไม่ใช้เป็น endpoint/contract proof. Production create_url เดิมอยู่ game root ถูกต้องแล้ว.
อ่านเฉพาะ control metadata ใน empty create state ไม่กรอก เลือกข้อมูล หรือ submit.
ปิดเฉพาะแท็บตรวจที่เปิดเองหลังอ่าน; session/แท็บผู้ใช้คงเดิม.

ทั้งสี่หน้า: main มี heading สร้าง Item Code, form เดียวไม่มี stable form ID,
controls 36 รายการ และ nonempty control IDs 22 ค่าที่ไม่ซ้ำใน inventory.
PC SEA ตรวจ nonempty IDs ทั้ง main เพิ่มด้วย ไม่พบซ้ำ.

| Control | ID และ shape ที่พบทั้งสี่เกม |
| --- | --- |
| ชื่อ/Slug | name_th, name_en, slug: INPUT ค่า type attribute ว่าง (DOM type=text), name ตรง ID อยู่ใน form |
| Description | desc_th, desc_en: INPUT; slice นี้รักษาค่าเดิม ไม่กรอก |
| Redeem Type | redeem_type: BUTTON role=combobox, type=button; native SELECT ข้างกันไม่มี ID |
| ต่อ User | per_player_limit: INPUT type=number |
| วันเวลา | start_at, end_at: BUTTON type=button |
| Status/Limit | is_enabled, is_test_mode, is_shown_only_winner, is_limited: BUTTON role=switch |
| Reward 0 names/descriptions | rewards.0.name_th/name_en: INPUT; rewards.0.desc_th/desc_en: TEXTAREA |
| Reward 0 limit/type/codes | rewards.0.per_player_limit: number INPUT; rewards.0.is_limited: switch BUTTON; rewards.0.is_generate_code: combobox BUTTON; rewards.0.serial: TEXTAREA |
| Skip verify | rewards.0.is_skip_verify_game_data: BUTTON role=checkbox; ไม่เพิ่ม interaction |

ปุ่มเพิ่มของรางวัล, เลือก bundle, เพิ่มเงื่อนไข, บันทึกและสร้างต่อ และ submit สร้าง Item Code
ไม่มี ID ทั้งสี่หน้า. Framework relation IDs ไม่ใช้เป็น developer-maintained contract.
Quantity/remaining เมื่อเปิด Limit, Server Generate, Reward index>0, Bundle picker และ confirmation
ยังไม่ได้อ่านในรอบนี้; ไม่ extrapolate IDs/shapes ของ state ที่ยังไม่ปรากฏ.

เปิดปฏิทิน start_at เฉพาะ PC SEA เพื่ออ่านโดยไม่เลือกวัน/กรอกเวลา:
trigger aria-controls ผูก unique role=dialog/data-state=open ที่มี radix runtime ID.
ปุ่มเดือนก่อน/ถัดไปมี aria-label Go to the Previous/Next Month;
SELECT เดือน/ปีมี aria-label Choose the Month/Year;
BUTTON ชั่วโมง role=combobox aria-label ชั่วโมง; INPUT นาที/วินาทีมี aria-label ตามนั้น.
ทุก internal control ไม่มี ID; button วันใช้ data-day เช่น `10/8/2026` (ไม่ใช่ ISO ใน snapshot นี้).
ปิด popover ด้วย Escape. Calendar evidence นี้จำกัด PC SEA start_at; ยังไม่ย้าย widget.

Shipping slice: unique `main form` เป็น documented no-ID scope exception;
name_th/name_en/slug ใช้ exact attribute ID ผ่าน require_control, ตรวจ INPUT/text,
fill และ readback; contract หาย/ซ้ำ/ผิดชนิดหยุดโดยไม่ fallback ไป name/label.
ItemCode READY_SELECTOR ใช้ main form input ID name_th; Event/Product readiness ไม่เปลี่ยน.
ส่วน limit/switch/select/date/reward/create/shared helpers ยังเป็น code เดิมและเป็นงานถัดไป.

Public seam: ItemCodeBuilder.fill_form/run/run_many กับ actual browser + synthetic DOM,
unexpected traffic abortทั้งหมด; preview มี GET เท่านั้น ไม่มี submit.
RED name-priority: old code ใส่ decoys และ actual ID boxes ว่าง; GREEN1 1 passed.
RED readiness: เปลี่ยน name attribute ทำ old name selector timeout 20s; GREEN1 1 passed.
Guards1 + legacy activity tests 87 passed. Target1 หยุดหลังใช้ wrong test game keys
`Cabal PC`/`Cabal PC SEA`; แก้ test data เป็น project keys CabalPC TH/SEA ไม่แก้ production URL.
Guards2 18 passed in 39.34s (exit0): ID missing/duplicate/hidden/wrong tag/type,
outside-form ID, two main forms, unrelated form, lazy mount, four game previews และ queue stop.
แทน private mocked code-wide-limit test ด้วย public fill_form DOM assertions:
limited=true ใส่40/40; unlimited รักษา7/6 แม้ spec มี40/40. ไม่ลด behavior coverage.
Standards/Spec static reviews ของ slice นี้ 0 actionable finding; syntax3filesผ่าน.
Source/test3filesตรึง hashes ใน build-cache/itemcode-names-freeze.json.
Target2 ItemCode/Activity/Product/validation: 768 passed in 143.52s (exit0),
JUnit tests768/failures0/errors0/skipped0; source/test3hashesตรงfreezeหลังจบ.
Full suite 1,937 เป็นฐานก่อน slice นี้ ไม่ใช่ full ของ source ใหม่.
Full suite รอบใหม่ไว้ท้าย implementation งาน #16; ตอนนี้ยังไม่ครบ shared widgets/rewards/create.
Review/verification ยังไม่ถือว่า #16 หรือ parent #13 เสร็จ.
ไม่มี real Item Code write, ไม่มี Setup/commit/push/publish และ New Item #12 ยังพัก.

### Item Code header limit/type increment — 2026-10-08 (partial #16)

อ่าน metadata ของ empty create ทั้งสี่เกมผ่าน Brave session เดิม หลัง origin approval:
เปิด `is_limited` บนฟอร์มที่ยังไม่บันทึกเพื่ออ่าน แล้วปิดกลับ; เปิด redeem popup แล้ว Escape
โดยไม่เลือกค่า/กรอก/submit. แท็บตรวจของตนเองปิดแล้ว; ไม่แก้ records เดิม.

| Control | Contract ที่ยืนยันทั้งสี่เกม |
| --- | --- |
| Limit | is_limited: BUTTON role=switch, type=button, aria-checked boolean |
| จำนวนรวม/คงเหลือ | quantity/remaining: INPUT type=number, name ตรง ID; mount เมื่อเปิด Limit |
| Redeem Type | redeem_type: BUTTON role=combobox type=button; immediate next sibling SELECT ไม่มี ID, parent มี SELECT เดียว |
| Native select options | WINNER/ALL เป็น option values; aria-hidden=true และ style clipped 1px ไม่ใช่ display:none |

No-ID exception ของ native SELECT จำกัด owning parent ของ verified trigger และ SELECT เดียว
(ไม่ค้น page-wide ตาม option text); framework popup IDs ยังเป็น runtime relation เท่านั้น.
Shipping header ย้าย per_player_limit, is_limited, quantity/remaining และ redeem_type เป็น ID-first แล้ว.
Require shape/unique scope, bounded mount, value/state readback; broken contracts หยุดพร้อมชื่อช่อง.
Unlimited ไม่กรอก quantity/remaining; descriptions/status อื่นคงพฤติกรรมเดิม.
Legacy Event/Product helper consumers ไม่เปลี่ยน; helper ID-first เป็น path แยกสำหรับ Item Code.

Public fill_form synthetic DOM/network abort: RED per-user decoy, limit label decoy/lazy fields,
redeem decoy จับการเขียนผิดของ code เดิม; GREEN หลังย้าย ID.
Review พบ requested options ไม่มี bounded mounting wait: RED4 1 failed; GREEN4 3 passed
(lazy option, observed clipped native, non-actionable display:none refusal).
Review พบปุ่ม disabled เปลี่ยนเป็น submit ระหว่าง actionability wait: RED5 submits=1.
Shape-constrained locator click ยัง fail เช่นเดิม จึงใช้ trial click (ไม่ activate) แล้วตรวจ
BUTTON/type=button/role=switch/enabled/connected/boolean state แบบ atomic ก่อน DOM activation.
GREEN6 2 passed: mutation หยุดพร้อม error, submits=0/counts unchanged; normal switch ยังผ่าน.
คง state readback หลัง activate; ไม่ force selection บน display:none หรือ fallback ไป control อื่น.
Guards1 เคยได้ 44 passed/1 failed เพราะ positive fixture ใช้ display:none ไม่ตรง DOM จริง;
diagnostic clipped style ผ่านโดยไม่แก้ select interaction, จึงแก้ fixture ตาม evidence
และเพิ่ม display:none เป็น negative refusal ไม่อ้าง run ที่ล้มว่า passed.

Standards/Spec re-review 0 residual scoped findings; syntax 4 files/diff check ผ่าน.
Source/test4files freeze: build-cache/itemcode-limit-freeze.json.
Regression2 ItemCode/Activity/Product/validation: 798 passed in241.59s (exit0),
JUnit tests798/failures0/errors0/skipped0; source/test4hashesตรงfreezeหลังจบ.
Full1,937เป็นฐานก่อน ItemCode ไม่ใช่ full ของ source รอบนี้; ไม่อ้าง typecheck.
Remaining #16: date/time/shared calendar, status/reward/tab/picker, create/confirmation;
state Server Generate/reward index>0 และ picker/confirmation ยังขาด live evidence.
Full suite ใหม่ไว้ท้าย #16; #16/#13 ยังไม่เสร็จ. ไม่มี real write/Setup/commit/push/publish.

### Item Code calendar increment — 2026-10-08 (partial #16)

Read-only ผ่าน Brave session เดิม: start_at/end_at empty-create popovers ทั้ง PC/M TH/SEA.
เปิดปฏิทิน/ชั่วโมงเพื่ออ่าน metadata แล้ว Escape; ไม่เลือกวัน/เวลา ไม่กรอก/submit;
ปิดเฉพาะแท็บตรวจของตนเอง. DOM contract ที่พบ:

| Control | Stable ID / scoped exception |
| --- | --- |
| Start/End trigger | start_at/end_at: BUTTON type=button; current aria-controls -> unique role=dialog/data-state=open |
| Year/Month | ไม่มี ID; owning-dialog SELECT aria-label Choose the Year/Month; month values0–11 |
| Day | ไม่มี ID; owning-dialog TD role=gridcell/data-day ISO; child BUTTON type=button data-day เป็น M/D/YYYY |
| Hour | ไม่มี ID; owning-dialog BUTTON combobox aria-label ชั่วโมง; current aria-controls -> role=listbox/data-state=open; DIV role=option00–23 ไม่มี ID |
| Minute/Second | ไม่มี ID; owning-dialog INPUT type=text aria-label นาที/วินาที |

Runtime ARIA IDs ใช้เฉพาะความสัมพันธ์ปัจจุบัน ไม่อ้างเป็น DEV-maintained stable IDs.
DEV gap: calendar/year/month/day/hour/minute/second IDs; ใช้ bounded unique scoped exceptions ตามตาราง.
ItemCode consumer ใช้ set_datetime_by_id; legacy Event/Product date helpers ไม่เปลี่ยน.
Trial+atomic shape guard ก่อน date/day/hour BUTTON activation; เปลี่ยนปี/เดือนก่อนเลือกวัน,
เลือกชั่วโมงจาก owning listbox, commit seconds ก่อน minutes, exact trigger readback.
Readback retry มากสุด2รอบ; ค่ายังไม่ตรงเป็น missing ไม่อนุญาตสร้าง; contractเสียเป็น named error.

Public fill_form/run synthetic/network-abort: RED1 codeเดิมไม่กรอก ID dates;
GREEN2 1 passed หลัง diagnose CSS JSON ASCII escaping ของ Thai aria-label
(diagnostic ensure_ascii=true matches0 vs false matches1, popupยังvisible).
Guards1 12 passed in33.94s exit0: ID missing/duplicate/submit type, broken/duplicate relation,
wrong popup role, duplicate internal fields, lazy relation/mount, seconds-reset recovery,
persistent mismatch และ unrelated calendar unchanged/preview submit0.
เพิ่ม invalid date/hour และ4game public preview cases ใน regressionรอบล่าสุด.
Start-hour portals อ่าน metadata เพิ่มครบ4เกมด้วย; ไม่ใช้ end_at state แทน start_at โดยเดา.
RED2 option ผิดชนิดเป็น BUTTON submit + form association ทำ submits1 ใน synthetic;
GREEN3 2 passed หลัง require DIV/role option และ retain shape ใน final click locator.
Standards/Spec re-review0 residual scopedcodefindings; syntax4files/diffcheckผ่าน.
Regression1 853 passed in320.27s exit0 เป็นฐานก่อน hour-option guard ไม่ใช่ผลfinalsource.
Final freeze4files: build-cache/itemcode-date-final-freeze.json.
Regression2 ItemCode/Activity/Product/validation/calendar UI: 854 passed in328.35s exit0;
JUnit tests854/failures0/errors0/skipped0; source/test4hashesตรงfreezeหลังจบ.
Full1,937ยังเป็นฐานก่อน ItemCode slices; ไม่อ้าง fullของsourceใหม่หรือ typecheck.
Remaining16: status/reward/tab/picker/create/confirmation และ fullsuiteท้ายticket;
live populated/readback format และ stateอื่นยังไม่พิสูจน์จาก metadata-only audit.
ยังไม่ถือ16/13เสร็จ; ไม่มี real ItemCode write/Setup/commit/push/publish; New Item12ยังพัก.

### Item Code Reward Set increment — 2026-10-08 (partial #16)

อ่าน empty create ผ่าน Brave session เดิมครบ PC/M TH/SEA ตาม origin approval:
เพิ่มชุดรางวัลบนฟอร์มที่ยังไม่บันทึกเพื่ออ่าน indexed controls และเปิด/ปิด limit ของชุดแรก/ชุดที่สอง;
M TH เพิ่มถึงชุดที่สามและสลับกลับชุดแรกเพื่อยืนยันการ unmount/mount.
ไม่กรอกชื่อ/จำนวน/โค้ด ไม่เลือก Bundle ไม่ submit; ปิดเฉพาะแท็บ audit ที่เปิดเอง.

| Control/state | หลักฐานและ contract |
| --- | --- |
| Reward names | rewards.0/1.name_th/name_en: INPUT DOM type=text ทั้ง4เกม; M TH index2 เพิ่มด้วย |
| ต่อ User | rewards.0/1.per_player_limit: INPUT type=number ทั้ง4เกม |
| Limit/counters | rewards.0/1.is_limited: BUTTON role=switch/type=button/boolean aria-checked; rewards.0/1.quantity/remaining: INPUT number mount เมื่อเปิด limit ทั้ง4เกม |
| Code type | rewards.0/1.is_generate_code: BUTTON combobox/type=button; owning parent มี native SELECT เดียวไม่มี ID; option business values 1=Fix/2=Server ทั้ง4เกม; reward0 native aria-hidden/clipped1px ไม่ใช่ display:none ทั้ง4เกม |
| FIX codes | rewards.0/1.serial: TEXTAREA ทั้ง4เกม; M TH index2 เพิ่มด้วย |
| Add/tab exception | unique main form; add BUTTON type=button ข้อความ + เพิ่มของรางวัล ไม่มี ID; DIV tablist/BUTTON tabs ไม่มี ID และไม่มี ARIA panel relation; direct span แรกเป็นเลขชุด span ถัดไปเป็นชื่อที่แก้ได้ |

มีชุดเดียวไม่แสดงแท็บ; เพิ่มชุดแล้วเลือกชุดใหม่และ mount เฉพาะ indexed controls ของชุด active.
DEV gap: stable IDs ของ form/add/tablist/tab และ ARIA panel relation; ordinal เป็น audited no-ID
exception ไม่ใช่ business record identity หรือ selector ตามชื่อรางวัลที่เปลี่ยนได้.
Scope exception ต้อง unique/shape ถูกต้อง; ID/ordinal หายซ้ำผิดชนิดหยุด ไม่เลือกตัวแรก.

Shipping: ItemCode override add_reward_set จำกัด form + non-submit action; รอ indexed name ID,
เปิดแท็บตาม ordinal ตรวจ active tab เดียว และรอ mount ก่อนกรอก.
Names/per-user/limit/counters/code-type/FIX serial ใช้ stable IDs, shape/unique/readback.
Unlimited ไม่กรอก counters; descriptions/skip-verify/status defaults และ Event consumer คงเดิม.
ตาม review รวม fill/readback เป็น fill_by_id และตั้งชื่อ shared activation เป็น
activate_verified_button; calendar interaction/atomic non-submit guard คงเดิม ไม่เพิ่ม framework.

Public fill_form/run/run_many กับ real synthetic browser; external traffic abort ทั้งหมด:
RED1 legacy name decoys ถูกกรอกแต่ ID names ว่าง; GREEN1 1 passed.
RED2 page-wide add คลิกปุ่มนอก form ไม่เพิ่มชุด; GREEN2 2 passed รวม3 distinct sets/lazy mounts.
RED3 quota/serial ลง decoys ไม่ลงชุดที่ขอ; GREEN3 3 passed หลังย้าย indexed IDs.
Guards1 26 passed/4 failed: name readiness error ขาดชื่อช่อง และ wrong-serial fixture replacement
วน MutationObserver เพราะ node ใหม่ไม่มี mutated marker. แก้ชื่อ error/fixture marker ไม่ลด assertions;
Diagnose1 6 passed in19.61s exit0. Guards2 35 passed in130.88s exit0;
รวม missing/duplicate/wrong type IDs, add/tab ambiguity, mutation disabled→submit,
4game two-reward previews และ queue second-set failure ที่รักษา slug/ID outcomes และ submit0.
Tab1 2 passed in4.16s exit0: เปิด first inactive tab ตาม ordinal แม้ชื่อเปลี่ยน,
รักษาชุดที่สอง และหยุดเมื่อ tab เป็น submit.
แทน source-string assertion ของ reward limit ด้วย public multi-set DOM/counter assertions.
Standards review แก้2 heuristic smells แล้ว; Spec เพิ่ม1 P2 finding เรื่อง raw error ของ
disabled button/tab ไม่ active. Regression1 หยุดเฉพาะ pytest ของตนเองก่อนแก้ finding
จึงไม่มีผลจบและไม่ใช้เป็นผลผ่าน. RED error1 2 failed ยืนยัน raw timeout/assertion;
GREEN error1 5 passed in19.27s exit0 หลัง wrap พร้อมชื่อชุด โดยเก็บ cause เดิม/ไม่ retry action.
รวม guards ปุ่มเปลี่ยนเป็น submit และ inactive first tab เดิมยังผ่าน; syntax4files/diffcheckผ่าน.
Final freeze4files: build-cache/itemcode-reward-error-final-freeze-20261008.json;
freeze itemcode-reward-final รุ่นก่อนเป็นประวัติก่อน error fix ไม่ใช่ source ปัจจุบัน.
Standards/Spec final re-review0 residual scoped findings หลัง error fix.
Regression2 (ItemCode/Activity/Product/validation/calendar UI): 892 passed in479.69s exit0;
JUnit tests892/failures0/errors0/skipped0; source/test4hashesตรงfinalfreezeหลังจบ.
Syntax4files/diffcheckผ่าน; ทดสอบชุดที่เกี่ยวข้อง ไม่ใช่ full suite ของ source ใหม่.

Remaining16 ณจบรอบ Reward ก่อน SERVER increment ด้านล่าง: prefix/amount ยังใช้ legacy path;
Bundle picker/create/confirmation ยังไม่ย้าย; status defaults ไม่เพิ่ม setter/business behavior.
Live filled/populated/readback/success states ยังไม่พิสูจน์; audit นี้เป็น DOM metadata เท่านั้น.
Full1,937ยังเป็นฐานก่อน ItemCode slices; fullใหม่ไว้ท้าย16 ไม่อ้าง typecheck.
ไม่มี real ItemCode write/Setup/commit/push/publish; #16/#13 ยังไม่เสร็จ และ New Item12ยังพัก.

### Item Code SERVER prefix/amount increment — 2026-10-08 (partial #16)

อ่าน empty create ผ่าน Brave session เดิมตาม origin approval ครบ CabalM TH/SEA และ CabalPC TH/SEA.
เลือก Server Generate ในชุด0 เพิ่มชุด1แล้วเลือก Server Generate บนฟอร์มที่ยังไม่บันทึก
เพื่ออ่าน control metadata เท่านั้น; ไม่กรอกชื่อ/prefix/จำนวน/โค้ด ไม่เลือก Bundle ไม่ submit.
ปิดเฉพาะ audit tabs ที่เปิดเอง; user Bundle/Item tabs และ one-write marker คงเดิม.

| Control/state | Contract ที่ตรวจครบทั้ง4เกม/ชุด0และ1 |
| --- | --- |
| SERVER prefix | rewards.N.prefix: INPUT DOM type=text, nameตรงID, maxlength6; optional ตามพฤติกรรมเดิม |
| SERVER amount | rewards.N.amount: INPUT DOM type=number, nameตรงID, min1; ไม่มี max/step explicit |
| Mode mounting | SERVER mounts prefix/amount; FIX serial ไม่อยู่ใน active SERVER set |

Shipping ใช้ fill_by_id ใน owning form ของ active indexed set;
IDหาย/ซ้ำ/ผิดชนิดหยุดพร้อมชื่อชุด/ช่อง ไม่ fallback ไป name เก่า.
Prefix ว่างได้ แต่ readback mismatch ทำให้ฟอร์มไม่ครบ; amount ต้องมีค่าและ readback ตรง.
ไม่เพิ่ม business validation ใหม่หรือเปลี่ยน FIX/default/status behavior.
ไม่มี no-ID exception ใหม่; Bundle picker/create/confirmation ยังเป็น slice ถัดไป.

Public fill_form/run/run_many กับ actual synthetic browser โดย abort external traffic:
RED1 1 failed: name-based legacy path กรอก decoys แต่ indexed SERVER prefix/amount ว่าง.
GREEN1 1 passed in3.78s exit0 หลังย้าย scoped IDs.
Guards1 22 passed in88.75s exit0; JUnit failures/errors/skipped0:
SERVER–FIX–SERVER แยกค่า3ชุด; missing/duplicate/wrong-type prefix/amount ทั้งindex0/1;
optional blank prefix, required blank amount, maxlength truncation/readback mismatch,
lazy SERVER mount, GET-only mixed-mode previews4เกม และ broken second-set amount ในคิว
รักษา slug/saved=false/made_id=null ไม่ submit/retry-write.
Standards/Spec static review0 scoped findings; ไม่อ้างว่ารีวิวรันทดสอบหรือเข้าถึง live.
Freeze4files: build-cache/itemcode-server-final-freeze-20261008.json.
Regression1 (ItemCode/Activity/Product/validation/calendar UI): 914 passed in561.50s exit0;
JUnit tests914/failures0/errors0/skipped0; source/test4hashesตรงfreezeหลังจบ.
Guards1 JUnit tests22/failures0/errors0/skipped0; syntax4files/diffcheckผ่าน.
ผล892เดิมเป็นฐานก่อน SERVER increment; ผล914เป็น related regression ไม่ใช่ full suite.

Remaining16 ณจบรอบ SERVER ก่อน picker increment ด้านล่าง: Bundle picker/create/confirmation/fullท้ายticket.
Live audit เป็น metadata-only ไม่อ้าง live filled/populated/success states;
Full1,937ยังเป็นฐานก่อน ItemCode slices ไม่อ้าง fullใหม่/typecheck.
ไม่มี real ItemCode write/Setup/commit/push/publish; #16/#13 ยังไม่เสร็จ และ New Item12ยังพัก.

### Item Code Bundle picker increment — 2026-10-08 (partial #16)

อ่าน empty create ของ PC/M TH/SEA ชุด0และ1 ผ่าน Brave session เดิมตาม origin approval.
เปิด/ปิด picker และเพิ่มชุดรางวัลบนฟอร์มที่ไม่บันทึก; ไม่กรอกชื่อ/โค้ด/จำนวน ไม่ submit.
อ่านเฉพาะ control/row structure ไม่เก็บชื่อ/ค่าของ Bundle อื่น.
ผู้ใช้อนุญาตเพิ่มเติมให้เลือก Bundle ทดสอบเดิม225954 บนฟอร์ม Item Code ใหม่ของ M TH
ที่ไม่บันทึก เพื่ออ่าน selected state; ดู badge/ปุ่มเปลี่ยน แล้วล้างตัวเลือกและปิดแท็บ audit.
ไม่กดสร้าง/บันทึก ไม่เปลี่ยน Bundle225954 หรือ Item224375 และไม่ใช้สิทธิ์สร้าง Bundle เพิ่ม.

| Control/state | Evidence-backed contract / ข้อยกเว้น |
| --- | --- |
| Reward owner | ทั้ง4เกม/index0และ1: nearest common DIV ของ stable rewards.N.name_th และ rewards.N.is_generate_code อยู่ใน owning form; ไม่มี ID ของ DIV; มี Bundle labelหนึ่งตัว |
| Bundle section | LABEL normalize-space เป็น Bundle * และ parent DIV ไม่มี ID; จำกัดใน Reward owner ที่ผูกกับ stable IDs และตรวจ owning form ตรงก่อน interaction |
| Unselected trigger | ทั้ง4เกม/index0และ1: BUTTON type=button ไม่มี ID/role; aria-haspopup=dialog, aria-expanded, aria-controls มีเมื่อเปิด; ไม่ cache runtime ID |
| Dialog relation | ทั้ง4เกม/index0และ1: aria-controls ชี้ DIV role=dialog/data-state=open/data-slot=popover-content, idแบบradix เป็น runtime relation เท่านั้น |
| Search | ทั้ง4เกม/index0และ1: INPUT DOM type=text, ไม่มี ID, placeholder exact ค้นหาด้วยชื่อหรือ id; uniqueใน dialog ที่สัมพันธ์กับ trigger |
| Rows | ทั้ง4เกมเห็น row metadata ในชุด1; M TH ชุด0เพิ่ม: BUTTON type=button ไม่มี ID/role; direct SPAN ชื่อ + direct SPAN ID: digits; ไม่ถือ business ID เป็น HTML ID |
| Selected/change | ยืนยัน live เฉพาะ M TH/ชุด0/Bundle225954: sectionมี DIV พร้อม SPAN #225954 — ชื่อ และ BUTTON type=button เปลี่ยน; ไม่มี ID; เปลี่ยนล้างค่ากลับสู่เลือก bundle ไม่ได้เปิด dialog ทันที |

อีก3เกม/indexอื่นยังไม่อ่าน live selected/populated/change state; synthetic4เกมไม่แทนหลักฐานนั้น.
DEV gaps: stable IDs สำหรับ Reward owner/form, Bundle section/trigger/search/row และ selected value/change;
ใช้เฉพาะ no-ID exceptions ตามตาราง ไม่ inject IDs หรือเลือก first/last portal เพื่อทำให้ผ่าน.

Shipping: ItemCode ใช้ pick_reward_bundle; Event/Product legacy pick_bundle/reward_card คงเดิม.
Lookup Reward stable ID pair ก่อน แล้วตรวจ nearest common DIV อยู่ใน intended formจริง.
ID/shape/section/action/ARIA relation/search/row ambiguity หยุดพร้อมชื่อชุด/Bundle.
ค้นเลข exactและอ่านค่าค้นกลับ; รอ row mount แทน fixed sleep; direct ID spanต้องตรง ไม่เลือก10010แทน1001.
ทุก action ผ่าน non-submit guard; หลังเลือกต้อง dialogปิดและ badge #เลข — ชื่อ ตรงจริงก่อนบอกสำเร็จ.
Bundleที่เลือกอยู่ตรงอยู่แล้วคงไว้; ต่างเลขต้องเปลี่ยนเพื่อล้างก่อนเปิด pickerใหม่.
ตรวจ anchorก่อนเลือกและหลัง readback; failureคง queue identity/saved=false/made_id=null ไม่ retry-write.
ตาม Standards review เปลี่ยนชื่อ shared ARIA helperจาก _related_calendar_popup เป็น _related_popup
ทั้งcalendarและBundle callers; semanticเดิมคงเดิม ไม่เพิ่ม framework/HTTP API/schema.

Public fill_form/run/run_many กับ real synthetic browser โดย abort external trafficทั้งหมด:
RED1 1 failed: legacy pathไม่ใส่สอง Bundleลงชุดที่ขอ; GREEN1 1 passed in4.00s exit0.
RED2 2 failed: selected stateไม่พบเลือก bundle; GREEN2 3 passed in8.25s exit0หลังรองรับsame/change.
RED3 1 failed: another Bundle widgetในformทำให้scopeกำกวม; GREEN3 4 passed in11.30s exit0.
RED4 1 failed: missing ownlabelเดินไปกด widgetอื่น; GREEN4 5 passed in18.26s exit0หลังbindownerด้วยstableIDpair.
Guards1 30 passed in123.81s exit0 (ก่อนscope-escape fix): missing/duplicate/wrong-type section,
trigger/ARIA/dialog/search/row/badge, wrong selectedID, tab identity change, lazyrows/badge,
4gamefullyfilledGET-only previewพร้อมวินาที59 และ failedsecondBundleรักษาคิว/firstBundle/submit0.
Spec review1 P2: common DIVอาจอยู่นอกformเมื่อlayoutเปลี่ยน และอ่าน outside badgeเป็นsuccess.
Scope RED1 1 failed ยืนยัน false successจากoutside badge; เพิ่ม exact owning-form identity guard.
Guards2หลังscopefix/rename: 31 passed in129.53s exit0; JUnit tests31/failures0/errors0/skipped0.
Standards review1 documentation gap/1 naming heuristic: แก้เอกสาร/renameแล้ว.
Standards/Spec final re-review0 residual scoped findings; ไม่ใช่การปิดticketทั้งหมด.
Freeze4files: build-cache/itemcode-picker-final-freeze-20261008.json.
Related regression1หลังsourceใหม่: 945 passed in699.80s exit0.
JUnit build-cache/itemcode-picker-regression1-20261008.xml: tests945/failures0/errors0/skipped0.
Source/test4hashesตรงfinalfreezeหลังจบ; fullใหม่ยังไม่รัน และไม่อ้างtypecheck.
ผล914เดิมเป็นฐานก่อนpicker ไม่ใช่ผลของ sourceนี้.

Remaining16: create/confirmation และ full suite ท้ายticket.
Live auditไม่สร้าง ItemCode; selected metadataที่อนุญาตไม่ใช่saved ItemCode success/recheck.
Full1,937ยังเป็นฐานก่อนItemCode slices ไม่อ้างfullใหม่/typecheck.
ไม่มี Setup/commit/push/publish; #16/#13ยังไม่เสร็จ และ New Item12ยังพัก.
