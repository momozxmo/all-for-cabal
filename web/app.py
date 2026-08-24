# -*- coding: utf-8 -*-
"""All for Cabal Web — local Item Finder application."""
import asyncio
import hashlib
import hmac
import json
import os
import re
import sys
import tempfile
import threading
import time
import warnings
from collections.abc import Callable
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Literal

from fastapi import (APIRouter, Cookie, Depends, FastAPI, File, Form,
                     HTTPException, Request, Response, UploadFile, WebSocket,
                     WebSocketDisconnect)
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                               RedirectResponse)
from pydantic import (BaseModel, Field, StrictBool, StrictStr,
                      ValidationError)
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import item_finder  # noqa: E402
from web import aztek_form, aztek_sessions as pairing_service  # noqa: E402
from web import item_service, search_runner  # noqa: E402
from web.audit import write_audit  # noqa: E402
from web.auth_service import AuthService  # noqa: E402
from web.aztek_sessions import (AztekSessionService, InvalidStorageState,  # noqa: E402
                                PairingTokenIssueConflict,
                                PairingTokenNotFound, PairingTokenUnavailable)
from web.browser_gate import BrowserOperationGate  # noqa: E402
from web.db import Database  # noqa: E402
from web.local_access import LocalAccessService  # noqa: E402
from web.local_aztek_capture import (LocalAztekCaptureService,  # noqa: E402
                                     LocalCaptureClosed,
                                     LocalCaptureLoginRequired,
                                     LocalCaptureTimeout)
from web.models import Job, User, utc_now  # noqa: E402
from web.pairing_http import (PairingIssueReservations, PairingParseResult,  # noqa: E402
                              PairingPrincipalSnapshot, StorageStatePayload,
                              pairing_parse_dependency,
                              resolve_pairing_principal)
from web.request_limits import RequestSizeLimitMiddleware, WORKBOOK_BODY_MAX  # noqa: E402
from web.search_coordinator import SearchCoordinator  # noqa: E402
from web.security import hash_password, verify_password  # noqa: E402
from web.settings import Settings  # noqa: E402
from web.validation import (PayloadValueError, non_negative_int_text,  # noqa: E402
                            optional_text, plain_decimal_text,
                            positive_int_text, strict_bool)
from web.workspaces import (DuplicateSheetSelection, EmptySheetSelection,
                            PendingImportNotFound, UnknownSheetSelection,
                            WorkspaceBusy, WorkspaceNotFound,
                            WorkspaceRepository,
                            is_sqlite_busy)  # noqa: E402


router = APIRouter()
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
# Retained for compatibility with legacy callers; handlers never use it as data.
WORKSPACES = item_service.WorkspaceStore()
Mode = Literal['event', 'itemcode', 'shop']


class _JsonNumberLexeme:
    __slots__ = ('text',)

    def __init__(self, text: str) -> None:
        self.text = text


class ApplyPlanRequest(BaseModel):
    pending_id: str
    selected_sheets: list[str]


class BundleRequest(BaseModel):
    selected_indexes: list[int] = Field(default_factory=list)
    source_group_key: str = Field(default='', max_length=240)


class BundleSpec(BaseModel):
    """One bundle as the operator built it on the Create Bundle page.

    Items are whatever they typed, pasted or sent over from Item Finder — the
    page is a tool in its own right, so nothing here is tied to a search.
    """
    client_key: StrictStr = Field(default='', max_length=80)
    name: str = Field(default='', max_length=200)
    bundle_type: Literal['FIXED', 'CHOICE', 'RANDOM'] = 'FIXED'
    deliver: StrictBool = True
    # [{id, qty, tier, rate}] — id is the only required part.
    items: list[dict] = Field(default_factory=list)
    # Rewards are per bundle, not per run: two bundles in the same batch rarely
    # hand out the same currency.
    rewards: list[dict] = Field(default_factory=list)


class BundleRunRequest(BaseModel):
    game: str = Field(min_length=1, max_length=64)
    bundles: list[BundleSpec] = Field(default_factory=list)
    # Off by default: bundles are only written on an explicit opt-in, so a
    # replayed or malformed preview request can never reach the live site.
    # A preview takes exactly one bundle; a create takes the whole queue.
    do_save: StrictBool = False


class ItemCodeSpec(BaseModel):
    """One Item Code as the operator filled it in.

    ``rewards`` is a list of sets: each carries its own codes and exactly one
    bundle, because v2 replaces a reward set's bundle rather than adding to it.

    The type is not a field: an Item Code is always ALL. Descriptions are left
    to the page defaults. The code-wide limit is separate from the limit on
    each reward set and is filled only when imported data or the operator
    enables it.
    """
    client_key: StrictStr = Field(default='', max_length=80)
    name_th: str = Field(default='', max_length=200)
    name_en: str = Field(default='', max_length=200)
    slug: str = Field(default='', max_length=120)
    uses_per_user: object = '1'
    limited: StrictBool = False
    quantity: object = ''
    remaining: object = ''
    start_time: str = Field(default='', max_length=32)
    end_time: str = Field(default='', max_length=32)
    # Which bundle group this came from, so a page that handed it over can show
    # the outcome against the right row.
    group: str = Field(default='', max_length=200)
    rewards: list[dict] = Field(default_factory=list)


class ItemCodeRunRequest(BaseModel):
    game: str = Field(min_length=1, max_length=64)
    itemcodes: list[ItemCodeSpec] = Field(default_factory=list)
    # Off by default, like the bundle route: writing to the live site is always
    # an explicit opt-in, so a replayed preview can never create anything.
    do_save: StrictBool = False


class EventSpec(BaseModel):
    """One Event. The bundle ids come from the plan, so nothing is searched."""
    client_key: StrictStr = Field(default='', max_length=80)
    slug: str = Field(default='', max_length=120)
    name_th: str = Field(default='', max_length=200)
    name_en: str = Field(default='', max_length=200)
    kind: Literal['WINNER', 'ALL'] = 'WINNER'
    uses_per_user: object = '1'
    quantity: object = '0'
    remaining: object = '0'
    start_event: str = Field(default='', max_length=32)
    end_event: str = Field(default='', max_length=32)
    start_claim: str = Field(default='', max_length=32)
    end_claim: str = Field(default='', max_length=32)
    group: str = Field(default='', max_length=200)
    rewards: list[dict] = Field(default_factory=list)


class EventRunRequest(BaseModel):
    game: str = Field(min_length=1, max_length=64)
    events: list[EventSpec] = Field(default_factory=list)
    do_save: StrictBool = False


class RewardOptionsRequest(BaseModel):
    game: str = Field(min_length=1, max_length=64)


class ProductOptionsRequest(BaseModel):
    game: str = Field(min_length=1, max_length=64)
    kinds: list[Literal['currencies', 'categories']] = Field(
        default_factory=lambda: ['currencies', 'categories'])


class ProductPriceSpec(BaseModel):
    currency_id: StrictStr = Field(min_length=1, max_length=120)
    currency_slug: StrictStr = Field(default='', max_length=160)
    currency_label: StrictStr = Field(default='', max_length=200)
    original_price: object
    price: object


class ProductSpec(BaseModel):
    client_key: StrictStr = Field(min_length=1, max_length=80)
    source_group_key: StrictStr = Field(default='', max_length=240)
    name_th: StrictStr = Field(max_length=200)
    name_en: StrictStr = Field(max_length=200)
    category_id: StrictStr = Field(max_length=120)
    category_label: StrictStr = Field(default='', max_length=200)
    details_th: StrictStr = Field(default='', max_length=20000)
    details_en: StrictStr = Field(default='', max_length=20000)
    start_at: StrictStr = Field(max_length=32)
    end_at: StrictStr = Field(max_length=32)
    bundle_id: object = ''
    bundle_ids: list[object] = Field(default_factory=list, max_length=20)
    primary_bundle_id: object = ''
    prices: list[ProductPriceSpec] = Field(min_length=1, max_length=20)
    limit_type: Literal['UNLIMITED', 'PLAYER', 'CHARACTER'] = 'UNLIMITED'
    limit_quantity: object = ''
    limit_reset_interval_days: object = ''
    limit_reset_at: object = ''
    tags: list[Literal['EVENT', 'HOT', 'LIMITED', 'NEW', 'SALE']] = Field(
        default_factory=list, max_length=5)
    is_enabled: StrictBool = False
    is_test_mode: StrictBool = True
    is_hidden: StrictBool = False
    position: object = '0'


class ProductRunRequest(BaseModel):
    game: StrictStr = Field(min_length=1, max_length=64)
    products: list[ProductSpec] = Field(default_factory=list, max_length=30)
    do_save: StrictBool = False


class LoginRequest(BaseModel):
    username: str
    password: str


class LocalLaunchRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class LoginThrottle:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def is_limited(self, client_ip: str) -> bool:
        with self._lock:
            return len(self._recent_failures(client_ip)) >= 5

    def record_failure(self, client_ip: str) -> None:
        with self._lock:
            self._recent_failures(client_ip).append(self._clock())

    def clear(self, client_ip: str) -> None:
        with self._lock:
            self._failures.pop(client_ip, None)

    def _recent_failures(self, client_ip: str) -> list[float]:
        cutoff = self._clock() - 600
        failures = [
            occurred_at
            for occurred_at in self._failures.get(client_ip, [])
            if occurred_at > cutoff
        ]
        self._failures[client_ip] = failures
        return failures


def _safe_user(user: User) -> dict[str, str | bool]:
    return {
        'id': user.id,
        'username': user.username,
        'role': user.role,
        'is_active': user.is_active,
    }


def _login_username_fingerprint(username: str, request: Request) -> str:
    key = request.app.state.settings.app_secret_key.encode('utf-8')
    normalized = username.strip().casefold().encode('utf-8')
    return hmac.new(key, normalized, hashlib.sha256).hexdigest()[:32]


def _set_session_cookie(
    response: Response,
    raw_token: str,
    settings: Settings,
    *,
    samesite: str = 'lax',
) -> None:
    response.set_cookie(
        'afc_session',
        raw_token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=samesite,
        path='/',
    )


def _clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        'afc_session',
        path='/',
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite='lax',
    )


def get_db(request: Request):
    with request.app.state.database.session() as db:
        yield db


def require_user(
    request: Request,
    afc_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    user = request.app.state.auth_service.resolve_session(db, afc_session)
    if user is None:
        raise HTTPException(status_code=401, detail='กรุณาเข้าสู่ระบบ')
    return user


def require_pairing_principal(
    request: Request,
    afc_session: str | None = Cookie(default=None),
) -> PairingPrincipalSnapshot:
    """Authenticate pairing issuance in one closed, short-lived Session."""
    failed = False
    principal = None
    try:
        principal = resolve_pairing_principal(
            request.app.state.database,
            request.app.state.auth_service,
            afc_session,
        )
    except Exception:
        failed = True
    if failed:
        raise HTTPException(status_code=500, detail='pairing_failed')
    if principal is None:
        raise HTTPException(status_code=401, detail='กรุณาเข้าสู่ระบบ')
    return principal


def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail='ไม่มีสิทธิ์ใช้งานส่วนนี้')
    return user


def _running_job(db, workspace) -> dict | None:
    """The search still going for this workspace, if there is one.

    A search outlives the page that started it, so a page coming back has to be
    able to tell 'no results yet' from 'results are still on their way'.
    """
    job = db.scalar(
        select(Job)
        .where(Job.workspace_id == workspace.id,
               Job.status.in_(('queued', 'running')))
        .order_by(Job.created_at.desc()))
    if job is None:
        return None
    return {
        'job_id': job.id,
        'status': job.status,
        'source_group_key': str((job.config or {}).get('source_group_key') or '').strip(),
    }


