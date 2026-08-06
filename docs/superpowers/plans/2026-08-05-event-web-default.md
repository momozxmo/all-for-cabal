# Event Web Result Default Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Item Finder Event mode select “ไม่มี” as its editable default for “แสดงผลบนเว็บ”.

**Architecture:** Change the shared Event mode policy so `/api/modes` remains the single source of truth used by the Item Finder page and search runner. Preserve the existing `applyMode()` rendering path and lock semantics; add policy, API, and visible browser assertions around the new value.

**Tech Stack:** Python, FastAPI, static HTML/JavaScript, pytest, Playwright.

## Global Constraints

- Event uses `web_mode: no` and `web_locked: false`.
- Item Code remains `web_mode: no` and locked.
- Shop remains `web_mode: no` and editable.
- Existing imported workspaces and search data are not rewritten.
- Do not modify Event import/creation, Item Code, Shop, Product, Setup, or release files.
- Keep the implementation uncommitted until the user explicitly requests a commit.

---

### Task 1: Change the shared Event mode default with a red-green test cycle

**Files:**
- Modify: `tests/test_web_item_service.py:18-27`
- Modify: `tests/test_web_api.py:49-54`
- Modify: `tests/test_web_calendar_ui.py:420-445`
- Modify: `web/item_service.py:146-152`

**Interfaces:**
- Consumes: `ItemService.mode_policy(mode: str) -> dict[str, object]` and `GET /api/modes`.
- Produces: Event policy `{'web_mode': 'no', 'web_locked': False, 'read_desc': False}`; the existing `applyMode('event', false)` selects `#webNo` while leaving every `input[name=webMode]` enabled.

- [x] **Step 1: Change the service expectation before production code**

Update the Event assertion in `tests/test_web_item_service.py` to:

```python
assert svc.mode_policy('event') == {
    'web_mode': 'no', 'web_locked': False, 'read_desc': False,
}
```

Extend `tests/test_web_api.py` so the endpoint contract includes:

```python
assert response.json()['event'] == {
    'web_mode': 'no', 'web_locked': False, 'read_desc': False,
}
```

- [x] **Step 2: Run the policy/API tests and verify RED**

Run:

```powershell
python -m pytest -q tests/test_web_item_service.py tests/test_web_api.py -k "mode_policy or modes_and_template_download"
```

Expected: Event assertions fail because the current value is `web_mode: any`.

- [x] **Step 3: Add visible Item Finder mode assertions**

In `test_item_finder_shows_only_the_handoff_for_the_selected_mode`, set the same policies the API returns before applying modes:

```javascript
state.modes = {
  event:{web_mode:'no',web_locked:false},
  itemcode:{web_mode:'no',web_locked:true},
  shop:{web_mode:'no',web_locked:false}
};
```

Immediately after `applyMode('event', false)`, assert:

```python
assert page.locator('#webNo').is_checked()
assert page.locator('input[name=webMode]:disabled').count() == 0
```

Keep the existing handoff-button assertions for all modes.

- [x] **Step 4: Implement the minimal shared policy change**

Change only the Event row in `ItemService.MODE_POLICIES`:

```python
'event': {'web_mode': 'no', 'web_locked': False, 'read_desc': False},
```

- [x] **Step 5: Run focused tests and verify GREEN**

Run:

```powershell
python -m pytest -q tests/test_web_item_service.py tests/test_web_api.py tests/test_web_calendar_ui.py
```

Expected: all focused tests pass, including the Event `webNo` and unlocked assertions.

### Task 2: Verify the complete project and change boundary

**Files:**
- Verify: `web/item_service.py`
- Verify: `tests/test_web_item_service.py`
- Verify: `tests/test_web_api.py`
- Verify: `tests/test_web_calendar_ui.py`

**Interfaces:**
- Consumes: the completed policy and regression tests from Task 1.
- Produces: verification evidence without creating Aztek records or changing repository integration state.

- [x] **Step 1: Run the complete test suite**

Run:

```powershell
python -m pytest -q tests
```

Expected: all tests pass; browser tests use local/stubbed pages and do not create real Aztek data.

- [x] **Step 2: Inspect whitespace and scope**

Run:

```powershell
git diff --check
git status --short
git diff -- web/item_service.py tests/test_web_item_service.py tests/test_web_api.py tests/test_web_calendar_ui.py
```

Expected: no whitespace errors; Event-default changes are limited to the four listed code/test files plus this plan. Pre-existing uncommitted Product files remain untouched.
