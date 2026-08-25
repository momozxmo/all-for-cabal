from __future__ import annotations

import asyncio
import importlib
import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import timedelta

import httpx
import pytest
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from web import security
from web import aztek_sessions as pairing_module
from web.aztek_sessions import (AztekSessionService, InvalidStorageState,
                                PairingTokenNotFound,
                                PairingTokenUnavailable)
from web.models import (AuditLog, AztekSession, PairingToken, User, WebSession,
                        utc_now)


SECRET_COOKIE_VALUE = 'top-secret-aztek-cookie'
PAIRING_PRIVACY_SENTINEL = 'PAIRING-PRIVATE-SENTINEL-DO-NOT-LEAK'


def _pairing_http_module():
    return importlib.import_module('web.pairing_http')


def _pairing_interface(name):
    value = getattr(pairing_module, name, None)
    assert value is not None, 'Task 3 pairing interface %s is missing' % name
    return value


def _audit_snapshot(test_database):
    with test_database.session() as db:
        return [
            (row.action, row.status, row.summary, row.resource_id)
            for row in db.scalars(select(AuditLog).order_by(AuditLog.id)).all()
        ]


def _pairing_snapshot(test_database, user_id):
    with test_database.session() as db:
        tokens = db.scalars(
            select(PairingToken)
            .where(PairingToken.user_id == user_id)
            .order_by(PairingToken.created_at, PairingToken.id)
        ).all()
        session = db.scalar(
            select(AztekSession).where(AztekSession.user_id == user_id))
        return (
            [(row.id, row.token_hash, row.status, row.used_at) for row in tokens],
            None if session is None else (
                session.encrypted_state, session.account_label, session.status),
        )


def valid_storage_state():
    return {
        'cookies': [{
            'name': 'session',
            'value': SECRET_COOKIE_VALUE,
            'domain': '.combo-interactive.com',
            'path': '/',
            'httpOnly': True,
            'secure': True,
            'sameSite': 'Lax',
        }],
        'origins': [{
            'origin': 'https://aztek-tools.combo-interactive.com',
            'localStorage': [{'name': 'lang', 'value': 'th'}],
        }],
    }


def auth_storage_state():
    """A session captured while the user is on the shared SSO login host."""
    state = valid_storage_state()
    state['cookies'][0]['domain'] = 'auth.combo-interactive.com'
    state['origins'][0]['origin'] = 'https://auth.combo-interactive.com'
    return state


def issue_pairing_token(client) -> str:
    response = client.post('/api/aztek/pairing-token')
    assert response.status_code == 200
    body = response.json()
    assert 'expires_at' in body
    return body['pairing_token']


def test_pair_bridge_uses_the_one_time_token_instead_of_a_web_login(
        anonymous_client):
    """The bookmarklet opens from an Aztek tab, which may not share the local
    app's host-only login cookie. The bridge itself is harmless; /api/aztek/pair
    still requires the short-lived, single-use pairing token."""
    response = anonymous_client.get('/pair-bridge', follow_redirects=False)

    assert response.status_code == 200
    assert 'id="token"' in response.text
    assert '/api/aztek/pair' in response.text


def test_pairing_token_then_pair_connects(client, anonymous_client, member,
                                          test_database, test_settings):
    token = issue_pairing_token(client)

    response = anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': token,
        'account_label': 'main aztek',
        'storage_state': valid_storage_state(),
    })
    assert response.status_code == 200
    assert response.json() == {'status': 'connected', 'account_label': 'main aztek'}

    status = client.get('/api/aztek/status').json()
    assert status['connected'] is True
    assert status['status'] == 'active'
    assert status['account_label'] == 'main aztek'

    with test_database.session() as db:
        record = db.scalar(
            select(AztekSession).where(AztekSession.user_id == member.id))
        assert record is not None
        # Stored ciphertext must not leak the plaintext cookie value.
        assert SECRET_COOKIE_VALUE not in record.encrypted_state
        assert (security.decrypt_storage_state(record.encrypted_state, test_settings)
                == valid_storage_state())


def test_shared_sso_auth_origin_is_accepted(client, anonymous_client):
    token = issue_pairing_token(client)
    response = anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': token, 'storage_state': auth_storage_state()})
    assert response.status_code == 200

    status = client.get('/api/aztek/status').json()
    assert status['connected'] is True


def test_v2_app_origin_is_accepted(client, anonymous_client):
    # The live web app runs on the v2 host; localStorage is captured under it.
    token = issue_pairing_token(client)
    state = valid_storage_state()
    state['origins'][0]['origin'] = 'https://aztek-tools-v2.combo-interactive.com'
    response = anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': token, 'storage_state': state})
    assert response.status_code == 200
    assert client.get('/api/aztek/status').json()['connected'] is True


def test_pairing_token_is_single_use(client, anonymous_client):
    token = issue_pairing_token(client)
    first = anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': token, 'storage_state': valid_storage_state()})
    assert first.status_code == 200

    second = anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': token, 'storage_state': valid_storage_state()})
    assert second.status_code == 410


def test_expired_pairing_token_returns_410(client, anonymous_client, member,
                                           test_database):
    token = issue_pairing_token(client)
    with test_database.session() as db:
        record = db.scalar(
            select(PairingToken).where(PairingToken.user_id == member.id))
        record.expires_at = utc_now() - timedelta(seconds=1)

    response = anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': token, 'storage_state': valid_storage_state()})
    assert response.status_code == 410


def test_unknown_pairing_token_returns_404(anonymous_client):
    response = anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': 'x' * 43, 'storage_state': valid_storage_state()})
    assert response.status_code == 404


def test_creating_a_new_token_supersedes_the_previous(client, anonymous_client):
    first_token = issue_pairing_token(client)
    second_token = issue_pairing_token(client)

    superseded = anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': first_token, 'storage_state': valid_storage_state()})
    assert superseded.status_code == 410

    accepted = anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': second_token, 'storage_state': valid_storage_state()})
    assert accepted.status_code == 200


def test_foreign_cookie_domain_is_rejected(client, anonymous_client):
    token = issue_pairing_token(client)
    state = valid_storage_state()
    state['cookies'][0]['domain'] = 'evil.example.com'
    response = anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': token, 'storage_state': state})
    assert response.status_code == 422


def test_public_suffix_cookie_domain_is_rejected(client, anonymous_client):
    token = issue_pairing_token(client)
    state = valid_storage_state()
    state['cookies'][0]['domain'] = '.com'
    response = anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': token, 'storage_state': state})
    assert response.status_code == 422


def test_foreign_origin_is_rejected(client, anonymous_client):
    token = issue_pairing_token(client)
    state = valid_storage_state()
    state['origins'][0]['origin'] = 'https://evil.example.com'
    response = anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': token, 'storage_state': state})
    assert response.status_code == 422


def test_empty_cookies_are_rejected(client, anonymous_client):
    token = issue_pairing_token(client)
    state = valid_storage_state()
    state['cookies'] = []
    response = anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': token, 'storage_state': state})
    assert response.status_code == 422


