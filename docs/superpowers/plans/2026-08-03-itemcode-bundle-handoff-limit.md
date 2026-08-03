# Item Code Bundle Handoff and Data-Driven Limit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve complete Item Code drafts through Bundle creation and add a data-driven, Aztek-compatible code-wide limit control.

**Architecture:** Extend the existing Item Code draft shape once, then carry it unchanged through the workspace API, Bundle page storage, Item Code queue, run API, and Aztek filler. Imported plan builders are the only place that infer whether an Item Code is finite; handoff and UI layers only preserve or edit that decision. Bundle matching uses the existing internal group key and applies one created Bundle ID to every reward set in the matching Item Code draft.

**Tech Stack:** Python 3, FastAPI, Pydantic v2, static HTML/CSS/JavaScript, Playwright browser tests, and pytest.

## Global Constraints

- A Bundle handoff must never enable `จำกัดจำนวน` by itself.
- A positive imported/calculated total enables the limit; a missing or invalid total leaves it disabled with blank counts.
- New manual drafts default to the current date at `00:00:00` in `Asia/Bangkok` and remain unlimited.
- Item Code type remains locked to `ALL`.
- Reward-level `จำกัดจำนวน Code` behavior remains unchanged.
- Do not create real Aztek Item Codes during verification.
- Do not build an installer, commit, push, or publish unless the user explicitly requests it later.

---

### Task 1: Derive code-wide limit fields in Item Code plan drafts

**Files:**
- Modify: `web/itemcode_plan.py:133-187`
- Test: `tests/test_web_itemcode_plan.py:76-156`

**Interfaces:**
- Consumes: existing numeric metadata `codes_per_set`, `set_count`, `total`, `code_count`, and `refill_limit`.
- Produces: every draft returned by `build_itemcodes` contains `limited: bool`, `quantity: str`, and `remaining: str`.

- [ ] **Step 1: Replace the old no-code-wide-count assertion with finite and unlimited cases**

Add these focused assertions in `tests/test_web_itemcode_plan.py`:

```python
def test_a_plan_with_a_calculable_total_limits_the_item_code():
    draft = _one(_event())
    assert draft['limited'] is True
    assert (draft['quantity'], draft['remaining']) == ('40', '40')


def test_a_plan_without_a_positive_total_leaves_the_item_code_unlimited():
    draft = _one(_event(codes_per_set='', set_count='', total=''))
    assert draft['limited'] is False
    assert (draft['quantity'], draft['remaining']) == ('', '')


def test_pride_uses_the_explicit_code_limit_at_item_level():
    draft = _one(_pride(unique_code=True, code_count='500'))
    assert draft['limited'] is True
    assert (draft['quantity'], draft['remaining']) == ('500', '500')
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_web_itemcode_plan.py -q -p no:cacheprovider -k "limits_the_item_code or leaves_the_item_code_unlimited or explicit_code_limit_at_item_level"
```

Expected: FAIL because code-wide fields are absent.

- [ ] **Step 3: Add the fields to both plan builders**

In `_from_event`, add the fields beside `uses_per_user`:

```python
    count = str(item_total) if item_total > 0 else ''
    return {
        'name_th': name,
        'name_en': name,
        'slug': _slug(name, game, notes),
        'uses_per_user': uses,
        'limited': bool(count),
        'quantity': count,
        'remaining': count,
        'start_time': start,
        'end_time': end,
        'rewards': rewards,
    }
```

In `_from_pride`, normalize the existing `limit` and insert the same three
fields beside `uses_per_user` in its existing return dictionary:

```python
    item_limit = limit if limit.isdigit() and int(limit) > 0 else ''
    # Keep the existing names, slug, window, and reward construction.
    # Add these fields to that existing dictionary:
    'limited': bool(item_limit),
    'quantity': item_limit,
    'remaining': item_limit,
```

Keep the existing reward construction and buffer rules exactly as they are.

