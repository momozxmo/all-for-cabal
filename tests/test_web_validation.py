# -*- coding: utf-8 -*-
"""Strict route-bound validation for values that may reach a live form.

Every runner in this file is a local fake.  The tests never contact Aztek and
never construct a real Bundle, Item Code, Event, or Product.
"""
from __future__ import annotations

import importlib
import json
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from web import activity_runner, bundle_runner, event_runner, itemcode_runner
from web import app as web_app
from web import product_runner
from web.models import AuditLog


GAME = 'CabalM TH'


def _validation():
    return importlib.import_module('web.validation')


@pytest.mark.parametrize('value, expected', [
    ('1', '1'), (' 12 ', '12'), (12, '12'),
])
def test_positive_integer_truth_table_accepts_only_canonical_values(
        value, expected):
    assert _validation().positive_int_text(value, 'field') == expected


@pytest.mark.parametrize('value', [
    '', None, True, False, 0, -1, 1.0, '0', '001', '+1', '-1',
    '1.0', '1e3', 'ID 11', '๑', '١', '１', '1234567890123',
])
def test_positive_integer_truth_table_rejects_ambiguous_values(value):
    module = _validation()
    with pytest.raises(module.PayloadValueError) as caught:
        module.positive_int_text(value, 'field')
    assert caught.value.detail == 'field ต้องเป็นจำนวนเต็มมากกว่า 0'


@pytest.mark.parametrize('value, expected', [
    ('0', '0'), (0, '0'), ('12', '12'),
])
def test_non_negative_integer_truth_table_accepts_only_canonical_values(
        value, expected):
    assert _validation().non_negative_int_text(value, 'field') == expected


@pytest.mark.parametrize('value', [
    '', None, True, False, 1.0, '-0', '-1', '+1', '00', '012',
    '1.0', '1e3', '๑', '١', '１', '1234567890123',
])
def test_non_negative_integer_truth_table_rejects_ambiguous_values(value):
    module = _validation()
    with pytest.raises(module.PayloadValueError) as caught:
        module.non_negative_int_text(value, 'field')
    assert caught.value.detail == 'field ต้องเป็นจำนวนเต็มตั้งแต่ 0 ขึ้นไป'


@pytest.mark.parametrize('value, expected', [
    ('0', '0'), (12, '12'), ('12.500', '12.5'), ('0.000', '0'),
])
def test_plain_decimal_truth_table_returns_non_exponent_text(value, expected):
    assert _validation().plain_decimal_text(
        value, 'field', minimum=Decimal('0'), maximum=Decimal('100'),
        places=3,
    ) == expected


@pytest.mark.parametrize('value', [
    '', None, True, False, 1.5, '+1', '-1', '.5', '1.', '01', '1e3',
    'NaN', 'Infinity', '-Infinity', '12 coins', '100.001', '12.5000',
    '1' * 65,
])
def test_plain_decimal_truth_table_rejects_non_plain_or_out_of_bound_values(
        value):
    module = _validation()
    with pytest.raises(module.PayloadValueError) as caught:
        module.plain_decimal_text(
            value, 'field', minimum=Decimal('0'), maximum=Decimal('100'),
            places=3,
        )
    assert caught.value.detail == 'field ต้องเป็นเลขทศนิยมในรูปแบบปกติ'


def test_decimal_length_is_rejected_before_decimal_construction(monkeypatch):
    module = _validation()

    def must_not_parse(_value):
        raise AssertionError('Decimal parser reached')

    monkeypatch.setattr(module, 'Decimal', must_not_parse)
    with pytest.raises(module.PayloadValueError):
        module.plain_decimal_text(
            '1' * 65, 'field', minimum=Decimal('0'), maximum=Decimal('100'))


@pytest.mark.parametrize('value, expected', [(True, True), (False, False)])
def test_strict_bool_accepts_only_exact_booleans(value, expected):
    assert _validation().strict_bool(value, 'field') is expected


@pytest.mark.parametrize('value', [
    0, 1, '', 'false', 'true', None, [], {}, 0.0,
])
def test_strict_bool_rejects_truthy_and_falsy_substitutes(value):
    module = _validation()
    with pytest.raises(module.PayloadValueError) as caught:
        module.strict_bool(value, 'field')
    assert caught.value.detail == (
        'field ต้องเป็น true หรือ false แบบ JSON boolean')


@pytest.mark.parametrize('value, expected', [
    ('', ''), (' 2026-08-20 ', '2026-08-20'),
])
def test_optional_text_strips_exact_strings(value, expected):
    assert _validation().optional_text(
        value, 'field', max_length=32) == expected


@pytest.mark.parametrize('value, detail', [
    (None, 'field ต้องเป็นข้อความ'),
    (True, 'field ต้องเป็นข้อความ'),
    (1, 'field ต้องเป็นข้อความ'),
    (1.0, 'field ต้องเป็นข้อความ'),
    ([], 'field ต้องเป็นข้อความ'),
    ({}, 'field ต้องเป็นข้อความ'),
    ('x' * 33, 'field ต้องเป็นข้อความยาวไม่เกิน 32 ตัวอักษร'),
])
def test_optional_text_rejects_wrong_types_and_post_trim_overflow(value, detail):
    module = _validation()
    with pytest.raises(module.PayloadValueError) as caught:
        module.optional_text(value, 'field', max_length=32)
    assert caught.value.detail == detail


def test_payload_value_error_never_retains_the_submitted_sentinel():
    module = _validation()
    with pytest.raises(module.PayloadValueError) as caught:
        module.positive_int_text('private-raw-sentinel', 'safe field')
    error = caught.value
    assert error.label == 'safe field'
    assert error.rule == 'ต้องเป็นจำนวนเต็มมากกว่า 0'
    assert 'private-raw-sentinel' not in str(error)
    assert 'private-raw-sentinel' not in repr(error.args)


def _connect_aztek(client):
    token_response = client.post('/api/aztek/pairing-token')
    assert token_response.status_code == 200, token_response.text
    response = client.post('/api/aztek/pair', json={
        'pairing_token': token_response.json()['pairing_token'],
        'storage_state': {
            'cookies': [{
                'name': 'session', 'value': 'local-fake',
                'domain': '.combo-interactive.com', 'path': '/',
            }],
            'origins': [],
        },
    })
    assert response.status_code == 200, response.text


