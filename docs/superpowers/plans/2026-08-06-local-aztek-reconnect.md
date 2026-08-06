# Local Aztek Reconnect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** เชื่อม Aztek แบบ Local ผ่าน `/init` กลาง และ reuse encrypted browser state เดิมเพื่อข้าม IPA เมื่อ SSO ยังใช้ได้

**Architecture:** เพิ่ม read path สำหรับถอดรหัส Aztek session เดิมได้ทั้งสถานะ active/expired โดยไม่เปลี่ยนสถานะ record แล้วส่ง state นี้เข้า `LocalAztekCaptureService.capture(seed_state)`. Capture ใช้ `/init` สำหรับเปิดและ probe; seeded context ยอมรับ authenticated page ได้ทันที ส่วน context ว่างยังต้องเห็น Login ก่อนเพื่อป้องกัน transient Aztek shell false-positive.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Playwright async API, pytest

## Global Constraints

- ไม่ถาม ไม่อ่าน และไม่เก็บรหัสผ่าน IPA/Aztek
- storage state ต้องอยู่แบบเข้ารหัสบนดิสก์ และถอดรหัสเฉพาะในหน่วยความจำ
- capture ล้มเหลวต้องไม่แทนหรือลบ session record เดิม
- `ตัดการเชื่อมต่อ` ยังลบ session record เหมือนเดิม
- ไม่เปลี่ยน Hosted mode หรือ bookmark pairing
- ยังไม่ build Setup หรือ push จนกว่าผู้ใช้จะสั่ง

---

### Task 1: Read Existing Session for Reconnect

**Files:**
- Modify: `web/aztek_sessions.py:292-306`
- Test: `tests/test_aztek_pairing.py`

**Interfaces:**
- Consumes: `AztekSessionService`, `AztekSession.encrypted_state`, `decrypt_storage_state`
- Produces: `AztekSessionService.load_storage_state_for_reconnect(db: Session, user: User) -> dict[str, Any] | None`

- [ ] **Step 1: Write the failing test**

```python
def test_expired_session_can_seed_local_reconnect(
        member, test_database, test_settings):
    service = AztekSessionService(test_settings)
    state = valid_storage_state()
    with test_database.session() as db:
        user = db.get(User, member.id)
        service.save_storage_state(db, member.id, state, 'old')
        service.mark_expired(db, user)
        assert service.load_storage_state(db, user) is None
        assert service.load_storage_state_for_reconnect(db, user) == state
```

- [ ] **Step 2: Run test to verify RED**

Run: `python -m pytest -q tests/test_aztek_pairing.py::test_expired_session_can_seed_local_reconnect`

Expected: FAIL because `load_storage_state_for_reconnect` does not exist.

- [ ] **Step 3: Implement the minimal read path**

```python
def load_storage_state_for_reconnect(
    self, db: Session, user: User
) -> dict[str, Any] | None:
    session = db.scalar(
        select(AztekSession).where(AztekSession.user_id == user.id)
    )
    if session is None:
        return None
    return decrypt_storage_state(session.encrypted_state, self.settings)
```

- [ ] **Step 4: Run focused service tests**

Run: `python -m pytest -q tests/test_aztek_pairing.py`

Expected: PASS.

- [ ] **Step 5: Commit the service boundary**

```powershell
git add -- web/aztek_sessions.py tests/test_aztek_pairing.py
git commit -m "feat(local): reuse encrypted Aztek session for reconnect"
```

### Task 2: Use Generic Init and Seeded Capture Context

**Files:**
- Modify: `web/local_aztek_capture.py:32-116`
- Test: `tests/test_local_aztek_capture.py`

**Interfaces:**
- Consumes: optional decrypted `seed_state: dict | None`
- Produces: `LocalAztekCaptureService.capture(seed_state: dict | None = None) -> dict`
- Produces: generic target URL `https://aztek-tools-v2.combo-interactive.com/init`

- [ ] **Step 1: Extend fakes and write failing boundary tests**

```python
AZTEK_INIT_URL = 'https://aztek-tools-v2.combo-interactive.com/init'

def test_capture_uses_game_neutral_init_for_login_and_probe(test_settings):
    page = FakePage([LOGIN_URL, AZTEK_INIT_URL], wait_urls=[AZTEK_INIT_URL])
    fake = FakePlaywright(page)
    run_capture(test_settings, fake)
    assert page.requested_urls == [AZTEK_INIT_URL, AZTEK_INIT_URL]

def test_seeded_authenticated_context_skips_login_page(test_settings):
    page = FakePage([AZTEK_INIT_URL, AZTEK_INIT_URL])
    fake = FakePlaywright(page)
    state = complete_storage_state()
    result = run_capture(test_settings, fake, seed_state=state)
    assert result == state
    assert fake.browser.new_context_calls == [
        {'no_viewport': True, 'storage_state': state}
    ]
```

