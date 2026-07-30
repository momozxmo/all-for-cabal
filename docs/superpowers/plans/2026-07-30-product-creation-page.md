# Product Creation Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a persistent Product queue from the Item Finder Shop workspace, match Product Category and Currency only against live Aztek options, and support safe fill-only review plus explicitly confirmed real creation.

**Architecture:** Enrich the existing Shop parser's `group_meta` with a backward-compatible `product_meta` block and convert it to UI drafts through a focused `web.product_plan` module. Reuse the existing persisted workspace/import-selection flow, add one Aztek-aligned Local Product page, and drive the live form through a dedicated `ProductBuilder` that extends the existing safe preview/create runner lifecycle.

**Tech Stack:** Python, FastAPI, Pydantic, SQLAlchemy JSON workspaces, openpyxl-backed workbook parsing, Playwright async API, vanilla HTML/CSS/JavaScript, localStorage, pytest, Playwright browser tests.

## Global Constraints

- Work in `C:\Users\koomo\Documents\Crazy\all for cabal\.worktrees\codex-web-auth` on branch `codex/local-windows-installer`.
- Preserve the existing `product` string in Shop `group_meta`; add Product fields only under `product_meta`.
- Item Finder and the direct Product fallback must use the existing persisted Shop workspace and sheet-selection endpoints.
- Detect Product blocks by normalized labels and structure, never fixed row/column coordinates or sheet-name allowlists.
- Copy the workbook Product Name into both Thai and English fields; do not translate automatically.
- Set Product start once to the current Bangkok date at `00:00:00`; preserve workbook End Date and End Time.
- Never hardcode Currency or Category names, IDs, slugs, or aliases.
- Auto-match a fetched option only when normalized matching produces exactly one result.
- Leave ambiguous Currency, Category, Bundle, date, and limit data visible and unresolved; never guess.
- Product images are explicitly selected local files. Do not scan workbook-adjacent paths or store image bytes/session data in localStorage.
- Fill-only mode operates on exactly one active Product and cannot submit.
- Real create requires selected rows, validation, and a second confirmation.
- Browser automation remains sequential under the existing one-browser-job behavior.
- Automated verification must not create a real Aztek Product.
- Do not deploy, publish a GitHub Release, or push a branch as part of this plan.
- Use TDD for every behavior: failing test, observed failure, minimal implementation, passing focused test, then commit.

## File Structure

- Modify `item_finder.py`
  - extract Product header metadata while the existing Shop parser identifies item tables.
- Create `web/product_plan.py`
  - convert persisted Product metadata to stable editable drafts and normalize limits/tags/dates.
- Modify `web/app.py`
  - Product models, page route, workspace draft API, option API, multipart run API, validation, and audit.
- Modify `web/activity_runner.py`
  - make the create URL overridable without changing Item Code/Event behavior.
- Create `web/product_runner.py`
  - Product create URL, read-only option harvesting, Product form filling, image upload, and save semantics.
- Create `web/static/products.html`
  - Product queue, sheet selection, shared-workspace handoff, Aztek-aligned editor, option cache/matching, execution modes, and results.
- Modify `web/static/index.html`
  - send the active Shop workspace to Product.
- Modify `web/static/bundles.html`
  - send created Bundle IDs and exact source group keys to Product.
- Modify `web/static/itemcodes.html`
  - add Product navigation.
- Modify `web/static/events.html`
  - add Product navigation.
- Modify `web/static/console.css`
  - Product layout, option status, language tabs, image controls, and responsive styling.
- Modify `docs/superpowers/specs/2026-07-30-product-creation-page-design.md`
  - record that direct Product import reuses `/api/import-plan` and `/api/import-plan/apply`.
- Create `tests/test_web_product_plan.py`
  - Product metadata-to-draft and workspace/API tests.
- Create `tests/test_web_product_runner.py`
  - read-only option fetching, selectors, form filling, images, preview, and save behavior.
- Create `tests/test_web_product_ui.py`
  - Playwright-visible queue, matching, cache, sheet picker, layout, handoff, and execution-mode tests.
- Modify `tests/test_pure.py`
  - Shop parser Product metadata regression tests.
- Modify `tests/test_web_activity.py`
  - overridable create URL and Product API safety tests.
- Modify `tests/test_web_ui.py`
  - static route/navigation/handoff contracts.

---

### Task 1: Extract Product Metadata During Shop Parsing

**Files:**
- Modify: `item_finder.py:552-625`
- Modify: `tests/test_pure.py:104-147`

**Interfaces:**
- Consumes: existing `_event_norm`, `_event_num`, `_shop_sheet_items(rows, sheet_title, skipped=None)`.
- Produces: `_shop_product_meta(header_rows, sheet_title, group, now=None) -> dict` and `group_meta["product_meta"]`.

- [ ] **Step 1: Write failing parser tests for shifted Promotion and Cash Shop blocks**

Add tests with labels deliberately placed in different columns:

```python
def test_shop_parser_keeps_product_header_metadata_without_fixed_columns():
    now = dt.datetime(2026, 7, 30, 19, 0, 0)
    rows = [
        ['', 'Main Shop', '', '', '', '', '', 'Future Coin', 6600],
        ['Bundle ID', 'Shop Label', '20% Off', 'Start Date', 46218,
         'Start Time', 'หลัง MA', 'Mystery Token', 66],
        [223553, 'Category', 'Highlight', 'End Date', 46233,
         'End Time', dt.time(7, 59)],
        ['', 'Product Name', '', 'Limited Orb x30+5'],
        ['', 'ItemKind', 'ItemIndex', 'ItemOption', 'DurationIndex',
         'Stackable', 'Itemmove', 'Item Name', 'Amt'],
        ['', 100, 200, 0, 0, 'No', 'No', 'Limited Orb x35', 1],
    ]

    items = item_finder._shop_sheet_items(
        rows, 'Promotion shifted', now=now)
    meta = items[0]['group_meta']['product_meta']

    assert meta['name'] == 'Limited Orb x30+5'
    assert meta['bundle_id'] == '223553'
    assert meta['category_label'] == 'Highlight'
    assert meta['shop_label'] == '20% Off'
    assert meta['start_at'] == '2026-07-30 00:00:00'
    assert meta['end_at'] == '2026-07-30 07:59:00'
    assert {p['source_label'] for p in meta['price_candidates']} >= {
        'Future Coin', 'Mystery Token'}
```

Add a second test whose `Product Name`, dates, Limit, Reset, and numeric
currency candidates use the Cash Shop column arrangement. Assert all items in
one table carry identical `product_meta` and preserve the existing string
`group_meta["product"]`.

