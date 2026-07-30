# Product Creation Page and Shared Plan Design

Date: 2026-07-30

## Goal

Add a Local Product workflow that follows the current Aztek v2 Product create
page, builds editable Product drafts from the plan already imported through
Item Finder, and supports both review-only filling and explicitly confirmed
real creation.

The imported plan is the shared source for Bundle, Item Code, Event, and
Product. The operator should not need to import the same workbook separately on
every page.

## Approved Approach

Use the existing persisted Item Finder workspace as the shared plan and enrich
its per-group metadata with Product fields. Do not introduce a second,
independent workbook store.

The current parser remains responsible for finding item rows and Bundle
contents. A Product-specific metadata layer reads labels around each detected
Shop product block and stores the extra values without changing the existing
item and Bundle payloads.

This is a hybrid approach:

- reuse the existing per-sheet workbook parsing and persisted workspace;
- add Product-specific draft construction in a separate module;
- keep Product automation isolated in a dedicated runner;
- keep the Local page editable and operator-controlled before any real create.

## Source Workbook Findings

The approved reference workbook is:

`[PCTH] 07 July 2026 - Monthly Plan.xlsx`

It contains 54 sheets and more than one Shop layout. Representative layouts
include:

- `Promotion ...` sheets with Product Name, Bundle ID, Shop Label, Category,
  start/end date and time, Limit, Reset, and adjacent currency/value pairs;
- `Cash Shop ...` sheets with Product Name, start/end date and time, Limit,
  Reset, and adjacent currency/value pairs;
- `In Game ...` sheets that may also contain Product-like blocks.

The Product parser must not decide eligibility only from the sheet name. It
detects Product blocks by labels and structure, reports the number found in
each sheet, and lets the operator select the sheets to import when multiple
candidate sheets are present.

The workbook layouts are not fixed. The parser must anchor on normalized label
text such as Product Name and ItemKind rather than fixed row and column
coordinates.

## Shared Plan and Persistence

### Existing workspace as source of truth

`WorkspaceRecord` already persists filename, game, criteria, occurrences,
group metadata, search results, skipped rows, and missing items in the Local
database. The Product work reuses this record.

Each Shop group keeps its current compatibility fields, including the existing
string `product` value. Product metadata is added under a new `product_meta`
dictionary so existing Bundle naming and other consumers do not break.

Representative stored shape:

```json
{
  "is_shop": true,
  "shop_sheet": "Promotion 15.7",
  "product": "Limited Orb x30+5",
  "product_meta": {
    "source_sheet": "Promotion 15.7",
    "source_group_key": "stable existing group key",
    "name": "Limited Orb x30+5",
    "bundle_id": "223553",
    "category_label": "Highlight",
    "shop_label": "20% Off / ลด 20%",
    "end_at": "2026-07-30 07:59:00",
    "limit_text": "10 ครั้ง/ไอดี",
    "reset_day": "No Reset",
    "reset_time": "",
    "price_candidates": [
      {
        "source_label": "workbook label",
        "sale_price": 6600,
        "original_price": 6600
      }
    ]
  }
}
```

The exact group-key scheme remains the existing Item Finder scheme. Product
must not create a second identity for the same workbook block.

### Import once through Item Finder

After Item Finder reads a workbook:

1. It shows the existing sheet-review step.
2. Candidate Product sheets display a Product count.
3. Only selected sheets are merged into the workspace.
4. Their item data and `product_meta` are persisted together.
5. The active workspace ID remains the handoff reference for every downstream
   page.

The Item Finder Product action navigates to `/products` with the active
workspace identity. It does not copy the full workbook-derived payload through
`sessionStorage`.

### Resume and clear

- Closing and reopening the Local application must preserve the workspace in
  the database.
- The browser remembers the last active workspace ID using the existing Item
  Finder mechanism.
- Product drafts saved in the Local queue retain their `workspace_id` and
  `source_group_key`.
