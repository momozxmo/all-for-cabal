# Product Live Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Product page's mode/selection strip with the same three explicit live-action controls used by Event and Item Code, while requiring a successful matching preview before creating the active Product.

**Architecture:** Keep `productQueue` as the only source of run scope. Track successful previews by Product queue key in page memory, derive all button labels and disabled states from the active entry, pending entries, preview keys, and busy state, and invalidate only the edited Product's preview. Reuse the existing Product submission, result, retry, and validation paths.

**Tech Stack:** Static HTML/CSS/JavaScript, FastAPI-served page, Playwright browser regression tests, pytest.

## Global Constraints

- Change only Product UI behavior and Product browser tests.
- Do not modify Item Code, Event, Product parsing, Product form data, Product API, or the Aztek runner.
- Never create a real Aztek Product during tests or verification.
- Do not build Setup, commit implementation changes, or push unless the user asks afterward.

---

### Task 1: Lock the new action-card contract with failing browser tests

**Files:**
- Modify: `tests/test_web_product_ui.py`

- [x] **Step 1: Replace the obsolete mode-toggle test**

Add a visible contract test that expects:

```python
assert page.get_by_role('heading', name='สร้างบนเว็บจริง').is_visible()
assert page.locator('#btnPreview').is_visible()
assert page.locator('#btnCreateOne').is_visible()
assert page.locator('#btnCreateAll').is_visible()
assert page.locator('#runModePreview').count() == 0
assert page.locator('#runModeCreate').count() == 0
assert page.locator('#selectForRun').count() == 0
```

- [x] **Step 2: Add the active-preview gate regression**

Seed two runnable Products, stub `submitProducts`, and assert:

```javascript
// create-one starts disabled
// preview submits only the active Product with doSave=false
// successful preview enables create-one for that Product key
// switching Product disables it; switching back restores it
// editing a field invalidates the preview and disables it again
```

- [x] **Step 3: Replace checked-entry creation coverage with active and bulk coverage**

Cover both paths:

```javascript
await runActiveProduct(); // one active Product, doSave=true
await runAllProducts();   // all entries without product_id, queue order, doSave=true
```

Assert the confirmation text includes the count and Product names, and the bulk button count excludes entries that already have `product_id`.

- [x] **Step 4: Run the focused tests and confirm RED**

Run:

```powershell
pytest -q tests/test_web_product_ui.py
```

Expected: the new tests fail because the card, `btnCreateOne`, `btnCreateAll`, preview-key gate, and bulk runner do not exist yet.

### Task 2: Implement the Product live-action card and derived state

**Files:**
- Modify: `web/static/products.html`

- [x] **Step 1: Replace the sticky mode strip markup**

Use a normal card matching the Event layout:

```html
<section class="card" aria-label="ส่ง Product">
  <div class="card-head"><h2>สร้างบนเว็บจริง</h2></div>
  <div class="card-body">
    <div class="result-actions">
      <button id="btnPreview" type="button">👁 เปิดหน้าเว็บดูก่อน (อันที่เลือก)</button>
      <button id="btnCreateOne" type="button">🚀 สร้างจริง (อันที่เลือก)</button>
      <button id="btnCreateAll" type="button">⚡ สร้างทุกอันในคิว (0)</button>
    </div>
    <p id="runMsg" class="hint" role="status" aria-live="polite"></p>
    <div id="productResults"></div>
  </div>
</section>
```

Remove Product-only sticky/mode CSS and add only the minimal wrapping rule needed for the three buttons.

- [x] **Step 2: Add preview and busy state**

Introduce:

```javascript
const previewedProductKeys = new Set();
let productRunBusy = false;

function pendingProducts() {
  return productQueue.items.filter(entry => !entry.product_id);
}

function paintRunActions() {
  const entry = productQueue.current();
  const pending = pendingProducts();
  $('btnPreview').disabled = productRunBusy || !entry || !!entry.product_id;
  $('btnCreateOne').disabled = productRunBusy || !entry
    || !!entry.product_id || !previewedProductKeys.has(entry.key);
  $('btnCreateAll').disabled = productRunBusy || !pending.length;
  $('btnCreateAll').textContent = `⚡ สร้างทุกอันในคิว (${pending.length})`;
}
```

Call `paintRunActions()` from queue rendering, active Product changes, successful/failed runs, and queue mutations.

- [x] **Step 3: Make preview ownership and invalidation key-specific**

On a successful preview response, add the submitted entry key to `previewedProductKeys`. On an input/change event inside `#editor`, delete only the active Product key and repaint actions. Programmatic rendering must not invalidate a preview.

Also remove stale preview keys when entries are deleted or the queue is cleared.

- [x] **Step 4: Replace selected creation with active and all creation**

Implement:

```javascript
async function runActiveProduct() {
  const entry = productQueue.current();
  if (!entry || !previewedProductKeys.has(entry.key)) return;
  return runCreatedProducts([entry], confirmationFor([entry]));
}

async function runAllProducts() {
  const entries = pendingProducts();
  return runCreatedProducts(entries, confirmationFor(entries));
}
```

Keep `runnableError`, `submitProducts`, `applyProductResults`, logs, IDs, missing fields, and retry behavior unchanged. Remove the run-mode and `selected` checkbox bindings; the compatibility property may remain in stored entries but must not affect run scope.

- [x] **Step 5: Bind the new buttons and initialize derived state**

Bind `btnPreview`, `btnCreateOne`, and `btnCreateAll` to their dedicated handlers, remove `paintRunMode`, and initialize through `renderQueue()`/`paintRunActions()`.

### Task 3: Verify regressions and scope

**Files:**
- Verify: `tests/test_web_product_ui.py`
- Verify: `web/static/products.html`

- [x] **Step 1: Run focused Product UI tests**

Run:

```powershell
pytest -q tests/test_web_product_ui.py
```

Expected: all Product browser tests pass.

- [x] **Step 2: Run the complete automated suite**

Run:

```powershell
pytest -q
```

Expected: full suite passes without launching a real Aztek create.

- [x] **Step 3: Inspect the final diff and forbidden scope**

Run:

```powershell
git diff --check
git status --short
git diff -- web/static/products.html tests/test_web_product_ui.py
```

Expected: no whitespace errors; implementation changes are limited to the Product page/tests plus this plan document; no Item Code/Event, Setup, release, database, profile, secret, or uploaded workbook changes.
