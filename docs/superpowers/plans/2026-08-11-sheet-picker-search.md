# Sheet Picker Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add immediate, consistent sheet-name search and fully wrapped sheet names to the Item Finder, Product, Event, and Item Code import dialogs.

**Architecture:** A focused `sheet_picker.js` helper owns filtering, visible-row bulk actions, counts, and reset behavior. A focused `sheet_picker.css` owns search layout and non-truncating sheet rows. Each page keeps its existing import parsing and apply action and only registers its list and bulk buttons with the helper.

**Tech Stack:** Plain HTML/CSS/JavaScript, Playwright sync browser tests, pytest.

## Global Constraints

- Search runs on every `input` event; there is no Search button.
- Matching is case-insensitive and trims the query.
- Select All and Clear affect only visible rows.
- Hidden rows retain checkbox state and still count as selected when applying.
- A new workbook picker resets the query.
- Long names wrap and never use ellipsis or horizontal clipping.
- No parser, API payload, workspace, queue, or Aztek creation behavior changes.
- Do not build Setup, push, publish, or create live Aztek records.
- Do not commit implementation changes until the user explicitly requests it.

---

### Task 1: Shared searchable sheet-list behavior

**Files:**
- Create: `web/static/sheet_picker.js`
- Create: `web/static/sheet_picker.css`
- Create: `tests/test_web_sheet_picker_ui.py`

**Interfaces:**
- Consumes: a list containing `.sheet-row` labels with exact sheet names in `data-sheet-name` and checkboxes at `input[type="checkbox"]`.
- Produces: `window.createSheetPickerSearch(options)`, where `options` contains `list`, `input`, `count`, `empty`, `selectAllButton`, and `clearButton`; returns `{refresh(resetQuery = false)}`.

- [ ] **Step 1: Write the failing browser test for immediate filtering**

Create a synthetic dialog with literal rows `Promotion July`, `Cash Shop July`, and `Guild Reward`. Call the required interface and assert real visible output:

```python
def test_shared_picker_filters_immediately_and_reports_visible_count():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(_synthetic_picker_html())
        page.evaluate(_shared_source())
        page.evaluate("createPickerForTest()")
        page.locator('#sheetSearch').fill('cash')
        assert page.locator('.sheet-row:visible').all_text_contents() == [
            'Cash Shop July'
        ]
        assert page.locator('#sheetSearchCount').inner_text() == '1 / 3 Sheet'
        browser.close()
```

Before the production helper exists, `_shared_source()` evaluates an empty string. The expected RED is `createSheetPickerSearch is not defined`, not a fixture error.

- [ ] **Step 2: Run the test and verify RED**

```powershell
python -m pytest -q tests/test_web_sheet_picker_ui.py::test_shared_picker_filters_immediately_and_reports_visible_count -p no:cacheprovider --basetemp=.pytest-sheet-picker-red
```

Expected: FAIL because `createSheetPickerSearch` does not exist.

- [ ] **Step 3: Add the minimal shared JavaScript**

Implement this public behavior in `web/static/sheet_picker.js`:

```javascript
(function (global) {
  function normalized(value) {
    return String(value || '').normalize('NFKC').trim().toLocaleLowerCase();
  }

  global.createSheetPickerSearch = function createSheetPickerSearch(options) {
    const rows = () => [...options.list.querySelectorAll('.sheet-row')];
    const refresh = (resetQuery = false) => {
      if (resetQuery) options.input.value = '';
      const query = normalized(options.input.value);
      let visible = 0;
      rows().forEach(row => {
        const matched = !query ||
          normalized(row.dataset.sheetName).includes(query);
        row.hidden = !matched;
        if (matched) visible += 1;
      });
      options.count.textContent = `${visible} / ${rows().length} Sheet`;
      options.empty.hidden = visible !== 0;
    };
    const setVisible = checked => {
      rows().filter(row => !row.hidden).forEach(row => {
        const box = row.querySelector('input[type="checkbox"]');
        if (box) box.checked = checked;
      });
    };
    options.input.addEventListener('input', () => refresh(false));
    options.selectAllButton.addEventListener('click', () => setVisible(true));
    options.clearButton.addEventListener('click', () => setVisible(false));
    return {refresh};
  };
})(window);
```