- [ ] **Step 2: Run the focused tests and observe the signature/metadata failure**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests/test_pure.py -q
```

Expected: FAIL because `_shop_sheet_items` does not accept `now` and does not
produce `product_meta`.

- [ ] **Step 3: Add label-anchored metadata extraction**

Add a small set of structural label keys, not Currency/Category catalogs:

```python
_PRODUCT_LABELS = {
    'productname': 'name',
    'bundleid': 'bundle_id',
    'shoplabel': 'shop_label',
    'category': 'category_label',
    'enddate': 'end_date',
    'endtime': 'end_time',
    'limit': 'limit_text',
    'resetday': 'reset_day',
    'resettime': 'reset_time',
}


def _shop_product_meta(header_rows, sheet_title, group, now=None):
    now = now or dt.datetime.now(dt.timezone.utc).astimezone()
    values = {}
    candidates = []
    for row in header_rows:
        for index, raw in enumerate(row):
            label = _event_norm(raw)
            if label in _PRODUCT_LABELS:
                value = _next_filled(row, index + 1)
                if value not in (None, ''):
                    values[_PRODUCT_LABELS[label]] = value
            if isinstance(raw, str) and index + 1 < len(row):
                numeric = _shop_number(row[index + 1])
                if numeric is not None and label not in _PRODUCT_LABELS:
                    candidates.append({
                        'source_label': raw.strip(),
                        'sale_price': numeric,
                        'original_price': numeric,
                    })
    return {
        'source_sheet': sheet_title,
        'name': str(values.get('name') or group).strip(),
        'bundle_id': _event_num(values.get('bundle_id')),
        'category_label': str(values.get('category_label') or '').strip(),
        'shop_label': str(values.get('shop_label') or '').strip(),
        'start_at': now.strftime('%Y-%m-%d 00:00:00'),
        'end_at': _shop_end_at(values.get('end_date'), values.get('end_time')),
        'limit_text': str(values.get('limit_text') or '').strip(),
        'reset_day': str(values.get('reset_day') or '').strip(),
        'reset_time': _shop_time_text(values.get('reset_time')),
        'price_candidates': _dedupe_price_candidates(candidates),
    }
```

Use the existing 16-row header buffer immediately before each ItemKind table.
Pass `now` through `_shop_sheet_items`, attach one metadata dict to all rows in
that Product group, and keep the existing `product`, `is_shop`, and
`shop_sheet` keys.

Handle Excel dates/times conservatively:

- Excel serial/date/datetime values become Gregorian `YYYY-MM-DD`.
- a time value becomes `HH:mm:ss`;
- an unreadable End Date or End Time yields `end_at=''` and a source warning;
- an explicitly labelled normal/full price is used only when it maps to one
  unambiguous price candidate; otherwise every original price remains equal to
  its sale price.

- [ ] **Step 4: Run parser and existing Shop regressions**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests/test_pure.py tests/test_web_item_service.py -q
```

Expected: PASS, including RANDOM-rate and Bundle-name tests.

- [ ] **Step 5: Commit the parser unit**

```powershell
git add item_finder.py tests/test_pure.py
git commit -m "feat(product): preserve shop product metadata"
```

---

### Task 2: Build Stable Product Drafts From Persisted Metadata

**Files:**
- Create: `web/product_plan.py`
- Create: `tests/test_web_product_plan.py`

**Interfaces:**
- Consumes: `group_meta[group_key]["product_meta"]` from Task 1 and a selected game string.
- Produces: `build_products(group_meta, game) -> list[dict]` and `count_products(rows) -> int`.

- [ ] **Step 1: Write failing draft-mapping tests**

Create metadata fixtures and assert the approved transformations:

```python
NOW = dt.datetime(2026, 7, 30, 19, 0, 0)


def test_product_draft_uses_same_name_end_time_limits_and_tags():
    meta = {
        'g1': {
            'is_shop': True,
            'product_meta': {
                'source_sheet': 'Promotion 15.7',
                'name': 'Limited Orb x30+5',
                'bundle_id': '223553',
                'category_label': 'Highlight',
                'shop_label': '20% Off / ลด 20%',
                'start_at': '2026-07-30 00:00:00',
                'end_at': '2026-07-30 07:59:00',
                'limit_text': '10 ครั้ง/ไอดี',
                'reset_day': 'No Reset',
                'reset_time': '',
                'price_candidates': [{
                    'source_label': 'Future Coin',
                    'original_price': 6600,
                    'sale_price': 6600,
                }],
            },
        },
    }

    draft = product_plan.build_products(meta, 'CabalPC TH', now=NOW)[0]

    assert (draft['name_th'], draft['name_en']) == (
        'Limited Orb x30+5', 'Limited Orb x30+5')
    assert draft['end_at'] == '2026-07-30 07:59:00'
    assert draft['limit_type'] == 'PLAYER'
    assert draft['limit_quantity'] == '10'
    assert draft['limit_reset_interval_days'] == ''
    assert draft['tags'] == ['SALE']
    assert draft['prices'] == []
    assert draft['price_candidates'][0]['source_label'] == 'Future Coin'
```

Add focused tests for unlimited, Character, Everyday one-day reset, weekday
seven-day reset, ambiguous limit warnings, tag combinations, missing end date,
same-name copying, defaults, and source order.

- [ ] **Step 2: Run the new file and observe the missing module failure**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests/test_web_product_plan.py -q
```

Expected: collection FAIL because `web.product_plan` does not exist.

- [ ] **Step 3: Implement the pure draft builder**

Create these exact public functions:

```python
def build_products(group_meta: dict, game: str, now=None) -> list[dict]:
    drafts = []
    for group_key, meta in group_meta.items():
        product = (meta or {}).get('product_meta') or {}
        if not product:
            continue
        drafts.append(_draft_from_meta(
            str(group_key), meta or {}, product, game, now=now))
    return drafts


def count_products(rows: list[dict]) -> int:
    keys = set()
    for row in rows:
        meta = row.get('group_meta') or {}
        product = meta.get('product_meta') or {}
        sources = row.get('group_keys') or row.get('sources') or ()
        key = (meta.get('group_key') or product.get('source_group_key')
               or (sources[0] if sources else ''))
        if product and key:
            keys.add(str(key))
    return len(keys)