- "ล้างแผนที่นำเข้า" deletes only the explicitly selected workspace and clears
  queue entries associated with that workspace after confirmation.
- It must not delete other workspaces, uploaded source files outside managed
  upload storage, or unrelated Local queues.

### Direct Product import fallback

The Product page keeps a direct import action for cases where it is opened
without an active Item Finder workspace.

Direct import:

- detects Product blocks with the same parser;
- returns Product counts grouped by sheet;
- shows checkboxes when multiple candidate sheets exist;
- creates or updates a persisted Shop workspace through the same repository;
- adds drafts only from the selected sheets and makes that workspace active;
- does not automatically create any Aztek record.

## Product Draft Construction

### Names

The workbook normally provides one Product Name. The same source value fills
both Thai and English name fields. No automatic translation is attempted.
Both fields remain editable.

### Selling period

- Start is set once when a Product draft is first built.
- Start uses the current Bangkok calendar date at `00:00:00`.
- Workbook Start Date and values such as "หลัง MA" are not used for Product
  start time.
- End uses the workbook End Date and End Time exactly.
- Times are displayed in the Local 24-hour picker as
  `YYYY-MM-DD HH:mm:ss`, never with a `T`.
- Reopening an already saved draft does not recompute its start date.

### Dynamic currency candidates

There is no hardcoded list of currency names, slugs, aliases, or IDs.

The parser collects adjacent text-and-number pairs from the Product header area
as price candidates. Known structural fields such as dates and limits are
excluded by structure. A candidate becomes a Product currency row only after
it is matched against the options fetched from the current Aztek server.

Matching rules:

1. Compare the workbook source label against every fetched currency display
   name and slug after case, whitespace, and separator normalization.
2. Auto-select only a single unambiguous match.
3. If there is no match or more than one possible match, retain the workbook
   label and value as unresolved data and require manual selection or explicit
   skipping.
4. Never invent an Aztek currency option.
5. Newly added Aztek currencies work without a code change.

The workbook's main price becomes the sale price. Original price defaults to
the same value. When the same Product block contains a clearly labelled normal
or full price associated with that candidate, that value becomes original
price and the main value remains sale price.

### Category

Category options are also fetched from the current Aztek server.

- Store the workbook Category text as `category_label`.
- Match it against fetched Category names and identifiers using normalized,
  unambiguous matching.
- If it cannot be matched uniquely, leave Category unresolved and require the
  operator to select one.
- Do not hardcode the Category list.

### Purchase limit and reset

Normalize workbook limit text as follows:

- `No Limit` becomes unlimited.
- `N ครั้ง/ไอดี` and `N Time / Account` become `PLAYER` with limit `N`.
- Character-specific text becomes `CHARACTER` with its limit.
- `Everyday` becomes a one-day reset interval at the workbook reset time.
- A named weekday becomes a seven-day reset interval aligned to that weekday
  and reset time.
- `No Reset` keeps the purchase limit but leaves the reset interval unset.
- Ambiguous or incomplete limit text is retained for review and not guessed.

### Tags

Map Shop Label to Aztek tags only when the meaning is clear:

- Sale, discount text, or `%` becomes `SALE`;
- Popular or Must Have becomes `HOT`;
- Limited becomes `LIMITED`;
- New becomes `NEW`;
- Event becomes `EVENT`.

More than one clear tag may be selected. Unmatched labels remain visible as
source context but do not select a tag.

### Bundle

Bundle resolution order:

1. a Bundle ID explicitly present in the workbook block;
2. a created Bundle handed off with the same `source_group_key`;
3. a single unambiguous existing Bundle match by the available Aztek selector;
4. manual Bundle ID entry.

If a created Bundle ID conflicts with a non-empty workbook Bundle ID, do not
silently overwrite either value. Show the conflict and require the operator to
choose.

When no Bundle is resolved, show the same numeric Bundle ID input pattern used
by the Item Code and Event pages. Product cannot be created until the Bundle is
resolved.

### Images and descriptions

