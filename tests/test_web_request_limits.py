from __future__ import annotations

import asyncio
import importlib
import os
import tempfile

import pytest
from fastapi import HTTPException

from web.request_limits import (
    COALESCE_FRAME_BYTES,
    MUTATION_BODY_MAX,
    PAIR_BODY_MAX,
    PRODUCT_BODY_MAX,
    WORKBOOK_BODY_MAX,
    RequestSizeLimitMiddleware,
    request_limit,
)


WORKBOOK_PATHS = (
    '/api/import-template',
    '/api/import-plan',
    '/api/itemcodes/import',
    '/api/events/import',
)


class RecordingApp:
    """A minimal ASGI endpoint that records the body it actually receives."""

    def __init__(self):
        self.calls: list[list[dict]] = []

    async def __call__(self, scope, receive, send):
        messages = []
        while True:
            message = await receive()
            messages.append(message)
            if message['type'] != 'http.request' or not message.get('more_body'):
                break
        self.calls.append(messages)
        await send({
            'type': 'http.response.start',
            'status': 204,
            'headers': [],
        })
        await send({
            'type': 'http.response.body',
            'body': b'',
        })


def _scope(method: str, path: str, content_length: str | None = None,
           headers=None):
    if headers is None:
        headers = []
    else:
        headers = list(headers)
    if content_length is not None:
        headers.append((b'content-length', content_length.encode('ascii')))
    return {
        'type': 'http',
        'asgi': {'version': '3.0'},
        'http_version': '1.1',
        'method': method,
        'scheme': 'http',
        'path': path,
        'raw_path': path.encode('ascii'),
        'query_string': b'',
        'headers': headers,
        'client': ('127.0.0.1', 1),
        'server': ('testserver', 80),
    }


def _run(middleware, scope, messages):
    received = iter(messages)
    sent = []

    async def receive():
        return next(received)

    async def send(message):
        sent.append(message)

    asyncio.run(middleware(scope, receive, send))
    return sent


@pytest.mark.parametrize(('method', 'path', 'expected'), [
    ('POST', '/api/aztek/pair', PAIR_BODY_MAX),
    ('POST', '/api/import-template', WORKBOOK_BODY_MAX),
    ('POST', '/api/import-plan', WORKBOOK_BODY_MAX),
    ('POST', '/api/itemcodes/import', WORKBOOK_BODY_MAX),
    ('POST', '/api/events/import', WORKBOOK_BODY_MAX),
    ('POST', '/api/products/run', PRODUCT_BODY_MAX),
    ('PUT', '/api/anything', MUTATION_BODY_MAX),
    ('PATCH', '/api/anything', MUTATION_BODY_MAX),
    ('DELETE', '/api/anything', MUTATION_BODY_MAX),
    ('GET', '/api/aztek/pair', None),
    ('OPTIONS', '/api/import-plan', None),
])
def test_request_limit_selects_exact_route_and_method_caps(method, path, expected):
    assert request_limit(method, path) == expected


@pytest.mark.parametrize(('path', 'limit'), [
    ('/api/aztek/pair', PAIR_BODY_MAX),
    *[(path, WORKBOOK_BODY_MAX) for path in WORKBOOK_PATHS],
    ('/api/products/run', PRODUCT_BODY_MAX),
    ('/api/ordinary-mutation', MUTATION_BODY_MAX),
])
def test_declared_exact_boundary_is_accepted_and_replayed(path, limit):
    recorded = RecordingApp()
    body = b'x' * limit
    original = {'type': 'http.request', 'body': body, 'more_body': False}

    sent = _run(
        RequestSizeLimitMiddleware(recorded),
        _scope('POST', path, str(limit)),
        [original],
    )

    received = recorded.calls[0]
    assert [message['status'] for message in sent if message['type'] == 'http.response.start'] == [204]
    assert b''.join(message['body'] for message in received) == body
    assert len(received) == (limit + COALESCE_FRAME_BYTES - 1) // COALESCE_FRAME_BYTES
    assert all(len(message['body']) <= COALESCE_FRAME_BYTES for message in received)
    assert [message['more_body'] for message in received] == (
        [True] * (len(received) - 1) + [False]
    )


