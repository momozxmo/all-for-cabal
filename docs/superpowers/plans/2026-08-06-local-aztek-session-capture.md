# Local Aztek Full-Session Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace incomplete Local bookmark pairing with a visible Chromium login flow that stores complete Aztek/IPA Playwright state, including HttpOnly cookies.

**Architecture:** Add one app-wide async browser gate, a testable local capture service, and a shared `AztekSessionService.save_storage_state` persistence boundary. Local account UI calls a loopback-only endpoint; hosted mode retains the existing bookmark/token flow for a future extension.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Playwright async API, pytest, Playwright sync browser UI tests, vanilla HTML/JavaScript.

## Global Constraints

- Local direct capture is available only when `LOCAL_DESKTOP_MODE=true` and the request comes from loopback.
- Credentials are entered only into the real IPA/Aztek page and are never stored or logged.
- Failed, closed, timed-out, or still-logged-out capture attempts must not overwrite an existing session.
- No real Aztek record creation or real login is performed by automated tests.
- Hosted mode retains bookmark pairing and returns `404` from the local-capture endpoint.
- Do not build Setup, commit implementation files, or push until the user explicitly requests it.
- Preserve all pre-existing uncommitted Product and Event changes.

---

### Task 1: Shared Browser Operation Gate

**Files:**
- Create: `web/browser_gate.py`
- Modify: `web/search_coordinator.py:56-67,242-282`
- Modify: `web/app.py:1114-1180,1420-1510,1611-1650,1930-1960`
- Test: `tests/test_browser_gate.py`

**Interfaces:**
- Produces: `BrowserOperationGate(limit: int)` and `async with gate.slot(): ...`.
- Produces: `SearchCoordinator(..., browser_gate: BrowserOperationGate | None = None)`.
- Consumes later: `LocalAztekCaptureService(..., browser_gate=gate)`.

- [ ] **Step 1: Write a failing gate serialization test**

```python
@pytest.mark.asyncio
async def test_one_slot_does_not_overlap_browser_operations():
    gate = BrowserOperationGate(1)
    first_entered = asyncio.Event()
    release_first = asyncio.Event()
    order = []

    async def first():
        async with gate.slot():
            order.append('first-enter')
            first_entered.set()
            await release_first.wait()
            order.append('first-exit')

    async def second():
        await first_entered.wait()
        async with gate.slot():
            order.append('second-enter')

    one = asyncio.create_task(first())
    two = asyncio.create_task(second())
    await first_entered.wait()
    await asyncio.sleep(0)
    assert order == ['first-enter']
    release_first.set()
    await asyncio.gather(one, two)
    assert order == ['first-enter', 'first-exit', 'second-enter']
```

- [ ] **Step 2: Run the test and confirm RED**

Run: `pytest -q tests/test_browser_gate.py`

Expected: collection/import failure because `web.browser_gate` does not exist.

- [ ] **Step 3: Implement the minimal gate**

```python
class BrowserOperationGate:
    def __init__(self, limit: int = 1) -> None:
        self._semaphore = asyncio.Semaphore(max(1, limit))

    @asynccontextmanager
    async def slot(self):
        async with self._semaphore:
            yield
```

Create one gate in `create_app`, pass it into `SearchCoordinator`, replace the coordinator's private semaphore acquire/release with `async with self._browser_gate.slot()`, and wrap every route-level browser launch (`reward_options`, `product_options`, Bundle run, `_run_activity`) in the same gate.

- [ ] **Step 4: Run gate and coordinator tests and confirm GREEN**

Run: `pytest -q tests/test_browser_gate.py tests/test_web_search_auth.py tests/test_web_api.py`

Expected: all selected tests pass.

- [ ] **Step 5: Review only this task's diff**

Run: `git diff --check -- web/browser_gate.py web/search_coordinator.py web/app.py tests/test_browser_gate.py`

Expected: exit code 0. Do not commit.

---

### Task 2: Shared Encrypted Session Persistence

**Files:**
- Modify: `web/aztek_sessions.py:148-218`
- Modify: `tests/test_aztek_pairing.py`

**Interfaces:**
- Produces: `AztekSessionService.save_storage_state(db, user_id, storage_state, account_label=None) -> AztekSession`.
- Preserves: pairing tokens are marked used only after storage succeeds.
- Consumes later: local capture endpoint calls `save_storage_state` after live validation.

- [ ] **Step 1: Write failing persistence behavior tests**

```python
def test_save_storage_state_reactivates_and_replaces_one_user_session(
        member, test_database, test_settings):
    service = AztekSessionService(test_settings)
    first = valid_storage_state()
    second = valid_storage_state()
    second['cookies'][0]['value'] = 'replacement-http-only-cookie'
    with test_database.session() as db:
        service.save_storage_state(db, member.id, first, 'old')
        service.mark_expired(db, member.id)
        saved = service.save_storage_state(db, member.id, second, 'local')
        assert saved.status == 'active'
        assert saved.account_label == 'local'
    with test_database.session() as db:
        rows = db.scalars(select(AztekSession).where(
            AztekSession.user_id == member.id)).all()
        assert len(rows) == 1
        assert decrypt_storage_state(rows[0].encrypted_state, test_settings) == second
```