- Thai and English details are editable and optional unless Aztek reports them
  as required.
- Thumbnail and Banner uploads remain manual for Thai and English.
- Imported workbooks are not searched for external image files.
- The Local application must not copy arbitrary workbook-adjacent files.

### Display defaults

New drafts use the inspected Aztek defaults:

- Enabled: off;
- Test mode: on;
- Hidden: off;
- Position: `0`.

All remain visible and editable.

## Currency and Category Fetching

The Product page obtains Currency and Category options from the live Aztek
Product create page for the selected server.

### Cache

- Cache Currency and Category independently by server/game.
- Cache the exact fetched option ID/slug and display name, plus `fetched_at`.
- Persist the cache in browser `localStorage` under versioned keys containing
  the server/game and option kind; do not put live Aztek session data in it.
- The first Product page use for a server fetches missing option kinds.
- A valid cached kind is reused on later visits and application restarts.
- The Local page exposes separate "Fetch Currency ใหม่" and
  "Fetch Category ใหม่" actions.
- Changing server loads that server's cache or performs a new fetch.
- Refresh failure leaves the last good cache available and shows a warning.

No options are seeded from a hardcoded list.

### Read-only safety

Option fetching opens the Product create page, reads the searchable selectors,
and leaves without submitting the form. It must not click Create Product or
upload an image.

## Local Product Page

### Route and navigation

- Add `GET /products` serving `web/static/products.html`.
- Add Product as navigation step 5 after Event on all workflow pages.
- Add "ส่งไปสร้าง Product" from Item Finder.
- Add "สร้าง Product" as a Bundle-result handoff destination.

### Queue

The page supports:

- a queue of multiple Product drafts;
- one active editable Product;
- source sheet and workspace indicators;
- selection of individual queue entries for real creation;
- select all and clear selected actions;
- per-entry status: draft, incomplete, previewed, created, or failed;
- created Product ID and last result.

Draft edits are saved locally without changing the original `product_meta`.
The Product queue uses a versioned `localStorage` key and stores no workbook
bytes or Aztek session data.
Re-importing the same workspace does not silently duplicate a draft with the
same `workspace_id` and `source_group_key`; it offers update/keep-current
behavior when fields have been edited.

### Aztek-aligned layout

Use the current Local visual theme while matching the section placement of the
inspected Aztek Product page.

Left column:

1. General information: Category, Thai name, English name.
2. Details: Thai and English tabs.
3. Product images: Thai and English tabs, Thumbnail and Banner.
4. Currency: repeatable fetched Currency rows with original and sale price.
5. Bundle: resolved summary and manual Bundle ID fallback.

Right column:

1. Display: enabled, test mode, hidden, and position.
2. Selling period: start and end.
3. Purchase limit: type, amount, interval, last reset, and computed next reset.
4. Tags: EVENT, HOT, LIMITED, NEW, and SALE.

A sticky action area follows the Aztek page structure. At widths of `1100px`
or less, columns stack left then right without horizontal scrolling.

## Execution Modes

The mode selector controls which action button is visible. Do not show both
primary execution buttons at the same time.

### Fill for review

- Visible action: "กรอก Product นี้เพื่อตรวจสอบ".
- Operates on the active Product only.
- Opens the matching Aztek Product create page and fills the supported fields.
- Stops before Create Product.
- Does not upload images that have not been explicitly selected.
- Reports missing or unmatched fields without submitting.

### Real create

- Visible action: "สร้าง Product ที่เลือก".
- Validates every selected draft before opening the runner.
- Shows a second confirmation containing the number of Products and their
  names.
- Creates sequentially through the existing single-browser-job policy.
- Returns created Product ID, success/failure, and log for every entry.
- Continues past an isolated failed entry and reports the final created/planned
  totals.
- Does not retry successful entries when retrying failed entries.

## API and Module Boundaries

Expected additions:

- `web/product_plan.py`
  - convert persisted `product_meta` into editable Product drafts;
  - perform date, limit, price-candidate, category-source, and tag mapping;