@pytest.mark.parametrize(('path', 'limit'), [
    ('/api/aztek/pair', PAIR_BODY_MAX),
    *[(path, WORKBOOK_BODY_MAX) for path in WORKBOOK_PATHS],
    ('/api/products/run', PRODUCT_BODY_MAX),
    ('/api/ordinary-mutation', MUTATION_BODY_MAX),
])
def test_declared_boundary_plus_one_is_rejected_before_wrapped_app(path, limit):
    recorded = RecordingApp()

    sent = _run(
        RequestSizeLimitMiddleware(recorded),
        _scope('POST', path, str(limit + 1)),
        [],
    )

    assert recorded.calls == []
    assert sent == [
        {
            'type': 'http.response.start',
            'status': 413,
            'headers': [(b'content-type', b'application/json')],
        },
        {
            'type': 'http.response.body',
            'body': (
                b'{"detail":"request_too_large","limit_bytes":'
                + str(limit).encode('ascii')
                + b'}'
            ),
        },
    ]


def test_valid_thousands_digit_content_length_is_rejected_as_too_large():
    recorded = RecordingApp()

    sent = _run(
        RequestSizeLimitMiddleware(recorded),
        _scope('POST', '/api/ordinary-mutation', '9' * 5000),
        [],
    )

    assert recorded.calls == []
    assert sent[-1]['body'] == (
        b'{"detail":"request_too_large","limit_bytes":2097152}'
    )


@pytest.mark.parametrize('content_length', (
    'many',
    '-1',
    '+1',
    ' 1',
    '1 ',
    '1_0',
))
def test_invalid_or_negative_content_length_is_rejected_before_wrapped_app(content_length):
    recorded = RecordingApp()

    sent = _run(
        RequestSizeLimitMiddleware(recorded),
        _scope('POST', '/api/ordinary-mutation', content_length),
        [],
    )

    assert recorded.calls == []
    assert sent == [
        {
            'type': 'http.response.start',
            'status': 400,
            'headers': [(b'content-type', b'application/json')],
        },
        {
            'type': 'http.response.body',
            'body': b'{"detail":"invalid_content_length"}',
        },
    ]


@pytest.mark.parametrize('headers', [
    [(b'content-length', b'1'), (b'content-length', b'1')],
    [(b'content-length', b'\xff')],
])
def test_duplicate_or_non_ascii_content_length_is_rejected_before_wrapped_app(headers):
    recorded = RecordingApp()

    sent = _run(
        RequestSizeLimitMiddleware(recorded),
        _scope('POST', '/api/ordinary-mutation', headers=headers),
        [],
    )

    assert recorded.calls == []
    assert sent[-1]['body'] == b'{"detail":"invalid_content_length"}'


@pytest.mark.parametrize('declared_length', (None, '1'))
def test_missing_or_lying_content_length_cannot_bypass_actual_byte_cap(declared_length):
    recorded = RecordingApp()
    limit = MUTATION_BODY_MAX
    messages = [
        {'type': 'http.request', 'body': b'x' * limit, 'more_body': True},
        {'type': 'http.request', 'body': b'y', 'more_body': False},
    ]

    sent = _run(
        RequestSizeLimitMiddleware(recorded),
        _scope('POST', '/api/ordinary-mutation', declared_length),
        messages,
    )

    assert recorded.calls == []
    assert sent[-1]['body'] == (
        b'{"detail":"request_too_large","limit_bytes":2097152}'
    )


def test_single_oversized_chunk_is_rejected_before_it_is_buffered(monkeypatch):
    limits_module = importlib.import_module('web.request_limits')
    recorded = RecordingApp()
    extended = []

    class TrackingBytearray(bytearray):
        def extend(self, chunk):
            extended.append(len(chunk))
            return super().extend(chunk)

    monkeypatch.setattr(limits_module, 'bytearray', TrackingBytearray,
                        raising=False)
    sent = _run(
        RequestSizeLimitMiddleware(recorded),
        _scope('POST', '/api/ordinary-mutation'),
        [{
            'type': 'http.request',
            'body': b'x' * (MUTATION_BODY_MAX + 1),
            'more_body': False,
        }],
    )

    assert extended == []
    assert recorded.calls == []
    assert sent[-1]['body'] == (
        b'{"detail":"request_too_large","limit_bytes":2097152}'
    )


