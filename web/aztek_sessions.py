"""Pairing tokens and encrypted per-user Aztek browser sessions.

A logged-in web user asks for a short-lived, single-use *pairing token* and
pastes it into the private browser extension. The extension posts the captured
Playwright ``storage_state`` back with that token to ``/api/aztek/pair`` — the
only endpoint that authenticates with the pairing token instead of a web
session cookie. The storage state is validated against the Aztek origin and
stored AES-GCM encrypted, one row per user.

Security invariants enforced here:

* Pairing tokens live at most ``settings.pairing_ttl_seconds`` and may be
  consumed once; issuing a new token supersedes any still-pending token.
* Only the HMAC hash of a pairing token is ever stored.
* Every cookie domain must equal or be a dot-aligned parent of the Aztek host
  or the shared SSO auth host, and every origin must equal ``aztek_origin`` or
  ``aztek_auth_origin``.
* Storage state is size/shape bounded before encryption.
* Ciphertext never leaves this module except to the search coordinator.
"""
from __future__ import annotations

import json
import secrets
import sqlite3
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select, Update

from web.models import AztekSession, PairingToken, User, utc_now
from web.security import (decrypt_storage_state, encrypt_storage_state,
                          hash_token)
from web.settings import Settings


_PAIRING_TOKEN_BYTES = 32
_MAX_STORAGE_STATE_BYTES = 256 * 1024
_MAX_COOKIES = 200
_MAX_LOCAL_STORAGE = 500


class PairingTokenNotFound(Exception):
    """The supplied pairing token is unknown (maps to HTTP 404)."""


class PairingTokenUnavailable(Exception):
    """The pairing token was already used or has expired (maps to HTTP 410)."""


class PairingTokenIssueConflict(Exception):
    """Another issue attempt won the immutable pending-token snapshot."""


class PairingBusy(Exception):
    """The bounded pairing write window was exhausted by SQLite contention."""


class InvalidStorageState(ValueError):
    """The browser storage state failed validation (maps to HTTP 422)."""


@dataclass(frozen=True)
class PairingIssue:
    raw_token: str
    expires_at: datetime


@dataclass(frozen=True)
class PairingIssueAttempt:
    user_id: str
    prior_token_id: str | None
    raw_token: str = dataclass_field(repr=False)
    token_hash: str = dataclass_field(repr=False)
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class PairingConsumptionAttempt:
    token_hash: str = dataclass_field(repr=False)
    ciphertext: str = dataclass_field(repr=False)
    account_label: str | None = dataclass_field(repr=False)


def _hostname(origin: str) -> str:
    return (urlsplit(origin).hostname or '').lower()


def _allowed_hosts(settings: Settings) -> tuple[str, ...]:
    """Every host whose cookies may appear in a captured Aztek session."""
    hosts = {
        _hostname(settings.aztek_origin),
        _hostname(settings.aztek_auth_origin),
    }
    return tuple(host for host in hosts if host)


def _origin_allowed(origin: Any, settings: Settings) -> bool:
    """True when ``origin`` is https on the Aztek registrable base domain.

    The live web app moved between the v1 and v2 hosts, and localStorage is
    captured under whichever host the user is on. Rather than pin exact hosts,
    accept any https host under the same base domain as ``aztek_origin`` (still
    rejects other sites and non-https origins).
    """
    if not isinstance(origin, str):
        return False
    parts = urlsplit(origin)
    if parts.scheme != 'https':
        return False
    host = (parts.hostname or '').lower()
    if not host:
        return False
    base = _base_domain(_hostname(settings.aztek_origin))
    return host == base or host.endswith('.' + base)


def _base_domain(host: str) -> str:
    labels = host.split('.')
    return '.'.join(labels[-2:]) if len(labels) >= 2 else host


def _cookie_domain_allowed(domain: Any, host: str) -> bool:
    """True when ``domain`` scopes a cookie to the Aztek host, parent domain, or sibling subdomain.

    Blocks over-broad public suffixes (``.com``) by requiring the normalized
    domain to still contain the Aztek registrable base domain.
    """
    if not isinstance(domain, str):
        return False
    norm = domain.strip().lstrip('.').lower()
    if not norm:
        return False
    base = _base_domain(host)
    return norm == base or norm.endswith('.' + base)


