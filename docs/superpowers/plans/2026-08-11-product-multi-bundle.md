# Direct Multi-Bundle Product Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let each Product contain 1-20 directly selected Bundle IDs, support manual editing and a selectable Primary Bundle, and fill the current Aztek multi-Bundle UI without creating a Composite Bundle.

**Architecture:** Promote Product Bundle state from one scalar to an ordered list plus one primary ID across parser drafts, API validation, browser queue persistence, and Playwright execution. Keep `bundle_id` as a compatibility mirror of the primary ID while new callers use `bundle_ids` and `primary_bundle_id`. The runner must add exact IDs sequentially, verify the selected list and count, set Primary, and fail closed on any mismatch.

**Tech Stack:** Python/Pydantic/FastAPI, vanilla JavaScript, localStorage queue, Playwright async runner, pytest, Playwright Chromium.

## Global Constraints

- Accept 1-20 unique positive numeric Bundle IDs per Product.
- Preserve imported order; default Primary to the first ID.
- Allow manual add, edit, remove, reorder-by-edit, and Primary selection.
- Removing the Primary promotes the first remaining ID.
- Block empty, duplicate, non-numeric, or more-than-20 lists before opening Aztek.
- Preview/fill mode must not create a real Product.
- Remove the normal Composite Bundle requirement and its handoff UI; multiple IDs go directly into Product.
- Preserve legacy saved queues and callers that only provide `bundle_id`.
- Do not commit installer/setup artifacts unless the user explicitly requests them after verification.

---

## Task 1: Normalize Product drafts to ordered direct Bundle IDs

**Files:**
- Modify: `tests/test_web_product_plan.py:50-100`
- Modify: `web/product_plan.py:228-267`

- [ ] **Step 1: Change the multi-source draft test to the direct contract**

Replace the Composite expectation with:

```python
def test_multiple_source_bundles_become_direct_product_bundles():
    draft = product_plan.build_products({
        'g1': _meta(bundle_id='', bundle_ids=['223930', '223931']),
    }, 'CabalPC TH', now=NOW)[0]

    assert draft['bundle_ids'] == ['223930', '223931']
    assert draft['primary_bundle_id'] == '223930'
    assert draft['bundle_id'] == '223930'
    assert draft['bundle_source'] == 'workbook'
    assert draft['composite_required'] is False
    assert not any('Composite Bundle' in warning for warning in draft['warnings'])
```

Extend the numeric/delimited test to assert stable deduplication and the same Primary rule.

- [ ] **Step 2: Run the focused plan tests and observe RED**

Run:

```powershell
python -m pytest -q tests/test_web_product_plan.py -k "multiple_source_bundles or numeric_and_delimited"
```

Expected: failures because the current draft blanks `bundle_id`, sets `composite_required`, and has no `primary_bundle_id`.

- [ ] **Step 3: Emit direct Bundle state from `_draft_from_meta`**

After `_id_tokens`, deduplicate without reordering and produce:

```python
primary_bundle_id = bundle_ids[0] if bundle_ids else ''
bundle_id = primary_bundle_id
```

Set:

```python
'bundle_ids': bundle_ids,
'primary_bundle_id': primary_bundle_id,
'composite_required': False,
'bundle_id': bundle_id,
'bundle_source': 'workbook' if bundle_ids else '',
```

Delete the Composite warning branch.

- [ ] **Step 4: Run all Product plan tests**

Run:

```powershell
python -m pytest -q tests/test_web_product_plan.py
```

Expected: all pass after updating obsolete Composite assertions only; parser, dates, prices, and limits remain unchanged.

## Task 2: Validate and clean the multi-Bundle API contract

**Files:**
- Modify: `web/app.py:168-191`
- Modify: `web/app.py:1350-1412`
- Modify: `tests/test_web_product_runner.py:95-145`

- [ ] **Step 1: Add request-capture tests for new and legacy payloads**

Add one `/api/products/run` test that sends:

```python
'bundle_ids': ['223930', '223931'],
'primary_bundle_id': '223931',
'bundle_id': '223931',
```

and asserts the captured runner spec preserves that order and Primary. Add a legacy case with only `'bundle_id': '223553'` and assert it normalizes to one ID and the same Primary.

- [ ] **Step 2: Add invalid-contract parameter cases**

Cover duplicate IDs, Primary not in the list, non-numeric IDs, zero IDs, and 21 IDs. Assert HTTP 400/422 and that the runner is never invoked.