def _bundle(key='bundle-1', **extra):
    result = {
        'client_key': key,
        'name': key,
        'bundle_type': 'FIXED',
        'deliver': True,
        'items': [{'id': ' 12 ', 'qty': 3, 'tier': 'Rare', 'rate': 'stale'}],
        'rewards': [{'type': 'credit', 'value': ' Alz ', 'qty': 2}],
    }
    result.update(extra)
    return result


def _reward(**extra):
    result = {
        'name_th': 'รางวัล', 'name_en': 'Reward', 'bundle_id': '208106',
        'quantity': ['inactive-stale'], 'remaining': None,
    }
    result.update(extra)
    return result


def _itemcode(key='itemcode-1', **extra):
    result = {
        'client_key': key,
        'name_th': key, 'name_en': key, 'slug': key,
        'uses_per_user': 2,
        'limited': False, 'quantity': {'inactive': True}, 'remaining': None,
        'start_time': '2026-08-01 00:00:00',
        'end_time': '2026-08-31 23:59:59',
        'rewards': [_reward(code_type='FIX', code_list='A\nB')],
    }
    result.update(extra)
    return result


def _event(key='event-1', **extra):
    result = {
        'client_key': key,
        'name_th': key, 'name_en': key, 'slug': key,
        'uses_per_user': 2, 'quantity': 0, 'remaining': '0',
        'start_event': '2026-08-01 00:00:00',
        'end_event': '2026-08-31 23:59:59',
        'start_claim': '2026-08-01 00:00:00',
        'end_claim': '2026-09-07 23:59:59',
        'rewards': [_reward()],
    }
    result.update(extra)
    return result


def _product(key='product-1', **extra):
    result = {
        'client_key': key,
        'source_group_key': 'group-' + key,
        'name_th': key,
        'name_en': key,
        'category_id': 'category-12',
        'category_label': 'Highlight',
        'start_at': '2026-08-01 00:00:00',
        'end_at': '2026-08-31 23:59:59',
        'bundle_ids': [223553, ' 223554 '],
        'primary_bundle_id': 223554,
        'prices': [{
            'currency_id': '91', 'currency_slug': 'future-token',
            'currency_label': 'Future Token',
            'original_price': 6600, 'price': '12.500',
        }],
        'limit_type': 'PLAYER',
        'limit_quantity': 10,
        'limit_reset_interval_days': 7,
        'limit_reset_at': ' 2026-08-20 09:15:00 ',
        'position': 0,
        'tags': ['SALE'],
    }
    result.update(extra)
    return result


def _post_product(client, products, *, do_save=False, payload_text=None):
    if payload_text is None:
        payload_text = json.dumps({
            'game': GAME, 'products': products, 'do_save': do_save,
        }, ensure_ascii=False)
    return client.post('/api/products/run', data={'payload': payload_text})


def _forbid_live_boundary(client, monkeypatch):
    """Fail a test if validation touches state, the gate, or a builder."""
    calls = {'state': 0, 'gate': 0, 'builder': 0}

    def forbidden_state(*_args, **_kwargs):
        calls['state'] += 1
        raise AssertionError('paired state loaded before validation finished')

    def forbidden_slot(*_args, **_kwargs):
        calls['gate'] += 1
        raise AssertionError('browser gate entered before validation finished')

    class ForbiddenBuilder:
        def __init__(self, *_args, **_kwargs):
            calls['builder'] += 1
            raise AssertionError('builder constructed before validation finished')

    monkeypatch.setattr(
        client.app.state.aztek_session_service,
        'load_storage_state',
        forbidden_state,
    )
    monkeypatch.setattr(client.app.state.browser_gate, 'slot', forbidden_slot)
    for module, name in (
        (bundle_runner, 'BundleBuilder'),
        (itemcode_runner, 'ItemCodeBuilder'),
        (event_runner, 'EventBuilder'),
        (product_runner, 'ProductBuilder'),
    ):
        monkeypatch.setattr(module, name, ForbiddenBuilder)
    return calls


@pytest.mark.parametrize('path, payload, detail', [
    ('/api/bundles/run', {
        'game': GAME, 'bundles': [_bundle(items=[{'id': 'ID 11'}])],
    }, 'Bundle ที่ 1: Item ID แถว 1 ต้องเป็นจำนวนเต็มมากกว่า 0'),
    ('/api/itemcodes/run', {
        'game': GAME, 'itemcodes': [_itemcode(uses_per_user='1e3')],
    }, 'Item Code ที่ 1: จำนวนครั้งต่อผู้ใช้ ต้องเป็นจำนวนเต็มมากกว่า 0'),
    ('/api/events/run', {
        'game': GAME, 'events': [_event(quantity='-1')],
    }, 'Event ที่ 1: จำนวนรางวัลทั้งหมด ต้องเป็นจำนวนเต็มตั้งแต่ 0 ขึ้นไป'),
])
def test_invalid_numeric_values_have_exact_safe_ordinal_400_responses(
        client, monkeypatch, path, payload, detail):
    calls = _forbid_live_boundary(client, monkeypatch)
    response = client.post(path, json=payload)
    assert response.status_code == 400
    assert response.json() == {'detail': detail}
    assert 'ID 11' not in response.text
    assert '1e3' not in response.text
    assert calls == {'state': 0, 'gate': 0, 'builder': 0}


@pytest.mark.parametrize('family', ['bundle', 'itemcode', 'event', 'product'])
def test_invalid_values_stop_before_paired_state_or_runner(
        client, monkeypatch, family):
    calls = _forbid_live_boundary(client, monkeypatch)
    if family == 'bundle':
        response = client.post('/api/bundles/run', json={
            'game': GAME, 'bundles': [_bundle(items=[{'id': 'ID 11'}])],
        })
    elif family == 'itemcode':
        response = client.post('/api/itemcodes/run', json={
            'game': GAME, 'itemcodes': [_itemcode(uses_per_user='1e3')],
        })
    elif family == 'event':
        response = client.post('/api/events/run', json={
            'game': GAME, 'events': [_event(quantity='-1')],
        })
    else:
        product = _product()
        product['prices'][0]['price'] = 'not-a-decimal'
        response = _post_product(client, [product])
    assert response.status_code == 400
    assert calls == {'state': 0, 'gate': 0, 'builder': 0}