def test_status_never_exposes_ciphertext(client, anonymous_client):
    token = issue_pairing_token(client)
    anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': token, 'storage_state': valid_storage_state()})

    body = client.get('/api/aztek/status').json()
    assert 'encrypted_state' not in body
    assert SECRET_COOKIE_VALUE not in str(body)
    assert set(body) == {
        'connected', 'status', 'account_label', 'updated_at', 'last_validated_at'}


def test_disconnect_removes_the_session(client, anonymous_client, member,
                                        test_database):
    token = issue_pairing_token(client)
    anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': token, 'storage_state': valid_storage_state()})

    response = client.delete('/api/aztek/session')
    assert response.status_code == 204

    status = client.get('/api/aztek/status').json()
    assert status['connected'] is False
    assert status['status'] == 'disconnected'
    with test_database.session() as db:
        assert db.scalar(
            select(AztekSession).where(AztekSession.user_id == member.id)) is None


def test_pairing_endpoints_require_auth_except_pair(anonymous_client):
    assert anonymous_client.post('/api/aztek/pairing-token').status_code == 401
    assert anonymous_client.get('/api/aztek/status').status_code == 401
    assert anonymous_client.delete('/api/aztek/session').status_code == 401


def test_pairing_reconnect_replaces_prior_session(client, anonymous_client, member,
                                                  test_database, test_settings):
    first = issue_pairing_token(client)
    anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': first, 'account_label': 'first',
        'storage_state': valid_storage_state()})

    second_state = valid_storage_state()
    second_state['cookies'][0]['value'] = 'a-different-cookie'
    second = issue_pairing_token(client)
    response = anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': second, 'account_label': 'second',
        'storage_state': second_state})
    assert response.status_code == 200

    with test_database.session() as db:
        rows = db.scalars(
            select(AztekSession).where(AztekSession.user_id == member.id)).all()
        assert len(rows) == 1
        assert rows[0].account_label == 'second'
        assert (security.decrypt_storage_state(rows[0].encrypted_state, test_settings)
                == second_state)


def test_save_storage_state_reactivates_and_replaces_one_user_session(
        member, test_database, test_settings):
    """Duplicating instead of replacing would leave runners with stale state."""
    service = AztekSessionService(test_settings)
    first = valid_storage_state()
    second = valid_storage_state()
    second['cookies'][0]['value'] = 'replacement-http-only-cookie'

    with test_database.session() as db:
        service.save_storage_state(db, member.id, first, 'old')
        service.mark_expired(db, db.get(User, member.id))
        saved = service.save_storage_state(db, member.id, second, 'local')
        assert saved.status == 'active'
        assert saved.account_label == 'local'

    with test_database.session() as db:
        rows = db.scalars(select(AztekSession).where(
            AztekSession.user_id == member.id)).all()
        assert len(rows) == 1
        assert security.decrypt_storage_state(
            rows[0].encrypted_state, test_settings) == second


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


def test_invalid_storage_keeps_pairing_token_pending(
        client, member, test_database, test_settings):
    """A failed capture must not burn the operator's single-use token."""
    token = issue_pairing_token(client)
    service = AztekSessionService(test_settings)
    invalid = valid_storage_state()
    invalid['cookies'] = []

    with test_database.session() as db:
        try:
            service.consume_pairing_token(db, token, invalid)
        except InvalidStorageState:
            pass
        else:
            raise AssertionError('invalid storage state was accepted')

    with test_database.session() as db:
        record = db.scalar(select(PairingToken).where(
            PairingToken.user_id == member.id))
        assert record.status == 'pending'
        assert record.used_at is None


@pytest.mark.parametrize('case', [
    'malformed_json',
    'invalid_utf8',
    'empty_body',
    'non_json',
    'wrong_top_level',
    'short_token',
    'long_token',
    'wrong_storage_state',
    'long_label',
])
def test_manual_pairing_payload_is_fixed_private_and_opens_no_business_session(
        case, client, anonymous_client, application, member, test_database,
        monkeypatch, caplog):
    handler_calls = []

    async def validation_handler(_request, error):
        handler_calls.append(('validation', repr(error)))
        return JSONResponse({'detail': 'handler-called'}, status_code=598)

    async def generic_handler(_request, error):
        handler_calls.append(('generic', repr(error)))
        return JSONResponse({'detail': 'handler-called'}, status_code=599)

    application.add_exception_handler(RequestValidationError, validation_handler)
    application.add_exception_handler(Exception, generic_handler)
    token = issue_pairing_token(client)
    before = _pairing_snapshot(test_database, member.id)
    audits_before = _audit_snapshot(test_database)
    sentinel = '%s-%s' % (PAIRING_PRIVACY_SENTINEL, case)

    if case == 'malformed_json':
        body, content_type = ('{"pairing_token":"%s","x":"%s"' %
                              (token, sentinel)).encode(), 'application/json'
    elif case == 'invalid_utf8':
        body, content_type = b'{"pairing_token":"' + token.encode() + b'","x":"\xff"}', 'application/json'
    elif case == 'empty_body':
        body, content_type = b'', 'application/json'
    elif case == 'non_json':
        body = json.dumps({'pairing_token': token, 'storage_state': sentinel}).encode()
        content_type = 'text/plain'
    elif case == 'wrong_top_level':
        body, content_type = json.dumps([sentinel]).encode(), 'application/json'
    elif case == 'short_token':
        body = json.dumps({'pairing_token': 'short', 'probe': sentinel,
                           'storage_state': valid_storage_state()}).encode()
        content_type = 'application/json'
    elif case == 'long_token':
        body = json.dumps({'pairing_token': sentinel + ('x' * 210),
                           'storage_state': valid_storage_state()}).encode()
        content_type = 'application/json'
    elif case == 'wrong_storage_state':
        body = json.dumps({'pairing_token': token,
                           'storage_state': sentinel}).encode()
        content_type = 'application/json'
    else:
        body = json.dumps({'pairing_token': token,
                           'account_label': sentinel + ('x' * 150),
                           'storage_state': valid_storage_state()}).encode()
        content_type = 'application/json'

    original_session = test_database.session
    opened = []

    @contextmanager
    def tracked_session():
        opened.append('opened')
        with original_session() as db:
            yield db

    monkeypatch.setattr(test_database, 'session', tracked_session)
    with caplog.at_level('DEBUG'):
        response = anonymous_client.post(
            '/api/aztek/pair', content=body,
            headers={'content-type': content_type})
    monkeypatch.setattr(test_database, 'session', original_session)

    assert response.status_code == 422
    assert response.json() == {'detail': 'ข้อมูลเซสชันไม่ถูกต้อง'}
    assert opened == []
    assert handler_calls == []
    assert _pairing_snapshot(test_database, member.id) == before
    assert _audit_snapshot(test_database) == audits_before
    assert sentinel not in response.text
    assert sentinel not in caplog.text


def test_pairing_throttle_privacy_uses_domain_hmac_for_invalid_payloads(
        anonymous_client, application, test_settings):
    raw_token = 'T' * 24 + PAIRING_PRIVACY_SENTINEL
    payload = {'pairing_token': raw_token,
               'account_label': PAIRING_PRIVACY_SENTINEL,
               'storage_state': PAIRING_PRIVACY_SENTINEL}

    responses = [
        anonymous_client.post('/api/aztek/pair', json=payload)
        for _ in range(6)
    ]

    assert [response.status_code for response in responses] == [422] * 5 + [429]
    assert responses[-1].json() == {'detail': 'ลองใหม่ภายหลัง'}
    keys = tuple(application.state.pairing_throttle._failures)
    assert len(keys) == 1
    key = keys[0]
    assert key.startswith('testclient|')
    assert raw_token not in key
    assert PAIRING_PRIVACY_SENTINEL not in key
    assert security.hash_token(raw_token, test_settings) not in key
    assert len(key.rsplit('|', 1)[1]) == 64