```

Each draft must have this stable shape:

```python
{
    'source_group_key': group_key,
    'source_sheet': source_sheet,
    'name_th': name,
    'name_en': name,
    'category_source': category_label,
    'category_id': '',
    'category_label': '',
    'details_th': '',
    'details_en': '',
    'start_at': start_at,
    'end_at': end_at,
    'bundle_id': bundle_id,
    'bundle_source': 'workbook' if bundle_id else '',
    'price_candidates': price_candidates,
    'prices': [],
    'limit_type': 'UNLIMITED' | 'PLAYER' | 'CHARACTER',
    'limit_quantity': quantity,
    'limit_reset_interval_days': interval,
    'limit_reset_at': reset_at,
    'tags': tags,
    'is_enabled': False,
    'is_test_mode': True,
    'is_hidden': False,
    'position': '0',
    'warnings': warnings,
}
```

Keep parsing helpers private and deterministic:

- `_limit_fields(meta)`;
- `_tag_values(shop_label)`;
- `_reset_at(reset_day, reset_time, now)`;
- `_clean_prices(raw)`.

- [ ] **Step 4: Run the draft tests**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests/test_web_product_plan.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the draft unit**

```powershell
git add web/product_plan.py tests/test_web_product_plan.py
git commit -m "feat(product): build drafts from shared plan"
```

---

### Task 3: Expose Product Drafts Through the Existing Workspace Flow

**Files:**
- Modify: `web/app.py:785-873,925-981`
- Modify: `tests/test_web_product_plan.py`
- Modify: `tests/test_web_ownership.py`
- Modify: `docs/superpowers/specs/2026-07-30-product-creation-page-design.md`

**Interfaces:**
- Consumes: `product_plan.build_products` and `product_plan.count_products`.
- Produces: `GET /api/workspaces/{workspace_id}/products` and
  `sheets[].product_count` on `/api/import-plan`.

- [ ] **Step 1: Write failing ownership and response tests**

Add:

```python
def test_workspace_products_are_owned_and_keep_the_selected_game(
        client, test_database, workspace_for_member):
    with test_database.session() as db:
        record = db.get(WorkspaceRecord, workspace_for_member.id)
        record.game = 'CabalPC TH'
        record.group_meta = {'g1': {
            'is_shop': True,
            'product_meta': {
                'source_sheet': 'Promotion 15.7',
                'name': 'Orb Pack',
                'start_at': '2026-07-30 00:00:00',
                'end_at': '2026-08-30 07:59:00',
            },
        }}

    response = client.get(
        f'/api/workspaces/{workspace_for_member.id}/products')

    assert response.status_code == 200
    assert response.json()['game'] == 'CabalPC TH'
    assert response.json()['products'][0]['source_group_key'] == 'g1'
```

Assert anonymous access is `401`, another owner receives `404`, and a workspace
with no Product metadata returns an empty `products` list rather than opening a
browser.

Monkeypatch the Shop parser in `/api/import-plan` and assert:

```python
assert body['sheets'] == [{
    'name': 'Promotion 15.7',
    'count': 2,
    'product_count': 1,
}]
```

- [ ] **Step 2: Run the focused API tests and observe 404/missing-field failures**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests/test_web_product_plan.py tests/test_web_ownership.py -q
```

Expected: FAIL because the Product workspace route and `product_count` do not
exist.

- [ ] **Step 3: Add the route and enrich the existing import response**

Add:

```python
@router.get('/api/workspaces/{workspace_id}/products')
def workspace_products(
    workspace_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    from web import product_plan

    workspace = _get_workspace(
        WorkspaceRepository(db), user.id, workspace_id)
    return {
        'products': product_plan.build_products(
            workspace.group_meta, workspace.game or ''),
        'game': workspace.game or '',
        'workspace_id': workspace.id,
    }
```

Change only the `/api/import-plan` sheet summary:

```python
'sheets': [
    {
        'name': name,
        'count': len(rows),
        'product_count': product_plan.count_products(rows),
    }
    for name, rows in sheets
],
```

Import `product_plan` locally inside the handler to preserve the current light
module import behavior.

Update the approved spec's endpoint list so the direct Product fallback
explicitly reuses `/api/import-plan` and `/api/import-plan/apply`; do not add a
duplicate `/api/products/import`.

- [ ] **Step 4: Run API, workspace, and import tests**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests/test_web_product_plan.py tests/test_web_api.py tests/test_web_ownership.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the shared-workspace API**

```powershell
git add web/app.py tests/test_web_product_plan.py tests/test_web_ownership.py docs/superpowers/specs/2026-07-30-product-creation-page-design.md
git commit -m "feat(product): expose shared workspace drafts"
```

---

### Task 4: Add the Product Route, Navigation, and Persistent Queue Shell

**Files:**
- Create: `web/static/products.html`
- Modify: `web/app.py:373-423`
- Modify: `web/static/index.html:429-632`
- Modify: `web/static/bundles.html:12-105`
- Modify: `web/static/itemcodes.html:66-95`
- Modify: `web/static/events.html:64-92`
- Modify: `web/static/console.css`
- Modify: `tests/test_web_ui.py`
- Create: `tests/test_web_product_ui.py`

**Interfaces:**
- Consumes: `GET /api/workspaces/{workspace_id}/products`.
- Produces: `/products`, `afc.productQueue.v1`, `loadWorkspaceProducts(id)`,
  and Item Finder's `btnToProduct`.

- [ ] **Step 1: Write failing static and visible queue tests**

Static contract:

```python
PRODUCTS = open(
    os.path.join(ROOT, 'web', 'static', 'products.html'),
    encoding='utf-8').read()


def test_product_page_is_a_session_checked_tool_with_shared_workspace_handoff():
    assert 'id="productQueue"' in PRODUCTS
    assert 'afc.productQueue.v1' in PRODUCTS
    assert '/api/workspaces/' in PRODUCTS
    assert 'id="btnToProduct"' in HTML
    for page in (HTML, BUNDLES, ITEMCODES, EVENTS, PRODUCTS):
        assert 'href="/products"' in page or 'id="btnToProduct"' in page
```

Browser test:

```python
def test_product_queue_loads_workspace_drafts_once_and_survives_reload():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, PRODUCTS)
        page.evaluate("""addDrafts([
          {source_group_key:'g1', source_sheet:'Promotion 15.7',
           name_th:'Orb Pack', name_en:'Orb Pack'}
        ], 'workspace-1')""")
        page.reload()
        assert page.evaluate("productQueue.items.length") == 1
        assert page.evaluate("productQueue.items[0].source_group_key") == 'g1'
        browser.close()
```