- [ ] **Step 4: Run all Item Code plan tests**

Run:

```powershell
python -m pytest tests/test_web_itemcode_plan.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 5: Review checkpoint**

Inspect `git diff -- web/itemcode_plan.py tests/test_web_itemcode_plan.py` and
confirm no handoff, UI, Event, or Product code changed in this task. Do not
commit without a separate user instruction.

---

### Task 2: Accept, validate, and fill the code-wide limit on Aztek

**Files:**
- Modify: `web/app.py:87-108`
- Modify: `web/app.py:1735-1750`
- Modify: `web/itemcode_runner.py:37-65`
- Test: `tests/test_web_activity.py:120-220`
- Test: `tests/test_web_activity.py:381-396`

**Interfaces:**
- Consumes: draft fields `limited`, `quantity`, and `remaining` from the Local UI.
- Produces: cleaned runner jobs with the same fields and fills Aztek controls `is_limited`, `quantity`, and `remaining`.

- [ ] **Step 1: Add failing request-model and runner tests**

Add model assertions:

```python
def test_item_code_limit_defaults_to_unlimited():
    spec = ItemCodeRunRequest(game=GAME, itemcodes=[{}]).itemcodes[0]
    assert spec.limited is False
    assert (spec.quantity, spec.remaining) == ('', '')


def test_enabled_item_code_limit_requires_both_positive_counts(client):
    item = _itemcode(limited=True, quantity='', remaining='40')
    response = client.post('/api/itemcodes/run', json={
        'game': GAME, 'itemcodes': [item], 'do_save': False})
    assert response.status_code == 400
    assert 'จำนวนครั้งที่สามารถใช้งานได้' in response.json()['detail']
```

Add a runner test that monkeypatches `aztek_form.set_switch`,
`aztek_form.fill`, `aztek_form.select_by_options`, and
`aztek_form.set_datetime`, calls `_fill_header(...)` with:

```python
{
    'name_th': 'Finite', 'name_en': 'Finite', 'slug': 'finite',
    'uses_per_user': '1', 'limited': True,
    'quantity': '40', 'remaining': '40',
    'start_time': '2026-08-03 00:00:00',
    'end_time': '2026-08-31 22:59:59',
}
```

Assert the recorded calls include:

```python
('switch', 'จำกัดจำนวน', True)
('fill', 'input[name="quantity"]', '40')
('fill', 'input[name="remaining"]', '40')
```

Call it again with `limited=False` and assert neither top-level count selector
is filled.

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_web_activity.py -q -p no:cacheprovider -k "item_code_limit_defaults or fills_code_wide_limit"
```

Expected: FAIL because the request model and `_fill_header` omit these fields.

- [ ] **Step 3: Extend the request model and validate positive counts**

Add to `ItemCodeSpec`:

```python
    limited: bool = False
    quantity: str = Field(default='', max_length=12)
    remaining: str = Field(default='', max_length=12)
```

Add a required wrapper beside `_positive_digits`:

```python
def _required_positive_digits(value: str, label: str, where: str) -> str:
    cleaned = _positive_digits(value, label, where)
    if not cleaned:
        raise HTTPException(
            status_code=400, detail='%s ของ%s ห้ามว่าง' % (label, where))
    return cleaned
```

In `itemcodes_run`, normalize only enabled limits:

```python
        limited = bool(spec.limited)
        quantity = _required_positive_digits(spec.quantity, 'จำนวนครั้งที่สามารถใช้งานได้', where) \
            if limited else ''
        remaining = _required_positive_digits(spec.remaining, 'จำนวนคงเหลือ', where) \
            if limited else ''
```

Include those values in the job dictionary. Disabled limits must send empty
strings even if stale browser queue values exist.

- [ ] **Step 4: Fill the inspected Aztek v2 controls**

After filling the date range in `_fill_header`, add:

