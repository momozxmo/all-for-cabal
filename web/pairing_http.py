"""HTTP-boundary helpers for private, atomic Aztek pairing flows.

The pairing routes deliberately avoid FastAPI body models and ORM principals.
This module turns both inputs into small immutable snapshots before their
synchronous business endpoints enter the threadpool.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field as dataclass_field
from typing import Any

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from web.auth_service import AuthService
from web.aztek_sessions import PairingTokenIssueConflict
from web.db import Database
from web.settings import Settings


_THROTTLE_DOMAIN = b'all-for-cabal/pairing-throttle/v1\x00'
_INVALID_PAYLOAD = b'invalid-pairing-payload'


@dataclass(frozen=True)
class PairingPrincipalSnapshot:
    """The only authentication data carried into pairing business work."""

    user_id: str


class StorageStatePayload(BaseModel):
    """Validated pairing body retained for the synchronous route only."""

    model_config = ConfigDict(frozen=True)

    pairing_token: str = Field(min_length=20, max_length=200, repr=False)
    account_label: str | None = Field(
        default=None, max_length=120, repr=False)
    storage_state: dict[str, Any] = Field(repr=False)


@dataclass(frozen=True)
class PairingParseResult:
    """A valid payload or one fixed invalid result plus a safe throttle key."""

    payload: StorageStatePayload | None = dataclass_field(repr=False)
    fingerprint: str


def _throttle_fingerprint(settings: Settings, value: bytes) -> str:
    return hmac.new(
        settings.app_secret_key.encode('utf-8'),
        _THROTTLE_DOMAIN + value,
        hashlib.sha256,
    ).hexdigest()


def _invalid_parse_result(
    settings: Settings,
    fingerprint: str | None = None,
) -> PairingParseResult:
    return PairingParseResult(
        payload=None,
        fingerprint=fingerprint or _throttle_fingerprint(
            settings, _INVALID_PAYLOAD),
    )


async def pairing_parse_dependency(request: Request) -> PairingParseResult:
    """Read and validate one bounded pairing body without validation echoes."""
    settings: Settings = request.app.state.settings
    media_type = request.headers.get('content-type', '').split(';', 1)[0]
    media_type = media_type.strip().lower()
    if not (media_type == 'application/json' or media_type.endswith('+json')):
        return _invalid_parse_result(settings)

    body: bytes | None = None
    decoded: Any = None
    candidate: str | None = None
    fingerprint: str | None = None
    failed = False
    try:
        body = await request.body()
        if not body:
            failed = True
        else:
            decoded = json.loads(body.decode('utf-8'))
            if isinstance(decoded, Mapping):
                candidate = decoded.get('pairing_token')
                if isinstance(candidate, str):
                    fingerprint = _throttle_fingerprint(
                        settings, candidate.encode('utf-8'))
            payload = StorageStatePayload.model_validate(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError,
            TypeError, ValueError):
        failed = True
        payload = None
    except Exception:
        failed = True
        payload = None

    # Clear raw/decoded/error-adjacent references after leaving every except.
    body = None
    decoded = None
    candidate = None
    if failed:
        return _invalid_parse_result(settings, fingerprint)
    return PairingParseResult(
        payload=payload,
        fingerprint=fingerprint or _throttle_fingerprint(
            settings, _INVALID_PAYLOAD),
    )


def resolve_pairing_principal(
    database: Database,
    auth_service: AuthService,
    raw_web_session: str | None,
) -> PairingPrincipalSnapshot | None:
    """Resolve auth in its own committed/closed Session and detach the ID."""
    with database.session() as db:
        user = auth_service.resolve_session(db, raw_web_session)
        user_id = None if user is None else str(user.id)
    if user_id is None:
        return None
    return PairingPrincipalSnapshot(user_id=user_id)


class PairingIssueReservations:
    """Non-blocking, per-user issuance reservations for one app process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reserved: set[str] = set()

    @contextmanager
    def reserve(self, user_id: str) -> Iterator[None]:
        with self._lock:
            if user_id in self._reserved:
                raise PairingTokenIssueConflict()
            self._reserved.add(user_id)
        try:
            yield
        finally:
            with self._lock:
                self._reserved.discard(user_id)

    @property
    def reserved_user_ids(self) -> tuple[str, ...]:
        """Safe diagnostic snapshot used by regression tests and shutdown."""
        with self._lock:
            return tuple(sorted(self._reserved))