def _cookie_domain_allowed_for_any(domain: Any, hosts: tuple[str, ...]) -> bool:
    """True when ``domain`` scopes a cookie to any allowed Aztek/auth host."""
    return any(_cookie_domain_allowed(domain, host) for host in hosts)


def validate_storage_state(storage_state: Any, settings: Settings) -> None:
    """Reject storage state that is malformed, oversized, or off-origin."""
    if not isinstance(storage_state, dict):
        raise InvalidStorageState('storage_state must be an object')

    cookies = storage_state.get('cookies')
    origins = storage_state.get('origins')
    if not isinstance(cookies, list) or not isinstance(origins, list):
        raise InvalidStorageState(
            'storage_state must include cookies and origins lists'
        )
    if not cookies:
        raise InvalidStorageState('storage_state must include at least one cookie')
    if len(cookies) > _MAX_COOKIES:
        raise InvalidStorageState('storage_state has too many cookies')

    try:
        serialized = json.dumps(storage_state, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise InvalidStorageState('storage_state is not serializable') from exc
    if len(serialized.encode('utf-8')) > _MAX_STORAGE_STATE_BYTES:
        raise InvalidStorageState('storage_state payload is too large')

    hosts = _allowed_hosts(settings)
    for cookie in cookies:
        if not isinstance(cookie, dict):
            raise InvalidStorageState('each cookie must be an object')
        if not _cookie_domain_allowed_for_any(cookie.get('domain', ''), hosts):
            raise InvalidStorageState('cookie domain is not allowed: %s' % cookie.get('domain'))

    local_storage_total = 0
    for origin in origins:
        if not isinstance(origin, dict):
            raise InvalidStorageState('each origin must be an object')
        if not _origin_allowed(origin.get('origin'), settings):
            raise InvalidStorageState('origin is not allowed: %s' % origin.get('origin'))
        entries = origin.get('localStorage', [])
        if not isinstance(entries, list):
            raise InvalidStorageState('localStorage must be a list')
        local_storage_total += len(entries)
    if local_storage_total > _MAX_LOCAL_STORAGE:
        raise InvalidStorageState('storage_state has too many localStorage entries')


def is_pairing_sqlite_busy(error: BaseException) -> bool:
    """Recognize contention only from SQLite's structured driver result code."""
    if isinstance(error, OperationalError):
        driver_error = error.orig
    elif isinstance(error, sqlite3.OperationalError):
        driver_error = error
    else:
        return False
    code = getattr(driver_error, 'sqlite_errorcode', None)
    if not isinstance(code, int):
        return False
    return (code & 0xFF) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)


def _begin_fresh_pairing_write(db: Session) -> None:
    """Acquire a route-owned SQLite write transaction on a pristine Session."""
    if db.new or db.dirty or db.deleted or db.in_transaction():
        raise RuntimeError('pairing write Session must be fresh')
    if db.get_bind().dialect.name != 'sqlite':
        return

    connection = db.connection()
    driver_connection = connection.connection.driver_connection
    if driver_connection.in_transaction:
        raise RuntimeError('pairing write driver transaction must be fresh')
    connection.exec_driver_sql('BEGIN IMMEDIATE')


def _pending_pairing_token_id(db: Session, user_id: str) -> str | None:
    return db.scalar(select(PairingToken.id).where(
        PairingToken.user_id == user_id,
        PairingToken.status == 'pending',
        PairingToken.used_at.is_(None),
    ))


def _supersede_pairing_token_statement(
    user_id: str,
    token_id: str,
) -> Update:
    return (
        update(PairingToken)
        .where(
            PairingToken.id == token_id,
            PairingToken.user_id == user_id,
            PairingToken.status == 'pending',
            PairingToken.used_at.is_(None),
        )
        .values(status='superseded')
    )