```python
        limited = bool(spec.get('limited'))
        await aztek_form.set_switch(page, 'จำกัดจำนวน', limited, self.log)
        if limited:
            await aztek_form.fill(
                page, 'input[name="quantity"]', spec.get('quantity') or '',
                self.log, 'จำนวนครั้งที่สามารถใช้งานได้')
            await aztek_form.fill(
                page, 'input[name="remaining"]', spec.get('remaining') or '',
                self.log, 'จำนวนคงเหลือ')
```

Do not change `_fill_reward` or its `จำกัดจำนวน Code` selector.

- [ ] **Step 5: Run request and runner regressions**

Run:

```powershell
python -m pytest tests/test_web_activity.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 6: Review checkpoint**

Inspect `git diff -- web/app.py web/itemcode_runner.py tests/test_web_activity.py`.
Confirm Item Code type remains `ALL`, disabled limits erase counts in cleaned
jobs, and reward-set limit selectors are unchanged. Do not commit.

---

### Task 3: Add the Local switch, Aztek layout, and Bangkok-midnight defaults

**Files:**
- Modify: `web/static/itemcodes.html:8-55`
- Modify: `web/static/itemcodes.html:100-140`
- Modify: `web/static/itemcodes.html:187-255`
- Modify: `web/static/itemcodes.html:491-520`
- Test: `tests/test_web_calendar_ui.py:250-380`

**Interfaces:**
- Consumes: queue-entry fields from Task 1 and manual/default entries.
- Produces: `jobFrom(entry)` serializes `limited`, `quantity`, and `remaining`.

- [ ] **Step 1: Add failing browser tests for defaults and layout**

Add a test that creates `blankCode('Fallback Name')` and asserts:

```python
entry = page.evaluate("blankCode('Fallback Name')")
assert entry['name_en'] == 'Fallback Name'
assert entry['limited'] is False
assert (entry['quantity'], entry['remaining']) == ('', '')
assert re.fullmatch(r'\d{4}-\d{2}-\d{2} 00:00:00', entry['start_time'])
```

Add a browser layout test that selects a draft, confirms `#itemLimitFields` is
hidden initially, clicks `#itemLimited`, and then verifies:

```python
assert page.locator('#itemLimitFields').is_visible()
assert page.locator('#itemLimitFields').evaluate(
    "el => getComputedStyle(el).gridTemplateColumns"
).count('px') == 2
assert page.locator('#itemQuantity').count() == 1
assert page.locator('#itemRemaining').count() == 1
```

Also assert that `addDrafts(...)` and `jobFrom(...)` preserve all three fields.

- [ ] **Step 2: Run the new UI tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_web_calendar_ui.py -q -p no:cacheprovider -k "itemcode_code_wide_limit or itemcode_blank_code_uses_midnight"
```

Expected: FAIL because the controls and fields do not exist.

- [ ] **Step 3: Add a Bangkok-midnight helper and queue fields**

Add a page-local helper:

```javascript
function bangkokMidnight() {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Bangkok', year: 'numeric', month: '2-digit', day: '2-digit'
  }).formatToParts(new Date()).filter(part => part.type !== 'literal')
    .map(part => [part.type, part.value]));
  return `${parts.year}-${parts.month}-${parts.day} 00:00:00`;
}
```

Change `blankCode(name)` to use:

```javascript
name_th: name || '',
name_en: name || '',
limited: false,
quantity: '',
remaining: '',
start_time: bangkokMidnight(),
```

Keep end time empty.

- [ ] **Step 4: Add the inspected Aztek-style settings controls**

Append this structure inside the settings panel after the date inputs:

```html
<label class="itemcode-limit-toggle full">
  <input id="itemLimited" type="checkbox"> จำกัดจำนวน
</label>
<div id="itemLimitFields" class="itemcode-limit-fields full" hidden>
  <label>จำนวนครั้งที่สามารถใช้งานได้ *
    <input id="itemQuantity" type="number" min="1" step="1">
  </label>
  <label>จำนวนคงเหลือ
    <input id="itemRemaining" type="number" min="1" step="1">
  </label>