_POSITIVE_INVALID_VALUES = [
    ('blank', ''), ('whitespace', '   '), ('null', None),
    ('bool-true', True),
    ('bool-false', False), ('zero-int', 0), ('zero-text', '0'),
    ('float', 1.5), ('partial', 'ID 11'), ('exponent', '1e3'),
    ('plus-sign', '+1'), ('negative', '-1'), ('thai-digit', '๑'),
    ('arabic-digit', '١'), ('fullwidth-digit', '１'),
    ('list', []), ('object', {}),
    ('over-length', '1234567890123'),
]
_NON_NEGATIVE_INVALID_VALUES = [
    ('blank', ''), ('whitespace', '   '), ('null', None),
    ('bool-true', True),
    ('bool-false', False), ('negative-int', -1), ('negative-text', '-1'),
    ('float', 1.5), ('partial', 'ID 11'), ('exponent', '1e3'),
    ('plus-sign', '+1'), ('leading-zero', '00'), ('thai-digit', '๑'),
    ('arabic-digit', '١'), ('fullwidth-digit', '１'),
    ('list', []), ('object', {}),
    ('over-length', '1234567890123'),
]
_BOOLEAN_INVALID_VALUES = [
    ('blank', ''), ('null', None), ('text-true', 'true'),
    ('text-false', 'false'), ('one', 1), ('zero', 0), ('float', 1.0),
    ('list', []), ('object', {}),
]

_MISSING = object()


_JSON_BOOL_BINDINGS = [
    ('bundle-deliver', '/api/bundles/run', 'bundles', _bundle, 'deliver'),
    ('bundle-do-save', '/api/bundles/run', 'bundles', _bundle, 'do_save'),
    ('itemcode-limited', '/api/itemcodes/run', 'itemcodes', _itemcode, 'limited'),
    ('itemcode-do-save', '/api/itemcodes/run', 'itemcodes', _itemcode, 'do_save'),
    ('event-do-save', '/api/events/run', 'events', _event, 'do_save'),
]


def _json_bool_parameters():
    for binding in _JSON_BOOL_BINDINGS:
        case_id = binding[0]
        for value_id, value in _BOOLEAN_INVALID_VALUES:
            yield pytest.param(binding, value, id=f'{case_id}-{value_id}')


@pytest.mark.parametrize('binding, invalid', _json_bool_parameters())
def test_json_route_strict_bool_bindings_keep_framework_list_422(
        client, monkeypatch, binding, invalid):
    calls = _forbid_live_boundary(client, monkeypatch)
    _case_id, path, key, factory, field = binding
    spec = factory()
    payload = {'game': GAME, key: [spec], 'do_save': False}
    if field == 'do_save':
        payload[field] = invalid
    else:
        spec[field] = invalid
    response = client.post(path, json=payload)
    assert response.status_code == 422
    assert isinstance(response.json()['detail'], list)
    assert calls == {'state': 0, 'gate': 0, 'builder': 0}


def _product_bool_parameters():
    for field in ('do_save', 'is_enabled', 'is_test_mode', 'is_hidden'):
        for value_id, value in _BOOLEAN_INVALID_VALUES:
            yield pytest.param(field, value, id=f'{field}-{value_id}')


@pytest.mark.parametrize('field, invalid', _product_bool_parameters())
def test_product_model_booleans_have_fixed_sanitized_422(
        client, monkeypatch, field, invalid):
    calls = _forbid_live_boundary(client, monkeypatch)
    product = _product()
    top = {'game': GAME, 'products': [product], 'do_save': False}
    if field == 'do_save':
        top[field] = invalid
    else:
        product[field] = invalid
    response = _post_product(
        client, [], payload_text=json.dumps(top, ensure_ascii=False))
    assert response.status_code == 422
    assert response.json() == {'detail': 'ข้อมูล Product ไม่ถูกต้อง'}
    assert calls == {'state': 0, 'gate': 0, 'builder': 0}


_ACTIVITY_FIELD_BINDINGS = [
    ('ic-top-uses', 'itemcode', 'top', 'uses_per_user', 'positive',
     'Item Code ที่ 1: จำนวนครั้งต่อผู้ใช้'),
    ('ic-top-quantity', 'itemcode', 'top-limited', 'quantity', 'positive',
     'Item Code ที่ 1: จำนวนครั้งที่สามารถใช้งานได้'),
    ('ic-top-remaining', 'itemcode', 'top-limited', 'remaining', 'positive',
     'Item Code ที่ 1: จำนวนคงเหลือ'),
    ('ic-reward-uses', 'itemcode', 'reward', 'uses_per_user', 'positive',
     'Item Code ที่ 1: ชุดรางวัลที่ 1: จำนวนครั้งต่อผู้ใช้'),
    ('ic-reward-bundle', 'itemcode', 'reward', 'bundle_id', 'positive',
     'Item Code ที่ 1: ชุดรางวัลที่ 1: Bundle ID'),
    ('ic-reward-limited', 'itemcode', 'reward', 'limited', 'boolean',
     'Item Code ที่ 1: ชุดรางวัลที่ 1: จำกัดจำนวน'),
    ('ic-reward-quantity', 'itemcode', 'reward-limited', 'quantity', 'positive',
     'Item Code ที่ 1: ชุดรางวัลที่ 1: จำนวนครั้ง'),
    ('ic-reward-remaining', 'itemcode', 'reward-limited', 'remaining', 'positive',
     'Item Code ที่ 1: ชุดรางวัลที่ 1: จำนวนคงเหลือ'),
    ('ic-reward-num-codes', 'itemcode', 'reward-server', 'num_codes', 'positive',
     'Item Code ที่ 1: ชุดรางวัลที่ 1: จำนวนโค้ด'),
    ('event-top-uses', 'event', 'top', 'uses_per_user', 'positive',
     'Event ที่ 1: จำนวนครั้งต่อผู้ใช้'),
    ('event-top-quantity', 'event', 'top', 'quantity', 'non-negative',
     'Event ที่ 1: จำนวนรางวัลทั้งหมด'),
    ('event-top-remaining', 'event', 'top', 'remaining', 'non-negative',
     'Event ที่ 1: จำนวนคงเหลือ'),
    ('event-reward-uses', 'event', 'reward', 'uses_per_user', 'positive',
     'Event ที่ 1: ชุดรางวัลที่ 1: จำนวนครั้งต่อผู้ใช้'),
    ('event-reward-bundle', 'event', 'reward', 'bundle_id', 'positive',
     'Event ที่ 1: ชุดรางวัลที่ 1: Bundle ID'),
    ('event-reward-limited', 'event', 'reward', 'limited', 'boolean',
     'Event ที่ 1: ชุดรางวัลที่ 1: จำกัดจำนวน'),
    ('event-reward-quantity', 'event', 'reward-limited', 'quantity', 'positive',
     'Event ที่ 1: ชุดรางวัลที่ 1: จำนวนครั้ง'),
    ('event-reward-remaining', 'event', 'reward-limited', 'remaining', 'positive',
     'Event ที่ 1: ชุดรางวัลที่ 1: จำนวนคงเหลือ'),
]