- [ ] **Step 4: Add failing tests for bulk state, no matches, and wrapping**

Add separate tests with literal expectations:

```python
def test_shared_picker_bulk_buttons_change_only_visible_rows():
    # Filter to Cash, clear visible, clear query.
    # Assert checked states are exactly [True, False, True].

def test_shared_picker_shows_empty_state_without_losing_checks():
    # Search "missing"; assert 0 / 3 and a visible empty message.
    # Clear the query; assert all three original checks remain.

def test_long_sheet_name_wraps_without_ellipsis_or_horizontal_overflow():
    # Use a 320px dialog and a literal long name.
    # Assert complete text, multiline height, no horizontal overflow,
    # whiteSpace == "normal", and textOverflow != "ellipsis".
```

- [ ] **Step 5: Run these nodes and verify RED**

Expected: bulk/no-match behavior fails until completed; wrapping fails because shared CSS is absent.

- [ ] **Step 6: Add minimal shared CSS and complete helper behavior**

Create `web/static/sheet_picker.css`:

```css
.sheet-search-tools{display:grid;gap:6px;margin:10px 0}
.sheet-search-tools input{width:100%}
.sheet-search-status{font-size:12px;color:var(--muted)}
.sheet-row[hidden],.sheet-empty[hidden]{display:none!important}
.sheet-row{height:auto;min-width:0;align-items:flex-start}
.sheet-row .sheet-name{min-width:0;white-space:normal;overflow-wrap:anywhere;word-break:break-word;text-overflow:clip}
.sheet-empty{padding:14px;text-align:center;color:var(--muted)}
```

Do not add fuzzy matching, debounce, keyboard shortcuts, or persisted queries.

- [ ] **Step 7: Run Task 1 and verify GREEN**

```powershell
python -m pytest -q tests/test_web_sheet_picker_ui.py -p no:cacheprovider --basetemp=.pytest-sheet-picker-task1
```

### Task 2: Product, Event, and Item Code integration

**Files:**
- Modify: `web/static/products.html`
- Modify: `web/static/events.html`
- Modify: `web/static/itemcodes.html`
- Modify: `tests/test_web_sheet_picker_ui.py`
- Modify: browser page loaders in `tests/test_web_product_ui.py` and `tests/test_web_calendar_ui.py` only when required to inline the new shared assets.

**Interfaces:**
- Consumes: `createSheetPickerSearch(options)` from Task 1.
- Produces: one initialized `sheetPickerSearch` per page and sheet rows carrying `data-sheet-name` plus a `.sheet-name` span.

- [ ] **Step 1: Write parameterized failing integration tests**

Use each actual opener: `openProductSheetPicker(...)` for Product and `showSheets(...)` for Event/Item Code.

```python
@pytest.mark.parametrize('page_name', ['products', 'events', 'itemcodes'])
def test_tool_sheet_picker_searches_as_the_operator_types(page_name):
    page = _open_real_picker(page_name, [
        {'name': 'Promotion July', 'count': 1, 'product_count': 1},
        {'name': 'Cash Shop July', 'count': 1, 'product_count': 1},
        {'name': 'Guild Reward', 'count': 1, 'product_count': 1},
    ])
    page.locator('#sheetSearch').fill('CASH')
    assert page.locator('#sheetList .sheet-row:visible').count() == 1
    assert page.locator('#sheetSearchCount').inner_text() == '1 / 3 Sheet'
```

- [ ] **Step 2: Run integration tests and verify RED**

Expected: FAIL because these pages expose no `#sheetSearch` and load no helper.

- [ ] **Step 3: Wire shared markup and assets into all three pages**