</div>
```

Style `.itemcode-limit-fields` as a two-column grid with the existing field
gap and add `.itemcode-limit-fields[hidden]{display:none}` so the display rule
cannot override the native `hidden` state.

Bind the switch and inputs to the active queue entry, persist with
`queue.save()`, and update visibility whenever `select(key)` runs.

- [ ] **Step 5: Preserve limit fields through import and run payloads**

Add `limited`, `quantity`, and `remaining` to the fields copied by
`addDrafts(...)`. Add to `jobFrom(entry)`:

```javascript
limited: !!entry.limited,
quantity: entry.limited ? String(entry.quantity || '') : '',
remaining: entry.limited ? String(entry.remaining || '') : '',
```

- [ ] **Step 6: Run Item Code browser regressions**

Run:

```powershell
python -m pytest tests/test_web_calendar_ui.py -q -p no:cacheprovider -k "itemcode"
```

Expected: PASS.

- [ ] **Step 7: Review checkpoint**

Inspect `git diff -- web/static/itemcodes.html tests/test_web_calendar_ui.py`.
Confirm the count row is two columns at desktop width, hidden when disabled,
and manual end time is still blank. Do not commit.

---

### Task 4: Preserve complete drafts through Bundle creation

**Files:**
- Modify: `web/app.py:1068-1099`
- Modify: `web/static/index.html:588-591`
- Modify: `web/static/bundles.html:132-178`
- Modify: `web/static/bundles.html:230-255`
- Modify: `web/static/bundles.html:563-593`
- Modify: `web/static/itemcodes.html:405-438`
- Test: `tests/test_web_api.py:150-225`
- Test: `tests/test_web_calendar_ui.py:380-470`
- Test: `tests/test_web_ui.py:55-70`

**Interfaces:**
- Consumes: `itemcode_plan.build_itemcodes(group_meta, game, groups=group_keys)`.
- Produces: Bundle payload field `itemcode_drafts` and `applyBundleHandoff(payload)` on the Item Code page.

- [ ] **Step 1: Add failing API and static-contract tests**

Extend the existing bundle-preview API test for an `itemcode` workspace and
assert:

```python
body = response.json()
assert len(body['itemcode_drafts']) == 1
assert body['itemcode_drafts'][0]['group'] == expected_group_key
assert body['itemcode_drafts'][0]['name_en']
assert body['itemcode_drafts'][0]['start_time'].endswith('00:00:00')
```

In `tests/test_web_ui.py`, assert `itemcode_drafts` appears in the Item Finder
handoff, Bundle page state/storage, and `afc.codeHandoff` payload.

- [ ] **Step 2: Run the focused API/static tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_web_api.py tests/test_web_ui.py -q -p no:cacheprovider -k "bundle and itemcode"
```

Expected: FAIL because the bundle response carries only Event drafts.

- [ ] **Step 3: Add Item Code drafts to the bundle-preview response**

Import `itemcode_plan` in `bundle_preview` and calculate:

```python
    itemcode_drafts = itemcode_plan.build_itemcodes(
        workspace.group_meta, workspace.game, groups=group_keys
    ) if workspace.mode == 'itemcode' else []
```

Return it beside `event_drafts`. Add `itemcode_drafts` to the Item Finder
session handoff, Bundle page state, `localStorage`, and the final code handoff.

- [ ] **Step 4: Add a failing browser handoff test for a complete multi-set draft**

Call `applyBundleHandoff(...)` with one created row and a matching draft:

```javascript
{
  game: 'CabalPC TH',
  itemcode_drafts: [{
    group: 'group-a', name_th: 'Summer Prize', name_en: 'Summer Prize EN',
    slug: 'summer-prize-pcth', uses_per_user: '40',
    limited: true, quantity: '40', remaining: '40',
    start_time: '2026-08-03 00:00:00',
    end_time: '2026-08-31 23:59:59',
    rewards: [
      {name_th: 'Set 1', name_en: 'Set 1', bundle_id: ''},
      {name_th: 'Set 2', name_en: 'Set 2', bundle_id: ''}
    ]
  }],
  rows: [{group: 'group-a', group_key: 'group-a',
          name: 'Bundle A', bundle_id: '224184'}]
}
```