def _workspace_view(workspace, db=None):
    running = _running_job(db, workspace) if db is not None else None
    return {
        'running_job': running,
        'workspace_id': workspace.id,
        'mode': workspace.mode,
        # The game the search ran against, so reopening the page puts the
        # operator back on the same server rather than the first in the list.
        'game': workspace.game or '',
        'filename': workspace.filename,
        'count': len(workspace.criteria),
        'items': workspace.criteria,
        'occurrence_count': len(workspace.occurrences),
        'skipped': workspace.skipped,
        'result_count': len(workspace.results),
        'results': [search_runner.result_view(row) for row in workspace.results],
        'not_found': workspace.not_found,
        'policy': item_service.mode_policy(workspace.mode),
    }


def _get_workspace(repository: WorkspaceRepository, user_id: str, workspace_id: str):
    try:
        return repository.get_owned(user_id, workspace_id)
    except WorkspaceNotFound:
        raise HTTPException(status_code=404, detail='ไม่พบงาน Item Finder นี้')


async def _temporary_upload(file: UploadFile, max_bytes: int = WORKBOOK_BODY_MAX) -> str:
    suffix = os.path.splitext(file.filename or '')[1] or '.xlsx'
    raw_fd, path = tempfile.mkstemp(suffix=suffix)
    handle = None
    try:
        handle = os.fdopen(raw_fd, 'wb')
        written = 0
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > max_bytes:
                raise HTTPException(status_code=413, detail='workbook_too_large')
            handle.write(chunk)
        handle.close()
    except BaseException:
        try:
            if handle is not None:
                handle.close()
        except Exception:
            pass
        try:
            os.close(raw_fd)
        except OSError:
            pass
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return path


