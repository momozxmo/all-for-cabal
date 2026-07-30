# -*- coding: utf-8 -*-
"""All for Cabal Web — local Item Finder application."""
import asyncio
import hashlib
import hmac
import os
import re
import sys
import tempfile
import threading
import time
import warnings
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import (APIRouter, Cookie, Depends, FastAPI, File, Form,
                     HTTPException, Request, Response, UploadFile, WebSocket,
                     WebSocketDisconnect)
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                               RedirectResponse)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import item_finder  # noqa: E402
from web import aztek_form, item_service, search_runner  # noqa: E402
from web.audit import write_audit  # noqa: E402
from web.auth_service import AuthService  # noqa: E402
from web.aztek_sessions import (AztekSessionService, InvalidStorageState,  # noqa: E402
                                PairingTokenNotFound, PairingTokenUnavailable)
from web.db import Database  # noqa: E402
from web.local_access import LocalAccessService  # noqa: E402
from web.models import Job, User, utc_now  # noqa: E402
from web.search_coordinator import SearchCoordinator  # noqa: E402
from web.security import hash_password, hash_token, verify_password  # noqa: E402
from web.settings import Settings  # noqa: E402
from web.workspaces import (PendingImportNotFound, WorkspaceNotFound,
                            WorkspaceRepository)  # noqa: E402


router = APIRouter()
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
# Retained for compatibility with legacy callers; handlers never use it as data.
WORKSPACES = item_service.WorkspaceStore()
Mode = Literal['event', 'itemcode', 'shop']


class ApplyPlanRequest(BaseModel):
    pending_id: str
    selected_sheets: list[str]


class BundleRequest(BaseModel):
    selected_indexes: list[int] = Field(default_factory=list)


class BundleSpec(BaseModel):
    """One bundle as the operator built it on the Create Bundle page.

    Items are whatever they typed, pasted or sent over from Item Finder — the
    page is a tool in its own right, so nothing here is tied to a search.
    """
    name: str = Field(default='', max_length=200)
    bundle_type: Literal['FIXED', 'CHOICE', 'RANDOM'] = 'FIXED'
    deliver: bool = True
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
    do_save: bool = False


class ItemCodeSpec(BaseModel):
    """One Item Code as the operator filled it in.

    ``rewards`` is a list of sets: each carries its own codes and exactly one
    bundle, because v2 replaces a reward set's bundle rather than adding to it.

    The type is not a field: an Item Code is always ALL. Neither are the
    descriptions or the code-wide "จำกัดจำนวน" — those are not part of how
    these are written, and the counts live on the reward set.
    """
    name_th: str = Field(default='', max_length=200)
    name_en: str = Field(default='', max_length=200)
    slug: str = Field(default='', max_length=120)
    uses_per_user: str = Field(default='1', max_length=12)
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
    do_save: bool = False


class EventSpec(BaseModel):
    """One Event. The bundle ids come from the plan, so nothing is searched."""
    slug: str = Field(default='', max_length=120)
    name_th: str = Field(default='', max_length=200)
    name_en: str = Field(default='', max_length=200)
    kind: Literal['WINNER', 'ALL'] = 'WINNER'
    uses_per_user: str = Field(default='1', max_length=12)
    quantity: str = Field(default='0', max_length=12)
    remaining: str = Field(default='0', max_length=12)
    start_event: str = Field(default='', max_length=32)
    end_event: str = Field(default='', max_length=32)
    start_claim: str = Field(default='', max_length=32)
    end_claim: str = Field(default='', max_length=32)
    group: str = Field(default='', max_length=200)
    rewards: list[dict] = Field(default_factory=list)


class EventRunRequest(BaseModel):
    game: str = Field(min_length=1, max_length=64)
    events: list[EventSpec] = Field(default_factory=list)
    do_save: bool = False


class RewardOptionsRequest(BaseModel):
    game: str = Field(min_length=1, max_length=64)


class ProductOptionsRequest(BaseModel):
    game: str = Field(min_length=1, max_length=64)
    kinds: list[Literal['currencies', 'categories']] = Field(
        default_factory=lambda: ['currencies', 'categories'])


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
    tags: list[Literal['EVENT', 'HOT', 'LIMITED', 'NEW', 'SALE']] = Field(
        default_factory=list, max_length=5)
    is_enabled: bool = False
    is_test_mode: bool = True
    is_hidden: bool = False
    position: str = Field(default='0', max_length=12)


