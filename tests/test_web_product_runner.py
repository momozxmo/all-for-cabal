# -*- coding: utf-8 -*-
"""Product live-form URL, option cleaning, and read-only API gates."""
from web import product_runner


GAME = 'CabalM TH'


def _connect_aztek(client):
    token = client.post(
        '/api/aztek/pairing-token').json()['pairing_token']
    response = client.post('/api/aztek/pair', json={
        'pairing_token': token,
        'storage_state': {
            'cookies': [{
                'name': 'session',
                'value': 'cookie-value',
                'domain': '.combo-interactive.com',
                'path': '/',
            }],
            'origins': [],
        },
    })
    assert response.status_code == 200


def test_product_create_url_is_under_shop():
    assert product_runner.product_create_url(GAME).endswith(
        '/combo/cabalm/shop/products/create')


def test_option_rows_keep_live_value_slug_and_label():
    rows = product_runner._clean_option_rows([
        {'value': '17', 'text': 'ankh-coin - Ankh Coin'},
        {'value': '18', 'text': 'future-token - Future Token'},
        {'value': '22', 'text': 'Bonus Shop - General - Bonus'},
        {'value': '', 'text': 'เลือกสกุลเงิน'},
    ])
    assert rows == [
        {'id': '17', 'slug': 'ankh-coin', 'label': 'Ankh Coin'},
        {'id': '18', 'slug': 'future-token', 'label': 'Future Token'},
        {'id': '22', 'slug': '', 'label': 'Bonus Shop - General - Bonus'},
    ]


def test_product_options_requires_authentication(anonymous_client):
    response = anonymous_client.post('/api/products/options', json={
        'game': GAME, 'kinds': ['currencies']})
    assert response.status_code == 401


def test_product_options_rejects_unknown_game(client):
    response = client.post('/api/products/options', json={
        'game': 'Unknown Cabal', 'kinds': ['currencies']})
    assert response.status_code == 400


def test_product_options_requires_paired_aztek_session(client):
    response = client.post('/api/products/options', json={
        'game': GAME, 'kinds': ['currencies']})
    assert response.status_code == 409
    assert 'Aztek' in response.json()['detail']


def test_product_options_fetches_only_requested_live_kind(
        client, monkeypatch):
    _connect_aztek(client)
    calls = []

    async def fake_fetch(game, storage_state, kinds):
        calls.append((game, storage_state, kinds))
        return {
            'currencies': [{
                'id': '91',
                'slug': 'future-token',
                'label': 'Future Token',
            }],
        }

    monkeypatch.setattr(product_runner, 'fetch_options', fake_fetch)
    response = client.post('/api/products/options', json={
        'game': GAME, 'kinds': ['currencies', 'currencies']})

    assert response.status_code == 200, response.text
    assert calls[0][0] == GAME
    assert calls[0][2] == ['currencies']
    assert response.json() == {'options': {
        'currencies': [{
            'id': '91',
            'slug': 'future-token',
            'label': 'Future Token',
        }],
    }}
    assert 'categories' not in response.text