@router.get('/', response_class=HTMLResponse)
def index(
    request: Request,
    afc_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    user = request.app.state.auth_service.resolve_session(db, afc_session)
    if user is None:
        return RedirectResponse('/login')
    with open(os.path.join(STATIC_DIR, 'index.html'), encoding='utf-8') as stream:
        return stream.read()


@router.get('/login', response_class=HTMLResponse)
def login_page(
    request: Request,
    afc_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    if request.app.state.settings.local_desktop_mode:
        return RedirectResponse('/local-start')
    user = request.app.state.auth_service.resolve_session(db, afc_session)
    if user is not None:
        return RedirectResponse('/')
    with open(os.path.join(STATIC_DIR, 'login.html'), encoding='utf-8') as stream:
        return stream.read()


@router.get('/account', response_class=HTMLResponse)
def account_page(
    request: Request,
    afc_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    user = request.app.state.auth_service.resolve_session(db, afc_session)
    if user is None:
        return RedirectResponse('/login')
    with open(os.path.join(STATIC_DIR, 'account.html'), encoding='utf-8') as stream:
        return stream.read()


def _tool_page(request, afc_session, db, filename):
    """Serve a tool page, or send someone without a session to log in.

    Every tool drives the operator's own Aztek session, so none of these pages
    is public — and they all answer the question the same way.
    """
    user = request.app.state.auth_service.resolve_session(db, afc_session)
    if user is None:
        return RedirectResponse('/login')
    with open(os.path.join(STATIC_DIR, filename), encoding='utf-8') as stream:
        return stream.read()


@router.get('/static/console.css')
def console_css():
    """The stylesheet the tool pages share.

    Public because it is styling and nothing else: the pages that use it are
    behind a session, and a login screen that cannot fetch its own CSS helps
    nobody.
    """
    return FileResponse(os.path.join(STATIC_DIR, 'console.css'),
                        media_type='text/css')


@router.get('/static/console.js')
def console_js():
    """The plumbing the tool pages share — top bar, server picker, queue, log.

    It holds no data of its own: everything it shows it fetches through the
    session-checked APIs.
    """
    return FileResponse(os.path.join(STATIC_DIR, 'console.js'),
                        media_type='application/javascript')


@router.get('/static/game_sync.js')
def game_sync_js():
    """Synchronize the shared game/server picker between open tool tabs."""
    return FileResponse(os.path.join(STATIC_DIR, 'game_sync.js'),
                        media_type='application/javascript')


@router.get('/static/sheet_picker.css')
def sheet_picker_css():
    """Shared search and long-name layout for workbook sheet pickers."""
    return FileResponse(os.path.join(STATIC_DIR, 'sheet_picker.css'),
                        media_type='text/css')


@router.get('/static/sheet_picker.js')
def sheet_picker_js():
    """Client-side filtering used by every workbook sheet picker."""
    return FileResponse(os.path.join(STATIC_DIR, 'sheet_picker.js'),
                        media_type='application/javascript')


@router.get('/bundles', response_class=HTMLResponse)
def bundles_page(
    request: Request,
    afc_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    # Create Bundle is a tool of its own, not a view over a search: it builds
    # bundles from typed or pasted item ids just as well as from ones Item
    # Finder sent over, so it gets its own page rather than a panel on that one.
    return _tool_page(request, afc_session, db, 'bundles.html')


@router.get('/itemcodes', response_class=HTMLResponse)
def itemcodes_page(
    request: Request,
    afc_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    return _tool_page(request, afc_session, db, 'itemcodes.html')


@router.get('/events', response_class=HTMLResponse)
def events_page(
    request: Request,
    afc_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    return _tool_page(request, afc_session, db, 'events.html')


@router.get('/products', response_class=HTMLResponse)
def products_page(
    request: Request,
    afc_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    return _tool_page(request, afc_session, db, 'products.html')


@router.get('/pair-bridge', response_class=HTMLResponse)
def pair_bridge_page():
    # Landing page for the bookmarklet: it receives the Aztek cookies in the URL
    # fragment (never sent to the server) and POSTs them same-origin to
    # /api/aztek/pair. The short-lived, single-use pairing token authenticates
    # that POST, so this inert bridge page must not depend on a host-only web
    # login cookie that the Aztek browser tab may not share.
    with open(os.path.join(STATIC_DIR, 'pair_bridge.html'), encoding='utf-8') as stream:
        return stream.read()


def _client_host(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post('/api/local/launch')
def local_launch(request: Request):
    try:
        token = request.app.state.local_access.issue(
            request.headers.get('X-AFC-Launcher-Secret'),
            _client_host(request),
        )
    except LookupError:
        raise HTTPException(status_code=404)
    return {'token': token}


@router.get('/local-start', response_class=HTMLResponse)
def local_start(request: Request):
    if not request.app.state.local_access.enabled_for(_client_host(request)):
        raise HTTPException(status_code=404)
    with open(
        os.path.join(STATIC_DIR, 'local_start.html'),
        encoding='utf-8',
    ) as stream:
        return stream.read()


@router.post('/api/local/session', status_code=204)
def local_session(
    payload: LocalLaunchRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    if not request.app.state.local_access.consume(
        payload.token,
        _client_host(request),
    ):
        raise HTTPException(status_code=404)
    try:
        owner = request.app.state.local_access.ensure_owner(db)
    except RuntimeError:
        raise HTTPException(status_code=409)
    response = Response(status_code=204)
    _set_session_cookie(
        response,
        request.app.state.auth_service.create_session(db, owner),
        request.app.state.settings,
        samesite='strict',
    )
    return response


@router.post('/api/auth/login')
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    if request.app.state.settings.local_desktop_mode:
        raise HTTPException(status_code=404)
    client_ip = request.client.host if request.client else 'unknown'
    throttle: LoginThrottle = request.app.state.login_throttle
    if throttle.is_limited(client_ip):
        write_audit(
            db,
            user_id=None,
            action='auth.login_failed',
            status='failure',
            summary={
                'reason': 'throttled',
                'target_username': _login_username_fingerprint(payload.username, request),
            },
            tool='auth',
            request=request,
        )
        return JSONResponse({'detail': 'ลองใหม่ภายหลัง'}, status_code=429)
    user = request.app.state.auth_service.authenticate(
        db, payload.username, payload.password
    )
    if user is None:
        throttle.record_failure(client_ip)
        write_audit(
            db,
            user_id=None,
            action='auth.login_failed',
            status='failure',
            summary={
                'reason': 'invalid_credentials',
                'target_username': _login_username_fingerprint(payload.username, request),
            },
            tool='auth',
            request=request,
        )
        return JSONResponse(
            {'detail': 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง'}, status_code=401
        )
    throttle.clear(client_ip)
    response = JSONResponse(_safe_user(user))
    _set_session_cookie(
        response,
        request.app.state.auth_service.create_session(db, user),
        request.app.state.settings,
    )
    write_audit(
        db,
        user_id=user.id,
        action='auth.login_succeeded',
        status='success',
        summary={'role': user.role},
        tool='auth',
        resource_type='user',
        resource_id=user.id,
        request=request,
    )
    return response


@router.post('/api/auth/logout', status_code=204)
def logout(
    request: Request,
    afc_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    user = request.app.state.auth_service.resolve_session(db, afc_session)
    request.app.state.auth_service.revoke_session(db, afc_session)
    write_audit(
        db,
        user_id=user.id if user is not None else None,
        action='auth.logout',
        status='success',
        summary={'role': user.role} if user is not None else {},
        tool='auth',
        resource_type='user' if user is not None else '',
        resource_id=user.id if user is not None else '',
        request=request,
    )
    response = Response(status_code=204)
    _clear_session_cookie(response, request.app.state.settings)
    return response


@router.get('/api/auth/me')
def me(request: Request, user: User = Depends(require_user)):
    result = _safe_user(user)
    result['local_mode'] = request.app.state.settings.local_desktop_mode
    return result


@router.post('/api/auth/change-password', status_code=204)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    if (
        not verify_password(payload.current_password, user.password_hash)
        or len(payload.new_password) < 10
    ):
        raise HTTPException(status_code=400, detail='ไม่สามารถเปลี่ยนรหัสผ่านได้')
    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = utc_now()
    request.app.state.auth_service.revoke_all_sessions(db, user.id)
    write_audit(
        db,
        user_id=user.id,
        action='auth.password_changed',
        status='success',
        resource_type='user',
        resource_id=user.id,
        request=request,
    )
    response = Response(status_code=204)
    _clear_session_cookie(response, request.app.state.settings)
    return response


@router.post('/api/aztek/pairing-token')
def create_pairing_token(
    request: Request,
    principal: PairingPrincipalSnapshot = Depends(require_pairing_principal),
):
    """Issue atomically, exposing a token only after commit and close."""
    database: Database = request.app.state.database
    service: AztekSessionService = request.app.state.aztek_session_service
    reservations: PairingIssueReservations = (
        request.app.state.pairing_issue_reservations)
    outcome = 'pairing_failed'
    committed_issue = None

    try:
        with reservations.reserve(principal.user_id):
            snapshot_failed = False
            snapshot_busy = False
            attempt = None
            try:
                with database.session() as snapshot_db:
                    attempt = service._prepare_pairing_issue(
                        snapshot_db, principal.user_id)
            except Exception as error:
                snapshot_busy = pairing_service.is_pairing_sqlite_busy(error)
                snapshot_failed = True
                error = None

            if snapshot_failed:
                outcome = 'pairing_busy' if snapshot_busy else 'pairing_failed'
            else:
                for write_number in range(4):
                    issue = None
                    durable = False
                    write_busy = False
                    write_conflict = False
                    write_failed = False
                    try:
                        with database.session() as write_db:
                            pairing_service._begin_fresh_pairing_write(write_db)
                            issue = service._apply_pairing_issue(write_db, attempt)
                            write_audit(
                                write_db,
                                user_id=principal.user_id,
                                action='aztek.pairing_requested',
                                status='success',
                                tool='aztek',
                                resource_type='aztek_session',
                                resource_id=principal.user_id,
                            )
                            write_db.commit()
                            durable = True
                    except PairingTokenIssueConflict:
                        write_conflict = True
                    except Exception as error:
                        write_busy = pairing_service.is_pairing_sqlite_busy(error)
                        write_failed = True
                        error = None

                    if write_conflict:
                        outcome = 'pairing_token_conflict'
                        break
                    if write_failed:
                        if write_busy and not durable and write_number < 3:
                            time.sleep(0.025 * (write_number + 1))
                            continue
                        outcome = 'pairing_busy' if write_busy else 'pairing_failed'
                        break
                    committed_issue = issue
                    outcome = 'success'
                    break
    except PairingTokenIssueConflict:
        outcome = 'pairing_token_conflict'
    except Exception as error:
        outcome = ('pairing_busy'
                   if pairing_service.is_pairing_sqlite_busy(error)
                   else 'pairing_failed')
        error = None

    if outcome == 'success' and committed_issue is not None:
        return {
            'pairing_token': committed_issue.raw_token,
            'expires_at': committed_issue.expires_at.isoformat(),
        }
    if outcome == 'pairing_token_conflict':
        return JSONResponse(
            {'detail': 'pairing_token_conflict'}, status_code=409)
    if outcome == 'pairing_busy':
        return JSONResponse({'detail': 'pairing_busy'}, status_code=409)
    return JSONResponse({'detail': 'pairing_failed'}, status_code=500)


@router.post('/api/aztek/local-capture')
async def capture_local_aztek_session(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Capture complete SSO state in visible Chromium on Local Setup only."""
    if not request.app.state.local_access.enabled_for(_client_host(request)):
        raise HTTPException(status_code=404)

    # Preview windows intentionally stay open. Close this operator's kept
    # previews before starting a clean authentication context.
    from web import activity_runner, bundle_runner
    await activity_runner.close_kept(str(user.id))
    await bundle_runner.close_kept(str(user.id))

    try:
        session_service = request.app.state.aztek_session_service
        seed_state = session_service.load_storage_state_for_reconnect(
            db, user)
        storage_state = await request.app.state.local_aztek_capture.capture(
            seed_state)
        session = session_service.save_storage_state(
            db, user.id, storage_state, 'Local Chromium')
    except LocalCaptureClosed:
        detail = 'ปิดหน้าต่าง Aztek ก่อนเชื่อมต่อเสร็จ — session เดิมยังอยู่'
        failure = 'window_closed'
    except LocalCaptureTimeout:
        detail = 'หมดเวลารอเข้าสู่ระบบ Aztek — session เดิมยังอยู่'
        failure = 'timeout'
    except LocalCaptureLoginRequired:
        detail = 'ยังเข้าสู่ระบบ IPA/Aztek ไม่สำเร็จ — session เดิมยังอยู่'
        failure = 'login_required'
    except InvalidStorageState:
        detail = 'ข้อมูล session ที่จับมาไม่สมบูรณ์ — session เดิมยังอยู่'
        failure = 'invalid_storage_state'
    except Exception:  # noqa: BLE001 - do not leak browser/session details
        write_audit(
            db, user_id=user.id, action='aztek.local_capture',
            status='failed', summary={'reason': 'browser_error'},
            tool='aztek', resource_type='aztek_session', resource_id=user.id,
            request=request)
        raise HTTPException(
            status_code=502,
            detail='เปิด Chromium เพื่อเชื่อม Aztek ไม่สำเร็จ — session เดิมยังอยู่')
    else:
        write_audit(
            db, user_id=user.id, action='aztek.local_capture',
            status='success', summary={'source': 'local_chromium'},
            tool='aztek', resource_type='aztek_session', resource_id=user.id,
            request=request)
        return {'status': 'connected',
                'account_label': session.account_label}

    write_audit(
        db, user_id=user.id, action='aztek.local_capture', status='failed',
        summary={'reason': failure}, tool='aztek',
        resource_type='aztek_session', resource_id=user.id, request=request)
    raise HTTPException(status_code=409, detail=detail)


@router.post('/api/aztek/pair')
def pair_aztek_session(
    request: Request,
    parsed: PairingParseResult = Depends(pairing_parse_dependency),
):
    """Consume one parsed token in fresh, bounded route-owned transactions."""
    client_ip = request.client.host if request.client else 'unknown'
    throttle: LoginThrottle = request.app.state.pairing_throttle
    throttle_key = '%s|%s' % (client_ip, parsed.fingerprint)
    if throttle.is_limited(throttle_key):
        return JSONResponse({'detail': 'ลองใหม่ภายหลัง'}, status_code=429)

    payload = parsed.payload
    if payload is None:
        throttle.record_failure(throttle_key)
        return JSONResponse(
            {'detail': 'ข้อมูลเซสชันไม่ถูกต้อง'}, status_code=422)

    service: AztekSessionService = request.app.state.aztek_session_service
    database: Database = request.app.state.database
    outcome = 'pairing_failed'
    account_label = None
    prepared = None
    validation_failed = False
    try:
        prepared = service._prepare_pairing_consumption(
            payload.pairing_token,
            payload.storage_state,
            payload.account_label,
        )
    except InvalidStorageState:
        validation_failed = True
    except Exception:
        outcome = 'pairing_failed'

    if validation_failed:
        throttle.record_failure(throttle_key)
        outcome = 'invalid'
    elif prepared is not None:
        for write_number in range(4):
            attempt_outcome = 'success'
            saved_label = None
            durable = False
            write_busy = False
            write_failed = False
            try:
                with database.session() as write_db:
                    pairing_service._begin_fresh_pairing_write(write_db)
                    try:
                        session = service._apply_pairing_consumption(
                            write_db, prepared)
                    except PairingTokenNotFound:
                        attempt_outcome = 'not_found'
                    except PairingTokenUnavailable:
                        attempt_outcome = 'unavailable'
                    else:
                        saved_label = session.account_label
                        write_audit(
                            write_db,
                            user_id=session.user_id,
                            action='aztek.connected',
                            status='success',
                            tool='aztek',
                            resource_type='aztek_session',
                            resource_id=session.user_id,
                        )
                    write_db.commit()
                    durable = True
            except Exception as error:
                write_busy = pairing_service.is_pairing_sqlite_busy(error)
                write_failed = True
                error = None

            if write_failed:
                if write_busy and not durable and write_number < 3:
                    time.sleep(0.025 * (write_number + 1))
                    continue
                outcome = 'pairing_busy' if write_busy else 'pairing_failed'
                break
            outcome = attempt_outcome
            account_label = saved_label
            break

    if outcome == 'success':
        throttle.clear(throttle_key)
        return {'status': 'connected', 'account_label': account_label}
    if outcome == 'not_found':
        throttle.record_failure(throttle_key)
        return JSONResponse({'detail': 'ไม่พบรหัสจับคู่'}, status_code=404)
    if outcome == 'unavailable':
        throttle.record_failure(throttle_key)
        return JSONResponse(
            {'detail': 'รหัสจับคู่หมดอายุหรือถูกใช้ไปแล้ว'}, status_code=410)
    if outcome == 'invalid':
        return JSONResponse(
            {'detail': 'ข้อมูลเซสชันไม่ถูกต้อง'}, status_code=422)
    if outcome == 'pairing_busy':
        return JSONResponse({'detail': 'pairing_busy'}, status_code=409)
    return JSONResponse({'detail': 'pairing_failed'}, status_code=500)


@router.get('/api/aztek/status')
def aztek_status(request: Request, user: User = Depends(require_user),
                 db: Session = Depends(get_db)):
    return request.app.state.aztek_session_service.get_status(db, user)


@router.delete('/api/aztek/session', status_code=204)
def disconnect_aztek_session(request: Request, user: User = Depends(require_user),
                             db: Session = Depends(get_db)):
    removed = request.app.state.aztek_session_service.disconnect(db, user)
    if removed:
        write_audit(
            db, user_id=user.id, action='aztek.disconnected', status='success',
            tool='aztek', resource_type='aztek_session', resource_id=user.id,
            request=request,
        )
    return Response(status_code=204)


@router.get('/api/health')
def health(request: Request):
    result = {'ok': True}
    if request.app.state.settings.local_desktop_mode:
        result['product'] = 'all-for-cabal-local'
    return result


@router.get('/api/games')
def games(user: User = Depends(require_user)):
    return {'games': list(item_finder.GAME_NAMES)}


_RANDOM_RATE_RULE = (
    'ต้องเป็นเลขทศนิยมมากกว่า 0 และไม่เกิน 100 '
    'โดยมีทศนิยมไม่เกิน 3 ตำแหน่ง')
_PRODUCT_PRICE_RULE = (
    'ต้องเป็นเลขทศนิยมตั้งแต่ 0 ขึ้นไปในรูปแบบปกติ'
    'และยาวไม่เกิน 64 ตัวอักษร')


def _safe_failure(detail: str) -> PayloadValueError:
    return PayloadValueError(detail, '')


def _decimal_with_rule(value: object, label: str, *, minimum: Decimal,
                       maximum: Decimal | None = None,
                       places: int | None = None, rule: str) -> str:
    failed = False
    try:
        text = plain_decimal_text(
            value, label, minimum=minimum, maximum=maximum, places=places)
    except PayloadValueError:
        failed = True
        text = ''
    if failed:
        raise PayloadValueError(label, rule) from None
    return text


def _nonblank_client_keys_are_unique(jobs: list[dict]) -> bool:
    keys = [job.get('client_key', '') for job in jobs
            if job.get('client_key', '')]
    return len(keys) == len(set(keys))


def _clean_rewards(raw: list[dict], *, bundle_number: int = 1) -> list[dict]:
    """Validate every submitted Bundle reward without dropping a row."""
    from web import bundle_runner

    cleaned = []
    for row, entry in enumerate(raw, 1):
        entry = entry if isinstance(entry, dict) else {}
        kind_value = entry.get('type')
        kind = kind_value.strip().upper() if isinstance(kind_value, str) else ''
        if kind not in bundle_runner.REWARD_KINDS:
            raise _safe_failure(
                f'Bundle ที่ {bundle_number}: ประเภท reward แถว {row} '
                'ไม่ถูกต้อง')

        value_source = entry.get('value')
        value = value_source.strip() if isinstance(value_source, str) else ''
        if not value:
            raise _safe_failure(
                f'Bundle ที่ {bundle_number}: ค่า reward แถว {row} '
                'ต้องเป็นข้อความที่ไม่ว่าง')

        qty_source = entry['qty'] if 'qty' in entry else '1'
        qty = positive_int_text(
            qty_source,
            f'Bundle ที่ {bundle_number}: จำนวน reward แถว {row}')
        cleaned.append({'type': kind, 'value': value, 'qty': qty})
    return cleaned



@router.get('/api/capabilities')
def capabilities(request: Request, user: User = Depends(require_user)):
    """What this deployment can offer the UI.

    A watchable (headed) browser needs the server to share the operator's
    desktop, which is only true for a local run — a hosted server has no
    display to draw on, so the UI must not offer the choice there.
    """
    return {'allow_headed': request.app.state.settings.app_env != 'production'}


@router.get('/api/modes')
def modes(user: User = Depends(require_user)):
    return {mode: item_service.mode_policy(mode)
            for mode in ('event', 'itemcode', 'shop')}


@router.get('/api/template')
def download_template(user: User = Depends(require_user)):
    handle, path = tempfile.mkstemp(suffix='.xlsx')
    os.close(handle)
    try:
        item_finder.download_template(path)
        with open(path, 'rb') as stream:
            content = stream.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return Response(
        content,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename="item_finder_template.xlsx"'},
    )


@router.post('/api/import-template')
async def import_template(request: Request, file: UploadFile = File(...), mode: Mode = Form('event'),
                          workspace_id: str = Form(''),
                          user: User = Depends(require_user),
                          db: Session = Depends(get_db)):
    item_service.mode_policy(mode)
    path = await _temporary_upload(file)
    try:
        rows = await asyncio.to_thread(
            item_service.parse_workbook_locked, item_finder.read_template, path)
    except Exception as error:
        raise HTTPException(status_code=400, detail='อ่าน template ไม่สำเร็จ: %s' % error)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    if workspace_id:
        repository = WorkspaceRepository(db)
        workspace = _get_workspace(repository, user.id, workspace_id)
        if workspace.mode != mode:
            raise HTTPException(status_code=400, detail='โหมดของงานไม่ตรงกับไฟล์ที่นำเข้า')
        workspace = repository.replace_template(
            user.id, workspace.id, file.filename or 'template.xlsx', rows)
    else:
        workspace = WorkspaceRepository(db).create(
            user.id, mode, file.filename or 'template.xlsx', rows)
    if not workspace_id:
        write_audit(
            db, user_id=user.id, action='workspace.created', status='success',
            summary={'mode': mode, 'filename': file.filename or 'template.xlsx'},
            tool='item_finder', resource_type='workspace',
            resource_id=workspace.id, request=request,
        )
    write_audit(
        db, user_id=user.id, action='template.imported', status='success',
        summary={
            'count': len(rows), 'mode': mode,
            'filename': file.filename or 'template.xlsx',
        },
        tool='item_finder', resource_type='workspace', resource_id=workspace.id,
        request=request,
    )
    return _workspace_view(workspace)


@router.post('/api/import-plan')
async def import_plan(request: Request, file: UploadFile = File(...), mode: Mode = Form('event'),
                      workspace_id: str = Form(''),
                      user: User = Depends(require_user),
                      db: Session = Depends(get_db)):
    from web import product_plan

    parser = item_service.parser_for_mode(mode)
    repository = WorkspaceRepository(db)
    workspace = (_get_workspace(repository, user.id, workspace_id) if workspace_id
                 else repository.create(user.id, mode, file.filename or 'plan.xlsx'))
    if workspace.mode != mode:
        raise HTTPException(status_code=400, detail='โหมดของงานไม่ตรงกับไฟล์ที่นำเข้า')
    path = await _temporary_upload(file)
    try:
        sheets, skipped = await asyncio.to_thread(
            item_service.parse_workbook_locked, parser, path)
    except Exception as error:
        raise HTTPException(status_code=400, detail='อ่าน Event/Prize ไม่สำเร็จ: %s' % error)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    if not sheets:
        raise HTTPException(status_code=400, detail='ไม่พบตารางไอเทมในไฟล์นี้')
    pending = repository.add_pending(user.id, workspace.id, sheets, skipped)
    if not workspace_id:
        write_audit(
            db, user_id=user.id, action='workspace.created', status='success',
            summary={'mode': mode, 'filename': file.filename or 'plan.xlsx'},
            tool='item_finder', resource_type='workspace',
            resource_id=workspace.id, request=request,
        )
    write_audit(
        db, user_id=user.id, action='plan.imported', status='success',
        summary={
            'count': sum(len(rows) for _name, rows in sheets), 'mode': mode,
            'filename': file.filename or 'plan.xlsx',
        },
        tool='item_finder', resource_type='workspace', resource_id=workspace.id,
        request=request,
    )
    return {
        'workspace_id': workspace.id,
        'pending_id': pending.id,
        'needs_sheet_selection': True,
        'sheets': [
            {
                'name': name,
                'display_name': item_service.sheet_display_name(name, rows),
                'count': len(rows),
                **({
                    'product_count': product_plan.count_products(rows),
                } if mode == 'shop' else {}),
            }
            for name, rows in sheets
        ],
        'skipped': list(skipped or []),
    }


@router.post('/api/import-plan/apply')
def apply_plan(payload: ApplyPlanRequest, request: Request,
               user: User = Depends(require_user),
               db: Session = Depends(get_db)):
    pending_id = payload.pending_id.strip()
    selected = payload.selected_sheets
    if not pending_id or not selected:
        raise HTTPException(status_code=400, detail='กรุณาเลือกอย่างน้อย 1 sheet')
    if len(selected) != len(set(selected)):
        raise HTTPException(status_code=400, detail='เลือก sheet ซ้ำกัน')
    try:
        workspace = WorkspaceRepository(db).apply_pending(user.id, pending_id, selected)
        write_audit(
            db, user_id=user.id, action='plan.applied', status='success',
            summary={'count': len(selected), 'mode': workspace.mode},
            tool='item_finder', resource_type='workspace', resource_id=workspace.id,
            request=request,
        )
        db.commit()
    except EmptySheetSelection:
        db.rollback()
        raise HTTPException(status_code=400, detail='กรุณาเลือกอย่างน้อย 1 sheet')
    except DuplicateSheetSelection:
        db.rollback()
        raise HTTPException(status_code=400, detail='เลือก sheet ซ้ำกัน')
    except UnknownSheetSelection:
        db.rollback()
        raise HTTPException(status_code=400, detail='ไม่พบ sheet ที่เลือก')
    except (PendingImportNotFound, WorkspaceNotFound):
        db.rollback()
        raise HTTPException(status_code=404, detail='ไม่พบไฟล์นำเข้าที่รอเลือก sheet')
    except WorkspaceBusy:
        db.rollback()
        raise HTTPException(status_code=409, detail='workspace_busy')
    except OperationalError as error:
        db.rollback()
        if is_sqlite_busy(error):
            raise HTTPException(status_code=409, detail='workspace_busy')
        raise
    except BaseException:
        db.rollback()
        raise
    return _workspace_view(workspace)


@router.get('/api/workspaces/{workspace_id}')
def get_workspace(workspace_id: str, user: User = Depends(require_user),
                  db: Session = Depends(get_db)):
    # Only this route reports a running search: it is the one a page reopening
    # after a trip elsewhere calls.
    return _workspace_view(
        _get_workspace(WorkspaceRepository(db), user.id, workspace_id), db)


@router.delete('/api/workspaces/{workspace_id}', status_code=204)
def delete_workspace(workspace_id: str, request: Request,
                     user: User = Depends(require_user),
                     db: Session = Depends(get_db)):
    repository = WorkspaceRepository(db)
    workspace = _get_workspace(repository, user.id, workspace_id)
    summary = {'mode': workspace.mode, 'filename': workspace.filename}
    try:
        with request.app.state.search_coordinator.deletion_guard(workspace_id):
            try:
                repository.delete_owned(user.id, workspace_id)
                write_audit(
                    db, user_id=user.id, action='workspace.deleted',
                    status='success', summary=summary,
                    tool='item_finder', resource_type='workspace',
                    resource_id=workspace_id, request=request,
                )
                db.commit()
            except BaseException:
                db.rollback()
                raise
    except WorkspaceBusy:
        db.rollback()
        raise HTTPException(status_code=409, detail='workspace_busy')
    except WorkspaceNotFound:
        db.rollback()
        raise HTTPException(status_code=404, detail='ไม่พบงาน Item Finder นี้')
    except OperationalError as error:
        db.rollback()
        if is_sqlite_busy(error):
            raise HTTPException(status_code=409, detail='workspace_busy')
        raise
    return Response(status_code=204)


@router.get('/api/workspaces/{workspace_id}/export.csv')
def export_csv(workspace_id: str, request: Request,
               user: User = Depends(require_user),
               db: Session = Depends(get_db)):
    workspace = _get_workspace(WorkspaceRepository(db), user.id, workspace_id)
    if not workspace.results:
        raise HTTPException(status_code=400, detail='ยังไม่มีผลลัพธ์')
    write_audit(
        db, user_id=user.id, action='workspace.exported_csv', status='success',
        summary={
            'count': len(workspace.results), 'format': 'csv', 'game': workspace.game,
        },
        tool='item_finder', resource_type='workspace', resource_id=workspace_id,
        request=request,
    )
    return Response(
        item_service.export_csv_bytes(workspace.results),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="item_finder_results.csv"'},
    )


@router.get('/api/workspaces/{workspace_id}/export.xlsx')
def export_xlsx(workspace_id: str, request: Request,
                user: User = Depends(require_user),
                db: Session = Depends(get_db)):
    workspace = _get_workspace(WorkspaceRepository(db), user.id, workspace_id)
    if not workspace.results:
        raise HTTPException(status_code=400, detail='ยังไม่มีผลลัพธ์')
    write_audit(
        db, user_id=user.id, action='workspace.exported_xlsx', status='success',
        summary={
            'count': len(workspace.results), 'format': 'xlsx', 'game': workspace.game,
        },
        tool='item_finder', resource_type='workspace', resource_id=workspace_id,
        request=request,
    )
    return Response(
        item_service.export_xlsx_bytes(workspace.results, workspace.game),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename="item_finder_results.xlsx"'},
    )


@router.get('/api/workspaces/{workspace_id}/itemcodes')
def workspace_itemcodes(workspace_id: str, request: Request,
                        user: User = Depends(require_user),
                        db: Session = Depends(get_db)):
    """Draft one Item Code per group, from what the imported plan said.

    Available as soon as the file is imported: the conditions block — expiry,
    codes per set, whether a code may be reused — is read at import time and
    has nothing to do with whether the items have been found yet.
    """
    from web import itemcode_plan

    workspace = _get_workspace(WorkspaceRepository(db), user.id, workspace_id)
    if not workspace.group_meta:
        raise HTTPException(
            status_code=400,
            detail='ไฟล์นี้ไม่มีเงื่อนไข Item Code (นำเข้าไฟล์ Event/Prize ก่อน)')
    drafts = itemcode_plan.build_itemcodes(workspace.group_meta, workspace.game)
    write_audit(
        db, user_id=user.id, action='itemcode.drafted', status='success',
        summary={'count': len(drafts), 'mode': workspace.mode,
                 'game': workspace.game},
        tool='item_finder', resource_type='workspace', resource_id=workspace_id,
        request=request,
    )
    return {'itemcodes': drafts, 'game': workspace.game or ''}


@router.get('/api/workspaces/{workspace_id}/products')
def workspace_products(
    workspace_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Return editable Product drafts from the persisted Shop plan."""
    from web import product_plan

    workspace = _get_workspace(
        WorkspaceRepository(db), user.id, workspace_id)
    return {
        'products': product_plan.build_products(
            workspace.group_meta, workspace.game or ''),
        'game': workspace.game or '',
        'workspace_id': workspace.id,
    }


@router.get('/api/workspaces/{workspace_id}/events')
def workspace_events(workspace_id: str, request: Request, game: str = '',
                     user: User = Depends(require_user),
                     db: Session = Depends(get_db)):
    """Reassemble the selected Event sheets into editable Event drafts."""
    from web import event_plan

    workspace = _get_workspace(WorkspaceRepository(db), user.id, workspace_id)
    if workspace.mode != 'event':
        raise HTTPException(
            status_code=400, detail='งานนี้ไม่ได้อยู่ในโหมด Event')
    if not workspace.group_meta:
        raise HTTPException(
            status_code=400, detail='ไฟล์นี้ไม่มีข้อมูล Event ที่เลือกไว้')
    selected_game = game or workspace.game
    if selected_game and selected_game not in item_finder.GAMES:
        raise HTTPException(
            status_code=400, detail='ไม่รู้จักเกม: %s' % selected_game)
    drafts = event_plan.build_workspace_events(
        workspace.group_meta, selected_game)
    write_audit(
        db, user_id=user.id, action='event.drafted', status='success',
        summary={'count': len(drafts), 'mode': workspace.mode,
                 'game': selected_game},
        tool='item_finder', resource_type='workspace',
        resource_id=workspace_id, request=request,
    )
    return {'events': drafts, 'game': selected_game or ''}


@router.post('/api/workspaces/{workspace_id}/bundles')
def bundle_preview(workspace_id: str, payload: BundleRequest, request: Request,
                   user: User = Depends(require_user), db: Session = Depends(get_db)):
    from web import event_plan, itemcode_plan

    workspace = _get_workspace(WorkspaceRepository(db), user.id, workspace_id)
    source_group_key = payload.source_group_key.strip()
    indexes = payload.selected_indexes
    if source_group_key:
        rows = item_service.rows_for_source_group(
            workspace.results, source_group_key)
    elif indexes:
        rows = [workspace.results[index] for index in sorted(set(indexes))
                if isinstance(index, int) and 0 <= index < len(workspace.results)]
    else:
        rows = workspace.results
    if not rows and source_group_key:
        criteria = item_service.rows_for_source_group(
            workspace.criteria, source_group_key)
        if criteria:
            return {
                'bundles': [], 'needs_search': True,
                'mode': workspace.mode, 'game': workspace.game or '',
                'event_drafts': [], 'itemcode_drafts': [],
                'not_found': workspace.not_found or [],
                'search_handoff': {
                    'workspace_id': workspace_id,
                    'source_group_key': source_group_key,
                    'criteria': criteria,
                },
            }
    if not rows:
        raise HTTPException(status_code=400, detail='ไม่มีไอเทมให้รวมเป็นบันเดิล')
    bundles = item_service.build_bundles(rows, workspace.group_meta)
    if source_group_key:
        bundles = [bundle for bundle in bundles
                   if str(bundle.get('group_key') or '').strip()
                   == source_group_key]
        if not bundles:
            raise HTTPException(
                status_code=400,
                detail='ไม่พบแถว Item ของ Product กลุ่มที่เลือก')
    group_keys = [bundle.get('group_key') for bundle in bundles
                  if bundle.get('group_key')]
    event_drafts = event_plan.build_workspace_events(
        workspace.group_meta, workspace.game, group_keys=group_keys
    ) if workspace.mode == 'event' else []
    itemcode_drafts = itemcode_plan.build_itemcodes(
        workspace.group_meta, workspace.game, groups=group_keys
    ) if workspace.mode == 'itemcode' else []
    write_audit(
        db, user_id=user.id, action='bundle.previewed', status='success',
        summary={'count': len(rows), 'mode': workspace.mode},
        tool='item_finder', resource_type='workspace', resource_id=workspace_id,
        request=request,
    )
    # The mode decides which columns matter when checking a bundle against the
    # document, and the misses are the most dangerous thing to leave behind on
    # this page — the document asked for them and no item is going in.
    return {'bundles': bundles, 'mode': workspace.mode,
            'game': workspace.game or '',
            'event_drafts': event_drafts,
            'itemcode_drafts': itemcode_drafts,
            'not_found': workspace.not_found or []}


@router.post('/api/reward-options')
async def reward_options(payload: RewardOptionsRequest, request: Request,
                         user: User = Depends(require_user),
                         db: Session = Depends(get_db)):
    """Read the reward dropdown choices for a game off the live Aztek page.

    Read-only: it opens the create-bundle page, harvests the options and
    leaves. No workspace is involved because the lists are per-game site data,
    not per-search results.
    """
    from web import bundle_runner

    if payload.game not in item_finder.GAMES:
        raise HTTPException(status_code=400, detail='ไม่รู้จักเกม: %s' % payload.game)
    storage_state = request.app.state.aztek_session_service.load_storage_state(db, user)
    if storage_state is None:
        raise HTTPException(status_code=409, detail='ยังไม่ได้เชื่อมเซสชัน Aztek')

    logs: list[dict] = []
    try:
        async with request.app.state.browser_gate.slot():
            options = await bundle_runner.fetch_reward_options(
                payload.game, storage_state,
                lambda message, level='INFO': logs.append(
                    {'msg': message, 'level': level}))
    except Exception as exc:
        write_audit(
            db, user_id=user.id, action='bundle.reward_options', status='failed',
            summary={'error': str(exc)[:200], 'game': payload.game},
            tool='create_bundle', resource_type='aztek_session',
            resource_id=user.id, request=request)
        raise HTTPException(status_code=502, detail='ดึงตัวเลือก reward ไม่สำเร็จ: %s' % exc)

    write_audit(
        db, user_id=user.id, action='bundle.reward_options', status='success',
        summary={'game': payload.game,
                 'found': sum(len(v) for v in options.values())},
        tool='create_bundle', resource_type='aztek_session',
        resource_id=user.id, request=request)
    return {'reward_options': options, 'logs': logs}


@router.post('/api/products/options')
async def product_options(
    payload: ProductOptionsRequest,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Read selected Product option kinds from the live Aztek form."""
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
        async with request.app.state.browser_gate.slot():
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
    counts = {
        kind: len(options.get(kind) or ())
        for kind in kinds
    }
    write_audit(
        db, user_id=user.id, action='product.options',
        status='success',
        summary={'game': payload.game, 'counts': counts},
        tool='create_product', resource_type='aztek_session',
        resource_id=user.id, request=request)
    return {'options': options}


IMAGE_KEY = re.compile(
    r'^image__(?P<client>[A-Za-z0-9_-]{1,80})__'
    r'(?P<slot>thumb_th|banner_th|thumb_en|banner_en)$')
ALLOWED_IMAGE_TYPES = {
    'image/png', 'image/jpeg', 'image/webp', 'image/gif'}
MAX_PRODUCT_IMAGE_BYTES = 10 * 1024 * 1024
_PRODUCT_IMAGE_SLOT = {
    'thumb_th': 'thumbnail_th',
    'banner_th': 'banner_th',
    'thumb_en': 'thumbnail_en',
    'banner_en': 'banner_en',
}


def _product_numeric(value: object) -> object:
    if type(value) is _JsonNumberLexeme:
        return value.text
    return value


def _product_datetime(value: str, label: str) -> str:
    text = value.strip()
    if aztek_form.parse_datetime(text) is None:
        raise PayloadValueError(label, 'ต้องเป็นวันเวลาที่ถูกต้อง')
    return text


def _clean_product(spec: ProductSpec, *, product_number: int = 1) -> dict:
    prefix = f'Product ที่ {product_number}'
    name_th = spec.name_th.strip()
    name_en = spec.name_en.strip()
    if not name_th:
        raise _safe_failure(f'{prefix}: ชื่อ Product (ไทย) ห้ามว่าง')
    if not name_en:
        raise _safe_failure(f'{prefix}: ชื่อ Product (อังกฤษ) ห้ามว่าง')
    category_id = spec.category_id.strip()
    if not category_id:
        raise _safe_failure(f'{prefix}: หมวดหมู่ห้ามว่าง')
    start_at = _product_datetime(spec.start_at, f'{prefix}: วันเริ่มขาย')
    end_at = _product_datetime(spec.end_at, f'{prefix}: วันสิ้นสุด')
    if aztek_form.parse_datetime(start_at) >= aztek_form.parse_datetime(end_at):
        raise _safe_failure(f'{prefix}: วันเริ่มขายต้องมาก่อนวันสิ้นสุด')

    if spec.bundle_ids:
        raw_bundle_ids = spec.bundle_ids
    elif isinstance(spec.bundle_id, str) and not spec.bundle_id.strip():
        raw_bundle_ids = []
    else:
        raw_bundle_ids = [spec.bundle_id]
    bundle_ids: list[str] = []
    seen_bundle_ids: set[str] = set()
    for row, raw_bundle_id in enumerate(raw_bundle_ids, 1):
        bundle_id = positive_int_text(
            _product_numeric(raw_bundle_id),
            f'{prefix}: Bundle ID แถว {row}', max_length=32)
        if bundle_id in seen_bundle_ids:
            raise _safe_failure(f'{prefix}: Bundle ID ห้ามซ้ำกัน')
        seen_bundle_ids.add(bundle_id)
        bundle_ids.append(bundle_id)
    if not bundle_ids:
        raise _safe_failure(f'{prefix}: ต้องมี Bundle อย่างน้อย 1 รายการ')

    raw_primary = spec.primary_bundle_id
    if isinstance(raw_primary, str) and not raw_primary.strip():
        primary_bundle_id = bundle_ids[0]
    else:
        primary_bundle_id = positive_int_text(
            _product_numeric(raw_primary),
            f'{prefix}: Primary Bundle ID', max_length=32)
        if primary_bundle_id not in seen_bundle_ids:
            raise _safe_failure(
                f'{prefix}: Primary Bundle ID ต้องอยู่ในรายการ Bundle')

    position = non_negative_int_text(
        _product_numeric(spec.position), f'{prefix}: ตำแหน่ง')

    prices = []
    currency_ids: set[str] = set()
    for row, price in enumerate(spec.prices, 1):
        currency_id = price.currency_id.strip()
        if currency_id in currency_ids:
            raise _safe_failure(f'{prefix}: Currency ห้ามซ้ำกัน')
        currency_ids.add(currency_id)
        prices.append({
            'currency_id': currency_id,
            'currency_slug': price.currency_slug.strip(),
            'currency_label': price.currency_label.strip(),
            'original_price': _decimal_with_rule(
                _product_numeric(price.original_price),
                f'{prefix}: ราคาปกติแถว {row}', minimum=Decimal('0'),
                rule=_PRODUCT_PRICE_RULE),
            'price': _decimal_with_rule(
                _product_numeric(price.price),
                f'{prefix}: ราคาขายแถว {row}', minimum=Decimal('0'),
                rule=_PRODUCT_PRICE_RULE),
        })

    if spec.limit_type == 'UNLIMITED':
        limit_quantity = ''
        reset_interval = ''
        reset_at = ''
    else:
        limit_quantity = positive_int_text(
            _product_numeric(spec.limit_quantity),
            f'{prefix}: จำนวนที่ซื้อได้')

        raw_interval = spec.limit_reset_interval_days
        if isinstance(raw_interval, str) and not raw_interval.strip():
            reset_interval = ''
        else:
            reset_interval = positive_int_text(
                _product_numeric(raw_interval), f'{prefix}: รอบรีเซ็ต')

        reset_at = optional_text(
            spec.limit_reset_at, f'{prefix}: เวลารีเซ็ต', max_length=32)
        if reset_at and aztek_form.parse_datetime(reset_at) is None:
            raise PayloadValueError(
                f'{prefix}: เวลารีเซ็ต', 'ต้องเป็นวันเวลาที่ถูกต้อง')

    return {
        'client_key': spec.client_key,
        'source_group_key': spec.source_group_key,
        'group': spec.source_group_key,
        'name_th': name_th,
        'name_en': name_en,
        'category_id': category_id,
        'category_label': spec.category_label.strip(),
        'details_th': spec.details_th,
        'details_en': spec.details_en,
        'start_at': start_at,
        'end_at': end_at,
        'bundle_ids': bundle_ids,
        'primary_bundle_id': primary_bundle_id,
        'bundle_id': primary_bundle_id,
        'prices': prices,
        'limit_type': spec.limit_type,
        'limit_quantity': limit_quantity,
        'limit_reset_interval_days': reset_interval,
        'limit_reset_at': reset_at,
        'tags': list(spec.tags),
        'is_enabled': spec.is_enabled,
        'is_test_mode': spec.is_test_mode,
        'is_hidden': spec.is_hidden,
        'position': position,
        'images': {},
    }


async def _product_images(request: Request, jobs: list[dict]) -> None:
    """Attach validated image bytes to their Product job, never a file path."""
    by_client = {job['client_key']: job for job in jobs}
    form = await request.form()
    for field, upload in form.multi_items():
        if field == 'payload':
            continue
        if not field.startswith('image__'):
            continue
        match = IMAGE_KEY.match(field)
        if not match:
            raise HTTPException(
                status_code=400, detail='ชื่อช่องรูป Product ไม่ถูกต้อง')
        job = by_client.get(match.group('client'))
        if job is None:
            raise HTTPException(
                status_code=400,
                detail='รูป Product อ้างถึงรายการที่ไม่มีในคำขอ')
        content_type = str(getattr(upload, 'content_type', '') or '').lower()
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail='ชนิดไฟล์รูป Product ไม่รองรับ: %s' % content_type)
        data = await upload.read(MAX_PRODUCT_IMAGE_BYTES + 1)
        if len(data) > MAX_PRODUCT_IMAGE_BYTES:
            raise HTTPException(
                status_code=400,
                detail='รูป Product ต้องไม่เกิน 10 MiB ต่อไฟล์')
        slot = _PRODUCT_IMAGE_SLOT[match.group('slot')]
        if slot in job['images']:
            raise HTTPException(
                status_code=400, detail='ส่งรูป Product ช่องเดิมซ้ำ')
        job['images'][slot] = {
            'name': os.path.basename(str(
                getattr(upload, 'filename', '') or 'image')),
            'content_type': content_type,
            'bytes': data,
        }


def _parse_product_payload(payload: str) -> ProductRunRequest:
    failed = False
    decoded = None
    try:
        decoded = json.loads(
            payload,
            parse_int=_JsonNumberLexeme,
            parse_float=_JsonNumberLexeme,
            parse_constant=_JsonNumberLexeme,
        )
    except (json.JSONDecodeError, RecursionError):
        failed = True

    parsed = None
    if not failed:
        try:
            parsed = ProductRunRequest.model_validate(decoded)
        except (ValidationError, RecursionError):
            failed = True

    if failed or parsed is None:
        raise HTTPException(
            status_code=422, detail='ข้อมูล Product ไม่ถูกต้อง') from None
    return parsed


@router.post('/api/products/run')
async def products_run(
    request: Request,
    payload: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Preview one Product or explicitly create the checked Product queue."""
    from web import product_runner

    parsed = _parse_product_payload(payload)
    validation_detail = None
    try:
        jobs = [
            _clean_product(spec, product_number=number)
            for number, spec in enumerate(parsed.products, 1)
        ]
    except PayloadValueError as error:
        validation_detail = error.detail
        jobs = []
    if validation_detail is not None:
        raise HTTPException(
            status_code=400, detail=validation_detail) from None
    if not _nonblank_client_keys_are_unique(jobs):
        raise HTTPException(
            status_code=400, detail='client_key ของรายการห้ามซ้ำกัน')
    _prepare(parsed.game, jobs, parsed.do_save)
    await _product_images(request, jobs)

    settings: Settings = request.app.state.settings
    logs: list[dict] = []
    builder = product_runner.ProductBuilder(_collect(logs))
    result = await _run_activity(
        builder, jobs, game=parsed.game, do_save=parsed.do_save,
        request=request, db=db, user=user, tool='create_product',
        action='product.create' if parsed.do_save else 'product.preview_open',
        headed=settings.app_env != 'production')
    for row, job in zip(result['results'], jobs):
        row['client_key'] = job['client_key']
        row['source_group_key'] = job['source_group_key']
    return dict(result, logs=logs)


MAX_BUNDLE_ITEMS = 200


def _clean_items(raw: list[dict], *, bundle_number: int = 1) -> list[dict]:
    """Validate each Bundle item in order; never repair or truncate input."""
    if len(raw) > MAX_BUNDLE_ITEMS:
        raise _safe_failure(
            f'Bundle ที่ {bundle_number}: มีไอเทมได้ไม่เกิน 200 แถว')

    items: list[dict] = []
    seen: set[str] = set()
    for row, entry in enumerate(raw, 1):
        entry = entry if isinstance(entry, dict) else {}
        item_id = positive_int_text(
            entry.get('id'),
            f'Bundle ที่ {bundle_number}: Item ID แถว {row}')
        if item_id in seen:
            raise _safe_failure(
                f'Bundle ที่ {bundle_number}: Item ID ห้ามซ้ำกัน')
        seen.add(item_id)

        qty_source = entry['qty'] if 'qty' in entry else '1'
        qty = positive_int_text(
            qty_source,
            f'Bundle ที่ {bundle_number}: จำนวนไอเทมแถว {row}')

        tier_source = entry.get('tier')
        tier = tier_source.strip() if isinstance(tier_source, str) else ''
        tier = tier or 'Common'

        rate_source = entry['rate'] if 'rate' in entry else ''
        if isinstance(rate_source, str) and not rate_source.strip():
            rate = ''
        elif 'rate' not in entry:
            rate = ''
        else:
            rate = _decimal_with_rule(
                rate_source,
                f'Bundle ที่ {bundle_number}: เรทสุ่มแถว {row}',
                minimum=Decimal('0'), maximum=Decimal('100'), places=3,
                rule=_RANDOM_RATE_RULE)
            if Decimal(rate) <= 0:
                raise PayloadValueError(
                    f'Bundle ที่ {bundle_number}: เรทสุ่มแถว {row}',
                    _RANDOM_RATE_RULE)
        items.append({
            'id': item_id, 'qty': qty, 'tier': tier, 'rate': rate})
    return items


@router.post('/api/bundles/run')
async def bundles_run(payload: BundleRunRequest, request: Request,
                      user: User = Depends(require_user),
                      db: Session = Depends(get_db)):
    """Fill — and, only when asked, create — the bundles the operator built.

    No workspace: the Create Bundle page stands on its own, so items may be
    typed, pasted or sent over from a search. What guards this route is the
    session and the operator's own Aztek cookies, exactly as on the desktop
    tool where any item id can be entered by hand.

    ``do_save=False`` previews a single bundle and never writes. ``True`` runs
    the whole queue for real, one browser for the batch, and reports each id.
    """
    from web import bundle_runner

    settings: Settings = request.app.state.settings
    if payload.game not in item_finder.GAMES:
        raise HTTPException(status_code=400, detail='ไม่รู้จักเกม: %s' % payload.game)

    jobs = []
    validation_detail = None
    try:
        for index, spec in enumerate(payload.bundles, 1):
            if spec.bundle_type == 'RANDOM':
                raw_items = spec.items
            else:
                raw_items = [
                    dict(entry, rate='') for entry in spec.items
                ]
            items = _clean_items(raw_items, bundle_number=index)
            rewards = _clean_rewards(spec.rewards, bundle_number=index)
            if spec.bundle_type == 'RANDOM':
                for row, item in enumerate(items, 1):
                    if not item['rate']:
                        raise PayloadValueError(
                            f'Bundle ที่ {index}: เรทสุ่มแถว {row}',
                            _RANDOM_RATE_RULE)
            if not items and not rewards:
                raise _safe_failure(
                    f'Bundle ที่ {index}: ต้องมีไอเทมหรือ reward '
                    'อย่างน้อย 1 รายการ')
            jobs.append({
                'client_key': spec.client_key,
                'name': spec.name.strip() or f'Bundle {index}',
                'type': spec.bundle_type,
                'deliver': spec.deliver,
                'items': items,
                'rewards': rewards,
            })
    except PayloadValueError as error:
        validation_detail = error.detail
        jobs = []
    if validation_detail is not None:
        raise HTTPException(
            status_code=400, detail=validation_detail) from None
    if not jobs:
        raise HTTPException(status_code=400, detail='ไม่มีบันเดิลให้ทำ (ยังไม่มีไอเทม)')
    if not _nonblank_client_keys_are_unique(jobs):
        raise HTTPException(
            status_code=400, detail='client_key ของรายการห้ามซ้ำกัน')
    if not payload.do_save and len(jobs) != 1:
        raise HTTPException(status_code=400,
                            detail='ดูตัวอย่างได้ทีละบันเดิลเท่านั้น')

    storage_state = request.app.state.aztek_session_service.load_storage_state(db, user)
    if storage_state is None:
        raise HTTPException(status_code=409, detail='ยังไม่ได้เชื่อมเซสชัน Aztek')

    logs: list[dict] = []
    builder = bundle_runner.BundleBuilder(
        lambda message, level='INFO': logs.append({'msg': message, 'level': level}))
    # A real (watchable) window only makes sense where the server shares the
    # user's desktop — i.e. a local development run.
    headed = settings.app_env != 'production'
    action = 'bundle.create' if payload.do_save else 'bundle.preview_open'
    try:
        async with request.app.state.browser_gate.slot():
            if payload.do_save:
                # This run owns the single browser slot, so a window an earlier
                # preview left standing has to go first.
                await bundle_runner.close_kept(str(user.id))
                results = await builder.run_many(
                    game=payload.game, bundles=jobs, storage_state=storage_state,
                    headed=headed)
            else:
                job = jobs[0]
                outcome = await builder.run(
                    game=payload.game, name=job['name'], btype=job['type'],
                    deliver=job['deliver'], items=job['items'],
                    storage_state=storage_state, headed=headed,
                    rewards=job['rewards'], do_save=False,
                    # Keyed per operator so one person's leftover window is the only
                    # one their next run closes.
                    keep_open_key=str(user.id))
                results = [{
                    'name': job['name'], 'saved': False, 'bundle_id': None,
                    'added': outcome['added'], 'total': outcome['total'],
                    'rewards_added': outcome['rewards_added'],
                    'rewards_total': outcome['rewards_total'],
                    'error': None, 'kept_open': outcome['kept_open'],
                    'screenshot': outcome.get('screenshot'),
                }]
    except Exception as exc:
        write_audit(
            db, user_id=user.id, action=action, status='failed',
            summary={'error': str(exc)[:200], 'game': payload.game,
                     'planned': len(jobs)},
            tool='create_bundle', resource_type='aztek_session',
            resource_id=user.id, request=request)
        raise HTTPException(status_code=502, detail='ทำรายการบันเดิลไม่สำเร็จ: %s' % exc)

    for entry, job in zip(results, jobs):
        entry['client_key'] = job['client_key']

    screenshot_b64 = None
    for entry in results:
        shot = entry.pop('screenshot', None)
        if shot and screenshot_b64 is None:
            import base64
            screenshot_b64 = base64.b64encode(shot).decode('ascii')
        # Each bundle is audited on its own: a run that half-succeeds must leave
        # a record of exactly which bundles exist now.
        write_audit(
            db, user_id=user.id, action=action,
            status='success' if (entry['saved'] or not payload.do_save) else 'failed',
            summary={'game': payload.game, 'name': entry['name'],
                     'added': entry['added'], 'total': entry['total'],
                     'rewards': entry['rewards_added'],
                     'bundle_id': entry['bundle_id'], 'error': entry['error']},
            tool='create_bundle', resource_type='aztek_session',
            resource_id=user.id, request=request)
    return {'results': results, 'logs': logs, 'headed': headed,
            'screenshot_b64': screenshot_b64,
            'created': sum(1 for r in results if r['saved']),
            'planned': len(jobs)}

MAX_ACTIVITIES = 30
MAX_REWARD_SETS = 20
_SLUG = re.compile(r'^[a-z0-9-]+$')


def _collect(logs: list):
    """A log sink that keeps the lines for the response."""
    return lambda message, level='INFO': logs.append(
        {'msg': message, 'level': level})


def _require_slug(slug: str, where: str) -> str:
    """Aztek only takes lowercase-and-hyphens, and says so after the trip.

    Checking here costs nothing and saves opening a browser to be told.
    """
    slug = str(slug or '').strip()
    if not _SLUG.match(slug):
        raise HTTPException(
            status_code=400,
            detail='slug ของ%s ต้องเป็น a-z 0-9 และขีดกลางเท่านั้น: %r'
                   % (where, slug))
    return slug


def _require_datetime(value: str, label: str, where: str) -> str:
    value = str(value or '').strip()
    if aztek_form.parse_datetime(value) is None:
        raise HTTPException(
            status_code=400,
            detail='%s ของ%s ต้องเป็นวันเวลาที่ถูกต้อง: %r' % (label, where, value))
    return value


def _require_order(start: str, end: str, labels: tuple, where: str) -> None:
    """An end before its start is never what was meant.

    Plan files get re-used for the next run of the same activity, so a date
    that has already passed reaches this route more often than it should.
    """
    if aztek_form.parse_datetime(start) >= aztek_form.parse_datetime(end):
        raise HTTPException(
            status_code=400,
            detail='%s ของ%s ต้องมาก่อน%s (ตอนนี้ %s → %s)'
                   % (labels[0], where, labels[1], start, end))


def _reward_head(entry: dict, *, family: str = 'Item Code', number: int = 1,
                 row: int = 1) -> dict:
    """Canonical numeric fields shared by Item Code and Event rewards."""
    prefix = f'{family} ที่ {number}: ชุดรางวัลที่ {row}'
    name_th_source = entry.get('name_th')
    name_en_source = entry.get('name_en')
    name_th = name_th_source.strip() if isinstance(name_th_source, str) else ''
    name_en = name_en_source.strip() if isinstance(name_en_source, str) else ''

    uses_source = entry['uses_per_user'] if 'uses_per_user' in entry else '1'
    uses_per_user = positive_int_text(
        uses_source, f'{prefix}: จำนวนครั้งต่อผู้ใช้')

    if 'limited' in entry:
        limited = strict_bool(entry['limited'], f'{prefix}: จำกัดจำนวน')
    else:
        limited = False
    if limited:
        quantity = positive_int_text(
            entry.get('quantity'), f'{prefix}: จำนวนครั้ง')
        remaining = positive_int_text(
            entry.get('remaining'), f'{prefix}: จำนวนคงเหลือ')
    else:
        quantity = ''
        remaining = ''

    bundle_id = positive_int_text(
        entry.get('bundle_id'), f'{prefix}: Bundle ID')
    return {
        'name_th': name_th,
        'name_en': name_en,
        'uses_per_user': uses_per_user,
        'limited': limited,
        'quantity': quantity,
        'remaining': remaining,
        'bundle_id': bundle_id,
    }


def _clean_itemcode_rewards(
    raw: list[dict],
    *,
    itemcode_number: int = 1,
) -> list[dict]:
    """Validate every Item Code reward set and preserve its position."""
    from web import itemcode_runner

    if len(raw) > MAX_REWARD_SETS:
        raise _safe_failure(
            f'Item Code ที่ {itemcode_number}: '
            'มีชุดรางวัลได้ไม่เกิน 20 ชุด')
    cleaned = []
    for row, entry in enumerate(raw, 1):
        reward = _reward_head(
            entry, family='Item Code', number=itemcode_number, row=row)
        reward['code_type'] = itemcode_runner.code_type_value(
            entry.get('code_type'))
        reward['code_list'] = str(entry.get('code_list') or '')
        reward['prefix'] = str(entry.get('prefix') or '').strip()
        if reward['code_type'] == '2':
            reward['num_codes'] = positive_int_text(
                entry.get('num_codes'),
                f'Item Code ที่ {itemcode_number}: ชุดรางวัลที่ {row}: '
                'จำนวนโค้ด')
        else:
            reward['num_codes'] = ''
        cleaned.append(reward)
    return cleaned


def _clean_event_rewards(
    raw: list[dict],
    *,
    event_number: int = 1,
) -> list[dict]:
    if len(raw) > MAX_REWARD_SETS:
        raise _safe_failure(
            f'Event ที่ {event_number}: มีชุดรางวัลได้ไม่เกิน 20 ชุด')
    cleaned = []
    for row, entry in enumerate(raw, 1):
        reward = _reward_head(
            entry, family='Event', number=event_number, row=row)
        cleaned.append(reward)
    return cleaned


async def _run_activity(builder, specs, *, game, do_save, request, db, user,
                        tool, action, headed):
    """Preview one form, or create the whole queue — shared by both tools."""
    # Imported here, like the runners themselves, so importing this module does
    # not pull in playwright.
    from web import activity_runner

    storage_state = request.app.state.aztek_session_service.load_storage_state(
        db, user)
    if storage_state is None:
        raise HTTPException(status_code=409, detail='ยังไม่ได้เชื่อมเซสชัน Aztek')
    try:
        async with request.app.state.browser_gate.slot():
            if do_save:
                # This run owns the single browser slot, so a window an earlier
                # preview left standing has to go first.
                await activity_runner.close_kept(str(user.id))
                results = await builder.run_many(
                    game=game, specs=specs, storage_state=storage_state,
                    headed=headed)
            else:
                spec = specs[0]
                outcome = await builder.run(
                    game=game, spec=spec, storage_state=storage_state,
                    headed=headed, keep_open_key=str(user.id))
                results = [{
                    'name': spec.get('name_th') or spec.get('slug') or '',
                    'slug': spec.get('slug', ''),
                    'group': spec.get('group', ''), 'saved': False,
                    'made_id': None, 'missing': outcome['missing'],
                    'error': None, 'kept_open': outcome['kept_open'],
                    'screenshot': outcome.get('screenshot'),
                }]
    except Exception as exc:
        write_audit(
            db, user_id=user.id, action=action, status='failed',
            summary={'error': str(exc)[:200], 'game': game,
                     'planned': len(specs)},
            tool=tool, resource_type='aztek_session', resource_id=user.id,
            request=request)
        raise HTTPException(status_code=502, detail='ทำรายการไม่สำเร็จ: %s' % exc)

    for entry, spec in zip(results, specs):
        entry['client_key'] = spec.get('client_key', '')

    screenshot_b64 = None
    for entry in results:
        shot = entry.pop('screenshot', None)
        if shot and screenshot_b64 is None:
            import base64
            screenshot_b64 = base64.b64encode(shot).decode('ascii')
        # One record each: a run that half-succeeds must leave a trail of
        # exactly which ones exist now.
        write_audit(
            db, user_id=user.id, action=action,
            status='success' if (entry['saved'] or not do_save) else 'failed',
            summary={'game': game, 'name': entry['name'],
                     'slug': entry['slug'], 'made_id': entry['made_id'],
                     'missing': entry['missing'][:5], 'error': entry['error']},
            tool=tool, resource_type='aztek_session', resource_id=user.id,
            request=request)
    return {'results': results, 'headed': headed,
            'screenshot_b64': screenshot_b64,
            'created': sum(1 for r in results if r['saved']),
            'planned': len(specs)}


def _prepare(payload_game, jobs, do_save):
    """Shared gatekeeping: a known game, something to do, one at a time to preview."""
    if payload_game not in item_finder.GAMES:
        raise HTTPException(status_code=400,
                            detail='ไม่รู้จักเกม: %s' % payload_game)
    if not jobs:
        raise HTTPException(status_code=400, detail='ยังไม่มีรายการให้ทำ')
    if not do_save and len(jobs) != 1:
        raise HTTPException(status_code=400, detail='ดูตัวอย่างได้ทีละรายการเท่านั้น')


@router.post('/api/itemcodes/import')
async def itemcodes_import(request: Request, file: UploadFile = File(...),
                           game: str = Form(''),
                           user: User = Depends(require_user),
                           db: Session = Depends(get_db)):
    """Read a plan file straight into Item Code drafts, tab by tab.

    No workspace and no search: everything an Item Code needs is in the
    conditions block above each prize table, so the file can be looked at here
    before deciding whether any items need finding at all. Drafts carry the
    sheet they came from so the page can offer the tabs to pick from.
    """
    from web import itemcode_plan

    path = await _temporary_upload(file)
    try:
        sheets, skipped = await asyncio.to_thread(
            item_service.parse_workbook_locked,
            item_service.parser_for_mode('itemcode'), path)
    except Exception as error:
        raise HTTPException(status_code=400,
                            detail='อ่านไฟล์ไม่สำเร็จ: %s' % error)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    drafts = []
    counts = []
    for name, rows in sheets:
        # One group per prize table, first row wins — they all carry the same
        # conditions, which is what a draft is made of.
        group_meta = {}
        for row in rows:
            group = (row.get('sources') or [''])[0]
            if group and group not in group_meta:
                group_meta[group] = row.get('group_meta') or {}
        made = itemcode_plan.build_itemcodes(group_meta, game)
        for draft in made:
            draft['sheet'] = name
        drafts.extend(made)
        counts.append({
            'name': name,
            'display_name': item_service.sheet_display_name(name, rows),
            'count': len(made),
        })

    write_audit(
        db, user_id=user.id, action='itemcode.imported', status='success',
        summary={'filename': file.filename or 'plan.xlsx', 'game': game,
                 'sheets': len(counts), 'drafts': len(drafts)},
        tool='create_itemcode', resource_type='user', resource_id=user.id,
        request=request,
    )
    return {'sheets': counts, 'itemcodes': drafts, 'skipped': list(skipped or [])}


@router.post('/api/itemcodes/run')
async def itemcodes_run(payload: ItemCodeRunRequest, request: Request,
                        user: User = Depends(require_user),
                        db: Session = Depends(get_db)):
    """Fill — and only when asked, create — the Item Codes in the queue."""
    from web import itemcode_runner

    settings: Settings = request.app.state.settings
    if len(payload.itemcodes) > MAX_ACTIVITIES:
        raise HTTPException(
            status_code=400,
            detail='Item Code ทำได้ไม่เกิน 30 รายการต่อครั้ง')
    jobs = []
    result_slots = []
    batch_create = payload.do_save and len(payload.itemcodes) > 1
    validation_detail = None
    for index, spec in enumerate(payload.itemcodes, 1):
        try:
            prefix = f'Item Code ที่ {index}'
            where = spec.name_th.strip() or prefix
            limited = spec.limited
            uses_per_user = positive_int_text(
                spec.uses_per_user, f'{prefix}: จำนวนครั้งต่อผู้ใช้')
            if limited:
                quantity = positive_int_text(
                    spec.quantity,
                    f'{prefix}: จำนวนครั้งที่สามารถใช้งานได้')
                remaining = positive_int_text(
                    spec.remaining, f'{prefix}: จำนวนคงเหลือ')
            else:
                quantity = ''
                remaining = ''
            job = {
                'client_key': spec.client_key,
                'name_th': spec.name_th.strip(),
                'name_en': spec.name_en.strip(),
                'slug': _require_slug(spec.slug, where),
                'uses_per_user': uses_per_user,
                'limited': limited,
                'quantity': quantity,
                'remaining': remaining,
                'start_time': _require_datetime(
                    spec.start_time, 'เวลาเริ่มใช้งาน', where),
                'end_time': _require_datetime(
                    spec.end_time, 'เวลาสิ้นสุด', where),
                'group': spec.group,
                'rewards': _clean_itemcode_rewards(
                    spec.rewards, itemcode_number=index),
            }
            _require_order(job['start_time'], job['end_time'],
                           ('เวลาเริ่มใช้งาน', 'เวลาสิ้นสุด'), where)
            jobs.append(job)
            result_slots.append(None)
        except (PayloadValueError, HTTPException) as error:
            if isinstance(error, HTTPException) and error.status_code != 400:
                raise
            detail = error.detail
            if not batch_create:
                validation_detail = detail
                jobs = []
                break
            result_slots.append({
                'client_key': spec.client_key,
                'name': spec.name_th.strip() or spec.slug or prefix,
                'slug': spec.slug,
                'group': spec.group,
                'saved': False,
                'made_id': None,
                'missing': [],
                'error': detail,
            })
    if validation_detail is not None:
        raise HTTPException(
            status_code=400, detail=validation_detail) from None
    if not _nonblank_client_keys_are_unique(jobs):
        raise HTTPException(
            status_code=400, detail='client_key ของรายการห้ามซ้ำกัน')
    if batch_create and not jobs:
        if payload.game not in item_finder.GAMES:
            raise HTTPException(
                status_code=400, detail='ไม่รู้จักเกม: %s' % payload.game)
        return {
            'results': result_slots,
            'headed': settings.app_env != 'production',
            'screenshot_b64': None,
            'created': 0,
            'planned': len(payload.itemcodes),
            'logs': [],
        }
    _prepare(payload.game, jobs, payload.do_save)
    builder = itemcode_runner.ItemCodeBuilder(_collect(logs := []))
    result = await _run_activity(
        builder, jobs, game=payload.game, do_save=payload.do_save,
        request=request, db=db, user=user, tool='create_itemcode',
        action='itemcode.create' if payload.do_save else 'itemcode.preview_open',
        headed=settings.app_env != 'production')
    if batch_create and any(slot is not None for slot in result_slots):
        valid_results = iter(result['results'])
        merged_results = [
            slot if slot is not None else next(valid_results)
            for slot in result_slots
        ]
        result = dict(
            result,
            results=merged_results,
            created=sum(1 for row in merged_results if row['saved']),
            planned=len(payload.itemcodes),
        )
    return dict(result, logs=logs)


@router.post('/api/events/import')
async def events_import(request: Request, file: UploadFile = File(...),
                        game: str = Form(''),
                        user: User = Depends(require_user),
                        db: Session = Depends(get_db)):
    """Read a workbook into one editable Event draft per recognized sheet."""
    import event_tool
    from web import event_plan

    path = await _temporary_upload(file)
    try:
        parsed = await asyncio.to_thread(
            item_service.parse_workbook_locked,
            event_tool.parse_event_plan, path)
    except Exception as error:
        raise HTTPException(
            status_code=400, detail='อ่านไฟล์ Event ไม่สำเร็จ: %s' % error)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    drafts = event_plan.build_event_drafts(parsed, game)
    counts = [
        {
            'name': sheet,
            'display_name': str((event or {}).get('name') or sheet).strip(),
            'count': len((event or {}).get('rewards') or []),
        }
        for sheet, event in parsed
        if (event or {}).get('rewards')
    ]
    write_audit(
        db, user_id=user.id, action='event.imported', status='success',
        summary={'filename': file.filename or 'plan.xlsx', 'game': game,
                 'sheets': len(counts), 'drafts': len(drafts)},
        tool='create_event', resource_type='user', resource_id=user.id,
        request=request,
    )
    return {'sheets': counts, 'events': drafts, 'skipped': []}


@router.post('/api/events/run')
async def events_run(payload: EventRunRequest, request: Request,
                     user: User = Depends(require_user),
                     db: Session = Depends(get_db)):
    """Fill — and only when asked, create — the Events in the queue."""
    from web import event_runner

    settings: Settings = request.app.state.settings
    if len(payload.events) > MAX_ACTIVITIES:
        raise HTTPException(
            status_code=400, detail='Event ทำได้ไม่เกิน 30 รายการต่อครั้ง')
    jobs = []
    validation_detail = None
    try:
        for index, spec in enumerate(payload.events, 1):
            prefix = f'Event ที่ {index}'
            where = spec.name_th.strip() or prefix
            job = {
                'client_key': spec.client_key,
                'slug': _require_slug(spec.slug, where),
                'name_th': spec.name_th.strip(),
                'name_en': spec.name_en.strip(),
                'type': spec.kind,
                'uses_per_user': positive_int_text(
                    spec.uses_per_user, f'{prefix}: จำนวนครั้งต่อผู้ใช้'),
                'quantity': non_negative_int_text(
                    spec.quantity, f'{prefix}: จำนวนรางวัลทั้งหมด'),
                'remaining': non_negative_int_text(
                    spec.remaining, f'{prefix}: จำนวนคงเหลือ'),
                'group': spec.group,
                'rewards': _clean_event_rewards(
                    spec.rewards, event_number=index),
            }
            for key, label in (('start_event', 'วันเริ่มกิจกรรม'),
                               ('end_event', 'วันสิ้นสุดกิจกรรม'),
                               ('start_claim', 'วันเริ่มรับรางวัล'),
                               ('end_claim', 'วันสิ้นสุดการรับรางวัล')):
                job[key] = _require_datetime(getattr(spec, key), label, where)
            _require_order(job['start_event'], job['end_event'],
                           ('วันเริ่มกิจกรรม', 'วันสิ้นสุดกิจกรรม'), where)
            _require_order(job['start_claim'], job['end_claim'],
                           ('วันเริ่มรับรางวัล', 'วันสิ้นสุดการรับรางวัล'), where)
            jobs.append(job)
    except PayloadValueError as error:
        validation_detail = error.detail
        jobs = []
    if validation_detail is not None:
        raise HTTPException(
            status_code=400, detail=validation_detail) from None
    if not _nonblank_client_keys_are_unique(jobs):
        raise HTTPException(
            status_code=400, detail='client_key ของรายการห้ามซ้ำกัน')
    _prepare(payload.game, jobs, payload.do_save)
    builder = event_runner.EventBuilder(_collect(logs := []))
    result = await _run_activity(
        builder, jobs, game=payload.game, do_save=payload.do_save,
        request=request, db=db, user=user, tool='create_event',
        action='event.create' if payload.do_save else 'event.preview_open',
        headed=settings.app_env != 'production')
    return dict(result, logs=logs)


@router.websocket('/ws/search')
async def ws_search(ws: WebSocket):
    """Authenticate and own-check, then delegate to the search coordinator."""
    application = ws.scope['app']
    raw_session = ws.cookies.get('afc_session', '')
    with application.state.database.session() as db:
        user = application.state.auth_service.resolve_session(db, raw_session)
    if user is None:
        await ws.close(code=4401)
        return
    await ws.accept()
    try:
        request = await ws.receive_json()
    except Exception:
        await ws.close()
        return

    workspace_id = str(request.get('workspace_id') or '')
    user_id = user.id
    with application.state.database.session() as db:
        try:
            WorkspaceRepository(db).get_owned(user_id, workspace_id)
        except WorkspaceNotFound:
            await ws.close(code=4404)
            return

    async def send(message):
        await ws.send_json(message)

    coordinator = application.state.search_coordinator
    try:
        # The socket is a watcher, not the owner. Starting is a no-op when a
        # search for this workspace is already going — reconnecting after a trip
        # to another page attaches to it and replays the log so far.
        started = await coordinator.start(user_id, workspace_id, request, send)
        if started:
            await coordinator.attach(
                workspace_id, send, request.get('source_group_key') or '')
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass


@router.post('/api/workspaces/{workspace_id}/search/stop')
def stop_search(workspace_id: str, request: Request,
                user: User = Depends(require_user),
                db: Session = Depends(get_db)):
    """Stop a running search.

    Its own route rather than a closed socket: the run no longer belongs to any
    one page, so stopping has to be something the operator asks for explicitly
    — from whichever page they happen to be on.
    """
    _get_workspace(WorkspaceRepository(db), user.id, workspace_id)
    stopped = request.app.state.search_coordinator.stop(workspace_id)
    if stopped:
        write_audit(
            db, user_id=user.id, action='item_finder.stopped', status='success',
            summary={}, tool='item_finder', resource_type='workspace',
            resource_id=workspace_id, request=request)
    return {'stopped': stopped}


def create_app(
    settings: Settings | None = None,
    database: Database | None = None,
    monotonic_clock: Callable[[], float] = time.monotonic,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    resolved_settings.validate()
    resolved_database = database or Database(resolved_settings)
    auth_service = AuthService(resolved_settings)
    local_access = LocalAccessService(
        resolved_settings,
        auth_service,
        monotonic_clock,
    )
    aztek_session_service = AztekSessionService(resolved_settings)
    browser_gate = BrowserOperationGate(resolved_settings.browser_concurrency)
    local_aztek_capture = LocalAztekCaptureService(
        resolved_settings, browser_gate)
    search_coordinator = SearchCoordinator(
        resolved_database, resolved_settings, aztek_session_service,
        browser_gate=browser_gate)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        with application.state.database.session() as db:
            application.state.auth_service.bootstrap_admin(db)
        # A search only lives as long as the process driving it, so anything
        # still marked running belongs to a process that is gone.
        stale = application.state.search_coordinator.sweep_interrupted_jobs()
        if stale:
            warnings.warn('marked %d interrupted search job(s) as failed' % stale,
                          RuntimeWarning, stacklevel=2)
        yield

    application = FastAPI(title='All for Cabal — Web', lifespan=lifespan)
    application.add_middleware(RequestSizeLimitMiddleware)
    application.state.settings = resolved_settings
    application.state.database = resolved_database
    application.state.auth_service = auth_service
    application.state.local_access = local_access
    application.state.aztek_session_service = aztek_session_service
    application.state.browser_gate = browser_gate
    application.state.local_aztek_capture = local_aztek_capture
    application.state.search_coordinator = search_coordinator
    application.state.login_throttle = LoginThrottle(monotonic_clock)
    application.state.pairing_throttle = LoginThrottle(monotonic_clock)
    application.state.pairing_issue_reservations = PairingIssueReservations()
    application.include_router(router)
    return application


app = create_app()