class ProductRunRequest(BaseModel):
    game: str = Field(min_length=1, max_length=64)
    products: list[ProductSpec] = Field(default_factory=list, max_length=30)
    do_save: bool = False


class LoginRequest(BaseModel):
    username: str
    password: str


class LocalLaunchRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class StorageStatePayload(BaseModel):
    pairing_token: str = Field(min_length=20, max_length=200)
    account_label: str | None = Field(default=None, max_length=120)
    storage_state: dict


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
    return {'job_id': job.id, 'status': job.status}


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


async def _temporary_upload(file):
    suffix = os.path.splitext(file.filename or '')[1] or '.xlsx'
    raw = await file.read()
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        handle.write(raw)
        handle.close()
    except Exception:
        handle.close()
        try:
            os.unlink(handle.name)
        except OSError:
            pass
        raise
    return handle.name


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
    response = Response(status_code=204)
    _clear_session_cookie(response, request.app.state.settings)
    return response


@router.post('/api/aztek/pairing-token')
def create_pairing_token(request: Request, user: User = Depends(require_user),
                         db: Session = Depends(get_db)):
    issue = request.app.state.aztek_session_service.create_pairing_token(db, user)
    write_audit(
        db, user_id=user.id, action='aztek.pairing_requested', status='success',
        tool='aztek', resource_type='aztek_session', resource_id=user.id,
        request=request,
    )
    return {'pairing_token': issue.raw_token, 'expires_at': issue.expires_at.isoformat()}


@router.post('/api/aztek/pair')
def pair_aztek_session(payload: StorageStatePayload, request: Request,
                       db: Session = Depends(get_db)):
    # The only endpoint authenticated by pairing token instead of a cookie.
    client_ip = request.client.host if request.client else 'unknown'
    settings: Settings = request.app.state.settings
    throttle: LoginThrottle = request.app.state.pairing_throttle
    throttle_key = '%s|%s' % (
        client_ip, hash_token(payload.pairing_token, settings))
    if throttle.is_limited(throttle_key):
        return JSONResponse({'detail': 'ลองใหม่ภายหลัง'}, status_code=429)

    service: AztekSessionService = request.app.state.aztek_session_service
    try:
        session = service.consume_pairing_token(
            db, payload.pairing_token, payload.storage_state, payload.account_label)
    except PairingTokenNotFound:
        throttle.record_failure(throttle_key)
        raise HTTPException(status_code=404, detail='ไม่พบรหัสจับคู่')
    except PairingTokenUnavailable:
        throttle.record_failure(throttle_key)
        raise HTTPException(status_code=410, detail='รหัสจับคู่หมดอายุหรือถูกใช้ไปแล้ว')
    except InvalidStorageState as exc:
        throttle.record_failure(throttle_key)
        raise HTTPException(status_code=422, detail='ข้อมูลเซสชันไม่ถูกต้อง: %s' % str(exc))
    throttle.clear(throttle_key)
    write_audit(
        db, user_id=session.user_id, action='aztek.connected', status='success',
        tool='aztek', resource_type='aztek_session', resource_id=session.user_id,
        request=request,
    )
    return {'status': 'connected', 'account_label': session.account_label}


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