def test_pairing_transaction_state_parser_result_is_frozen_and_secret_free(
        test_settings):
    module = _pairing_http_module()
    payload = module.StorageStatePayload(
        pairing_token='x' * 24, storage_state=valid_storage_state())
    result = module.PairingParseResult(payload=payload, fingerprint='f' * 64)

    with pytest.raises(Exception):
        payload.pairing_token = 'changed'
    with pytest.raises(Exception):
        result.fingerprint = PAIRING_PRIVACY_SENTINEL
    assert PAIRING_PRIVACY_SENTINEL not in repr(result)


def test_pairing_issue_auth_session_closes_before_business_session(
        client, application, test_database, monkeypatch):
    module = _pairing_http_module()
    conflict_type = _pairing_interface('PairingTokenIssueConflict')
    service = application.state.aztek_session_service
    original_apply = service._apply_pairing_issue
    raw_web_session = client.cookies.get('afc_session')
    assert raw_web_session

    with test_database.session() as db:
        web_session = db.scalar(select(WebSession).where(
            WebSession.token_hash == security.hash_token(
                raw_web_session, application.state.settings)))
        before_last_seen = web_session.last_seen_at

    def conflict(_db, _attempt):
        raise conflict_type()

    monkeypatch.setattr(service, '_apply_pairing_issue', conflict)
    original_session = test_database.session
    events = []
    active = set()

    @contextmanager
    def tracked_session():
        with original_session() as db:
            identity = id(db)
            events.append(('open', identity, tuple(active)))
            active.add(identity)
            try:
                yield db
            finally:
                active.remove(identity)
                events.append(('close', identity, tuple(active)))

    monkeypatch.setattr(test_database, 'session', tracked_session)
    response = client.post('/api/aztek/pairing-token')
    monkeypatch.setattr(test_database, 'session', original_session)
    monkeypatch.setattr(service, '_apply_pairing_issue', original_apply)

    assert response.status_code == 409
    assert response.json() == {'detail': 'pairing_token_conflict'}
    opened = [event for event in events if event[0] == 'open']
    assert len(opened) == 3
    assert len({event[1] for event in opened}) == 3
    assert all(event[2] == () for event in opened)
    assert active == set()
    assert application.state.pairing_issue_reservations.reserved_user_ids == ()
    with test_database.session() as db:
        web_session = db.scalar(select(WebSession).where(
            WebSession.token_hash == security.hash_token(
                raw_web_session, application.state.settings)))
        assert web_session.last_seen_at is not None
        assert web_session.last_seen_at != before_last_seen
    assert module.PairingPrincipalSnapshot.__dataclass_params__.frozen is True


def test_concurrent_pairing_issue_same_user_has_one_http_winner(
        client, application, member, test_database, monkeypatch):
    service = application.state.aztek_session_service
    original_prepare = service._prepare_pairing_issue
    entered = threading.Event()
    release = threading.Event()
    call_lock = threading.Lock()
    call_count = 0

    def held_prepare(db, user_id):
        nonlocal call_count
        attempt = original_prepare(db, user_id)
        with call_lock:
            call_count += 1
            first = call_count == 1
        if first:
            entered.set()
            assert release.wait(5)
        return attempt

    monkeypatch.setattr(service, '_prepare_pairing_issue', held_prepare)
    from fastapi.testclient import TestClient
    second_client = TestClient(application)
    second_client.cookies.set('afc_session', client.cookies.get('afc_session'))
    results = []

    first_thread = threading.Thread(
        target=lambda: results.append(client.post('/api/aztek/pairing-token')))
    second_thread = threading.Thread(
        target=lambda: results.append(second_client.post('/api/aztek/pairing-token')))
    first_thread.start()
    assert entered.wait(5)
    second_thread.start()
    second_thread.join(5)
    assert not second_thread.is_alive()
    release.set()
    first_thread.join(5)
    assert not first_thread.is_alive()

    assert sorted(response.status_code for response in results) == [200, 409]
    loser = next(response for response in results if response.status_code == 409)
    assert loser.json() == {'detail': 'pairing_token_conflict'}
    with test_database.session() as db:
        pending = db.scalars(select(PairingToken).where(
            PairingToken.user_id == member.id,
            PairingToken.status == 'pending',
            PairingToken.used_at.is_(None))).all()
        assert len(pending) == 1
    assert application.state.pairing_issue_reservations.reserved_user_ids == ()


