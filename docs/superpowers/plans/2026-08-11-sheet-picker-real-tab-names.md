# Exact Worksheet Tab Names Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every workbook Sheet picker display and search only the exact Excel worksheet tab name while continuing to submit that exact name to the import API.

**Architecture:** Keep the import-plan API response backward compatible, including `display_name`, but make the shared UI contract authoritative on `sheet.name`. Cover the four creation surfaces with one parameterized visible-browser regression so Item Finder, Event, Item Code, and Product cannot drift apart.

**Tech Stack:** FastAPI static HTML/JavaScript, shared Sheet picker JavaScript/CSS, pytest, Playwright Chromium.

## Global Constraints

- Preserve `display_name` in API payloads because other callers may still consume it.
- Do not derive, shorten, expand, or replace the worksheet tab name in the picker.
- Checkbox values and search text must both use `sheet.name`.
- Preserve the existing live search, visible-only bulk selection, wrapping, and import behavior.
- Do not touch the existing uncommitted Event warning-highlight work.

---

## Task 1: Lock the visible contract to the exact worksheet name

**Files:**
- Modify: `tests/test_web_sheet_picker_ui.py:211-237`

- [ ] **Step 1: Replace the content-name browser regression with an exact-tab regression**

Change the parameterized test to supply deliberately conflicting values and assert that only `name` is visible and searchable:

```python
@pytest.mark.parametrize('page_name', ['index', 'products', 'events', 'itemcodes'])
def test_sheet_picker_displays_searches_and_submits_exact_sheet_name(page_name):
    tab_name = 'ID COM Cabal Community Quiz ! "'
    derived_name = 'Cabal Community Quiz ! "Where am i now?"'
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _open_real_picker(browser, page_name, [{
            'name': tab_name,
            'display_name': derived_name,
            'count': 5,
            'product_count': 1,
        }])

        visible = page.locator('#sheetList .sheet-name').inner_text()
        assert tab_name in visible
        assert derived_name not in visible

        page.locator('#sheetSearch').fill('Where am i now')
        assert page.locator('#sheetList .sheet-row:visible').count() == 0
        page.locator('#sheetSearch').fill('ID COM Cabal')
        assert page.locator('#sheetList .sheet-row:visible').count() == 1
        assert page.locator('#sheetList input').get_attribute('value') == tab_name
        browser.close()
```

- [ ] **Step 2: Run the focused test and observe RED on all four pages**

Run:

```powershell
python -m pytest -q tests/test_web_sheet_picker_ui.py -k "exact_sheet_name"
```

Expected: four failures because each page currently renders `sheet.display_name || sheet.name`.

## Task 2: Make all four pickers render and search `sheet.name`

**Files:**
- Modify: `web/static/index.html:552`
- Modify: `web/static/events.html:452-460`
- Modify: `web/static/itemcodes.html:558-566`
- Modify: `web/static/products.html:944-955`

- [ ] **Step 1: Change Item Finder to use the exact tab name**

Replace the derived label source with:

```javascript
const displayName = sheet.name;
```

Keep both `label.dataset.sheetName = displayName` and `input.value = sheet.name` unchanged so visible search and submitted identity match.

- [ ] **Step 2: Apply the same exact-name rule to Event**

Use `const displayName = sheet.name;` and preserve the existing reward-count suffix.

- [ ] **Step 3: Apply the same exact-name rule to Item Code**

Use `const displayName = sheet.name;` and preserve the existing Item Code-count suffix.

- [ ] **Step 4: Apply the same exact-name rule to Product**

Use `const displayName = sheet.name;` and preserve the existing Product/row-count suffix.

- [ ] **Step 5: Run the focused Sheet picker browser suite**

Run:

```powershell
python -m pytest -q tests/test_web_sheet_picker_ui.py
```

Expected: all tests pass, including exact-name search, long-name wrapping, live filtering, and visible-only bulk controls.

- [ ] **Step 6: Run related import UI regressions**

Run:

```powershell
python -m pytest -q tests/test_web_ui.py tests/test_web_calendar_ui.py tests/test_web_product_ui.py
```

Expected: all tests pass and existing Event warning-highlight changes remain intact.

- [ ] **Step 7: Review the scoped diff**

Run:

```powershell
git diff --check
git diff -- tests/test_web_sheet_picker_ui.py web/static/index.html web/static/events.html web/static/itemcodes.html web/static/products.html
```

Verify no code path still uses `display_name || sheet.name` for a Sheet picker.

- [ ] **Step 8: Commit the exact-name change after the Product work is also green**

Stage only the reviewed files together with the approved Event warning work when the user requests the final commit:

```powershell
git add tests/test_web_sheet_picker_ui.py web/static/index.html web/static/events.html web/static/itemcodes.html web/static/products.html
git commit -m "fix(import): show exact worksheet tab names"
```