Assert the queue entry preserves every header field, limit field, both reward
sets, and that both rewards have Bundle ID `224184`.

Add a fallback case with no matching draft and assert both names use the bundle
name, start time is Bangkok midnight, and `limited` is false.

- [ ] **Step 5: Run the browser handoff test and verify it fails**

Run:

```powershell
python -m pytest tests/test_web_calendar_ui.py -q -p no:cacheprovider -k "itemcode_bundle_handoff"
```

Expected: FAIL because the current handoff creates a partial `blankCode` and
fills only one reward slot.

- [ ] **Step 6: Implement deterministic full-draft matching**

Refactor `drainHandoff()` into a testable `applyBundleHandoff(payload)` plus the
existing storage drain. For each row:

1. Match a draft by `draft.group === row.group_key`, falling back to
   `draft.group === row.group`.
2. If a matching queue entry already exists, use it; otherwise pass the draft
   through `addDrafts([draft], 'หน้าสร้าง Bundle', payload.game)`.
3. Fill `row.bundle_id` into every reward with an empty `bundle_id`.
4. If no draft matches, use `blankCode(row.name || row.group || '')`, generate
   the server-suffixed slug, and create one reward with the Bundle ID.
5. Save and select the first affected entry without duplicating a queue item.

Do not mutate the stored `payload.itemcode_drafts` objects directly; clone the
draft and reward dictionaries through the existing `blankCode`, `blankReward`,
and `Object.assign` construction path.

- [ ] **Step 7: Run handoff and existing Event regressions**

Run:

```powershell
python -m pytest tests/test_web_calendar_ui.py tests/test_web_api.py tests/test_web_ui.py -q -p no:cacheprovider -k "handoff or bundle or itemcode or event_drafts"
```

Expected: PASS, including existing Event group-key matching.

- [ ] **Step 8: Review checkpoint**

Inspect the diff for the five handoff files and three test files. Confirm Event
uses `event_drafts`, Item Code uses `itemcode_drafts`, and Product handoff is
unchanged. Do not commit.

---

### Task 5: Verify the complete behavior without publishing

**Files:**
- Verify: `web/itemcode_plan.py`
- Verify: `web/app.py`
- Verify: `web/itemcode_runner.py`
- Verify: `web/static/index.html`
- Verify: `web/static/bundles.html`
- Verify: `web/static/itemcodes.html`
- Verify: all modified tests and design documents

**Interfaces:**
- Consumes: all deliverables from Tasks 1-4.
- Produces: a verified working tree ready for the user's later Setup/commit/push instruction.

- [ ] **Step 1: Run the focused Item Code modules**

```powershell
python -m pytest tests/test_web_itemcode_plan.py tests/test_web_activity.py tests/test_web_calendar_ui.py tests/test_web_api.py tests/test_web_ui.py -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 2: Run the full suite in an isolated temporary directory**

```powershell
python -m pytest tests -q --basetemp C:\tmp\afc-itemcode-limit-verify -p no:cacheprovider
```

Expected: all tests PASS.

- [ ] **Step 3: Review scope and sensitive-file hygiene**

Run:

```powershell
git status --short
git diff --check
git diff --stat
```

Confirm the diff contains only source, tests, and the two approved planning
documents. Confirm there are no `.env` files, databases, profiles, cookies,
uploaded workbooks, screenshots, `dist/` outputs, or installers.

- [ ] **Step 4: Report without publishing**

Report the exact passing test count, the handoff behavior, limit inference
rule, Local layout, and Aztek selectors verified. Do not create a real record,
build Setup, commit, push, or publish a release.