def test_concurrent_pairing_issue_different_users_do_not_semantically_conflict(
        client_for, member, other_member, application, test_database, monkeypatch):
    service = application.state.aztek_session_service
    original_prepare = service._prepare_pairing_issue
    barrier = threading.Barrier(2)

    def held_prepare(db, user_id):
        attempt = original_prepare(db, user_id)
        barrier.wait(timeout=5)
        return attempt

    monkeypatch.setattr(service, '_prepare_pairing_issue', held_prepare)
    clients = [client_for(member), client_for(other_member)]
    results = []
    threads = [
        threading.Thread(target=lambda item=item: results.append(
            item.post('/api/aztek/pairing-token')))
        for item in clients
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(8)
        assert not thread.is_alive()

    assert sorted(response.status_code for response in results) == [200, 200]
    with test_database.session() as db:
        for user_id in (member.id, other_member.id):
            assert len(db.scalars(select(PairingToken).where(
                PairingToken.user_id == user_id,
                PairingToken.status == 'pending',
                PairingToken.used_at.is_(None))).all()) == 1


@pytest.mark.parametrize('with_prior', [False, True])
def test_concurrent_pairing_issue_same_snapshot_cross_worker_has_one_winner(
        with_prior, member, test_database, test_settings):
    service = AztekSessionService(test_settings)
    conflict_type = _pairing_interface('PairingTokenIssueConflict')
    begin_fresh = _pairing_interface('_begin_fresh_pairing_write')
    if with_prior:
        with test_database.session() as db:
            service.create_pairing_token(db, db.get(User, member.id))

    attempts = []
    for _ in range(2):
        with test_database.session() as db:
            attempts.append(service._prepare_pairing_issue(db, member.id))
    assert attempts[0].prior_token_id == attempts[1].prior_token_id
    original_attempts = [(item.raw_token, item.token_hash, item.created_at,
                          item.expires_at) for item in attempts]

    results = []
    for attempt in attempts:
        try:
            with test_database.session() as db:
                begin_fresh(db)
                results.append(service._apply_pairing_issue(db, attempt))
        except conflict_type:
            results.append('conflict')

    assert sum(item == 'conflict' for item in results) == 1
    assert sum(item != 'conflict' for item in results) == 1
    assert [(item.raw_token, item.token_hash, item.created_at, item.expires_at)
            for item in attempts] == original_attempts
    with test_database.session() as db:
        pending = db.scalars(select(PairingToken).where(
            PairingToken.user_id == member.id,
            PairingToken.status == 'pending',
            PairingToken.used_at.is_(None))).all()
        assert len(pending) == 1


@pytest.mark.parametrize('with_prior', [False, True])
def test_concurrent_pairing_issue_same_snapshot_uses_two_http_worker_apps(
        with_prior, member, test_database, test_settings, monkeypatch):
    app_module = importlib.import_module('web.app')
    applications = [
        app_module.create_app(test_settings, test_database),
        app_module.create_app(test_settings, test_database),
    ]
    if with_prior:
        with test_database.session() as db:
            applications[0].state.aztek_session_service.create_pairing_token(
                db, db.get(User, member.id))
    with test_database.session() as db:
        raw_web_session = applications[0].state.auth_service.create_session(
            db, db.get(User, member.id))

    barrier = threading.Barrier(2)

    def synchronized_prepare(original):
        def prepare(db, user_id):
            attempt = original(db, user_id)
            barrier.wait(timeout=5)
            return attempt
        return prepare

    for worker_app in applications:
        service = worker_app.state.aztek_session_service
        monkeypatch.setattr(
            service, '_prepare_pairing_issue',
            synchronized_prepare(service._prepare_pairing_issue))

    from fastapi.testclient import TestClient
    clients = [TestClient(worker_app) for worker_app in applications]
    for worker_client in clients:
        worker_client.cookies.set('afc_session', raw_web_session)
    results = []
    threads = [
        threading.Thread(target=lambda index=index: results.append(
            clients[index].post('/api/aztek/pairing-token')))
        for index in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(8)
        assert not thread.is_alive()

    assert sorted(response.status_code for response in results) == [200, 409]
    loser = next(response for response in results if response.status_code == 409)
    assert loser.json() == {'detail': 'pairing_token_conflict'}
    assert all(
        worker_app.state.pairing_issue_reservations.reserved_user_ids == ()
        for worker_app in applications)
    with test_database.session() as db:
        pending = db.scalars(select(PairingToken).where(
            PairingToken.user_id == member.id,
            PairingToken.status == 'pending',
            PairingToken.used_at.is_(None))).all()
        assert len(pending) == 1


def test_pairing_partial_index_integrity_failure_leaves_caller_session_failed(
        member, test_database, test_settings, monkeypatch):
    service = AztekSessionService(test_settings)
    conflict_type = _pairing_interface('PairingTokenIssueConflict')
    attempts = []
    for _ in range(2):
        with test_database.session() as snapshot_db:
            attempts.append(service._prepare_pairing_issue(
                snapshot_db, member.id))
    with test_database.session() as winner_db:
        service._apply_pairing_issue(winner_db, attempts[0])

    caller: Session = test_database._session_factory()
    commit_calls = []
    rollback_calls = []
    original_commit = caller.commit
    original_rollback = caller.rollback
    monkeypatch.setattr(caller, 'commit', lambda: commit_calls.append(True))
    monkeypatch.setattr(caller, 'rollback', lambda: rollback_calls.append(True))
    try:
        with pytest.raises(conflict_type) as caught:
            service._apply_pairing_issue(caller, attempts[1])
        assert caught.value.__context__ is None
        assert caught.value.__cause__ is None
        assert caller.is_active is False
        assert caller.in_transaction()
        assert commit_calls == []
        assert rollback_calls == []
    finally:
        monkeypatch.setattr(caller, 'commit', original_commit)
        monkeypatch.setattr(caller, 'rollback', original_rollback)
        caller.rollback()
        caller.close()

    with test_database.session() as db:
        pending = db.scalars(select(PairingToken).where(
            PairingToken.user_id == member.id,
            PairingToken.status == 'pending',
            PairingToken.used_at.is_(None))).all()
        assert len(pending) == 1


def test_concurrent_pairing_consumption_two_http_clients_have_one_winner(
        client, application, member, test_database, test_settings, monkeypatch):
    token = issue_pairing_token(client)
    begin_fresh = _pairing_interface('_begin_fresh_pairing_write')
    barrier = threading.Barrier(2)
    seen_threads = set()
    seen_lock = threading.Lock()

    def synchronized_begin(db):
        identity = threading.get_ident()
        with seen_lock:
            first = identity not in seen_threads
            seen_threads.add(identity)
        if first:
            barrier.wait(timeout=5)
        return begin_fresh(db)

    monkeypatch.setattr(pairing_module, '_begin_fresh_pairing_write',
                        synchronized_begin)
    from fastapi.testclient import TestClient
    clients = [TestClient(application), TestClient(application)]
    states = [valid_storage_state(), valid_storage_state()]
    states[0]['cookies'][0]['value'] = 'winner-a'
    states[1]['cookies'][0]['value'] = 'winner-b'
    results = []
    threads = [
        threading.Thread(target=lambda index=index: results.append((
            index, clients[index].post('/api/aztek/pair', json={
                'pairing_token': token,
                'account_label': 'account-%d' % index,
                'storage_state': states[index],
            }))))
        for index in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(8)
        assert not thread.is_alive()

    assert sorted(response.status_code for _, response in results) == [200, 410]
    winner_index, winner_response = next(
        item for item in results if item[1].status_code == 200)
    assert winner_response.json() == {
        'status': 'connected', 'account_label': 'account-%d' % winner_index}
    with test_database.session() as db:
        record = db.scalar(select(PairingToken).where(
            PairingToken.user_id == member.id))
        saved = db.scalar(select(AztekSession).where(
            AztekSession.user_id == member.id))
        assert record.status == 'used'
        assert record.used_at is not None
        assert security.decrypt_storage_state(
            saved.encrypted_state, test_settings) == states[winner_index]


def test_pairing_event_loop_heartbeat_advances_during_sqlite_contention(
        client, application, test_database):
    token = issue_pairing_token(client)
    raw_connection = test_database.engine.raw_connection()
    cursor = raw_connection.cursor()
    cursor.execute('BEGIN IMMEDIATE')

    async def scenario():
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(
                transport=transport, base_url='http://testserver') as async_client:
            request_task = asyncio.create_task(async_client.post(
                '/api/aztek/pair', json={
                    'pairing_token': token,
                    'storage_state': valid_storage_state(),
                }))
            ticks = 0
            while not request_task.done():
                await asyncio.sleep(0.01)
                ticks += 1
            return await request_task, ticks

    try:
        started = time.monotonic()
        response, ticks = asyncio.run(scenario())
        elapsed = time.monotonic() - started
    finally:
        raw_connection.rollback()
        cursor.close()
        raw_connection.close()

    assert response.status_code == 409
    assert response.json() == {'detail': 'pairing_busy'}
    assert ticks >= 5
    assert elapsed < 3


def test_pairing_busy_issue_reuses_one_snapshot_candidate_under_real_lock(
        client, application, member, test_database, monkeypatch):
    service = application.state.aztek_session_service
    original_prepare = service._prepare_pairing_issue
    prepared = []
    snapshot_ready = threading.Event()
    release_snapshot = threading.Event()

    def tracked_prepare(db, user_id):
        attempt = original_prepare(db, user_id)
        prepared.append(attempt)
        snapshot_ready.set()
        assert release_snapshot.wait(5)
        return attempt

    monkeypatch.setattr(service, '_prepare_pairing_issue', tracked_prepare)
    responses = []
    request_thread = threading.Thread(target=lambda: responses.append(
        client.post('/api/aztek/pairing-token')))
    request_thread.start()
    assert snapshot_ready.wait(5)

    raw_connection = test_database.engine.raw_connection()
    cursor = raw_connection.cursor()
    cursor.execute('BEGIN IMMEDIATE')
    release_snapshot.set()
    started = time.monotonic()
    try:
        request_thread.join(5)
        assert not request_thread.is_alive()
        elapsed = time.monotonic() - started
    finally:
        raw_connection.rollback()
        cursor.close()
        raw_connection.close()

    assert len(prepared) == 1
    assert responses[0].status_code == 409
    assert responses[0].json() == {'detail': 'pairing_busy'}
    assert elapsed < 3
    with test_database.session() as db:
        assert db.scalar(select(PairingToken.id).where(
            PairingToken.user_id == member.id)) is None


def test_pairing_busy_nonbusy_operational_error_is_fixed_500_without_retry(
        client, application, member, test_database, monkeypatch, caplog):
    service = application.state.aztek_session_service
    original_prepare = service._prepare_pairing_issue
    prepare_calls = []
    begin_calls = []

    def tracked_prepare(db, user_id):
        attempt = original_prepare(db, user_id)
        prepare_calls.append(attempt)
        return attempt

    def fail_begin(_db):
        begin_calls.append(True)
        raise OperationalError(
            'fixed-sql', {}, RuntimeError(PAIRING_PRIVACY_SENTINEL))

    monkeypatch.setattr(service, '_prepare_pairing_issue', tracked_prepare)
    monkeypatch.setattr(pairing_module, '_begin_fresh_pairing_write', fail_begin)
    with caplog.at_level('DEBUG'):
        response = client.post('/api/aztek/pairing-token')

    assert response.status_code == 500
    assert response.json() == {'detail': 'pairing_failed'}
    assert len(prepare_calls) == 1
    assert begin_calls == [True]
    with test_database.session() as db:
        assert db.scalar(select(PairingToken.id).where(
            PairingToken.user_id == member.id)) is None
    assert PAIRING_PRIVACY_SENTINEL not in response.text
    assert PAIRING_PRIVACY_SENTINEL not in caplog.text


def test_postgresql_pairing_statements_are_bound_conditional_and_locking():
    user_sentinel = 'user-' + PAIRING_PRIVACY_SENTINEL
    token_id_sentinel = 'token-id-' + PAIRING_PRIVACY_SENTINEL
    token_hash_sentinel = 'hash-' + PAIRING_PRIVACY_SENTINEL
    supersede = _pairing_interface('_supersede_pairing_token_statement')(
        user_sentinel, token_id_sentinel)
    claim = _pairing_interface('_claim_pairing_token_statement')(
        token_hash_sentinel, utc_now())
    expire = _pairing_interface('_expire_pairing_token_statement')(
        token_hash_sentinel, utc_now())
    user_lock = _pairing_interface('_pairing_user_for_update_statement')(
        user_sentinel)
    session_lock = _pairing_interface('_aztek_session_for_update_statement')(
        user_sentinel)

    compiled_objects = [statement.compile(
        dialect=postgresql.dialect(), compile_kwargs={'literal_binds': False})
        for statement in (supersede, claim, expire, user_lock, session_lock)]
    compiled = [str(item).upper() for item in compiled_objects]

    assert all(fragment in compiled[0] for fragment in (
        'PAIRING_TOKENS.ID', 'PAIRING_TOKENS.USER_ID',
        'PAIRING_TOKENS.STATUS', 'PAIRING_TOKENS.USED_AT IS NULL'))
    assert all(fragment in compiled[1] for fragment in (
        'PAIRING_TOKENS.TOKEN_HASH', 'PAIRING_TOKENS.STATUS',
        'PAIRING_TOKENS.USED_AT IS NULL', 'PAIRING_TOKENS.EXPIRES_AT >'))
    assert all(fragment in compiled[2] for fragment in (
        'PAIRING_TOKENS.TOKEN_HASH', 'PAIRING_TOKENS.STATUS',
        'PAIRING_TOKENS.USED_AT IS NULL', 'PAIRING_TOKENS.EXPIRES_AT <='))
    assert ('RETURNING PAIRING_TOKENS.USER_ID, PAIRING_TOKENS.EXPIRES_AT'
            in compiled[1])
    assert 'RETURNING PAIRING_TOKENS.USER_ID' in compiled[2]
    assert 'FOR UPDATE' in compiled[3]
    assert 'FOR UPDATE' in compiled[4]

    bound_values = [set(item.params.values()) for item in compiled_objects]
    assert {user_sentinel, token_id_sentinel}.issubset(bound_values[0])
    assert token_hash_sentinel in bound_values[1]
    assert token_hash_sentinel in bound_values[2]
    assert user_sentinel in bound_values[3]
    assert user_sentinel in bound_values[4]
    assert all(PAIRING_PRIVACY_SENTINEL not in sql for sql in compiled)


def test_encrypt_failure_stops_before_pairing_write_and_is_private(
        client, anonymous_client, application, member, test_database,
        monkeypatch, caplog):
    token = issue_pairing_token(client)
    before = _pairing_snapshot(test_database, member.id)
    audits_before = _audit_snapshot(test_database)
    begin_calls = []
    claim_calls = []

    def fail_encrypt(_state, _settings):
        raise RuntimeError(PAIRING_PRIVACY_SENTINEL)

    def begin_spy(_db):
        begin_calls.append(True)

    def claim_spy(*_args):
        claim_calls.append(True)

    monkeypatch.setattr(pairing_module, 'encrypt_storage_state', fail_encrypt)
    monkeypatch.setattr(pairing_module, '_begin_fresh_pairing_write', begin_spy)
    monkeypatch.setattr(pairing_module, '_claim_pairing_token', claim_spy)
    with caplog.at_level('DEBUG'):
        response = anonymous_client.post('/api/aztek/pair', json={
            'pairing_token': token,
            'account_label': PAIRING_PRIVACY_SENTINEL,
            'storage_state': valid_storage_state(),
        })

    assert response.status_code == 500
    assert response.json() == {'detail': 'pairing_failed'}
    assert begin_calls == []
    assert claim_calls == []
    assert _pairing_snapshot(test_database, member.id) == before
    assert _audit_snapshot(test_database) == audits_before
    assert PAIRING_PRIVACY_SENTINEL not in response.text
    assert PAIRING_PRIVACY_SENTINEL not in caplog.text


@pytest.mark.parametrize('failure', ['save', 'audit'])
def test_pairing_save_failure_and_pairing_audit_failure_roll_back_claim(
        failure, client, anonymous_client, application, member, test_database,
        test_settings, monkeypatch, caplog):
    first = issue_pairing_token(client)
    first_response = anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': first, 'account_label': 'prior',
        'storage_state': valid_storage_state()})
    assert first_response.status_code == 200
    token = issue_pairing_token(client)
    before = _pairing_snapshot(test_database, member.id)
    audits_before = _audit_snapshot(test_database)
    next_state = valid_storage_state()
    next_state['cookies'][0]['value'] = PAIRING_PRIVACY_SENTINEL

    if failure == 'save':
        def fail_save(*_args, **_kwargs):
            raise RuntimeError(PAIRING_PRIVACY_SENTINEL)
        monkeypatch.setattr(
            application.state.aztek_session_service,
            '_save_encrypted_state', fail_save)
    else:
        app_module = importlib.import_module('web.app')
        original_audit = app_module.write_audit

        def fail_connected_audit(*args, **kwargs):
            if kwargs.get('action') == 'aztek.connected':
                raise RuntimeError(PAIRING_PRIVACY_SENTINEL)
            return original_audit(*args, **kwargs)

        monkeypatch.setattr(app_module, 'write_audit', fail_connected_audit)

    with caplog.at_level('DEBUG'):
        response = anonymous_client.post('/api/aztek/pair', json={
            'pairing_token': token,
            'account_label': PAIRING_PRIVACY_SENTINEL,
            'storage_state': next_state,
        })

    assert response.status_code == 500
    assert response.json() == {'detail': 'pairing_failed'}
    assert _pairing_snapshot(test_database, member.id) == before
    assert _audit_snapshot(test_database) == audits_before
    assert PAIRING_PRIVACY_SENTINEL not in response.text
    assert PAIRING_PRIVACY_SENTINEL not in caplog.text


def _context_failure_wrapper(original_session, *, fail_call, after_commit,
                             error_factory, evidence):
    calls = 0

    @contextmanager
    def wrapped():
        nonlocal calls
        calls += 1
        cm = original_session()
        db = cm.__enter__()
        this_call = calls
        try:
            yield db
        except BaseException as error:
            evidence.append(('error-exit', this_call))
            cm.__exit__(type(error), error, error.__traceback__)
            evidence.append(('rolled-back-closed', this_call))
            raise
        else:
            if this_call == fail_call and not after_commit:
                error = error_factory()
                evidence.append(('inject-before-commit', this_call))
                cm.__exit__(type(error), error, error.__traceback__)
                evidence.append(('rolled-back-closed', this_call))
                raise error
            cm.__exit__(None, None, None)
            evidence.append(('committed-closed', this_call))
            if this_call == fail_call and after_commit:
                evidence.append(('inject-after-commit', this_call))
                raise error_factory()

    return wrapped


def _cleanup_busy_after_commit_wrapper(
        original_session, *, fail_call, evidence):
    calls = 0

    @contextmanager
    def wrapped():
        nonlocal calls
        calls += 1
        this_call = calls
        with original_session() as db:
            if this_call == fail_call:
                original_commit = db.commit
                commit_calls = 0

                def cleanup_busy_commit():
                    nonlocal commit_calls
                    commit_calls += 1
                    if commit_calls == 1:
                        result = original_commit()
                        evidence.append(('durable-explicit-commit', this_call))
                        return result
                    evidence.append(('coded-busy-cleanup', this_call))
                    raise _sqlalchemy_operational_error(busy=True)

                db.commit = cleanup_busy_commit
            yield db

    return wrapped


def test_pairing_cleanup_busy_after_durable_issue_does_not_retry_to_conflict(
        client, application, member, test_database, monkeypatch):
    original_session = test_database.session
    evidence = []
    # auth, snapshot, then the first write context
    monkeypatch.setattr(test_database, 'session',
                        _cleanup_busy_after_commit_wrapper(
                            original_session, fail_call=3,
                            evidence=evidence))
    response = client.post('/api/aztek/pairing-token')
    monkeypatch.setattr(test_database, 'session', original_session)

    assert response.status_code == 409
    assert response.json() == {'detail': 'pairing_busy'}
    assert evidence.count(('durable-explicit-commit', 3)) == 1
    assert evidence.count(('coded-busy-cleanup', 3)) == 1
    # A retry would turn this durable candidate into semantic conflict.
    assert not any(call > 3 for _event, call in evidence)
    with test_database.session() as db:
        pending = db.scalars(select(PairingToken).where(
            PairingToken.user_id == member.id,
            PairingToken.status == 'pending',
            PairingToken.used_at.is_(None))).all()
        assert len(pending) == 1


def test_pairing_cleanup_busy_after_durable_consume_does_not_retry_to_410(
        client, anonymous_client, member, test_database, monkeypatch):
    token = issue_pairing_token(client)
    original_session = test_database.session
    evidence = []
    monkeypatch.setattr(test_database, 'session',
                        _cleanup_busy_after_commit_wrapper(
                            original_session, fail_call=1,
                            evidence=evidence))
    response = anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': token,
        'account_label': 'durable-cleanup',
        'storage_state': valid_storage_state(),
    })
    monkeypatch.setattr(test_database, 'session', original_session)

    assert response.status_code == 409
    assert response.json() == {'detail': 'pairing_busy'}
    assert evidence == [
        ('durable-explicit-commit', 1), ('coded-busy-cleanup', 1)]
    with test_database.session() as db:
        record = db.scalar(select(PairingToken).where(
            PairingToken.user_id == member.id))
        saved = db.scalar(select(AztekSession).where(
            AztekSession.user_id == member.id))
        assert record.status == 'used'
        assert record.used_at is not None
        assert saved is not None
        assert saved.account_label == 'durable-cleanup'