- [ ] **Step 2: Run the static/UI tests and observe missing-file failures**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests/test_web_ui.py tests/test_web_product_ui.py -q
```

Expected: FAIL because `products.html`, `/products`, and navigation do not
exist.

- [ ] **Step 3: Add the authenticated page route and minimal queue**

Add:

```python
@router.get('/products', response_class=HTMLResponse)
def products_page(
    request: Request,
    afc_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    return _tool_page(request, afc_session, db, 'products.html')
```

In `products.html`, reuse `console.css` and `console.js`. Define:

```javascript
const PRODUCT_QUEUE_KEY = 'afc.productQueue.v1';
const PRODUCT_WORKSPACE_KEY = 'afc.productWorkspace';
const productQueue = new Queue(PRODUCT_QUEUE_KEY);
productQueue.load();
productQueue.active = productQueue.items[0]?.key || '';

function identityOf(entry) {
  return `${entry.workspace_id || ''}:${entry.source_group_key || ''}`;
}

function addDrafts(drafts, workspaceId) {
  const existing = new Map(productQueue.items.map(
    row => [identityOf(row), row]));
  for (const source of drafts || []) {
    const draft = structuredClone(source);
    draft.key = draft.key || nextKey('p');
    draft.workspace_id = workspaceId || draft.workspace_id || '';
    const old = existing.get(identityOf(draft));
    if (!old) productQueue.add(draft);
  }
  productQueue.save();
  renderQueue();
}

async function loadWorkspaceProducts(workspaceId) {
  const response = await apiFetch(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/products`);
  addDrafts(response.products || [], response.workspace_id || workspaceId);
  localStorage.setItem(PRODUCT_WORKSPACE_KEY, workspaceId);
}
```

On load, use the `workspace` query parameter first, then the remembered active
workspace ID. Add the Product navigation node as step 5 to every workflow page.

In Item Finder, show `btnToProduct` only in Shop mode and navigate with the
active workspace ID and selected game. Do not serialize all Product drafts
through sessionStorage.

- [ ] **Step 4: Run the page/auth/queue tests**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests/test_web_ui.py tests/test_web_product_ui.py tests/test_web_auth.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the Product page shell**

```powershell
git add web/app.py web/static/index.html web/static/bundles.html web/static/itemcodes.html web/static/events.html web/static/products.html web/static/console.css tests/test_web_ui.py tests/test_web_product_ui.py
git commit -m "feat(product): add shared-plan queue page"
```

---

### Task 5: Fetch Currency and Category Options Read-Only

**Files:**
- Create: `web/product_runner.py`
- Modify: `web/app.py`
- Create: `tests/test_web_product_runner.py`
- Modify: `tests/test_web_activity.py`

**Interfaces:**
- Produces: `product_create_url(game) -> str`,
  `fetch_options(game, storage_state, kinds) -> dict[str, list[dict]]`, and
  `POST /api/products/options`.
- Option shape: `{"id": str, "slug": str, "label": str}`.

- [ ] **Step 1: Write failing URL, option extraction, and API-gate tests**

Add:

```python
def test_product_create_url_is_under_shop():
    assert product_runner.product_create_url('CabalM TH').endswith(
        '/combo/cabalm/shop/products/create')


def test_option_rows_keep_live_value_slug_and_label():
    rows = product_runner._clean_option_rows([
        {'value': '17', 'text': 'ankh-coin - Ankh Coin'},
        {'value': '18', 'text': 'future-token - Future Token'},
        {'value': '', 'text': 'เลือกสกุลเงิน'},
    ])
    assert rows == [
        {'id': '17', 'slug': 'ankh-coin', 'label': 'Ankh Coin'},
        {'id': '18', 'slug': 'future-token', 'label': 'Future Token'},
    ]
```

API assertions:

- anonymous request returns `401`;
- unknown game returns `400`;
- missing Aztek session returns `409`;
- `kinds=["currencies"]` does not fetch Category;
- returned values come from a monkeypatched `fetch_options`, not constants.

- [ ] **Step 2: Run the focused tests and observe missing module/route failures**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests/test_web_product_runner.py tests/test_web_activity.py -q
```

Expected: FAIL because the runner and route do not exist.

- [ ] **Step 3: Implement read-only live option harvesting**

Create:

```python
OPTION_KINDS = frozenset({'currencies', 'categories'})


def product_create_url(game):
    return to_web_url(core.build_url(game, 'shop/products/create'))


async def _read_options(select):
    rows = await select.locator('option').evaluate_all(
        """nodes => nodes.map(node => ({
          value: node.value || '',
          text: (node.textContent || '').trim()
        }))""")
    return _clean_option_rows(rows)


async def fetch_options(game, storage_state, kinds):
    wanted = set(kinds) & OPTION_KINDS
    url = product_create_url(game)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            **browser_launch.launch_kwargs(False))
        context = await browser.new_context(
            **browser_launch.context_kwargs(
                False, storage_state=storage_state))
        page = await context.new_page()
        try:
            await page.goto(
                url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(2500)
            if any(part in page.url.lower()
                   for part in ('/login', '/signin')):
                raise RuntimeError('Aztek session expired')
            return await _harvest_product_options(page, wanted)
        finally:
            await context.close()
            await browser.close()
```

The Product page is a Radix-style UI over real selects. Locate Category by its
Thai label and the following select. For Currency, add one local price row only
when needed to reveal its select, read options, and leave without submitting:

```python
category = page.locator(
    'xpath=//label[contains(normalize-space(.),"หมวดหมู่")]'
    '/following::select[1]').first
currency = page.locator(
    'input[name="prices.0.original_price"]'
    '/ancestor::*[.//select][1] select').first
```

If no currency row exists, click the Product form's add-currency button, wait
for `prices.0.original_price`, then read. Option harvesting must never call
`ProductBuilder._save`.

- [ ] **Step 4: Add the request model and endpoint**

```python
class ProductOptionsRequest(BaseModel):
    game: str = Field(min_length=1, max_length=64)
    kinds: list[Literal['currencies', 'categories']] = Field(
        default_factory=lambda: ['currencies', 'categories'])


@router.post('/api/products/options')
async def product_options(
    payload: ProductOptionsRequest,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    from web import product_runner

    if payload.game not in item_finder.GAMES:
        raise HTTPException(status_code=400, detail='ไม่รู้จักเกม')
    kinds = list(dict.fromkeys(payload.kinds))
    storage_state = (
        request.app.state.aztek_session_service
        .load_storage_state(db, user)
    )
    if storage_state is None:
        raise HTTPException(
            status_code=409, detail='ยังไม่ได้เชื่อมเซสชัน Aztek')
    try:
        options = await product_runner.fetch_options(
            payload.game, storage_state, kinds)
    except Exception as exc:
        write_audit(
            db, user_id=user.id, action='product.options',
            status='failed',
            summary={'game': payload.game, 'error': str(exc)[:200]},
            tool='create_product', resource_type='aztek_session',
            resource_id=user.id, request=request)
        raise HTTPException(
            status_code=502,
            detail='ดึงตัวเลือก Product ไม่สำเร็จ: %s' % exc)
    counts = {kind: len(options.get(kind) or ()) for kind in kinds}
    write_audit(
        db, user_id=user.id, action='product.options',
        status='success',
        summary={'game': payload.game, 'counts': counts},
        tool='create_product', resource_type='aztek_session',
        resource_id=user.id, request=request)
    return {'options': options}
```

Validate the game, deduplicate `kinds`, load the user's paired Aztek session,
call `fetch_options`, and write an audit entry with counts only. Do not audit
the option payload or session state.

- [ ] **Step 5: Run the option tests**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests/test_web_product_runner.py tests/test_web_activity.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit the read-only options unit**

```powershell
git add web/product_runner.py web/app.py tests/test_web_product_runner.py tests/test_web_activity.py
git commit -m "feat(product): fetch live product options"
```

---

### Task 6: Add Dynamic Matching and Per-Server Option Cache

**Files:**
- Modify: `web/static/products.html`
- Modify: `web/static/console.css`
- Modify: `tests/test_web_product_ui.py`

**Interfaces:**
- Consumes: `POST /api/products/options`.
- Produces: `normalizeOptionText`, `matchFetchedOption`,
  `optionCacheKey(game, kind)`, `ensureOptions(kind, refresh=false)`, and
  `applyOptionMatches(entry)`.

- [ ] **Step 1: Write failing browser tests for future currencies and ambiguity**

```python
def test_future_currency_matches_fetched_data_without_a_catalog():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, PRODUCTS)
        matched = page.evaluate("""matchFetchedOption(
          ' Future Token ',
          [{id:'91', slug:'future-token', label:'Future Token'}]
        )""")
        assert matched == {
            'id': '91', 'slug': 'future-token', 'label': 'Future Token'}
        assert 'THB' not in page.content()
        assert 'Forcegem' not in page.content()
        browser.close()


def test_ambiguous_option_is_not_selected():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, PRODUCTS)
        assert page.evaluate("""matchFetchedOption(
          'coin',
          [{id:'1',slug:'coin',label:'Coin'},
           {id:'2',slug:'coin',label:'Coin'}]
        )""") is None
        browser.close()
```

Add cache tests that Currency and Category have separate versioned keys per
server, reload reuses cached options, explicit refresh calls the API again, and
a refresh failure retains the last good cached data.

- [ ] **Step 2: Run the Product UI tests and observe missing-function failures**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests/test_web_product_ui.py -q
```

Expected: FAIL because matching/cache functions do not exist.

- [ ] **Step 3: Implement normalization, exact unique matching, and cache**

```javascript
function normalizeOptionText(value) {
  return String(value || '')
    .normalize('NFKC')
    .toLocaleLowerCase()
    .replace(/[\s_\-–—:/()[\].]+/g, '');
}

function matchFetchedOption(source, options) {
  const wanted = normalizeOptionText(source);
  if (!wanted) return null;
  const hits = (options || []).filter(option =>
    [option.id, option.slug, option.label].some(
      value => normalizeOptionText(value) === wanted));
  return hits.length === 1 ? structuredClone(hits[0]) : null;
}

function optionCacheKey(game, kind) {
  return `afc.productOptions.v1:${game}:${kind}`;
}
```

`ensureOptions` loads localStorage first, otherwise POSTs only the missing kind.
Refresh bypasses the cache. Store:

```javascript
{fetched_at: new Date().toISOString(), options: response[kind] || []}
```

`applyOptionMatches(entry)`:

- matches `category_source` to fetched Categories;
- matches every unresolved `price_candidate.source_label` to fetched Currency;
- creates a price row only for one unique live option;
- preserves unmatched source labels and values for operator review;
- never introduces a predefined Currency/Category value.

- [ ] **Step 4: Render matched and unresolved states**

Add separate Currency and Category refresh buttons, fetched timestamp, loading
state, last-good refresh warning, and unresolved source chips. A manual option
selection updates the draft with the fetched `id`, `slug`, and `label`.

- [ ] **Step 5: Run matching/cache tests**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests/test_web_product_ui.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit dynamic matching**

```powershell
git add web/static/products.html web/static/console.css tests/test_web_product_ui.py
git commit -m "feat(product): match cached live options"
```

---

### Task 7: Build the Aztek-Aligned Editor, Sheet Picker, and Bundle Reconciliation

**Files:**
- Modify: `web/static/products.html`
- Modify: `web/static/bundles.html`
- Modify: `web/static/console.css`
- Modify: `tests/test_web_product_ui.py`
- Modify: `tests/test_web_ui.py`

**Interfaces:**
- Consumes: Product drafts, existing `/api/import-plan`,
  `/api/import-plan/apply`, and Bundle result rows.
- Produces: `jobFrom(entry)`, `applyBundleHandoff(payload)`,
  `importPlanFile(file)`, `applySelectedSheets()`, and complete Product editor
  state.

- [ ] **Step 1: Write failing visible layout and workflow tests**

Cover:

```python
def test_product_editor_matches_aztek_columns_and_collapses():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, PRODUCTS)
        page.set_viewport_size({'width': 1500, 'height': 1000})
        desktop = page.evaluate("""() => {
          const box = key => document.querySelector(
            `[data-product-section="${key}"]`).getBoundingClientRect();
          const general = box('general'), display = box('display');
          return {generalRight: general.right, displayLeft: display.left};
        }""")
        page.set_viewport_size({'width': 800, 'height': 1000})
        mobile = page.evaluate("""() => {
          const box = key => document.querySelector(
            `[data-product-section="${key}"]`).getBoundingClientRect();
          const general = box('general'), currency = box('currency');
          const display = box('display');
          return {generalLeft: general.left, generalTop: general.top,
                  currencyTop: currency.top, displayLeft: display.left,
                  displayTop: display.top};
        }""")
        assert desktop['displayLeft'] > desktop['generalRight']
        assert abs(mobile['generalLeft'] - mobile['displayLeft']) < 1
        assert mobile['generalTop'] < mobile['currencyTop'] < mobile['displayTop']
        browser.close()


def test_only_the_selected_execution_mode_button_is_visible():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser, PRODUCTS)
        page.locator('#runModePreview').check()
        assert page.locator('#btnPreview').is_visible()
        assert not page.locator('#btnCreateSelected').is_visible()
        page.locator('#runModeCreate').check()
        assert not page.locator('#btnPreview').is_visible()
        assert page.locator('#btnCreateSelected').is_visible()
        browser.close()
```

Also assert:

- multiple candidate sheets render checkboxes with Product counts;
- applying sheets calls the existing import apply endpoint then workspace
  Product endpoint;
- details/image language tabs keep both language values;
- file bytes are absent from localStorage;
- exact `source_group_key` fills the matching Bundle ID;
- conflicting workbook/created Bundle IDs show a conflict and overwrite
  neither;
- an unresolved Bundle renders a numeric manual input;
- deleting the active workspace calls the existing DELETE endpoint and removes
  only queue entries with that `workspace_id`.

- [ ] **Step 2: Run Product UI tests and observe layout/control failures**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests/test_web_product_ui.py tests/test_web_ui.py -q
```

Expected: FAIL because the complete editor and handoff behavior are absent.

- [ ] **Step 3: Add the two-column Product editor**

Use data attributes for visible regression tests:

```html
<section data-product-section="general"><div id="generalFields"></div></section>
<section data-product-section="details"><div id="detailTabs"></div></section>
<section data-product-section="images"><div id="imageTabs"></div></section>
<section data-product-section="currency"><div id="priceRows"></div></section>
<section data-product-section="bundle"><div id="bundlePicker"></div></section>
<section data-product-section="display"><div id="displayFields"></div></section>
<section data-product-section="selling-period"><div id="sellingPeriod"></div></section>
<section data-product-section="purchase-limit"><div id="purchaseLimit"></div></section>
<section data-product-section="tags"><div id="tagFields"></div></section>
```

Left column order: general, details, images, currency, bundle. Right column
order: display, selling period, purchase limit, tags. Add Thai/English tabs for
details and images, repeatable Currency rows, all approved defaults, the Local
24-hour date picker, and a sticky action bar. Collapse at `1100px`.

Keep file objects in memory only:

```javascript
const productFiles = new Map();

function rememberImage(entryKey, slot, file) {
  const row = productFiles.get(entryKey) || {};
  row[slot] = file || null;
  productFiles.set(entryKey, row);
  renderImageNames();
}
```

On reload, show "เลือกไฟล์ใหม่ก่อนส่ง" for any saved filename because browsers
cannot restore a file handle.

- [ ] **Step 4: Reuse the existing direct-import sheet selection**

`importPlanFile(file)` POSTs:

```javascript
const form = new FormData();
form.append('file', file);
form.append('mode', 'shop');
form.append('workspace_id', activeWorkspaceId || '');
const pending = await apiFetch('/api/import-plan', {
  method: 'POST', body: form
});
```

Render every returned sheet; use `product_count` in its label. On confirmation:

```javascript
await apiFetch('/api/import-plan/apply', {
  method: 'POST',
  body: JSON.stringify({
    pending_id: pending.pending_id,
    selected_sheets: checkedSheetNames
  })
});
await loadWorkspaceProducts(pending.workspace_id);
```

- [ ] **Step 5: Reconcile Bundle results by exact source key**

Extend Bundle result handoff with:

```javascript
sessionStorage.setItem('afc.productBundleHandoff', JSON.stringify({
  game: $('game').value,
  workspace_id: activeWorkspaceId,
  rows: createdRows.map(row => ({
    source_group_key: row.group_key,
    bundle_id: row.bundle_id,
    name: row.name
  }))
}));
```

`applyBundleHandoff` matches only exact non-empty source keys. Empty draft IDs
accept the created ID. Equal IDs remain unchanged. Different non-empty IDs set:

```javascript
entry.bundle_conflict = {
  workbook_id: entry.bundle_id,
  created_id: row.bundle_id
};
```

The operator must choose one before validation passes.

- [ ] **Step 6: Run editor, import, and handoff tests**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests/test_web_product_ui.py tests/test_web_ui.py tests/test_web_calendar_ui.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit the complete Local editor**

```powershell
git add web/static/products.html web/static/bundles.html web/static/console.css tests/test_web_product_ui.py tests/test_web_ui.py
git commit -m "feat(product): add aztek-aligned editor"
```

---

### Task 8: Fill the Live Product Form Without Saving

**Files:**
- Modify: `web/activity_runner.py:20-36,130-220`
- Modify: `web/product_runner.py`
- Modify: `web/aztek_form.py`
- Modify: `tests/test_web_product_runner.py`
- Modify: `tests/test_web_activity.py`

**Interfaces:**
- Consumes: a cleaned Product job plus optional in-memory image payloads.
- Produces: `ProductBuilder(ActivityBuilder)`, overridable
  `ActivityBuilder.create_url(game)`, and `fill_form(page, spec) -> list[str]`.

- [ ] **Step 1: Write failing runner safety and field tests**

Assert URL override does not move Item Code/Event:

```python
def test_activity_builder_uses_an_overridable_create_url():
    builder = product_runner.ProductBuilder(lambda *_: None)
    assert builder.create_url(GAME).endswith('/shop/products/create')
    assert itemcode_runner.ItemCodeBuilder(
        lambda *_: None).create_url(GAME).endswith('/itemcodes/create')
```

Use fake locators to assert `fill_form` addresses:

- `th_name` and `en_name`;
- fetched Category `id`;
- details only when non-empty;
- one Currency select and both `prices.0.original_price` and
  `prices.0.price`;
- `show_at` and `hide_at`;
- enabled/test/hidden switches and position;
- purchase-limit type/quantity/reset fields;
- tags;
- Bundle picker by exact ID;
- four image slots when explicitly supplied;
- missing Category, Currency, Bundle, date, or name appears in `missing`;
- no save call occurs during `run`.

- [ ] **Step 2: Run runner tests and observe missing URL/filler failures**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests/test_web_product_runner.py tests/test_web_activity.py -q
```

Expected: FAIL because `ActivityBuilder.create_url` and `ProductBuilder` are
absent.

- [ ] **Step 3: Make ActivityBuilder's URL overridable**

Add:

```python
class ActivityBuilder:
    def create_url(self, game):
        return create_url(game, self.PATH)
```

Insert this method next to the existing `log`/fill helpers without removing the
class's current methods. Replace both `create_url(game, self.PATH)` calls in
`run` and `run_many` with
`self.create_url(game)`. Keep the module-level function for existing callers
and tests.

- [ ] **Step 4: Implement ProductBuilder and stable field helpers**

```python
class ProductBuilder(ActivityBuilder):
    PATH = 'products'
    SAVE_LABEL = 'สร้าง Product'
    KIND = 'Product'
    WRITE_MARK = 'product'

    def create_url(self, game):
        return product_create_url(game)

    async def fill_form(self, page, spec):
        missing = []
        await self._fill_general(page, spec, missing)
        await self._fill_details(page, spec)
        await self._fill_images(page, spec, missing)
        await self._fill_prices(page, spec, missing)
        await self._fill_display(page, spec, missing)
        await self._fill_limit(page, spec, missing)
        await self._fill_tags(page, spec)
        await self._fill_bundle(page, spec, missing)
        return missing
```

Add `aztek_form.select_after_label(page, label, value, log=None)` for hidden
selects associated with a visible label. Currency rows are scoped from
`input[name="prices.{index}.original_price"]` to their nearest ancestor
containing a select. Add rows by clicking the add-currency button and waiting
for that indexed input.

Details use the visible TinyMCE iframe after switching the Thai/English tab:

```python
frame = page.locator('iframe.tox-edit-area__iframe:visible').first
body = frame.content_frame.locator('body')
await body.fill(value)
```

Images use Playwright memory payloads:

```python
await file_input.set_input_files({
    'name': image['name'],
    'mimeType': image['content_type'],
    'buffer': image['bytes'],
})
```

Never derive a filesystem path from the workbook or uploaded filename.

Use `aztek_form.set_datetime` for `show_at` and `hide_at`. Use exact fetched
Category/Currency IDs supplied by the job. Tags are clicked only from the
approved five values present in the job. Bundle uses
`aztek_form.pick_bundle(page, page, bundle_id, self.log)`.

- [ ] **Step 5: Run runner and existing activity tests**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests/test_web_product_runner.py tests/test_web_activity.py -q
```

Expected: PASS with existing Item Code/Event runner tests unchanged.

- [ ] **Step 6: Commit the fill-only runner**

```powershell
git add web/activity_runner.py web/product_runner.py web/aztek_form.py tests/test_web_product_runner.py tests/test_web_activity.py
git commit -m "feat(product): fill live product form safely"
```

---

### Task 9: Add Validated Multipart Preview/Create API and Result UI

**Files:**
- Modify: `web/app.py`
- Modify: `web/static/products.html`
- Modify: `tests/test_web_product_runner.py`
- Modify: `tests/test_web_product_ui.py`
- Modify: `tests/test_web_activity.py`

**Interfaces:**
- Consumes: `ProductBuilder` and `productFiles`.
- Produces: `ProductSpec`, `ProductPriceSpec`, `ProductRunRequest`,
  `POST /api/products/run`, `submitProducts(entries, doSave)`, and per-row
  Product IDs.

- [ ] **Step 1: Write failing request validation and safety tests**

Define a valid test payload:

```python
def _product(**extra):
    spec = {
        'client_key': 'p1',
        'source_group_key': 'g1',
        'name_th': 'Orb Pack',
        'name_en': 'Orb Pack',
        'category_id': '12',
        'category_label': 'Highlight',
        'start_at': '2026-07-30 00:00:00',
        'end_at': '2026-08-30 07:59:00',
        'bundle_id': '223553',
        'prices': [{
            'currency_id': '91',
            'currency_slug': 'future-token',
            'currency_label': 'Future Token',
            'original_price': 6600,
            'price': 6600,
        }],
        'limit_type': 'PLAYER',
        'limit_quantity': '10',
        'limit_reset_interval_days': '',
        'limit_reset_at': '',
        'tags': ['SALE'],
    }
    spec.update(extra)
    return spec
```

Assert:

- `do_save` defaults false;
- preview rejects more than one Product;
- empty queue, unknown game, missing paired session, missing names, Category,
  Currency, Bundle, or dates are rejected before a browser opens;
- end before start is rejected;
- negative/non-numeric price is rejected;
- non-unlimited limit requires a positive quantity;
- unsupported image type or image larger than 10 MiB is rejected;
- image form keys for unknown `client_key` are rejected;
- preview calls `builder.run` and cannot call `_save`;
- real create calls `builder.run_many`, continues per-entry failures, and
  returns created/planned counts plus `made_id`;
- audit entries contain Product name/result/ID but no image bytes or option
  catalogs.

- [ ] **Step 2: Run API tests and observe missing model/route failures**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests/test_web_product_runner.py tests/test_web_activity.py -q
```

Expected: FAIL because `/api/products/run` and Product request models do not
exist.

- [ ] **Step 3: Add Product request models and cleaners**

```python
class ProductPriceSpec(BaseModel):
    currency_id: str = Field(min_length=1, max_length=120)
    currency_slug: str = Field(default='', max_length=160)
    currency_label: str = Field(default='', max_length=200)
    original_price: float = Field(ge=0)
    price: float = Field(ge=0)


class ProductSpec(BaseModel):
    client_key: str = Field(min_length=1, max_length=80)
    source_group_key: str = Field(default='', max_length=240)
    name_th: str = Field(min_length=1, max_length=200)
    name_en: str = Field(min_length=1, max_length=200)
    category_id: str = Field(min_length=1, max_length=120)
    category_label: str = Field(default='', max_length=200)
    details_th: str = Field(default='', max_length=20000)
    details_en: str = Field(default='', max_length=20000)
    start_at: str = Field(min_length=1, max_length=32)
    end_at: str = Field(min_length=1, max_length=32)
    bundle_id: str = Field(min_length=1, max_length=32)
    prices: list[ProductPriceSpec] = Field(min_length=1, max_length=20)
    limit_type: Literal['UNLIMITED', 'PLAYER', 'CHARACTER'] = 'UNLIMITED'
    limit_quantity: str = Field(default='', max_length=12)
    limit_reset_interval_days: str = Field(default='', max_length=12)
    limit_reset_at: str = Field(default='', max_length=32)
    tags: list[Literal['EVENT', 'HOT', 'LIMITED', 'NEW', 'SALE']] = \
        Field(default_factory=list, max_length=5)
    is_enabled: bool = False
    is_test_mode: bool = True
    is_hidden: bool = False
    position: str = Field(default='0', max_length=12)


class ProductRunRequest(BaseModel):
    game: str = Field(min_length=1, max_length=64)
    products: list[ProductSpec] = Field(default_factory=list, max_length=30)
    do_save: bool = False
```

The endpoint receives `payload` as JSON text in multipart form, validates with
`ProductRunRequest.model_validate_json(payload)`, reads dynamic image fields
from `await request.form()`, and attaches only validated in-memory payloads:

```python
IMAGE_KEY = re.compile(
    r'^image__(?P<client>[A-Za-z0-9_-]{1,80})__'
    r'(?P<slot>thumb_th|banner_th|thumb_en|banner_en)$')
ALLOWED_IMAGE_TYPES = {
    'image/png', 'image/jpeg', 'image/webp', 'image/gif'}
MAX_PRODUCT_IMAGE_BYTES = 10 * 1024 * 1024
```

No temporary image path is persisted.

- [ ] **Step 4: Add the run endpoint using the existing safe lifecycle**

Clean dates with `_require_datetime`/`_require_order`, digits-only Bundle ID,
unique Currency IDs, positive limit quantities, and numeric position. Call
`_prepare` so preview remains one-at-a-time. Use `_run_activity` with
`ProductBuilder`, tool `create_product`, and actions
`product.preview_open`/`product.create`.

Return:

```python
{
    'results': results,
    'logs': logs,
    'headed': headed,
    'screenshot_b64': screenshot_b64,
    'created': created,
    'planned': planned,
}
```

- [ ] **Step 5: Send multipart jobs and render results in the Product page**

```javascript
async function submitProducts(entries, doSave) {
  const payload = {
    game: $('game').value,
    products: entries.map(jobFrom),
    do_save: !!doSave
  };
  const form = new FormData();
  form.append('payload', JSON.stringify(payload));
  for (const entry of entries) {
    const files = productFiles.get(entry.key) || {};
    for (const [slot, file] of Object.entries(files)) {
      if (file) form.append(`image__${entry.key}__${slot}`, file, file.name);
    }
  }
  return apiFetch('/api/products/run', {method: 'POST', body: form});
}
```

Preview sends only the active entry. Real create sends checked entries after:

```javascript
confirm(`สร้างจริงบน Aztek ${entries.length} Product ใช่ไหม?`)
```

Update queue status and `product_id` from each result's `made_id`. Retry sends
only entries whose last run failed or has no Product ID.

- [ ] **Step 6: Run API and visible result tests**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests/test_web_product_runner.py tests/test_web_product_ui.py tests/test_web_activity.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit the preview/create workflow**

```powershell
git add web/app.py web/static/products.html tests/test_web_product_runner.py tests/test_web_product_ui.py tests/test_web_activity.py
git commit -m "feat(product): validate and run product creation"
```

---

### Task 10: Complete Regression, Visual, and Standalone Verification

**Files:**
- Modify if required by failing checks: only Product-related files from Tasks 1-9.
- Update runtime snapshot files under:
  `C:\Users\koomo\Documents\Crazy\all for cabal web`
  after the canonical worktree passes.

**Interfaces:**
- Consumes: all Product parser, API, UI, options, and runner units.
- Produces: verified canonical source and synchronized standalone Local source.

- [ ] **Step 1: Run all focused Product and adjacent regressions**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests/test_pure.py tests/test_web_product_plan.py tests/test_web_product_runner.py tests/test_web_product_ui.py tests/test_web_activity.py tests/test_web_ui.py tests/test_web_calendar_ui.py tests/test_web_item_service.py tests/test_web_api.py tests/test_web_ownership.py -q
```

Expected: PASS.

- [ ] **Step 2: Run the complete canonical suite**

Run:

```powershell
& "C:\Users\koomo\Documents\Crazy\all for cabal web\.venv\Scripts\python.exe" -m pytest tests -q
```

Expected: PASS with no real Aztek Product created.

- [ ] **Step 3: Perform visual browser verification**

Start the Local app from the canonical worktree and verify at desktop and
800px widths:

- Product is step 5 in every navigation bar;
- shared workspace reload produces no duplicate Product;
- multiple candidate sheets remain selectable;
- left/right Product section order matches the inspected Aztek page;
- Currency and Category source warnings are visible and selectable;
- Currency matching works with a test-only fetched future option;
- Bundle conflict and manual numeric fallback are visible;
- only one execution-mode button is visible;
- date fields use a space, never `T`;
- selected image filenames are visible but not restored after reload;
- preview/fill stops before Create Product.

Do not select real-create mode during live visual verification.

- [ ] **Step 4: Synchronize only changed runtime/test files to the standalone folder**

Copy the exact changed application files from the canonical worktree into the
matching relative paths under:

`C:\Users\koomo\Documents\Crazy\all for cabal web`

Do not copy:

- `.git` or worktree metadata;
- `.env`, databases, uploads, browser profiles, cookies, tokens, or imported
  workbooks;
- `.codex-tmp`, caches, build, dist, or release artifacts;
- design/plan documents unless the standalone README links them.

Use explicit file paths and preserve the standalone `.venv`.

- [ ] **Step 5: Run the standalone Product and full suites**

Run from `C:\Users\koomo\Documents\Crazy\all for cabal web`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_web_product_plan.py tests/test_web_product_runner.py tests/test_web_product_ui.py -q
.\.venv\Scripts\python.exe -m pytest tests -q
```

Expected: both commands PASS without importing from the original checkout.

- [ ] **Step 6: Check source control scope and commit verification-only fixes**

Run:

```powershell
git status --short
git diff --check
git log --oneline -10
```

If verification required a Product-scoped fix, stage its source and regression
test together and commit:

```powershell
git add item_finder.py web/app.py web/activity_runner.py web/aztek_form.py web/product_plan.py web/product_runner.py web/static/products.html web/static/index.html web/static/bundles.html web/static/itemcodes.html web/static/events.html web/static/console.css tests/test_pure.py tests/test_web_product_plan.py tests/test_web_product_runner.py tests/test_web_product_ui.py tests/test_web_activity.py tests/test_web_ui.py
git commit -m "fix(product): address verification regression"
```

If no fix was required, do not create an empty commit.

- [ ] **Step 7: Request code review before any push or release**

Use `superpowers:requesting-code-review`, report:

- every commit created by Tasks 1-9;
- focused and full canonical test results;
- focused and full standalone test results;
- confirmation that live verification used fill-only mode;
- any known Aztek selector risk that can only be checked during an operator
  preview.

Do not push or publish until the user explicitly requests it.
