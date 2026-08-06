from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from web import security
from web.aztek_sessions import (AztekSessionService, InvalidStorageState)
from web.models import AztekSession, PairingToken, User, utc_now


SECRET_COOKIE_VALUE = 'top-secret-aztek-cookie'


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