@pytest.mark.parametrize('after_commit', [False, True])
def test_pairing_commit_failure_is_mapped_after_context_cleanup(
        after_commit, client, anonymous_client, application, member,
        test_database, monkeypatch, caplog):
    token = issue_pairing_token(client)
    original_session = test_database.session
    evidence = []
    monkeypatch.setattr(test_database, 'session', _context_failure_wrapper(
        original_session, fail_call=1, after_commit=after_commit,
        error_factory=lambda: RuntimeError(PAIRING_PRIVACY_SENTINEL),
        evidence=evidence))

    with caplog.at_level('DEBUG'):
        response = anonymous_client.post('/api/aztek/pair', json={
            'pairing_token': token, 'storage_state': valid_storage_state()})
    monkeypatch.setattr(test_database, 'session', original_session)

    assert response.status_code == 500
    assert response.json() == {'detail': 'pairing_failed'}
    assert any(item[0].endswith('closed') for item in evidence)
    after = _pairing_snapshot(test_database, member.id)
    # Both injected positions occur after the route's explicit durable commit.
    assert after[0][0][2] == 'used'
    assert after[1] is not None
    assert PAIRING_PRIVACY_SENTINEL not in response.text
    assert PAIRING_PRIVACY_SENTINEL not in caplog.text