def test_exact_cap_uses_only_bounded_frame_accumulators(monkeypatch):
    limits_module = importlib.import_module('web.request_limits')
    recorded = CoalescingApp()

    class TrackingBytearray(bytearray):
        maximum = 0

        def extend(self, chunk):
            result = super().extend(chunk)
            type(self).maximum = max(type(self).maximum, len(self))
            return result

    monkeypatch.setattr(limits_module, 'bytearray', TrackingBytearray,
                        raising=False)
    _run(
        RequestSizeLimitMiddleware(recorded),
        _scope('POST', '/api/ordinary-mutation', str(MUTATION_BODY_MAX)),
        [
            {
                'type': 'http.request',
                'body': b'x' * MUTATION_BODY_MAX,
                'more_body': False,
            },
            {'type': 'http.disconnect'},
        ],
    )

    assert TrackingBytearray.maximum <= COALESCE_FRAME_BYTES
    assert len(recorded.messages) == (
        MUTATION_BODY_MAX + COALESCE_FRAME_BYTES - 1
    ) // COALESCE_FRAME_BYTES
    assert all(len(message['body']) <= COALESCE_FRAME_BYTES
               for message in recorded.messages)
    assert b''.join(message['body'] for message in recorded.messages) == (
        b'x' * MUTATION_BODY_MAX
    )
    assert recorded.later_message == {'type': 'http.disconnect'}


class CoalescingApp:
    def __init__(self):
        self.messages = []
        self.later_message = None

    async def __call__(self, scope, receive, send):
        while True:
            message = await receive()
            self.messages.append(message)
            if message['type'] != 'http.request' or not message.get('more_body'):
                break
        self.later_message = await receive()
        await send({'type': 'http.response.start', 'status': 204, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})


def test_accepted_body_is_coalesced_and_later_receive_delegates_to_original():
    recorded = CoalescingApp()
    original = [
        {'type': 'http.request', 'body': b'first-', 'more_body': True},
        {'type': 'http.request', 'body': b'second', 'more_body': False},
        {'type': 'http.disconnect'},
    ]

    _run(
        RequestSizeLimitMiddleware(recorded),
        _scope('POST', '/api/ordinary-mutation', '12'),
        original,
    )

    assert recorded.messages == [
        {'type': 'http.request', 'body': b'first-second', 'more_body': False},
    ]
    assert recorded.later_message == {'type': 'http.disconnect'}


@pytest.mark.parametrize('chunk', (b'', b'x'))
def test_many_small_chunks_have_bounded_coalesced_delivery_and_exact_body(chunk):
    recorded = CoalescingApp()
    chunks = [
        {'type': 'http.request', 'body': chunk, 'more_body': True}
        for _ in range(1000)
    ]
    chunks.extend([
        {'type': 'http.request', 'body': b'', 'more_body': False},
        {'type': 'http.disconnect'},
    ])

    _run(
        RequestSizeLimitMiddleware(recorded),
        _scope('POST', '/api/ordinary-mutation', str(len(chunk) * 1000)),
        chunks,
    )

    assert recorded.messages == [
        {
            'type': 'http.request',
            'body': chunk * 1000,
            'more_body': False,
        },
    ]
    assert recorded.later_message == {'type': 'http.disconnect'}


def test_interrupted_body_preserves_partial_body_and_disconnect_semantics():
    recorded = CoalescingApp()

    _run(
        RequestSizeLimitMiddleware(recorded),
        _scope('POST', '/api/ordinary-mutation', '6'),
        [
            {'type': 'http.request', 'body': b'part-', 'more_body': True},
            {'type': 'http.disconnect'},
            {'type': 'test.after.disconnect'},
        ],
    )

    assert recorded.messages == [
        {'type': 'http.request', 'body': b'part-', 'more_body': True},
        {'type': 'http.disconnect'},
    ]
    assert recorded.later_message == {'type': 'test.after.disconnect'}


def test_interrupted_large_body_is_replayed_as_frames_then_disconnect():
    recorded = CoalescingApp()
    body = b'x' * (COALESCE_FRAME_BYTES + 1)

    _run(
        RequestSizeLimitMiddleware(recorded),
        _scope('POST', '/api/ordinary-mutation', str(len(body))),
        [
            {'type': 'http.request', 'body': body, 'more_body': True},
            {'type': 'http.disconnect'},
            {'type': 'test.after.disconnect'},
        ],
    )

    assert recorded.messages == [
        {
            'type': 'http.request',
            'body': b'x' * COALESCE_FRAME_BYTES,
            'more_body': True,
        },
        {'type': 'http.request', 'body': b'x', 'more_body': True},
        {'type': 'http.disconnect'},
    ]
    assert recorded.later_message == {'type': 'test.after.disconnect'}


@pytest.mark.parametrize(('scope', 'messages'), [
    ({'type': 'lifespan'}, [{'type': 'lifespan.startup'}]),
    (_scope('GET', '/api/ordinary-mutation', 'not-a-number'), [
        {'type': 'http.request', 'body': b'unlimited', 'more_body': False},
    ]),
])
def test_non_http_and_unlimited_requests_pass_through_untouched(scope, messages):
    recorded = RecordingApp()

    _run(RequestSizeLimitMiddleware(recorded), scope, messages)

    assert recorded.calls == [messages]