def _activity_invalid_parameters():
    values_by_rule = {
        'positive': _POSITIVE_INVALID_VALUES,
        'non-negative': _NON_NEGATIVE_INVALID_VALUES,
        'boolean': _BOOLEAN_INVALID_VALUES,
    }
    for binding in _ACTIVITY_FIELD_BINDINGS:
        case_id, _family, _scope, _field, rule, _label = binding
        for value_id, value in values_by_rule[rule]:
            yield pytest.param(binding, value, id=f'{case_id}-{value_id}')


def _activity_invalid_request(binding, value):
    _case_id, family, scope, field, rule, label = binding
    if family == 'itemcode':
        path, key = '/api/itemcodes/run', 'itemcodes'
        spec = _itemcode()
    else:
        path, key = '/api/events/run', 'events'
        spec = _event()

    if scope == 'top':
        spec[field] = value
    elif scope == 'top-limited':
        spec.update({'limited': True, 'quantity': '1', 'remaining': '1'})
        spec[field] = value
    else:
        reward = _reward()
        if scope == 'reward-limited':
            reward.update({'limited': True, 'quantity': '1', 'remaining': '1'})
        elif scope == 'reward-server':
            reward.update({'code_type': 'SERVER', 'num_codes': '1'})
        reward[field] = value
        spec['rewards'] = [reward]

    suffix = {
        'positive': 'ต้องเป็นจำนวนเต็มมากกว่า 0',
        'non-negative': 'ต้องเป็นจำนวนเต็มตั้งแต่ 0 ขึ้นไป',
        'boolean': 'ต้องเป็น true หรือ false แบบ JSON boolean',
    }[rule]
    return path, key, spec, f'{label} {suffix}'


@pytest.mark.parametrize('binding, invalid', _activity_invalid_parameters())
def test_every_activity_numeric_and_boolean_binding_rejects_invalid_families(
        client, monkeypatch, binding, invalid):
    calls = _forbid_live_boundary(client, monkeypatch)
    path, key, spec, detail = _activity_invalid_request(binding, invalid)
    response = client.post(path, json={'game': GAME, key: [spec]})
    assert response.status_code == 400
    assert response.json() == {'detail': detail}
    assert calls == {'state': 0, 'gate': 0, 'builder': 0}


_PRODUCT_ACTIVE_INVALID_BINDINGS = [
    (
        'limit-quantity',
        'limit_quantity',
        [('missing', _MISSING), *_POSITIVE_INVALID_VALUES],
        'Product ที่ 1: จำนวนที่ซื้อได้ ต้องเป็นจำนวนเต็มมากกว่า 0',
    ),
    (
        'reset-interval',
        'limit_reset_interval_days',
        [
            pair for pair in _POSITIVE_INVALID_VALUES
            if pair[0] not in {'blank', 'whitespace'}
        ],
        'Product ที่ 1: รอบรีเซ็ต ต้องเป็นจำนวนเต็มมากกว่า 0',
    ),
    (
        'reset-at',
        'limit_reset_at',
        [
            ('null', None), ('bool-true', True), ('bool-false', False),
            ('integer', 1), ('float', 1.5), ('list', []), ('object', {}),
        ],
        'Product ที่ 1: เวลารีเซ็ต ต้องเป็นข้อความ',
    ),
]


def _product_active_invalid_parameters():
    for case_id, field, values, detail in _PRODUCT_ACTIVE_INVALID_BINDINGS:
        for value_id, value in values:
            yield pytest.param(
                field, value, detail, id=f'{case_id}-{value_id}')


@pytest.mark.parametrize(
    'field, invalid, detail', _product_active_invalid_parameters())
def test_product_active_limit_bindings_reject_every_invalid_family_before_state(
        client, monkeypatch, field, invalid, detail):
    calls = _forbid_live_boundary(client, monkeypatch)
    product = _product()
    if invalid is _MISSING:
        product.pop(field)
    else:
        product[field] = invalid

    response = _post_product(client, [product])

    assert response.status_code == 400
    assert response.json() == {'detail': detail}
    assert calls == {'state': 0, 'gate': 0, 'builder': 0}


def _capture_product_jobs(client, monkeypatch, products):
    _connect_aztek(client)
    captured = []

    class Builder:
        def __init__(self, _log):
            pass

        async def run_many(self, **kwargs):
            captured.append(kwargs['specs'])
            return []

    monkeypatch.setattr(product_runner, 'ProductBuilder', Builder)
    response = _post_product(client, products, do_save=True)
    return response, captured


def test_product_active_optional_missing_blank_and_whitespace_reach_runner_as_empty(
        client, monkeypatch):
    missing = _product('active-missing')
    missing.pop('limit_reset_interval_days')
    missing.pop('limit_reset_at')
    products = [
        missing,
        _product(
            'active-blank', limit_reset_interval_days='', limit_reset_at=''),
        _product(
            'active-whitespace', limit_reset_interval_days='   ',
            limit_reset_at='   '),
    ]

    response, captured = _capture_product_jobs(client, monkeypatch, products)

    assert response.status_code == 200, response.text
    assert len(captured) == 1
    assert [
        (job['limit_reset_interval_days'], job['limit_reset_at'])
        for job in captured[0]
    ] == [('', ''), ('', ''), ('', '')]


@pytest.mark.parametrize('value_id, stale', [
    ('missing', _MISSING), ('blank', ''), ('whitespace', '   '),
    ('null', None), ('bool', True), ('integer', 123), ('float', 1.5),
    ('list', []), ('object', {}),
])
def test_product_unlimited_inactive_values_reach_runner_as_empty(
        client, monkeypatch, value_id, stale):
    product = _product(f'unlimited-{value_id}', limit_type='UNLIMITED')
    for field in (
            'limit_quantity', 'limit_reset_interval_days', 'limit_reset_at'):
        if stale is _MISSING:
            product.pop(field)
        else:
            product[field] = stale

    response, captured = _capture_product_jobs(client, monkeypatch, [product])

    assert response.status_code == 200, response.text
    assert len(captured) == 1
    assert {
        field: captured[0][0][field]
        for field in (
            'limit_quantity', 'limit_reset_interval_days', 'limit_reset_at')
    } == {
        'limit_quantity': '',
        'limit_reset_interval_days': '',
        'limit_reset_at': '',
    }