Add a second test that submits invalid storage through `consume_pairing_token`, asserts `InvalidStorageState`, and asserts the corresponding `PairingToken.status` remains `pending`.

- [ ] **Step 2: Run the tests and confirm RED**

Run: `pytest -q tests/test_aztek_pairing.py -k "save_storage_state or invalid_storage_keeps_pairing_token_pending"`

Expected: failure because `save_storage_state` does not exist.

- [ ] **Step 3: Extract minimal shared persistence**

```python
def save_storage_state(self, db, user_id, storage_state, account_label=None):
    validate_storage_state(storage_state, self.settings)
    ciphertext = encrypt_storage_state(storage_state, self.settings)
    session = db.scalar(select(AztekSession).where(
        AztekSession.user_id == user_id))
    clean_label = (account_label or '').strip() or None
    if session is None:
        session = AztekSession(
            user_id=user_id, encrypted_state=ciphertext,
            account_label=clean_label, status='active')
        db.add(session)
    else:
        session.encrypted_state = ciphertext
        session.account_label = clean_label
        session.status = 'active'
        session.last_validated_at = None
    db.flush()
    return session
```

Update `consume_pairing_token` to validate the token first, call this method, then mark the token used. Do not change response schemas or encryption.

- [ ] **Step 4: Run pairing tests and confirm GREEN**

Run: `pytest -q tests/test_aztek_pairing.py`

Expected: all pairing and storage tests pass.

- [ ] **Step 5: Review only this task's diff**

Run: `git diff --check -- web/aztek_sessions.py tests/test_aztek_pairing.py`

Expected: exit code 0. Do not commit.

---

### Task 3: Testable Local Chromium Capture Service

**Files:**
- Create: `web/local_aztek_capture.py`
- Create: `tests/test_local_aztek_capture.py`

**Interfaces:**
- Produces: `LocalAztekCaptureService(settings, browser_gate, playwright_factory=async_playwright)`.
- Produces: `await service.capture() -> dict` containing validated Playwright storage state.
- Produces: `LocalCaptureClosed`, `LocalCaptureTimeout`, and `LocalCaptureLoginRequired` exceptions.

- [ ] **Step 1: Write failing success and failure tests with a fake Playwright boundary**

The fake context must mirror Playwright methods used by production: async context manager, `chromium.launch`, `browser.new_context`, `context.new_page`, `page.goto`, `page.wait_for_timeout`, `page.is_closed`, `page.url`, `page.evaluate`, `context.storage_state`, and close methods.

```python
@pytest.mark.asyncio
async def test_capture_returns_complete_http_only_state_after_live_app_check(local_settings):
    state = valid_storage_state_with_http_only_cookie()
    fake = FakePlaywright(page_urls=[LOGIN_URL, AZTEK_ITEMS_URL], state=state)
    service = LocalAztekCaptureService(
        local_settings, BrowserOperationGate(1), playwright_factory=lambda: fake)
    assert await service.capture() == state
    assert fake.context.closed is True
    assert fake.browser.closed is True
```

Add separate tests for closed window, timeout, and a final validation that returns to login. Each asserts the precise exception and cleanup.

- [ ] **Step 2: Run capture tests and confirm RED**

Run: `pytest -q tests/test_local_aztek_capture.py`

Expected: collection/import failure because the service does not exist.

- [ ] **Step 3: Implement the smallest capture loop**

Use the existing Windows-safe `browser_launch.launch_kwargs(True)` and `context_kwargs(True)`. Open the v2 form URL derived from `search_runner.to_web_url(item_finder.GAMES[item_finder.GAME_NAMES[0]])`, wait at most 300 seconds, require an HTTPS `aztek-tools*.combo-interactive.com` page with no visible password/login route, repeat one final navigation in the same context, then return `context.storage_state()`.

Always close context/browser in `finally`. Never use a persistent Chrome profile, access normal Chrome cookies, log storage state, or accept credentials.

- [ ] **Step 4: Run capture tests and confirm GREEN**

Run: `pytest -q tests/test_local_aztek_capture.py`

Expected: all success, close, timeout, validation, and cleanup tests pass.

- [ ] **Step 5: Review only this task's diff**

Run: `git diff --check -- web/local_aztek_capture.py tests/test_local_aztek_capture.py`

Expected: exit code 0. Do not commit.

---

### Task 4: Loopback-only Capture API

**Files:**
- Modify: `web/app.py:659-727,1930-1960`
- Create: `tests/test_local_aztek_capture_api.py`

**Interfaces:**
- Adds: `POST /api/aztek/local-capture`.
- Success response: `{'status': 'connected', 'account_label': 'Local Chromium'}`.
- Hosted/non-loopback response: HTTP `404` before browser capture starts.
- Capture failure response: HTTP `409` with a Thai actionable message.

- [ ] **Step 1: Write failing endpoint tests**