class FakeUpload:
    def __init__(self, chunks, *, filename='plan.xlsx'):
        self.chunks = iter(chunks)
        self.filename = filename
        self.read_sizes = []

    async def read(self, size=-1):
        self.read_sizes.append(size)
        next_chunk = next(self.chunks)
        if isinstance(next_chunk, BaseException):
            raise next_chunk
        return next_chunk


def _mkstemp_factory(directory):
    mkstemp = tempfile.mkstemp

    def create(**kwargs):
        return mkstemp(dir=directory, **kwargs)

    return create


def test_temporary_upload_accepts_exact_maximum_in_bounded_chunks(monkeypatch):
    app_module = importlib.import_module('web.app')
    with tempfile.TemporaryDirectory(dir=os.getcwd()) as directory:
        monkeypatch.setattr(
            app_module.tempfile,
            'mkstemp',
            _mkstemp_factory(directory),
        )
        upload = FakeUpload(
            [b'x' * (1024 * 1024) for _ in range(16)] + [b'']
        )

        path = asyncio.run(app_module._temporary_upload(upload, WORKBOOK_BODY_MAX))

        assert os.path.exists(path)
        assert os.path.getsize(path) == WORKBOOK_BODY_MAX
        assert upload.read_sizes == [1024 * 1024] * 17
        os.unlink(path)


@pytest.mark.parametrize(('chunks', 'expected_exception'), [
    ([b'x' * (1024 * 1024) for _ in range(16)] + [b'y'], HTTPException),
    ([RuntimeError('read failed')], RuntimeError),
    ([asyncio.CancelledError()], asyncio.CancelledError),
])
def test_temporary_upload_removes_partial_file_after_limit_or_read_failure(
    monkeypatch,
    chunks,
    expected_exception,
):
    app_module = importlib.import_module('web.app')
    with tempfile.TemporaryDirectory(dir=os.getcwd()) as directory:
        monkeypatch.setattr(
            app_module.tempfile,
            'mkstemp',
            _mkstemp_factory(directory),
        )
        upload = FakeUpload(chunks)

        with pytest.raises(expected_exception) as exception:
            asyncio.run(app_module._temporary_upload(upload, WORKBOOK_BODY_MAX))

        if expected_exception is HTTPException:
            assert exception.value.status_code == 413
            assert exception.value.detail == 'workbook_too_large'
        assert os.listdir(directory) == []


class FailingUploadHandle:
    def __init__(self, fd, error):
        self.fd = fd
        self.error = error

    def write(self, _chunk):
        raise self.error

    def close(self):
        os.close(self.fd)


class CloseFailingUploadHandle:
    def __init__(self, fd):
        self.fd = fd

    def write(self, chunk):
        return len(chunk)

    def close(self):
        raise OSError('close failed')


@pytest.mark.parametrize(('handle_factory', 'expected_error'), [
    (lambda fd: FailingUploadHandle(fd, OSError('write failed')), 'write failed'),
    (CloseFailingUploadHandle, 'close failed'),
])
def test_temporary_upload_removes_partial_file_after_write_or_close_failure(
    monkeypatch,
    handle_factory,
    expected_error,
):
    app_module = importlib.import_module('web.app')
    raw_mkstemp = tempfile.mkstemp
    raw_close = os.close
    open_fds = []

    with tempfile.TemporaryDirectory(dir=os.getcwd()) as directory:
        def legacy_create(**kwargs):
            fd, path = raw_mkstemp(dir=directory, suffix=kwargs.get('suffix'))
            open_fds.append(fd)
            handle = handle_factory(fd)
            handle.name = path
            return handle

        def create(**kwargs):
            fd, path = raw_mkstemp(dir=directory, **kwargs)
            open_fds.append(fd)
            return fd, path

        monkeypatch.setattr(app_module.tempfile, 'NamedTemporaryFile', legacy_create)
        monkeypatch.setattr(app_module.tempfile, 'mkstemp', create)
        monkeypatch.setattr(app_module.os, 'fdopen',
                            lambda fd, *_args, **_kwargs: handle_factory(fd))
        try:
            with pytest.raises(OSError, match=expected_error):
                asyncio.run(app_module._temporary_upload(
                    FakeUpload([b'x', b'']), WORKBOOK_BODY_MAX))
        finally:
            for fd in open_fds:
                try:
                    raw_close(fd)
                except OSError:
                    pass

        assert os.listdir(directory) == []