_PRODUCT_SPECIAL_NUMERIC_BINDINGS = [
    (
        'legacy-bundle', 'legacy-bundle',
        'Product ที่ 1: Bundle ID แถว 1 ต้องเป็นจำนวนเต็มมากกว่า 0',
    ),
    (
        'bundle-row', 'bundle-row',
        'Product ที่ 1: Bundle ID แถว 1 ต้องเป็นจำนวนเต็มมากกว่า 0',
    ),
    (
        'primary-bundle', 'primary-bundle',
        'Product ที่ 1: Primary Bundle ID ต้องเป็นจำนวนเต็มมากกว่า 0',
    ),
    (
        'position', 'position',
        'Product ที่ 1: ตำแหน่ง ต้องเป็นจำนวนเต็มตั้งแต่ 0 ขึ้นไป',
    ),
    (
        'original-price', 'original-price',
        'Product ที่ 1: ราคาปกติแถว 1 ต้องเป็นเลขทศนิยมตั้งแต่ 0 '
        'ขึ้นไปในรูปแบบปกติและยาวไม่เกิน 64 ตัวอักษร',
    ),
    (
        'sale-price', 'sale-price',
        'Product ที่ 1: ราคาขายแถว 1 ต้องเป็นเลขทศนิยมตั้งแต่ 0 '
        'ขึ้นไปในรูปแบบปกติและยาวไม่เกิน 64 ตัวอักษร',
    ),
    (
        'limit-quantity', 'limit-quantity',
        'Product ที่ 1: จำนวนที่ซื้อได้ ต้องเป็นจำนวนเต็มมากกว่า 0',
    ),
    (
        'reset-interval', 'reset-interval',
        'Product ที่ 1: รอบรีเซ็ต ต้องเป็นจำนวนเต็มมากกว่า 0',
    ),
]


def _product_with_special_numeric(location, value):
    product = _product()
    if location == 'legacy-bundle':
        product.update(
            bundle_ids=[], bundle_id=value, primary_bundle_id='')
    elif location == 'bundle-row':
        product.update(bundle_ids=[value], primary_bundle_id='')
    elif location == 'primary-bundle':
        product.update(bundle_ids=['223553'], primary_bundle_id=value)
    elif location == 'position':
        product['position'] = value
    elif location == 'original-price':
        product['prices'][0]['original_price'] = value
    elif location == 'sale-price':
        product['prices'][0]['price'] = value
    elif location == 'limit-quantity':
        product['limit_quantity'] = value
    else:
        product['limit_reset_interval_days'] = value
    return product


def _product_special_numeric_parameters():
    for case_id, location, detail in _PRODUCT_SPECIAL_NUMERIC_BINDINGS:
        for token in ('NaN', 'Infinity', '-Infinity'):
            for mode in ('raw-token', 'string'):
                yield pytest.param(
                    location, token, mode, detail,
                    id=f'{case_id}-{token.lower()}-{mode}',
                )


@pytest.mark.parametrize(
    'location, token, mode, detail', _product_special_numeric_parameters())
def test_product_nan_and_infinity_numeric_paths_have_safe_exact_400(
        client, monkeypatch, location, token, mode, detail):
    calls = _forbid_live_boundary(client, monkeypatch)
    marker = '__SPECIAL_NUMERIC__'
    value = marker if mode == 'raw-token' else token
    product = _product_with_special_numeric(location, value)
    payload = json.dumps({
        'game': GAME, 'products': [product], 'do_save': False,
    }, ensure_ascii=False)
    if mode == 'raw-token':
        payload = payload.replace(f'"{marker}"', token, 1)

    response = _post_product(client, [], payload_text=payload)

    assert response.status_code == 400
    assert response.json() == {'detail': detail}
    assert token not in response.text
    assert calls == {'state': 0, 'gate': 0, 'builder': 0}


@pytest.mark.parametrize('field, wrong', [
    ('game', 1), ('client_key', 1), ('source_group_key', 1),
    ('name_th', 1), ('name_en', 1), ('category_id', 1),
    ('category_label', 1), ('details_th', 1), ('details_en', 1),
    ('start_at', 1), ('end_at', 1), ('limit_type', 1), ('tags', [1]),
])
def test_product_numeric_token_in_text_or_identity_is_fixed_422(
        client, monkeypatch, field, wrong):
    calls = _forbid_live_boundary(client, monkeypatch)
    product = _product()
    top = {'game': GAME, 'products': [product], 'do_save': False}
    if field == 'game':
        top[field] = wrong
    else:
        product[field] = wrong
    response = _post_product(
        client, [], payload_text=json.dumps(top, ensure_ascii=False))
    assert response.status_code == 422
    assert response.json() == {'detail': 'ข้อมูล Product ไม่ถูกต้อง'}
    assert calls == {'state': 0, 'gate': 0, 'builder': 0}


@pytest.mark.parametrize('field', [
    'currency_id', 'currency_slug', 'currency_label',
])
def test_product_numeric_token_in_price_identity_is_fixed_422(
        client, monkeypatch, field):
    calls = _forbid_live_boundary(client, monkeypatch)
    product = _product()
    product['prices'][0][field] = 1
    response = _post_product(client, [product])
    assert response.status_code == 422
    assert response.json() == {'detail': 'ข้อมูล Product ไม่ถูกต้อง'}
    assert calls == {'state': 0, 'gate': 0, 'builder': 0}