- [ ] **Step 3: Run the new API cases and observe RED**

Run:

```powershell
python -m pytest -q tests/test_web_product_runner.py -k "multi_bundle or legacy_bundle or invalid_bundle"
```

- [ ] **Step 4: Extend `ProductSpec` with list and Primary fields**

Use a backward-compatible model surface:

```python
bundle_id: str = Field(default='', max_length=32)
bundle_ids: list[str] = Field(default_factory=list, max_length=20)
primary_bundle_id: str = Field(default='', max_length=32)
```

Keep legacy `bundle_id`; do not require it at Pydantic field level.

- [ ] **Step 5: Normalize in `_clean_product`**

Build the ordered input from `spec.bundle_ids`, falling back to `[spec.bundle_id]`. Trim each ID, validate with `_positive_digits`, reject duplicates, require 1-20 IDs, and choose Primary from `primary_bundle_id` or the first ID. Reject a Primary outside the list. Return:

```python
'bundle_ids': bundle_ids,
'primary_bundle_id': primary_bundle_id,
'bundle_id': primary_bundle_id,
```

- [ ] **Step 6: Run the focused API suite**

Run:

```powershell
python -m pytest -q tests/test_web_product_runner.py -k "bundle or product_run"
```

Expected: new and legacy cases pass; invalid requests never reach browser automation.

## Task 3: Replace the scalar Product Bundle editor with a 1-20 row editor

**Files:**
- Modify: `web/static/products.html:175-200`
- Modify: `web/static/products.html:317-325`
- Modify: `web/static/products.html:573-655`
- Modify: `web/static/products.html:925-1025`
- Modify: `web/static/products.html:1125-1170`
- Modify: `web/static/products.html:1260-1280`
- Modify: `web/static/products.html:1420-1490`
- Modify: `tests/test_web_product_ui.py:753-900`
- Modify: `tests/test_web_product_ui.py:928-1076`
- Modify: `tests/test_web_product_ui.py:1362-1425`

- [ ] **Step 1: Add a visible browser regression for imported multiple IDs**

Load a queue entry with `bundle_ids:['223930','223931']` and assert two numeric text inputs appear in order, the first Primary radio is checked, the counter reads `2 / 20`, and no Composite notice/action is visible.

- [ ] **Step 2: Add a visible browser regression for manual editing**

Exercise Add Bundle, fill a third ID, select it as Primary, remove the original Primary, and assert the remaining state and counter are correct. Reload the page and assert localStorage restores order and Primary.

- [ ] **Step 3: Add a request-capture regression**

Submit preview mode and assert `/api/products/run` receives:

```javascript
bundle_ids: ['223930', '223931'],
primary_bundle_id: '223931',
bundle_id: '223931'
```

Add visible validation assertions for duplicate, blank, non-numeric, and 21st-row attempts.

- [ ] **Step 4: Run the focused UI tests and observe RED**

Run:

```powershell
python -m pytest -q tests/test_web_product_ui.py -k "multi_bundle or primary_bundle or manual_bundle"
```

- [ ] **Step 5: Replace the Bundle section markup**

Remove `#compositeNotice`, `#bundleSourceIds`, and the scalar `#bundleId` field. Add:

```html
<div id="bundleRows" class="bundle-rows"></div>
<div class="bundle-actions">
  <button id="btnAddBundle" type="button">+ เพิ่ม Bundle</button>
  <span id="bundleCount">0 / 20</span>
</div>
<div id="bundleError" class="warning" hidden></div>
```

Each rendered row contains a numeric text input, a Primary radio, and a remove button.

- [ ] **Step 6: Canonicalize old and new queue entries**

Add a helper such as:

```javascript
function normalizeProductBundles(entry) {
  const raw = Array.isArray(entry.bundle_ids) && entry.bundle_ids.length
    ? entry.bundle_ids : [entry.bundle_id];
  entry.bundle_ids = raw.map(value => String(value || '').trim());
  entry.primary_bundle_id = String(
    entry.primary_bundle_id || entry.bundle_id || entry.bundle_ids[0] || ''
  ).trim();
  entry.bundle_id = entry.primary_bundle_id;
  entry.composite_required = false;
  return entry;
}
```

Call it from `blankProduct`, imported-draft merge, handoff merge, queue load, and before render/job construction.

- [ ] **Step 7: Implement row rendering and mutations**