- `web/product_runner.py`
  - fetch live Currency/Category options;
  - fill Product fields;
  - optionally submit and read the resulting Product ID;
- `web/static/products.html`
  - queue, editor, option cache, sheet selection, validation, and results;
- Product request/response models and routes in `web/app.py`;
- navigation updates in existing static workflow pages.

Expected endpoints:

- `GET /api/workspaces/{workspace_id}/products`
  - build drafts from the shared persisted plan;
- existing `POST /api/import-plan` and `POST /api/import-plan/apply`
  - direct-import fallback using the same persisted Shop workspace and sheet
    selection flow as Item Finder;
- `POST /api/products/options`
  - fetch requested option kinds for a game, read-only;
- `POST /api/products/run`
  - run fill-only or confirmed real creation.

The option endpoint accepts requested kinds so Currency and Category can be
refreshed independently.

## Validation and Error Handling

Real create requires:

- Thai and English names;
- a fetched Category option;
- at least one resolved fetched Currency option;
- valid non-negative original and sale prices;
- start and end with end later than start;
- a resolved numeric Bundle ID;
- complete purchase-limit fields when limit type is not unlimited.

Unresolved source currency/category text remains visible beside the affected
field. Ambiguous matches are never silently chosen.

Errors must name the Product and field. A failure in one Product must not erase
other drafts or successful IDs.

## Verification

### Parser and plan tests

- detect Product blocks without relying on fixed row or column numbers;
- read representative Promotion and Cash Shop layouts;
- detect Product-capable In Game sheets and leave selection to the operator;
- preserve Product counts per sheet;
- persist `product_meta` through WorkspaceRepository JSON sanitization;
- use the same source group key as Bundle;
- fill both names with the same workbook Product Name;
- set start once to current Bangkok date at midnight;
- preserve workbook End Date and End Time;
- map limits, reset schedules, and tags as approved;
- preserve ambiguous data for review instead of guessing.

### Dynamic option tests

- match a future Currency unknown to the code when it is present in fetched
  options;
- do not depend on THB, Wallet Point, Forcegem, or any other hardcoded name;
- reject ambiguous normalized matches;
- keep last good cache when refresh fails;
- isolate caches by server and option kind;
- match Category only to fetched options.

### UI tests

- show sheet checkboxes when multiple Product-capable sheets exist;
- load drafts from the active Item Finder workspace without re-import;
- avoid duplicate drafts for the same workspace/group key;
- visibly show unresolved Currency, Category, and Bundle states;
- render the Aztek-aligned desktop and stacked layouts;
- keep all edits when switching queue entries and language tabs;
- display only the action button for the selected execution mode;
- require explicit confirmation before real create;
- show Product IDs and per-entry results after a mocked run.

### Runner tests

- fetch options without clicking Create Product;
- fill each supported Aztek section using stable field semantics;
- fill review mode and stop before submit;
- submit only when `do_save` is true;
- read the Product ID from the success result;
- return a clear missing-selector error when the live layout has changed.

Run the complete Local web test suite. Browser verification must use mocked or
fill-only paths. Implementation and automated verification must not create a
real Aztek Product.

## Non-goals

- no automatic translation of Product names or descriptions;
- no hardcoded Currency or Category catalog;
- no automatic discovery of external product images;
- no modification of the source workbook;
- no production deployment or GitHub Release;
- no real Aztek Product creation as part of implementation verification.

## Success Criteria

- One Item Finder import supplies the persisted data used by Product.
- Multiple detected sheets remain operator-selectable.
- Product drafts survive Local application restart.
- The Product editor matches the major Aztek layout and remains editable.
- Currency and Category values come only from fetched server options.
- Future Currency options can match without code changes.
- Bundle IDs reconcile by source identity or remain explicitly manual.
- Fill-only mode never submits.
- Real create requires explicit selection and confirmation and reports Product
  IDs per entry.