def _clean_rewards(raw: list[dict]) -> list[dict]:
    """Keep only well-formed rewards: a known kind, a value, a positive count."""
    # Imported here (like the endpoint below) so module import does not pull in
    # playwright.
    from web import bundle_runner

    cleaned = []
    for entry in raw:
        kind = str(entry.get('type') or '').strip().upper()
        value = str(entry.get('value') or '').strip()
        if kind not in bundle_runner.REWARD_KINDS or not value:
            continue
        try:
            qty = int(str(entry.get('qty') or '1').strip())
        except ValueError:
            continue
        if qty < 1:
            continue
        cleaned.append({'type': kind, 'value': value, 'qty': str(qty)})
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
    try:
        workspace = WorkspaceRepository(db).apply_pending(user.id, pending_id, selected)
    except (PendingImportNotFound, WorkspaceNotFound):
        raise HTTPException(status_code=404, detail='ไม่พบไฟล์นำเข้าที่รอเลือก sheet')
    write_audit(
        db, user_id=user.id, action='plan.applied', status='success',
        summary={'count': len(selected), 'mode': workspace.mode},
        tool='item_finder', resource_type='workspace', resource_id=workspace.id,
        request=request,
    )
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
    repository.delete_owned(user.id, workspace_id)
    write_audit(
        db, user_id=user.id, action='workspace.deleted', status='success',
        summary={'mode': workspace.mode, 'filename': workspace.filename},
        tool='item_finder', resource_type='workspace', resource_id=workspace_id,
        request=request,
    )
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
    from web import event_plan

    workspace = _get_workspace(WorkspaceRepository(db), user.id, workspace_id)
    indexes = payload.selected_indexes
    if indexes:
        rows = [workspace.results[index] for index in sorted(set(indexes))
                if isinstance(index, int) and 0 <= index < len(workspace.results)]
    else:
        rows = workspace.results
    if not rows:
        raise HTTPException(status_code=400, detail='ไม่มีไอเทมให้รวมเป็นบันเดิล')
    bundles = item_service.build_bundles(rows, workspace.group_meta)
    group_keys = [bundle.get('group_key') for bundle in bundles
                  if bundle.get('group_key')]
    event_drafts = event_plan.build_workspace_events(
        workspace.group_meta, workspace.game, group_keys=group_keys
    ) if workspace.mode == 'event' else []
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
        options = await bundle_runner.fetch_reward_options(
            payload.game, storage_state,
            lambda message, level='INFO': logs.append({'msg': message, 'level': level}))
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


def _positive_digits(value: str, label: str, where: str,
                     *, optional=False) -> str:
    text = str(value or '').strip()
    if optional and not text:
        return ''
    if not text.isdigit() or int(text) <= 0:
        raise HTTPException(
            status_code=400,
            detail='%s ของ%s ต้องเป็นจำนวนเต็มมากกว่า 0' % (label, where))
    return text


def _clean_product(spec: ProductSpec) -> dict:
    name_th = spec.name_th.strip()
    name_en = spec.name_en.strip()
    where = name_th or name_en or 'Product'
    if not name_th:
        raise HTTPException(
            status_code=400, detail='ชื่อ Product (ไทย) ของ%s ห้ามว่าง' % where)
    if not name_en:
        raise HTTPException(
            status_code=400, detail='ชื่อ Product (อังกฤษ) ของ%s ห้ามว่าง' % where)
    category_id = spec.category_id.strip()
    if not category_id:
        raise HTTPException(
            status_code=400, detail='หมวดหมู่ของ%s ห้ามว่าง' % where)
    start_at = _require_datetime(spec.start_at, 'วันเริ่มขาย', where)
    end_at = _require_datetime(spec.end_at, 'วันสิ้นสุด', where)
    _require_order(
        start_at, end_at, ('วันเริ่มขาย', 'วันสิ้นสุด'), where)
    bundle_id = _positive_digits(spec.bundle_id, 'Bundle ID', where)
    try:
        position = str(int(spec.position.strip() or '0'))
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail='ตำแหน่งของ%s ต้องเป็นตัวเลขจำนวนเต็ม' % where)

    prices = []
    currency_ids = set()
    for number, price in enumerate(spec.prices, 1):
        currency_id = price.currency_id.strip()
        if currency_id in currency_ids:
            raise HTTPException(
                status_code=400,
                detail='Currency ของ%s ซ้ำกัน: %s' % (where, currency_id))
        currency_ids.add(currency_id)
        prices.append({
            'currency_id': currency_id,
            'currency_slug': price.currency_slug.strip(),
            'currency_label': price.currency_label.strip(),
            'original_price': price.original_price,
            'price': price.price,
        })
    if not prices:
        raise HTTPException(
            status_code=400, detail='สกุลเงินของ%s ห้ามว่าง' % where)

    limit_quantity = spec.limit_quantity.strip()
    reset_interval = spec.limit_reset_interval_days.strip()
    reset_at = spec.limit_reset_at.strip()
    if spec.limit_type != 'UNLIMITED':
        limit_quantity = _positive_digits(
            limit_quantity, 'จำนวนที่ซื้อได้', where)
    if reset_interval:
        reset_interval = _positive_digits(
            reset_interval, 'รอบรีเซ็ต', where)
    if reset_at:
        reset_at = _require_datetime(reset_at, 'เวลารีเซ็ต', where)

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
        'bundle_id': bundle_id,
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