@pytest.mark.parametrize('after_commit', [False, True])
def test_pairing_issue_commit_failure_releases_reservation_after_cleanup(
        after_commit, client, application, member, test_database, monkeypatch,
        caplog):
    before = _pairing_snapshot(test_database, member.id)
    original_session = test_database.session
    evidence = []
    # auth, snapshot, then write
    monkeypatch.setattr(test_database, 'session', _context_failure_wrapper(
        original_session, fail_call=3, after_commit=after_commit,
        error_factory=lambda: RuntimeError(PAIRING_PRIVACY_SENTINEL),
        evidence=evidence))
    with caplog.at_level('DEBUG'):
        response = client.post('/api/aztek/pairing-token')
    monkeypatch.setattr(test_database, 'session', original_session)

    assert response.status_code == 500
    assert response.json() == {'detail': 'pairing_failed'}
    assert application.state.pairing_issue_reservations.reserved_user_ids == ()
    after = _pairing_snapshot(test_database, member.id)
    # Both injected positions occur after the route's explicit durable commit.
    assert len(after[0]) == len(before[0]) + 1
    assert sum(row[2] == 'pending' for row in after[0]) == 1
    assert PAIRING_PRIVACY_SENTINEL not in response.text
    assert PAIRING_PRIVACY_SENTINEL not in caplog.text