Add this inside every sheet dialog:

```html
<div class="sheet-search-tools">
  <input id="sheetSearch" type="search" placeholder="ค้นหาชื่อ Sheet..." autocomplete="off">
  <span id="sheetSearchCount" class="sheet-search-status" aria-live="polite"></span>
</div>
<div id="sheetSearchEmpty" class="sheet-empty" hidden>ไม่พบ Sheet ที่ค้นหา</div>
```

Load `/static/sheet_picker.css` in `<head>` and `/static/sheet_picker.js` before the page's inline script. Initialize with the page's existing bulk button IDs and remove their old `onclick` assignments.

When creating each row:
- set `row.dataset.sheetName = sheet.name`;
- put the complete displayed label in `<span class="sheet-name">`; and
- call `sheetPickerSearch.refresh(true)` immediately before `showModal()`.

- [ ] **Step 4: Add the failing visible-only bulk integration test**

On Product: select all three, filter to `cash`, click Clear, clear the query, and assert literal checked states `[True, False, True]`.

- [ ] **Step 5: Run RED, add only missing integration, and verify GREEN**

```powershell
python -m pytest -q tests/test_web_sheet_picker_ui.py tests/test_web_product_ui.py tests/test_web_calendar_ui.py -p no:cacheprovider --basetemp=.pytest-sheet-picker-task2
```

### Task 3: Item Finder integration and long-name regression

**Files:**
- Modify: `web/static/index.html`
- Modify: `tests/test_web_sheet_picker_ui.py`

**Interfaces:**
- Consumes: Task 1 shared assets.
- Produces: Item Finder behavior identical to the other three pickers.

- [ ] **Step 1: Write the failing Item Finder integration test**

Load real `index.html`, call `openSheetPicker(...)`, fill `#sheetSearch`, and assert the visible row and count. At a narrow viewport, assert a long literal sheet name is complete, multiline, and has no horizontal overflow.

- [ ] **Step 2: Run the Item Finder nodes and verify RED**

Expected: FAIL because Item Finder has no shared assets or search markup.

- [ ] **Step 3: Wire Item Finder**

Add the shared stylesheet/script and search markup. Change rows to use `data-sheet-name` and a `.sheet-name` span. Initialize against `btnSheetsAll` and `btnSheetsNone`, remove the old global handlers, and call `refresh(true)` before `showModal()`.

- [ ] **Step 4: Run focused tests and verify GREEN**

```powershell
python -m pytest -q tests/test_web_sheet_picker_ui.py tests/test_web_ui.py -p no:cacheprovider --basetemp=.pytest-sheet-picker-task3
```

### Task 4: Regression and scope verification

**Files:**
- Verify all modified files; no additional production scope is expected.

**Interfaces:**
- Consumes: completed shared helper and four page integrations.
- Produces: evidence that search works without changing imports or Aztek behavior.

- [ ] **Step 1: Run all focused UI tests**

```powershell
python -m pytest -q tests/test_web_sheet_picker_ui.py tests/test_web_product_ui.py tests/test_web_calendar_ui.py tests/test_web_ui.py -p no:cacheprovider --basetemp=.pytest-sheet-picker-focused
```

- [ ] **Step 2: Run the complete suite**

```powershell
python -m pytest -q tests -p no:cacheprovider --basetemp=.pytest-sheet-picker-full
```

- [ ] **Step 3: Inspect scope**

```powershell
git diff --check
git status --short
git diff -- web/static/sheet_picker.js web/static/sheet_picker.css web/static/index.html web/static/products.html web/static/events.html web/static/itemcodes.html tests/test_web_sheet_picker_ui.py tests/test_web_product_ui.py tests/test_web_calendar_ui.py
```

Confirm no parser/API/runner changes, no generated files, and no unrelated edits.

- [ ] **Step 4: Report without publishing**

Report exact test counts and modified files. State explicitly that no Setup, implementation commit, push, release, or live Aztek creation occurred.