@router.post('/api/products/run')
async def products_run(
    request: Request,
    payload: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Preview one Product or explicitly create the checked Product queue."""
    from pydantic import ValidationError
    from web import product_runner

    try:
        parsed = ProductRunRequest.model_validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail='ข้อมูล Product ไม่ถูกต้อง: %s' % exc)
    jobs = [_clean_product(spec) for spec in parsed.products]
    keys = [job['client_key'] for job in jobs]
    if len(keys) != len(set(keys)):
        raise HTTPException(
            status_code=400, detail='client_key ของ Product ห้ามซ้ำ')
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


def _clean_items(raw: list[dict]) -> list[dict]:
    """Keep the item rows that name a real id, in the order they were given.

    Order is the operator's: the plan file — or the column they pasted — lists
    items the way the bundle should read. Duplicates are dropped because Aztek
    refuses the second copy anyway.
    """
    items: list[dict] = []
    seen: set[str] = set()
    for entry in raw:
        digits = re.search(r'\d+', str(entry.get('id') or ''))
        if not digits or digits.group() in seen:
            continue
        item_id = digits.group()
        seen.add(item_id)
        try:
            qty = max(1, int(str(entry.get('qty') or '1').strip() or '1'))
        except ValueError:
            qty = 1
        items.append({'id': item_id, 'qty': str(qty),
                      'tier': str(entry.get('tier') or 'Common').strip() or 'Common',
                      'rate': str(entry.get('rate') or '').strip()})
        if len(items) >= MAX_BUNDLE_ITEMS:
            break
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
    for index, spec in enumerate(payload.bundles):
        items = _clean_items(spec.items)
        rewards = _clean_rewards(spec.rewards)
        if not items and not rewards:
            continue
        if spec.bundle_type == 'RANDOM' and any(not it['rate'] for it in items):
            raise HTTPException(
                status_code=400,
                detail='บันเดิลแบบ RANDOM ต้องใส่เรทสุ่มให้ครบทุกไอเทม: %s'
                       % (spec.name.strip() or 'บันเดิลที่ %d' % (index + 1)))
        jobs.append({'name': spec.name.strip() or 'Bundle %d' % (index + 1),
                     'type': spec.bundle_type, 'deliver': spec.deliver,
                     'items': items, 'rewards': rewards})
    if not jobs:
        raise HTTPException(status_code=400, detail='ไม่มีบันเดิลให้ทำ (ยังไม่มีไอเทม)')
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
            results = [{'name': job['name'], 'saved': False, 'bundle_id': None,
                        'added': outcome['added'], 'total': outcome['total'],
                        'rewards_added': outcome['rewards_added'],
                        'rewards_total': outcome['rewards_total'],
                        'error': None, 'kept_open': outcome['kept_open'],
                        'screenshot': outcome.get('screenshot')}]
    except Exception as exc:
        write_audit(
            db, user_id=user.id, action=action, status='failed',
            summary={'error': str(exc)[:200], 'game': payload.game,
                     'planned': len(jobs)},
            tool='create_bundle', resource_type='aztek_session',
            resource_id=user.id, request=request)
        raise HTTPException(status_code=502, detail='ทำรายการบันเดิลไม่สำเร็จ: %s' % exc)

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


def _reward_head(entry: dict) -> dict:
    """The fields every reward set has, whichever form it belongs to."""
    return {
        'name_th': str(entry.get('name_th') or '').strip(),
        'name_en': str(entry.get('name_en') or '').strip(),
        'uses_per_user': str(entry.get('uses_per_user') or '1').strip() or '1',
        'limited': bool(entry.get('limited')),
        'quantity': str(entry.get('quantity') or '').strip(),
        'remaining': str(entry.get('remaining') or '').strip(),
        'bundle_id': str(entry.get('bundle_id') or '').strip(),
    }


def _clean_itemcode_rewards(raw: list[dict]) -> list[dict]:
    """Reward sets with a name, in order. Codes are kept as the operator typed
    them; whether they are complete enough to save is the filler's call."""
    from web import itemcode_runner

    cleaned = []
    for entry in raw[:MAX_REWARD_SETS]:
        reward = _reward_head(entry)
        if not reward['name_th'] and not reward['name_en']:
            continue
        reward['code_type'] = itemcode_runner.code_type_value(
            entry.get('code_type'))
        reward['code_list'] = str(entry.get('code_list') or '')
        reward['prefix'] = str(entry.get('prefix') or '').strip()
        reward['num_codes'] = str(entry.get('num_codes') or '').strip()
        cleaned.append(reward)
    return cleaned


def _clean_event_rewards(raw: list[dict]) -> list[dict]:
    cleaned = []
    for entry in raw[:MAX_REWARD_SETS]:
        reward = _reward_head(entry)
        if not reward['name_th'] and not reward['name_en']:
            continue
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
            results = [{'name': spec.get('name_th') or spec.get('slug') or '',
                        'slug': spec.get('slug', ''),
                        'group': spec.get('group', ''), 'saved': False,
                        'made_id': None, 'missing': outcome['missing'],
                        'error': None, 'kept_open': outcome['kept_open'],
                        'screenshot': outcome.get('screenshot')}]
    except Exception as exc:
        write_audit(
            db, user_id=user.id, action=action, status='failed',
            summary={'error': str(exc)[:200], 'game': game,
                     'planned': len(specs)},
            tool=tool, resource_type='aztek_session', resource_id=user.id,
            request=request)
        raise HTTPException(status_code=502, detail='ทำรายการไม่สำเร็จ: %s' % exc)

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
        counts.append({'name': name, 'count': len(made)})

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
    jobs = []
    for index, spec in enumerate(payload.itemcodes[:MAX_ACTIVITIES]):
        where = spec.name_th.strip() or 'Item Code ที่ %d' % (index + 1)
        jobs.append({
            'name_th': spec.name_th.strip(), 'name_en': spec.name_en.strip(),
            'slug': _require_slug(spec.slug, where),
            'uses_per_user': spec.uses_per_user.strip() or '1',
            'start_time': _require_datetime(spec.start_time, 'เวลาเริ่มใช้งาน', where),
            'end_time': _require_datetime(spec.end_time, 'เวลาสิ้นสุด', where),
            'group': spec.group,
            'rewards': _clean_itemcode_rewards(spec.rewards)})
        _require_order(jobs[-1]['start_time'], jobs[-1]['end_time'],
                       ('เวลาเริ่มใช้งาน', 'เวลาสิ้นสุด'), where)
    _prepare(payload.game, jobs, payload.do_save)
    builder = itemcode_runner.ItemCodeBuilder(_collect(logs := []))
    result = await _run_activity(
        builder, jobs, game=payload.game, do_save=payload.do_save,
        request=request, db=db, user=user, tool='create_itemcode',
        action='itemcode.create' if payload.do_save else 'itemcode.preview_open',
        headed=settings.app_env != 'production')
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
        {'name': sheet, 'count': len((event or {}).get('rewards') or [])}
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
    jobs = []
    for index, spec in enumerate(payload.events[:MAX_ACTIVITIES]):
        where = spec.name_th.strip() or 'Event ที่ %d' % (index + 1)
        job = {'slug': _require_slug(spec.slug, where),
               'name_th': spec.name_th.strip(), 'name_en': spec.name_en.strip(),
               'type': spec.kind,
               'uses_per_user': spec.uses_per_user.strip() or '1',
               'quantity': spec.quantity.strip() or '0',
               'remaining': spec.remaining.strip() or '0',
               'group': spec.group,
               'rewards': _clean_event_rewards(spec.rewards)}
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
            await coordinator.attach(workspace_id, send)
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
    resolved_database = database or Database(resolved_settings)
    auth_service = AuthService(resolved_settings)
    local_access = LocalAccessService(
        resolved_settings,
        auth_service,
        monotonic_clock,
    )
    aztek_session_service = AztekSessionService(resolved_settings)
    search_coordinator = SearchCoordinator(
        resolved_database, resolved_settings, aztek_session_service)

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
    application.state.settings = resolved_settings
    application.state.database = resolved_database
    application.state.auth_service = auth_service
    application.state.local_access = local_access
    application.state.aztek_session_service = aztek_session_service
    application.state.search_coordinator = search_coordinator
    application.state.login_throttle = LoginThrottle(monotonic_clock)
    application.state.pairing_throttle = LoginThrottle(monotonic_clock)
    application.include_router(router)
    return application


app = create_app()