def test_pairing_issue_audit_failure_rolls_back_and_releases_reservation(
        client, application, member, test_database, monkeypatch, caplog):
    app_module = importlib.import_module('web.app')
    raw_web_session = client.cookies.get('afc_session')
    before = _pairing_snapshot(test_database, member.id)

    def fail_audit(*_args, **_kwargs):
        raise RuntimeError(PAIRING_PRIVACY_SENTINEL)

    monkeypatch.setattr(app_module, 'write_audit', fail_audit)
    with caplog.at_level('DEBUG'):
        response = client.post('/api/aztek/pairing-token')

    assert response.status_code == 500
    assert response.json() == {'detail': 'pairing_failed'}
    assert _pairing_snapshot(test_database, member.id) == before
    assert application.state.pairing_issue_reservations.reserved_user_ids == ()
    with test_database.session() as db:
        web_session = db.scalar(select(WebSession).where(
            WebSession.token_hash == security.hash_token(
                raw_web_session, application.state.settings)))
        assert web_session.last_seen_at is not None
    assert PAIRING_PRIVACY_SENTINEL not in response.text
    assert PAIRING_PRIVACY_SENTINEL not in caplog.text


@pytest.mark.parametrize('after_commit', [False, True])
def test_pairing_issue_snapshot_cleanup_failure_never_exposes_candidate(
        after_commit, client, application, member, test_database, monkeypatch,
        caplog):
    before = _pairing_snapshot(test_database, member.id)
    original_session = test_database.session
    evidence = []
    # call 1 authenticates; call 2 is the no-op snapshot context
    monkeypatch.setattr(test_database, 'session', _context_failure_wrapper(
        original_session, fail_call=2, after_commit=after_commit,
        error_factory=lambda: RuntimeError(PAIRING_PRIVACY_SENTINEL),
        evidence=evidence))
    with caplog.at_level('DEBUG'):
        response = client.post('/api/aztek/pairing-token')
    monkeypatch.setattr(test_database, 'session', original_session)

    assert response.status_code == 500
    assert response.json() == {'detail': 'pairing_failed'}
    assert 'pairing_token' not in response.text
    assert _pairing_snapshot(test_database, member.id) == before
    assert application.state.pairing_issue_reservations.reserved_user_ids == ()
    assert any(item[1] == 2 and item[0].endswith('closed') for item in evidence)
    assert PAIRING_PRIVACY_SENTINEL not in response.text
    assert PAIRING_PRIVACY_SENTINEL not in caplog.text


def test_pairing_issue_auth_cleanup_failure_is_fixed_and_has_no_business_session(
        client, application, test_database, monkeypatch, caplog):
    original_session = test_database.session
    evidence = []
    monkeypatch.setattr(test_database, 'session', _context_failure_wrapper(
        original_session, fail_call=1, after_commit=False,
        error_factory=lambda: RuntimeError(PAIRING_PRIVACY_SENTINEL),
        evidence=evidence))
    with caplog.at_level('DEBUG'):
        response = client.post('/api/aztek/pairing-token')
    monkeypatch.setattr(test_database, 'session', original_session)

    assert response.status_code == 500
    assert response.json() == {'detail': 'pairing_failed'}
    assert evidence == [
        ('inject-before-commit', 1), ('rolled-back-closed', 1)]
    assert application.state.pairing_issue_reservations.reserved_user_ids == ()
    assert PAIRING_PRIVACY_SENTINEL not in response.text
    assert PAIRING_PRIVACY_SENTINEL not in caplog.text


class _DriverBusyError(Exception):
    sqlite_errorcode = sqlite3.SQLITE_BUSY


def _sqlalchemy_operational_error(*, busy):
    original = _DriverBusyError() if busy else RuntimeError('not-busy-driver')
    return OperationalError('fixed statement', {}, original)


def _actual_commit_failure_sessions(
        original_session, *, first_fail_call, busy, evidence):
    calls = 0

    @contextmanager
    def wrapped():
        nonlocal calls
        calls += 1
        this_call = calls
        with original_session() as db:
            if this_call >= first_fail_call:
                original_rollback = db.rollback
                original_close = db.close

                def fail_commit():
                    evidence.append(('commit-raised', this_call))
                    raise _sqlalchemy_operational_error(busy=busy)

                def tracked_rollback():
                    evidence.append(('rollback', this_call))
                    return original_rollback()

                def tracked_close():
                    evidence.append(('close', this_call))
                    return original_close()

                db.commit = fail_commit
                db.rollback = tracked_rollback
                db.close = tracked_close
            yield db

    return wrapped


@pytest.mark.parametrize('flow', ['issue', 'consume', 'expiration'])
@pytest.mark.parametrize('busy', [True, False])
def test_pairing_actual_session_commit_failure_is_rolled_back_and_fixed(
        flow, busy, client, anonymous_client, application, member,
        test_database, monkeypatch, caplog):
    token = None
    if flow != 'issue':
        token = issue_pairing_token(client)
        if flow == 'expiration':
            with test_database.session() as db:
                record = db.scalar(select(PairingToken).where(
                    PairingToken.user_id == member.id))
                record.expires_at = utc_now() - timedelta(seconds=1)
    before = _pairing_snapshot(test_database, member.id)
    audits_before = _audit_snapshot(test_database)
    original_session = test_database.session
    evidence = []
    first_fail_call = 3 if flow == 'issue' else 1
    monkeypatch.setattr(
        test_database, 'session',
        _actual_commit_failure_sessions(
            original_session,
            first_fail_call=first_fail_call,
            busy=busy,
            evidence=evidence,
        ))

    with caplog.at_level('DEBUG'):
        if flow == 'issue':
            response = client.post('/api/aztek/pairing-token')
        else:
            response = anonymous_client.post('/api/aztek/pair', json={
                'pairing_token': token,
                'storage_state': valid_storage_state(),
            })
    monkeypatch.setattr(test_database, 'session', original_session)

    assert response.status_code == (409 if busy else 500)
    assert response.json() == {
        'detail': 'pairing_busy' if busy else 'pairing_failed'}
    expected_failures = 4 if busy else 1
    assert len([item for item in evidence if item[0] == 'commit-raised']) == expected_failures
    assert len([item for item in evidence if item[0] == 'rollback']) == expected_failures
    assert len([item for item in evidence if item[0] == 'close']) == expected_failures
    assert _pairing_snapshot(test_database, member.id) == before
    assert _audit_snapshot(test_database) == audits_before
    assert 'not-busy-driver' not in response.text
    assert 'not-busy-driver' not in caplog.text
    if flow == 'expiration':
        clean = anonymous_client.post('/api/aztek/pair', json={
            'pairing_token': token,
            'storage_state': valid_storage_state(),
        })
        assert clean.status_code == 410
        with test_database.session() as db:
            record = db.scalar(select(PairingToken).where(
                PairingToken.user_id == member.id))
            assert record.status == 'expired'
            assert record.used_at is None


