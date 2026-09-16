"""Early, framework-light byte limits for mutation requests."""
from __future__ import annotations

import json
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any


PAIR_BODY_MAX = 307200
WORKBOOK_BODY_MAX = 67108864
PRODUCT_BODY_MAX = 67108864
MUTATION_BODY_MAX = 2097152
COALESCE_FRAME_BYTES = 64 * 1024

WORKBOOK_PATHS = frozenset({
    '/api/import-template',
    '/api/import-plan',
    '/api/itemcodes/import',
    '/api/events/import',
    '/api/bundles/import',
})
_MUTATION_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})


def request_limit(method: str, path: str) -> int | None:
    """Return the applicable body cap, or ``None`` for unbounded methods."""
    if method.upper() not in _MUTATION_METHODS:
        return None
    if path == '/api/aztek/pair':
        return PAIR_BODY_MAX
    if path in WORKBOOK_PATHS:
        return WORKBOOK_BODY_MAX
    if path == '/api/products/run':
        return PRODUCT_BODY_MAX
    return MUTATION_BODY_MAX


def _declared_content_length(scope: dict[str, Any]) -> str | None:
    values = [
        value for name, value in scope.get('headers', [])
        if name.lower() == b'content-length'
    ]
    if not values:
        return None
    if len(values) != 1:
        raise ValueError('multiple Content-Length headers')
    try:
        text = values[0].decode('ascii')
    except UnicodeDecodeError as error:
        raise ValueError('invalid Content-Length') from error
    if not text.isdecimal():
        raise ValueError('invalid Content-Length')
    return text


def _decimal_exceeds(text: str, limit: int) -> bool:
    normalized = text.lstrip('0') or '0'
    maximum = str(limit)
    return (len(normalized), normalized) > (len(maximum), maximum)


async def _send_json(send: Callable[[dict[str, Any]], Awaitable[None]], status: int,
                     payload: dict[str, Any]) -> None:
    body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    await send({
        'type': 'http.response.start',
        'status': status,
        'headers': [(b'content-type', b'application/json')],
    })
    await send({'type': 'http.response.body', 'body': body})


def _too_large_payload(path: str, limit: int) -> dict[str, Any]:
    if path in WORKBOOK_PATHS:
        return {
            'detail': 'ไฟล์ Excel ใหญ่เกิน 64 MB',
            'code': 'request_too_large',
            'limit_bytes': limit,
        }
    return {'detail': 'request_too_large', 'limit_bytes': limit}


class RequestSizeLimitMiddleware:
    """Count complete mutation bodies before handing the request to FastAPI."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        limit = request_limit(scope['method'], scope['path'])
        if limit is None:
            await self.app(scope, receive, send)
            return

        try:
            declared = _declared_content_length(scope)
        except ValueError:
            await _send_json(send, 400, {'detail': 'invalid_content_length'})
            return
        if declared is not None and _decimal_exceeds(declared, limit):
            await _send_json(send, 413, _too_large_payload(scope['path'], limit))
            return

        parts = deque()
        pending = bytearray()
        size = 0
        interrupted = None
        saw_request = False
        message = chunk = view = None
        while True:
            message = await receive()
            if message['type'] != 'http.request':
                interrupted = message
                break
            saw_request = True
            chunk = message.get('body', b'')
            chunk_size = len(chunk)
            if chunk_size > limit - size:
                await _send_json(
                    send, 413, _too_large_payload(scope['path'], limit))
                return
            size += chunk_size
            view = memoryview(chunk)
            while view:
                take = min(COALESCE_FRAME_BYTES - len(pending), len(view))
                pending.extend(view[:take])
                view = view[take:]
                if len(pending) == COALESCE_FRAME_BYTES:
                    parts.append(bytes(pending))
                    pending.clear()
            del view
            view = None
            if not message.get('more_body', False):
                break

        if pending:
            parts.append(bytes(pending))
        pending.clear()
        del pending
        message = chunk = view = None
        terminal_body_pending = interrupted is None and not parts
        interrupted_empty_body_pending = (
            interrupted is not None and saw_request and not parts
        )

        async def replay_receive():
            nonlocal interrupted, terminal_body_pending
            nonlocal interrupted_empty_body_pending
            if parts:
                part = parts.popleft()
                return {
                    'type': 'http.request',
                    'body': part,
                    'more_body': bool(parts) or interrupted is not None,
                }
            if terminal_body_pending:
                terminal_body_pending = False
                return {'type': 'http.request', 'body': b'', 'more_body': False}
            if interrupted_empty_body_pending:
                interrupted_empty_body_pending = False
                return {'type': 'http.request', 'body': b'', 'more_body': True}
            if interrupted is not None:
                event = interrupted
                interrupted = None
                return event
            return await receive()

        await self.app(scope, replay_receive, send)