Create `renderBundleRows(entry)`, `addBundleRow`, `removeBundleRow`, and `setPrimaryBundle`. Every mutation must mark the relevant source fields dirty, persist the queue, invalidate preview state, and re-render. Enforce the 20-row cap in both UI and validation.

- [ ] **Step 8: Validate and serialize the list**

Add `validateProductBundles(entry)` returning a Thai error for zero rows, blanks, non-digits, duplicates, too many rows, or invalid Primary. In `jobFrom`, serialize ordered IDs, Primary, and the scalar compatibility mirror.

- [ ] **Step 9: Remove obsolete Composite flow**

Delete the normal `reviewComposite`, Bundle-preview handoff button, Composite submit blocker, and related listeners. Preserve generic Bundle-to-Product handoff support by merging incoming IDs into `bundle_ids` with stable-order deduplication.

- [ ] **Step 10: Run the full Product UI suite**

Run:

```powershell
python -m pytest -q tests/test_web_product_ui.py
```

Expected: all updated tests pass; queue persistence, selection, prices, date layout, and preview/create button behavior remain green.

## Task 4: Fill and verify all Bundle rows in Aztek

**Files:**
- Modify: `web/product_runner.py:406-425`
- Modify: `web/aztek_form.py` only if a reusable exact Bundle-list helper is required
- Modify: `tests/test_web_product_runner.py:215-260`
- Modify: `tests/test_web_product_runner.py:646-735`

- [ ] **Step 1: Add a fake-DOM test for selecting two exact IDs**

Model the current Aztek behavior: click `เลือก bundle`, search/select exact `#223930`, repeat for `#223931`, then expose two selected Bundle cards and `2/20 Bundles`. Assert both searches happen in order and no third selection occurs.

- [ ] **Step 2: Add Primary and fail-closed tests**

Assert the runner checks Primary for `223931`. Add cases where one ID is absent, a wrong ID is visible, selected count is wrong, or Primary cannot be confirmed; `fill_form` must report missing fields so save is not attempted.

- [ ] **Step 3: Run the runner tests and observe RED**

Run:

```powershell
python -m pytest -q tests/test_web_product_runner.py -k "bundle"
```

- [ ] **Step 4: Replace `_fill_bundle` with `_fill_bundles`**

Normalize `bundle_ids` with legacy fallback, then call the existing exact `aztek_form.pick_bundle` once per ID. After each selection, verify that selected IDs contain the requested ID exactly rather than relying only on a successful click.

- [ ] **Step 5: Set and verify Primary**

Locate the selected Bundle card whose visible text contains exact `#<primary_bundle_id>`, check its Primary control, and read it back. Verify the final selected-ID list and the visible `N/20 Bundles` count match the requested ordered unique set. Append a precise `missing` entry on any mismatch.

- [ ] **Step 6: Run the complete runner suite**

Run:

```powershell
python -m pytest -q tests/test_web_product_runner.py
```

Expected: all runner tests pass, including no-response save guards and legacy one-Bundle creation.

## Task 5: Cross-flow verification and review

**Files:**
- Verify only; modify failing files only with a new RED regression.

- [ ] **Step 1: Run all Product and Sheet picker tests together**

Run:

```powershell
python -m pytest -q tests/test_web_product_plan.py tests/test_web_product_ui.py tests/test_web_product_runner.py tests/test_web_sheet_picker_ui.py
```

- [ ] **Step 2: Run the complete suite**

Run:

```powershell
python -m pytest -q
```

Expected: complete suite passes; record the exact count and any non-fatal cache warning.

- [ ] **Step 3: Perform a no-save visible browser smoke test**

Run the local app, import a Product draft with two Bundle IDs, manually add/change Primary, choose preview/fill mode, and confirm Aztek shows the exact Bundle cards and Primary. Do not press any save/create control and do not create a real Aztek Product.

- [ ] **Step 4: Inspect the final diff and worktree status**

Run:

```powershell
git diff --check
git status --short
git diff --stat
```

Confirm the existing Event highlight files are preserved and that no `.env`, database, browser profile, workbook, upload, `dist/`, or installer artifact is staged.

- [ ] **Step 5: Commit only after user approval**

When explicitly requested:

```powershell
git add web/app.py web/product_plan.py web/product_runner.py web/aztek_form.py web/static/products.html tests/test_web_product_plan.py tests/test_web_product_ui.py tests/test_web_product_runner.py
git commit -m "feat(product): support direct multiple bundles"
```

Do not build Setup or push until the user separately requests those actions after the verified commit.