@pytest.mark.parametrize('busy, expected_status, expected_detail', [
    (True, 409, 'pairing_busy'),
    (False, 500, 'pairing_failed'),
])
def test_expired_pairing_cleanup_failure_preserves_durable_expiration(
        busy, expected_status, expected_detail, client, anonymous_client,
        application, member, test_database, monkeypatch):
    token = issue_pairing_token(client)
    with test_database.session() as db:
        record = db.scalar(select(PairingToken).where(
            PairingToken.user_id == member.id))
        record.expires_at = utc_now() - timedelta(seconds=1)

    original_session = test_database.session
    evidence = []
    fail_calls = 1
    calls = 0

    @contextmanager
    def failing_commits():
        nonlocal calls
        calls += 1
        cm = original_session()
        db = cm.__enter__()
        try:
            yield db
        except BaseException as error:
            cm.__exit__(type(error), error, error.__traceback__)
            raise
        else:
            if calls <= fail_calls:
                error = _sqlalchemy_operational_error(busy=busy)
                cm.__exit__(type(error), error, error.__traceback__)
                evidence.append('rolled-back')
                raise error
            cm.__exit__(None, None, None)

    monkeypatch.setattr(test_database, 'session', failing_commits)
    response = anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': token, 'storage_state': valid_storage_state()})
    monkeypatch.setattr(test_database, 'session', original_session)

    assert response.status_code == expected_status
    assert response.json() == {'detail': expected_detail}
    assert len(evidence) == 1
    with test_database.session() as db:
        record = db.scalar(select(PairingToken).where(
            PairingToken.user_id == member.id))
        assert record.status == 'expired'
        assert record.used_at is None

    clean = anonymous_client.post('/api/aztek/pair', json={
        'pairing_token': token, 'storage_state': valid_storage_state()})
    assert clean.status_code == 410
    with test_database.session() as db:
        record = db.scalar(select(PairingToken).where(
            PairingToken.user_id == member.id))
        assert record.status == 'expired'
        assert record.used_at is None


@pytest.mark.parametrize('mutation', ['add', 'update', 'delete', 'core'])
@pytest.mark.parametrize('operation', [
    'issue_success', 'issue_domain_error',
    'consume_success', 'consume_domain_error',
])
def test_pairing_caller_work_is_never_committed_or_rolled_back(
        mutation, operation, member, other_member, test_database, test_settings,
        monkeypatch):
    service = AztekSessionService(test_settings)
    raw_consume_token = None
    if operation == 'consume_success':
        with test_database.session() as setup_db:
            raw_consume_token = service.create_pairing_token(
                setup_db, setup_db.get(User, member.id)).raw_token

    session: Session = test_database._session_factory()
    commit_calls = []
    rollback_calls = []
    original_commit = session.commit
    original_rollback = session.rollback

    if mutation == 'add':
        session.add(User(username='unrelated-add-%s' % operation,
                         password_hash='unrelated-hash', role='member'))
        session.flush()
    elif mutation == 'update':
        row = session.get(User, other_member.id)
        row.username = 'unrelated-update-%s' % operation
        session.flush()
    elif mutation == 'delete':
        row = User(username='unrelated-delete-%s' % operation,
                   password_hash='unrelated-hash', role='member')
        session.add(row)
        session.flush()
        session.delete(row)
        session.flush()
    else:
        session.execute(update(User).where(User.id == other_member.id).values(
            username='unrelated-core-%s' % operation))

    monkeypatch.setattr(session, 'commit', lambda: commit_calls.append(True))
    monkeypatch.setattr(session, 'rollback', lambda: rollback_calls.append(True))
    try:
        if operation == 'issue_success':
            service.create_pairing_token(session, session.get(User, member.id))
        elif operation == 'issue_domain_error':
            conflict_type = _pairing_interface('PairingTokenIssueConflict')
            attempt_type = _pairing_interface('PairingIssueAttempt')
            fixed_attempt = attempt_type(
                user_id=member.id,
                prior_token_id='missing-prior-token',
                raw_token='fixed-candidate-token-' + ('x' * 20),
                token_hash='f' * 64,
                created_at=utc_now(),
                expires_at=utc_now() + timedelta(minutes=5),
            )
            monkeypatch.setattr(
                service, '_prepare_pairing_issue',
                lambda _db, _user_id: fixed_attempt)
            with pytest.raises(conflict_type):
                service.create_pairing_token(
                    session, session.get(User, member.id))
        elif operation == 'consume_success':
            service.consume_pairing_token(
                session, raw_consume_token, valid_storage_state())
        else:
            with pytest.raises(PairingTokenNotFound):
                service.consume_pairing_token(
                    session, 'unknown-token-' + ('x' * 24),
                    valid_storage_state())
        assert commit_calls == []
        assert rollback_calls == []
        assert session.in_transaction()
        if mutation == 'add':
            assert session.scalar(select(User.id).where(
                User.username == 'unrelated-add-%s' % operation)) is not None
        elif mutation in ('update', 'core'):
            expected = 'unrelated-%s-%s' % (mutation, operation)
            assert session.get(User, other_member.id).username == expected
        else:
            assert session.scalar(select(User.id).where(
                User.username == 'unrelated-delete-%s' % operation)) is None
    finally:
        monkeypatch.setattr(session, 'commit', original_commit)
        monkeypatch.setattr(session, 'rollback', original_rollback)
        session.rollback()
        session.close()


@pytest.mark.parametrize('mutation', ['add', 'update', 'delete', 'core'])
def test_pairing_transaction_state_rejects_nonfresh_session_before_begin(
        mutation, member, other_member, test_database, monkeypatch):
    begin_fresh = _pairing_interface('_begin_fresh_pairing_write')
    session: Session = test_database._session_factory()
    rollback_calls = []
    original_rollback = session.rollback

    if mutation == 'add':
        session.add(User(username='fresh-state-add', password_hash='hash',
                         role='member'))
    elif mutation == 'update':
        session.get(User, other_member.id).username = 'fresh-state-update'
    elif mutation == 'delete':
        session.delete(session.get(User, other_member.id))
    else:
        session.execute(update(User).where(User.id == member.id).values(
            username='fresh-state-core'))

    monkeypatch.setattr(session, 'rollback', lambda: rollback_calls.append(True))
    try:
        with pytest.raises(RuntimeError, match='fresh'):
            begin_fresh(session)
        assert rollback_calls == []
    finally:
        monkeypatch.setattr(session, 'rollback', original_rollback)
        session.rollback()
        session.close()


def test_pairing_busy_classifier_uses_only_driver_codes():
    classifier = _pairing_interface('is_pairing_sqlite_busy')
    assert classifier(_sqlalchemy_operational_error(busy=True)) is True
    assert classifier(_sqlalchemy_operational_error(busy=False)) is False
    message_only = OperationalError(
        'database is locked ' + PAIRING_PRIVACY_SENTINEL, {}, RuntimeError())
    assert classifier(message_only) is False