```python
def test_local_capture_endpoint_saves_complete_state(local_client, application, monkeypatch):
    state = valid_storage_state_with_http_only_cookie()
    async def capture():
        return state
    monkeypatch.setattr(application.state.local_aztek_capture, 'capture', capture)
    response = local_client.post('/api/aztek/local-capture')
    assert response.status_code == 200
    assert response.json() == {
        'status': 'connected', 'account_label': 'Local Chromium'}
    assert local_client.get('/api/aztek/status').json()['status'] == 'active'
```

Add hosted and non-loopback tests whose fake capture raises if invoked, plus a failure test that first stores an old session and verifies its encrypted state is unchanged after a capture exception.

- [ ] **Step 2: Run endpoint tests and confirm RED**

Run: `pytest -q tests/test_local_aztek_capture_api.py`

Expected: local route returns 404 because it is not registered.

- [ ] **Step 3: Add the route and application service**

Construct the capture service in `create_app` with the shared browser gate. In the route, check `local_access.enabled_for(_client_host(request))` before invoking capture; on success call `save_storage_state(db, user.id, state, 'Local Chromium')`; audit only result/reason class; translate close/timeout/login errors to Thai HTTP 409 responses; and never include state or cookies in any response/audit.

- [ ] **Step 4: Run endpoint tests and confirm GREEN**

Run: `pytest -q tests/test_local_aztek_capture_api.py tests/test_local_access.py tests/test_aztek_pairing.py`

Expected: all selected tests pass.

- [ ] **Step 5: Review only this task's diff**

Run: `git diff --check -- web/app.py tests/test_local_aztek_capture_api.py`

Expected: exit code 0. Do not commit.

---

### Task 5: Local Account UI and Hosted Fallback

**Files:**
- Modify: `web/static/account.html`
- Modify: `tests/test_web_calendar_ui.py:106-123`
- Create: `tests/test_web_account_ui.py`

**Interfaces:**
- Local primary control: `#localCaptureButton`.
- Local-only container: `[data-local-aztek]`.
- Hosted pairing containers: `[data-hosted-aztek]`.
- Button calls `POST /api/aztek/local-capture`, shows waiting/result in `#aztekMessage`, and refreshes `/api/aztek/status`.

- [ ] **Step 1: Write failing browser-visible UI tests**

Serve the real account HTML through Playwright routing. Return `local_mode: true` from `/api/auth/me`, an inactive status first, and a successful capture/status response after the button click.

Assert that local mode visibly shows `#localCaptureButton`, hides `#bookmarklet`, `#createPairingButton`, `#openAztekLink`, and `#pairingBox`, disables the button during the pending request, displays the waiting text, then displays success and refreshes status. Add a hosted-mode test asserting the inverse visibility and that no local capture request occurs.

- [ ] **Step 2: Run UI tests and confirm RED**

Run: `pytest -q tests/test_web_account_ui.py tests/test_web_calendar_ui.py -k "account or local_capture"`

Expected: failure because `#localCaptureButton` and runtime visibility groups do not exist.

- [ ] **Step 3: Implement minimal UI behavior**

Group all bookmark instructions/actions/token box under `data-hosted-aztek`, add a hidden `data-local-aztek` block with the direct button and short Thai instruction, and extend `applyRuntimeMode` to toggle both groups. Add one click handler using the existing `errorMessage` and `loadAztekStatus` helpers.

Do not remove hosted bookmark code; it remains dormant in Local mode and available when deployed.

- [ ] **Step 4: Run UI and static contract tests and confirm GREEN**

Run: `pytest -q tests/test_web_account_ui.py tests/test_web_calendar_ui.py tests/test_web_ui.py`

Expected: all selected tests pass with the new local/hosted visibility contract.

- [ ] **Step 5: Review only this task's diff**

Run: `git diff --check -- web/static/account.html tests/test_web_account_ui.py tests/test_web_calendar_ui.py`

Expected: exit code 0. Do not commit.

---

### Task 6: Regression and Safety Verification

**Files:**
- Verify all files changed in Tasks 1-5.

**Interfaces:**
- No new interface; this task proves the approved design end to end without real Aztek actions.

- [ ] **Step 1: Run focused authentication/capture/browser tests**

Run: `pytest -q tests/test_browser_gate.py tests/test_local_aztek_capture.py tests/test_local_aztek_capture_api.py tests/test_aztek_pairing.py tests/test_web_search_auth.py tests/test_web_account_ui.py`

Expected: zero failures.

- [ ] **Step 2: Run the complete suite**

Run: `pytest -q`

Expected: zero failures.

- [ ] **Step 3: Inspect scope and secrets**

Run: `git diff --check`

Run: `git status --short`

Confirm no `.env`, database, browser profile, cookies, token, uploaded workbook, `dist/`, installer, or unrelated generated artifact was added. Confirm pre-existing Product/Event modifications remain present and uncommitted.

- [ ] **Step 4: Report without committing or pushing**

Report the focused/full test counts, the files changed, the Local-versus-Hosted behavior, and that no Setup/commit/push was performed.