@pytest.mark.parametrize('field, blank_detail', [
    ('name_th', 'Product ที่ 1: ชื่อ Product (ไทย) ห้ามว่าง'),
    ('name_en', 'Product ที่ 1: ชื่อ Product (อังกฤษ) ห้ามว่าง'),
    ('category_id', 'Product ที่ 1: หมวดหมู่ห้ามว่าง'),
    ('start_at', 'Product ที่ 1: วันเริ่มขาย ต้องเป็นวันเวลาที่ถูกต้อง'),
    ('end_at', 'Product ที่ 1: วันสิ้นสุด ต้องเป็นวันเวลาที่ถูกต้อง'),
])
def test_product_required_text_distinguishes_structural_and_blank_failures(
        client, monkeypatch, field, blank_detail):
    calls = _forbid_live_boundary(client, monkeypatch)
    missing = _product()
    missing.pop(field)
    response = _post_product(client, [missing])
    assert response.status_code == 422
    assert response.json() == {'detail': 'ข้อมูล Product ไม่ถูกต้อง'}

    wrong = _product(**{field: 1})
    response = _post_product(client, [wrong])
    assert response.status_code == 422
    assert response.json() == {'detail': 'ข้อมูล Product ไม่ถูกต้อง'}

    blank = _product(**{field: '   '})
    response = _post_product(client, [blank])
    assert response.status_code == 400
    assert response.json() == {'detail': blank_detail}
    assert calls == {'state': 0, 'gate': 0, 'builder': 0}


def test_product_exponent_price_is_not_silently_converted(client, monkeypatch):
    calls = _forbid_live_boundary(client, monkeypatch)
    product = _product()
    product['prices'][0]['price'] = '__LEXEME__'
    top = {'game': GAME, 'products': [product], 'do_save': False}
    payload = json.dumps(top, ensure_ascii=False).replace('"__LEXEME__"', '1e3')
    response = _post_product(client, [], payload_text=payload)
    assert response.status_code == 400
    assert response.json() == {
        'detail': (
            'Product ที่ 1: ราคาขายแถว 1 ต้องเป็นเลขทศนิยมตั้งแต่ 0 '
            'ขึ้นไปในรูปแบบปกติและยาวไม่เกิน 64 ตัวอักษร'
        )
    }
    assert '1e3' not in response.text
    assert calls == {'state': 0, 'gate': 0, 'builder': 0}


@pytest.mark.parametrize('changes, detail', [
    ({'end_at': '2026-08-01 00:00:00'},
     'Product ที่ 1: วันเริ่มขายต้องมาก่อนวันสิ้นสุด'),
    ({'bundle_ids': [], 'bundle_id': ''},
     'Product ที่ 1: ต้องมี Bundle อย่างน้อย 1 รายการ'),
    ({'bundle_ids': ['bad'], 'primary_bundle_id': ''},
     'Product ที่ 1: Bundle ID แถว 1 ต้องเป็นจำนวนเต็มมากกว่า 0'),
    ({'bundle_ids': ['1', '1'], 'primary_bundle_id': ''},
     'Product ที่ 1: Bundle ID ห้ามซ้ำกัน'),
    ({'primary_bundle_id': 'bad'},
     'Product ที่ 1: Primary Bundle ID ต้องเป็นจำนวนเต็มมากกว่า 0'),
    ({'primary_bundle_id': '999'},
     'Product ที่ 1: Primary Bundle ID ต้องอยู่ในรายการ Bundle'),
    ({'position': '-1'},
     'Product ที่ 1: ตำแหน่ง ต้องเป็นจำนวนเต็มตั้งแต่ 0 ขึ้นไป'),
    ({'prices': [{
        'currency_id': '91', 'original_price': '-1', 'price': '1',
     }]},
     'Product ที่ 1: ราคาปกติแถว 1 ต้องเป็นเลขทศนิยมตั้งแต่ 0 '
     'ขึ้นไปในรูปแบบปกติและยาวไม่เกิน 64 ตัวอักษร'),
    ({'prices': [{
        'currency_id': '91', 'original_price': '1', 'price': '1' * 65,
     }]},
     'Product ที่ 1: ราคาขายแถว 1 ต้องเป็นเลขทศนิยมตั้งแต่ 0 '
     'ขึ้นไปในรูปแบบปกติและยาวไม่เกิน 64 ตัวอักษร'),
    ({'prices': [
        {'currency_id': '91', 'original_price': '1', 'price': '1'},
        {'currency_id': '91', 'original_price': '2', 'price': '2'},
     ]},
     'Product ที่ 1: Currency ห้ามซ้ำกัน'),
    ({'limit_quantity': '0'},
     'Product ที่ 1: จำนวนที่ซื้อได้ ต้องเป็นจำนวนเต็มมากกว่า 0'),
    ({'limit_reset_interval_days': '0'},
     'Product ที่ 1: รอบรีเซ็ต ต้องเป็นจำนวนเต็มมากกว่า 0'),
    ({'limit_reset_at': None},
     'Product ที่ 1: เวลารีเซ็ต ต้องเป็นข้อความ'),
    ({'limit_reset_at': 'x' * 33},
     'Product ที่ 1: เวลารีเซ็ต ต้องเป็นข้อความยาวไม่เกิน 32 ตัวอักษร'),
    ({'limit_reset_at': 'not-a-date'},
     'Product ที่ 1: เวลารีเซ็ต ต้องเป็นวันเวลาที่ถูกต้อง'),
])
def test_product_domain_error_matrix_uses_only_safe_ordinals(
        client, monkeypatch, changes, detail):
    calls = _forbid_live_boundary(client, monkeypatch)
    response = _post_product(client, [_product(**changes)])
    assert response.status_code == 400
    assert response.json() == {'detail': detail}
    assert calls == {'state': 0, 'gate': 0, 'builder': 0}


@pytest.mark.parametrize('rate', ['', None, '0', '100.001', '12.5000', '1e3'])
def test_random_bundle_rate_matrix_is_exact_and_never_echoes_input(
        client, monkeypatch, rate):
    calls = _forbid_live_boundary(client, monkeypatch)
    response = client.post('/api/bundles/run', json={
        'game': GAME,
        'bundles': [_bundle(
            bundle_type='RANDOM',
            items=[{'id': '12', 'qty': '1', 'rate': rate}],
        )],
    })
    assert response.status_code == 400
    assert response.json() == {
        'detail': (
            'Bundle ที่ 1: เรทสุ่มแถว 1 ต้องเป็นเลขทศนิยมมากกว่า 0 '
            'และไม่เกิน 100 โดยมีทศนิยมไม่เกิน 3 ตำแหน่ง'
        )
    }
    assert calls == {'state': 0, 'gate': 0, 'builder': 0}


