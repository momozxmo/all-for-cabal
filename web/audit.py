"""Safe, transaction-scoped audit log writes for the web application."""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from web.models import AuditLog


_SUMMARY_KEYS = {
    'count', 'mode', 'game', 'filename', 'format', 'reason',
    'target_username', 'role',
    # Creation audits need enough identity to reconcile a partially successful
    # batch without retaining request payloads, option catalogs, or file bytes.
    'name', 'slug', 'made_id', 'bundle_id', 'error', 'planned', 'created',
    'added', 'total', 'rewards',
}
_SECRET_KEY_PARTS = {
    'password', 'token', 'cookie', 'authorization', 'storage', 'secret',
}
_SUMMARY_LIMIT = 2000
_IP_ADDRESS_LIMIT = 255
_USER_AGENT_LIMIT = 512


def _is_scalar(value: Any) -> bool:
    return (
        value is None
        or isinstance(value, (str, bool, int))
        or (isinstance(value, float) and math.isfinite(value))
    )


def _safe_summary(summary: Any) -> str:
    if not isinstance(summary, Mapping):
        return '{}'

    clean = {
        key: value
        for key, value in summary.items()
        if (
            isinstance(key, str)
            and key in _SUMMARY_KEYS
            and not any(part in key.lower() for part in _SECRET_KEY_PARTS)
            and _is_scalar(value)
        )
    }
    while True:
        serialized = json.dumps(
            clean, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
            allow_nan=False,
        )
        if len(serialized) <= _SUMMARY_LIMIT:
            return serialized

        strings = [key for key, value in clean.items() if isinstance(value, str)]
        if not strings:
            return '{}'
        key = max(strings, key=lambda item: (len(clean[item]), item))
        if len(clean[key]) <= 1:
            del clean[key]
        else:
            clean[key] = clean[key][:len(clean[key]) // 2]


def _request_metadata(request: Any) -> tuple[str | None, str | None]:
    if request is None:
        return None, None

    client = getattr(request, 'client', None)
    client_ip = getattr(client, 'host', None)
    ip_address = str(client_ip)[:_IP_ADDRESS_LIMIT] if client_ip else None

    headers = getattr(request, 'headers', None)
    user_agent = headers.get('user-agent') if headers is not None else None
    return ip_address, (str(user_agent)[:_USER_AGENT_LIMIT] if user_agent else None)


def write_audit(
    db: Session,
    *,
    user_id: str | None,
    action: str,
    status: str,
    summary: Any = '',
    tool: str = '',
    resource_type: str = '',
    resource_id: str = '',
    request: Any = None,
) -> AuditLog:
    """Add a redacted audit row to the caller's current transaction."""
    ip_address, user_agent = _request_metadata(request)
    entry = AuditLog(
        user_id=user_id,
        action=action,
        status=status,
        summary=_safe_summary(summary),
        tool=tool or None,
        resource_type=resource_type or None,
        resource_id=resource_id or None,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)
    return entry
