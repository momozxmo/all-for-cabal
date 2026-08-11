# Event Warning Highlight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Highlight the imported-plan warning below the Event editor heading as a clearly visible, non-blocking general warning.

**Architecture:** Keep warning rendering and data flow unchanged. Add one Event-specific presentation class to the existing warning element and scope its CSS inside `events.html` so shared summaries and other pages are unaffected.

**Tech Stack:** Static HTML/CSS, pytest static UI contracts.

## Global Constraints

- Keep the existing warning text, icon, and `hidden` behavior.
- Use a translucent amber background, amber border, stronger amber left accent, and light amber text.
- Apply styling only to `#planWarnings` on the Event page.
- Do not change shared `.summary`, `.warning`, buttons, logs, or page layout.

---

### Task 1: Add the scoped Event warning highlight

**Files:**
- Modify: `tests/test_web_ui.py`
- Modify: `web/static/events.html`

**Interfaces:**
- Consumes: Existing `#planWarnings.summary.warning` element and JavaScript that sets its `hidden` property and text content.
- Produces: An additional `plan-warning-highlight` class and a scoped `.plan-warning-highlight` CSS rule.

- [x] **Step 1: Write the failing test**

Add this contract to `tests/test_web_ui.py`:

```python
def test_event_plan_warning_has_scoped_general_warning_highlight():
    assert 'id="planWarnings" class="summary warning plan-warning-highlight"' in EVENTS
    assert '.plan-warning-highlight{' in EVENTS
    assert 'border-left:4px solid var(--yellow)' in EVENTS
    assert 'background:rgba(242,182,75,.10)' in EVENTS
```

- [x] **Step 2: Run the test and verify RED**

Run:

```powershell
python -m pytest -q tests/test_web_ui.py::test_event_plan_warning_has_scoped_general_warning_highlight -p no:cacheprovider
```

Expected: FAIL because the Event warning does not yet have the dedicated class or visual rule.

- [x] **Step 3: Add the minimal scoped implementation**

In the page-specific `<style>` block in `web/static/events.html`, add:

```css
.plan-warning-highlight{
  border:1px solid rgba(242,182,75,.62);
  border-left:4px solid var(--yellow);
  background:rgba(242,182,75,.10);
  color:#ffe1a0;
  box-shadow:0 0 0 1px rgba(242,182,75,.06) inset;
}
```

Change the existing element to:

```html
<div id="planWarnings" class="summary warning plan-warning-highlight" hidden></div>
```

- [x] **Step 4: Run focused and related tests and verify GREEN**

Run:

```powershell
python -m pytest -q tests/test_web_ui.py::test_event_plan_warning_has_scoped_general_warning_highlight tests/test_web_calendar_ui.py -p no:cacheprovider
```

Expected: PASS, including the existing warning visibility test in `test_web_calendar_ui.py`.

- [x] **Step 5: Verify the final diff**

Run:

```powershell
git diff --check
git diff -- tests/test_web_ui.py web/static/events.html
```

Expected: only the regression test, Event-specific CSS rule, and the additional class are changed.