@pytest.mark.parametrize('raw_payload, private_sentinel', [
    ('{"game":"private-malformed-sentinel",',
     'private-malformed-sentinel'),
    ('[' * 2000 + '"private-deep-sentinel"' + ']' * 2000,
     'private-deep-sentinel'),
])
def test_product_malformed_and_deep_payloads_have_fixed_safe_422_before_state(
        client, monkeypatch, raw_payload, private_sentinel):
    calls = _forbid_live_boundary(client, monkeypatch)

    response = _post_product(client, [], payload_text=raw_payload)

    assert response.status_code == 422
    assert response.json() == {'detail': 'ข้อมูล Product ไม่ถูกต้อง'}
    assert private_sentinel not in response.text
    assert calls == {'state': 0, 'gate': 0, 'builder': 0}


@pytest.mark.parametrize('target', ['loads', 'model_validate'])
def test_product_parser_recursion_error_has_no_private_context(monkeypatch, target):
    def fail(*_args, **_kwargs):
        raise RecursionError('private-parser-sentinel')

    if target == 'loads':
        monkeypatch.setattr(web_app.json, 'loads', fail)
    else:
        monkeypatch.setattr(
            web_app.ProductRunRequest, 'model_validate', classmethod(fail))

    with pytest.raises(HTTPException) as caught:
        web_app._parse_product_payload('{}')
    error = caught.value
    assert error.status_code == 422
    assert error.detail == 'ข้อมูล Product ไม่ถูกต้อง'
    assert error.__context__ is None
    assert error.__cause__ is None
    assert 'private-parser-sentinel' not in str(error)


@pytest.mark.parametrize('target', ['loads', 'model_validate'])
def test_product_parser_failure_never_reaches_runner_audit_or_logs(
        client, monkeypatch, caplog, test_database, target):
    def fail(*_args, **_kwargs):
        raise RecursionError('private-http-parser-sentinel')

    calls = _forbid_live_boundary(client, monkeypatch)
    original_loads = web_app.json.loads
    if target == 'loads':
        monkeypatch.setattr(web_app.json, 'loads', fail)
    else:
        monkeypatch.setattr(
            web_app.ProductRunRequest, 'model_validate', classmethod(fail))
    response = _post_product(client, [_product()])
    if target == 'loads':
        monkeypatch.setattr(web_app.json, 'loads', original_loads)
    assert response.status_code == 422
    assert response.json() == {'detail': 'ข้อมูล Product ไม่ถูกต้อง'}
    assert 'private-http-parser-sentinel' not in response.text
    assert 'private-http-parser-sentinel' not in caplog.text
    assert calls == {'state': 0, 'gate': 0, 'builder': 0}
    with test_database.session() as db:
        summaries = [row.summary or '' for row in db.scalars(
            select(AuditLog))]
    assert 'private-http-parser-sentinel' not in '\n'.join(summaries)


def test_bundle_fake_create_gets_canonical_rows_and_returns_only_key_prefix(
        client, monkeypatch):
    _connect_aztek(client)
    calls = []

    class Builder:
        def __init__(self, _log):
            pass

        async def run_many(self, **kwargs):
            calls.append(kwargs['bundles'])
            return [{
                'name': job['name'], 'saved': True, 'bundle_id': str(index),
                'added': 1, 'total': 1, 'rewards_added': 1,
                'rewards_total': 1, 'error': None,
            } for index, job in enumerate(kwargs['bundles'][:2], 1)]

    monkeypatch.setattr(bundle_runner, 'BundleBuilder', Builder)
    bundles = [_bundle(f'bundle-{number}') for number in range(1, 4)]
    response = client.post('/api/bundles/run', json={
        'game': GAME, 'bundles': bundles, 'do_save': True,
    })
    assert response.status_code == 200, response.text
    assert calls[0][0]['items'][0] == {
        'id': '12', 'qty': '3', 'tier': 'Rare', 'rate': ''}
    assert calls[0][0]['rewards'][0]['qty'] == '2'
    assert [row['client_key'] for row in response.json()['results']] == [
        'bundle-1', 'bundle-2']


@pytest.mark.parametrize('path, key, builder_module, builder_name, factory', [
    ('/api/itemcodes/run', 'itemcodes', itemcode_runner,
     'ItemCodeBuilder', _itemcode),
    ('/api/events/run', 'events', event_runner, 'EventBuilder', _event),
])
def test_activity_fake_create_gets_canonical_values_and_key_prefix(
        client, monkeypatch, path, key, builder_module, builder_name, factory):
    _connect_aztek(client)
    calls = []

    class Builder:
        def __init__(self, _log):
            pass

        async def run_many(self, **kwargs):
            calls.append(kwargs['specs'])
            return [{
                'name': job['name_th'], 'slug': job['slug'],
                'group': job['group'], 'saved': True,
                'made_id': str(index), 'missing': [], 'error': None,
            } for index, job in enumerate(kwargs['specs'][:2], 1)]

    monkeypatch.setattr(builder_module, builder_name, Builder)
    specs = [factory(f'{key[:-1]}-{number}') for number in range(1, 4)]
    response = client.post(path, json={
        'game': GAME, key: specs, 'do_save': True,
    })
    assert response.status_code == 200, response.text
    assert calls[0][0]['uses_per_user'] == '2'
    assert calls[0][0]['rewards'][0]['uses_per_user'] == '1'
    assert calls[0][0]['rewards'][0]['bundle_id'] == '208106'
    assert calls[0][0]['rewards'][0]['limited'] is False
    assert calls[0][0]['rewards'][0]['quantity'] == ''
    assert calls[0][0]['rewards'][0]['remaining'] == ''
    if key == 'itemcodes':
        assert calls[0][0]['quantity'] == ''
        assert calls[0][0]['remaining'] == ''
        assert calls[0][0]['rewards'][0]['num_codes'] == ''
    assert [row['client_key'] for row in response.json()['results']] == [
        specs[0]['client_key'], specs[1]['client_key']]