def _claim_pairing_token_statement(
    token_hash: str,
    now: datetime,
) -> Update:
    return (
        update(PairingToken)
        .where(
            PairingToken.token_hash == token_hash,
            PairingToken.status == 'pending',
            PairingToken.used_at.is_(None),
            PairingToken.expires_at > now,
        )
        .values(status='used', used_at=now)
        .returning(PairingToken.user_id, PairingToken.expires_at)
    )


def _expire_pairing_token_statement(
    token_hash: str,
    now: datetime,
) -> Update:
    return (
        update(PairingToken)
        .where(
            PairingToken.token_hash == token_hash,
            PairingToken.status == 'pending',
            PairingToken.used_at.is_(None),
            PairingToken.expires_at <= now,
        )
        .values(status='expired')
        .returning(PairingToken.user_id)
    )


def _pairing_user_for_update_statement(user_id: str) -> Select:
    return select(User).where(User.id == user_id).with_for_update()


def _aztek_session_for_update_statement(user_id: str) -> Select:
    return (
        select(AztekSession)
        .where(AztekSession.user_id == user_id)
        .with_for_update()
    )


def _claim_pairing_token(
    db: Session,
    token_hash: str,
    now: datetime,
) -> tuple[str, datetime]:
    claimed = db.execute(
        _claim_pairing_token_statement(token_hash, now)).first()
    if claimed is not None:
        return str(claimed.user_id), claimed.expires_at

    known = db.execute(
        select(PairingToken.status, PairingToken.used_at,
               PairingToken.expires_at)
        .where(PairingToken.token_hash == token_hash)
    ).first()
    if known is None:
        raise PairingTokenNotFound()
    if (known.status == 'pending' and known.used_at is None
            and known.expires_at <= now):
        db.execute(_expire_pairing_token_statement(token_hash, now))
    raise PairingTokenUnavailable()


class AztekSessionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create_pairing_token(self, db: Session, user: User) -> PairingIssue:
        """Issue inside the caller's transaction without commit or rollback."""
        attempt = self._prepare_pairing_issue(db, str(user.id))
        return self._apply_pairing_issue(db, attempt)

    def _prepare_pairing_issue(
        self,
        db: Session,
        user_id: str,
    ) -> PairingIssueAttempt:
        """Snapshot the prior pending ID and generate one immutable candidate."""
        now = utc_now()
        raw_token = secrets.token_urlsafe(_PAIRING_TOKEN_BYTES)
        expires_at = now + timedelta(seconds=self.settings.pairing_ttl_seconds)
        return PairingIssueAttempt(
            user_id=str(user_id),
            prior_token_id=_pending_pairing_token_id(db, str(user_id)),
            raw_token=raw_token,
            token_hash=hash_token(raw_token, self.settings),
            created_at=now,
            expires_at=expires_at,
        )

    def _apply_pairing_issue(
        self,
        db: Session,
        attempt: PairingIssueAttempt,
    ) -> PairingIssue:
        """Apply exactly one snapshot/candidate; the caller owns transaction."""
        if attempt.prior_token_id is not None:
            changed = db.execute(_supersede_pairing_token_statement(
                attempt.user_id, attempt.prior_token_id))
            if changed.rowcount != 1:
                raise PairingTokenIssueConflict()

        db.add(PairingToken(
            user_id=attempt.user_id,
            token_hash=attempt.token_hash,
            status='pending',
            created_at=attempt.created_at,
            expires_at=attempt.expires_at,
        ))
        integrity_conflict = False
        try:
            db.flush()
        except IntegrityError:
            integrity_conflict = True
        if integrity_conflict:
            raise PairingTokenIssueConflict()
        return PairingIssue(
            raw_token=attempt.raw_token,
            expires_at=attempt.expires_at,
        )

    def _prepare_pairing_consumption(
        self,
        raw_token: str,
        storage_state: Any,
        account_label: str | None = None,
    ) -> PairingConsumptionAttempt:
        """Validate and encrypt before a route opens its business Session."""
        validate_storage_state(storage_state, self.settings)
        ciphertext = encrypt_storage_state(storage_state, self.settings)
        clean_label = (account_label or '').strip() or None
        return PairingConsumptionAttempt(
            token_hash=hash_token(raw_token, self.settings),
            ciphertext=ciphertext,
            account_label=clean_label,
        )

    def _save_encrypted_state(
        self,
        db: Session,
        user_id: str,
        ciphertext: str,
        account_label: str | None,
    ) -> AztekSession:
        """Persist only already-encrypted state, replacing the user's one row."""
        session = db.scalar(_aztek_session_for_update_statement(user_id))
        if session is None:
            session = AztekSession(
                user_id=user_id,
                encrypted_state=ciphertext,
                account_label=account_label,
                status='active',
            )
            db.add(session)
        else:
            session.encrypted_state = ciphertext
            session.account_label = account_label
            session.status = 'active'
            session.last_validated_at = None
        db.flush()
        return session

    def save_storage_state(
        self,
        db: Session,
        user_id: str,
        storage_state: Any,
        account_label: str | None = None,
    ) -> AztekSession:
        """Validate, encrypt, and activate one user's captured browser state."""
        validate_storage_state(storage_state, self.settings)
        ciphertext = encrypt_storage_state(storage_state, self.settings)
        clean_label = (account_label or '').strip() or None
        return self._save_encrypted_state(
            db, str(user_id), ciphertext, clean_label)

    def consume_pairing_token(
        self,
        db: Session,
        raw_token: str,
        storage_state: Any,
        account_label: str | None = None,
    ) -> AztekSession:
        """Consume inside the caller's transaction without commit/rollback."""
        attempt = self._prepare_pairing_consumption(
            raw_token, storage_state, account_label)
        return self._apply_pairing_consumption(db, attempt)

    def _apply_pairing_consumption(
        self,
        db: Session,
        attempt: PairingConsumptionAttempt,
    ) -> AztekSession:
        """Atomically claim then save encrypted state in one transaction."""
        user_id, _expires_at = _claim_pairing_token(
            db, attempt.token_hash, utc_now())
        user = db.scalar(_pairing_user_for_update_statement(user_id))
        if user is None:
            raise PairingTokenUnavailable()
        return self._save_encrypted_state(
            db, user_id, attempt.ciphertext, attempt.account_label)

    def get_status(self, db: Session, user: User) -> dict[str, Any]:
        """Return connection status only — never the ciphertext."""
        session = db.scalar(
            select(AztekSession).where(AztekSession.user_id == user.id)
        )
        if session is None:
            return {
                'connected': False,
                'status': 'disconnected',
                'account_label': None,
                'updated_at': None,
                'last_validated_at': None,
            }
        return {
            'connected': session.status == 'active',
            'status': session.status,
            'account_label': session.account_label,
            'updated_at': (
                session.updated_at.isoformat() if session.updated_at else None
            ),
            'last_validated_at': (
                session.last_validated_at.isoformat()
                if session.last_validated_at else None
            ),
        }

    def disconnect(self, db: Session, user: User) -> bool:
        session = db.scalar(
            select(AztekSession).where(AztekSession.user_id == user.id)
        )
        if session is None:
            return False
        db.delete(session)
        db.flush()
        return True

    def load_storage_state(self, db: Session, user: User) -> dict[str, Any] | None:
        """Decrypt the active storage state for the search coordinator."""
        session = db.scalar(
            select(AztekSession).where(AztekSession.user_id == user.id)
        )
        if session is None or session.status != 'active':
            return None
        return decrypt_storage_state(session.encrypted_state, self.settings)

    def load_storage_state_for_reconnect(
        self,
        db: Session,
        user: User,
    ) -> dict[str, Any] | None:
        """Decrypt any saved state solely to seed a Local reconnect browser."""
        session = db.scalar(
            select(AztekSession).where(AztekSession.user_id == user.id)
        )
        if session is None:
            return None
        return decrypt_storage_state(session.encrypted_state, self.settings)

    def mark_expired(self, db: Session, user: User) -> None:
        """Flag the stored session as expired (e.g. Aztek rejected the cookies)."""
        session = db.scalar(
            select(AztekSession).where(AztekSession.user_id == user.id)
        )
        if session is not None and session.status != 'expired':
            session.status = 'expired'
            db.flush()