Update `FakePage.goto()` to append the requested URL to `requested_urls`, update `FakeBrowser.new_context()` to append kwargs to `new_context_calls`, and update `run_capture(..., seed_state=None)` to call `service.capture(seed_state)`.

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m pytest -q tests/test_local_aztek_capture.py::test_capture_uses_game_neutral_init_for_login_and_probe tests/test_local_aztek_capture.py::test_seeded_authenticated_context_skips_login_page`

Expected: first assertion receives the game-specific URL; second test fails because `capture` has no seed argument and unconditionally requires a Login page.

- [ ] **Step 3: Implement generic init and seeded state**

```python
_AZTEK_INIT_URL = 'https://aztek-tools-v2.combo-interactive.com/init'

async def capture(self, seed_state: dict | None = None) -> dict:
    context = await browser.new_context(
        **browser_launch.context_kwargs(
            True, **({'storage_state': seed_state} if seed_state else {})
        )
    )
    await page.goto(self.target_url, ...)
    await self._wait_for_authenticated_app(
        page, allow_initial_authenticated=seed_state is not None
    )
```

Change `self.target_url` to `_AZTEK_INIT_URL`. Extend `_wait_for_authenticated_app(page, *, allow_initial_authenticated=False)` so a seeded authenticated page may return immediately, while an unseeded context still requires `saw_login_page` before accepting Aztek.

- [ ] **Step 4: Run all capture tests**

Run: `python -m pytest -q tests/test_local_aztek_capture.py`

Expected: PASS, including transient Aztek → IPA → Aztek and final-login rejection.

- [ ] **Step 5: Commit capture behavior**

```powershell
git add -- web/local_aztek_capture.py tests/test_local_aztek_capture.py
git commit -m "fix(local): connect Aztek through generic init"
```

### Task 3: Wire Reconnect State Through the Local API

**Files:**
- Modify: `web/app.py:677-730`
- Test: `tests/test_local_aztek_capture_api.py`

**Interfaces:**
- Consumes: `load_storage_state_for_reconnect(db, user)` from Task 1
- Consumes: `capture(seed_state)` from Task 2
- Produces: unchanged `POST /api/aztek/local-capture` response contract

- [ ] **Step 1: Write the failing API test**

```python
def test_local_capture_seeds_browser_with_expired_encrypted_session(
        test_settings, test_database):
    application = local_application(test_settings, test_database)
    client = signed_in_local_client(application)
    old_state = storage_state('old-sso-cookie')
    with test_database.session() as db:
        owner = db.scalar(select(User).where(User.username == 'local.owner'))
        application.state.aztek_session_service.save_storage_state(
            db, owner.id, old_state, 'old')
        application.state.aztek_session_service.mark_expired(db, owner)

    capture = SuccessfulCapture(storage_state('fresh-cookie'))
    application.state.local_aztek_capture = capture
    response = client.post('/api/aztek/local-capture')

    assert response.status_code == 200
    assert capture.seed_state == old_state
```

Change `SuccessfulCapture.capture(self, seed_state=None)` to record `self.seed_state` before returning the new state. Keep `FailingCapture` accepting the same optional argument.

- [ ] **Step 2: Run API test to verify RED**

Run: `python -m pytest -q tests/test_local_aztek_capture_api.py::test_local_capture_seeds_browser_with_expired_encrypted_session`

Expected: FAIL because the endpoint calls capture without the old state.

- [ ] **Step 3: Pass reconnect state into capture**

```python
seed_state = (
    request.app.state.aztek_session_service
    .load_storage_state_for_reconnect(db, user)
)
storage_state = await request.app.state.local_aztek_capture.capture(seed_state)
```

Do not save or mutate the old record until capture returns and `save_storage_state` validates the new state.

- [ ] **Step 4: Run Local capture API and UI tests**

Run: `python -m pytest -q tests/test_local_aztek_capture_api.py tests/test_web_account_ui.py`

Expected: PASS. If Chromium spawn is blocked by sandbox with `EPERM`, rerun the same command outside the sandbox.

- [ ] **Step 5: Commit API wiring**

```powershell
git add -- web/app.py tests/test_local_aztek_capture_api.py
git commit -m "feat(local): seed Aztek reconnect from saved session"
```

### Task 4: Full Verification

**Files:**
- Verify: `web/aztek_sessions.py`
- Verify: `web/local_aztek_capture.py`
- Verify: `web/app.py`
- Verify: `tests/test_aztek_pairing.py`
- Verify: `tests/test_local_aztek_capture.py`
- Verify: `tests/test_local_aztek_capture_api.py`

**Interfaces:**
- Consumes: all completed tasks
- Produces: verified source ready for a separately requested Setup/release

- [ ] **Step 1: Run focused regression suite**

Run: `python -m pytest -q tests/test_aztek_pairing.py tests/test_local_aztek_capture.py tests/test_local_aztek_capture_api.py tests/test_web_account_ui.py`

Expected: PASS.

- [ ] **Step 2: Run full suite**

Run: `python -m pytest -q tests`

Expected: PASS with no test failures. A `.pytest_cache` permission warning is environmental and does not change the exit code.

- [ ] **Step 3: Check the final diff and working tree**

Run: `git diff --check` and `git status --short --branch`.

Expected: no whitespace errors; only intended implementation/plan files or task commits are present.

- [ ] **Step 4: Report release boundary**

Report focused/full test counts and explicitly state that no Setup was built and nothing was pushed in this implementation run.