@pytest.mark.parametrize('invalid_changes, expected_error', [
    (
        {'uses_per_user': '0'},
        'Item Code ที่ 1: จำนวนครั้งต่อผู้ใช้ '
        'ต้องเป็นจำนวนเต็มมากกว่า 0',
    ),
    (
        {'start_time': 'not-a-date'},
        "เวลาเริ่มใช้งาน ของitemcode-invalid "
        "ต้องเป็นวันเวลาที่ถูกต้อง: 'not-a-date'",
    ),
    (
        {'end_time': '2026-07-31 23:59:59'},
        'เวลาเริ่มใช้งาน ของitemcode-invalid ต้องมาก่อนเวลาสิ้นสุด '
        '(ตอนนี้ 2026-08-01 00:00:00 → 2026-07-31 23:59:59)',
    ),
])
def test_itemcode_create_all_skips_an_invalid_row_and_runs_the_valid_rows(
        client, monkeypatch, invalid_changes, expected_error):
    """One bad queue entry must not stop Playwright opening for the rest."""
    _connect_aztek(client)
    captured = []

    class Builder:
        def __init__(self, _log):
            pass

        async def run_many(self, **kwargs):
            captured.extend(kwargs['specs'])
            return [{
                'name': job['name_th'], 'slug': job['slug'],
                'group': job['group'], 'saved': True, 'made_id': '501',
                'missing': [], 'error': None,
            } for job in kwargs['specs']]

    monkeypatch.setattr(itemcode_runner, 'ItemCodeBuilder', Builder)
    response = client.post('/api/itemcodes/run', json={
        'game': GAME,
        'itemcodes': [
            _itemcode('itemcode-invalid', **invalid_changes),
            _itemcode('itemcode-valid'),
        ],
        'do_save': True,
    })

    assert response.status_code == 200, response.text
    assert [job['client_key'] for job in captured] == ['itemcode-valid']
    body = response.json()
    assert body['created'] == 1
    assert body['planned'] == 2
    assert [(row['client_key'], row['saved']) for row in body['results']] == [
        ('itemcode-invalid', False), ('itemcode-valid', True)]
    assert body['results'][0]['error'] == expected_error


def test_product_fake_create_preserves_decimal_lexemes_and_key_group_prefix(
        client, monkeypatch):
    _connect_aztek(client)
    calls = []

    class Builder:
        def __init__(self, _log):
            pass

        async def run_many(self, **kwargs):
            calls.append(kwargs['specs'])
            return [{
                'name': job['name_th'], 'slug': '', 'group': job['group'],
                'saved': True, 'made_id': str(index), 'missing': [],
                'error': None,
            } for index, job in enumerate(kwargs['specs'][:2], 1)]

    monkeypatch.setattr(product_runner, 'ProductBuilder', Builder)
    products = [_product(f'product-{number}') for number in range(1, 4)]
    response = _post_product(client, products, do_save=True)
    assert response.status_code == 200, response.text
    first = calls[0][0]
    assert first['bundle_ids'] == ['223553', '223554']
    assert first['primary_bundle_id'] == '223554'
    assert first['position'] == '0'
    assert first['limit_quantity'] == '10'
    assert first['limit_reset_interval_days'] == '7'
    assert first['prices'][0]['original_price'] == '6600'
    assert first['prices'][0]['price'] == '12.5'
    assert [(row['client_key'], row['source_group_key'])
            for row in response.json()['results']] == [
        ('product-1', 'group-product-1'),
        ('product-2', 'group-product-2'),
    ]


@pytest.mark.parametrize('family, path, key, factory', [
    ('bundle', '/api/bundles/run', 'bundles', _bundle),
    ('itemcode', '/api/itemcodes/run', 'itemcodes', _itemcode),
    ('event', '/api/events/run', 'events', _event),
    ('product', '/api/products/run', 'products', _product),
])
def test_duplicate_nonblank_client_keys_are_rejected_before_state_for_all_routes(
        client, monkeypatch, family, path, key, factory):
    calls = _forbid_live_boundary(client, monkeypatch)
    specs = [factory('same'), factory('same')]
    if family == 'product':
        response = _post_product(client, specs, do_save=True)
    else:
        response = client.post(path, json={
            'game': GAME, key: specs, 'do_save': True,
        })
    assert response.status_code == 400
    assert response.json() == {
        'detail': 'client_key ของรายการห้ามซ้ำกัน'}
    assert calls == {'state': 0, 'gate': 0, 'builder': 0}


def test_collection_overflow_rejects_instead_of_truncating(
        client, monkeypatch):
    calls = _forbid_live_boundary(client, monkeypatch)
    response = client.post('/api/events/run', json={
        'game': GAME,
        'events': [_event(f'event-{number}') for number in range(31)],
        'do_save': True,
    })
    assert response.status_code == 400
    assert response.json() == {
        'detail': 'Event ทำได้ไม่เกิน 30 รายการต่อครั้ง'}

    response = client.post('/api/itemcodes/run', json={
        'game': GAME,
        'itemcodes': [_itemcode(rewards=[
            _reward(name_th=f'reward-{number}') for number in range(21)
        ])],
    })
    assert response.status_code == 400
    assert response.json() == {
        'detail': 'Item Code ที่ 1: มีชุดรางวัลได้ไม่เกิน 20 ชุด'}
    assert calls == {'state': 0, 'gate': 0, 'builder': 0}


def test_reward_boundaries_accept_20_and_reject_the_21st_for_both_families():
    rewards = [_reward(name_th=f'reward-{number}') for number in range(20)]
    assert len(web_app._clean_itemcode_rewards(rewards)) == 20
    assert len(web_app._clean_event_rewards(rewards)) == 20

    with pytest.raises(ValueError) as itemcode_error:
        web_app._clean_itemcode_rewards(rewards + [_reward()])
    assert str(itemcode_error.value) == (
        'Item Code ที่ 1: มีชุดรางวัลได้ไม่เกิน 20 ชุด')

    with pytest.raises(ValueError) as event_error:
        web_app._clean_event_rewards(rewards + [_reward()])
    assert str(event_error.value) == (
        'Event ที่ 1: มีชุดรางวัลได้ไม่เกิน 20 ชุด')


def test_activity_boundaries_send_all_30_jobs_without_truncating(
        client, monkeypatch):
    _connect_aztek(client)
    calls = []

    class Builder:
        def __init__(self, _log):
            pass

        async def run_many(self, **kwargs):
            calls.append(len(kwargs['specs']))
            return []

    monkeypatch.setattr(itemcode_runner, 'ItemCodeBuilder', Builder)
    monkeypatch.setattr(event_runner, 'EventBuilder', Builder)

    itemcode_response = client.post('/api/itemcodes/run', json={
        'game': GAME,
        'itemcodes': [_itemcode(f'itemcode-{number}') for number in range(30)],
        'do_save': True,
    })
    event_response = client.post('/api/events/run', json={
        'game': GAME,
        'events': [_event(f'event-{number}') for number in range(30)],
        'do_save': True,
    })
    assert itemcode_response.status_code == 200, itemcode_response.text
    assert event_response.status_code == 200, event_response.text
    assert calls == [30, 30]
    assert itemcode_response.json()['planned'] == 30
    assert event_response.json()['planned'] == 30
