"""Event result IDs through the public runner with all HTTP intercepted.

M TH's Oct17 envelope and independent M SEA/PC TH/PC SEA Oct21 captures
establish data.data.id and matching data.data.slug. UUIDs below are synthetic,
not the created records. These tests never access Aztek or replay those writes.
"""
import asyncio

import pytest

from web.event_runner import EventBuilder
from test_web_event_id_first import (
    CREATE_URLS, EVENT_WRITE_URLS, MTH_EVENT_WRITE, event_create_spec, event_mth_confirmation_html,
)
from test_web_itemcode_id_first import routed_runner_browser


GAME_CASES = (
    ('CabalM TH', CREATE_URLS[0], MTH_EVENT_WRITE),
    ('CabalM SEA', CREATE_URLS[1], EVENT_WRITE_URLS['CabalM SEA']),
    ('CabalPC TH', CREATE_URLS[2], EVENT_WRITE_URLS['CabalPC TH']),
    ('CabalPC SEA', CREATE_URLS[3], EVENT_WRITE_URLS['CabalPC SEA']),
)


def event_result_html(endpoint=MTH_EVENT_WRITE):
    html = event_mth_confirmation_html()
    original = "{method:'POST'})\">ยืนยัน</button>"
    updated = ("{method:'POST',body:JSON.stringify({slug:"
               "document.querySelector('main form input[id=slug]').value})})\">ยืนยัน</button>")
    assert original in html
    return html.replace(original, updated).replace(MTH_EVENT_WRITE, endpoint)


@pytest.mark.parametrize(('game', 'create_url', 'endpoint'), GAME_CASES)
def test_runner_reports_only_own_nested_event_uuid(monkeypatch, game, create_url, endpoint):
    payload = {'success': True, 'data': {'data': {
        'id': '11111111-2222-4333-8444-555555555555', 'slug': 'requested-event',
        'rewards': [{'bundle_id': 1001}],
    }}}
    traffic, snapshots = routed_runner_browser(
        monkeypatch, event_result_html(endpoint), preview_urls=CREATE_URLS,
        synthetic_write_url=endpoint, synthetic_write_json=payload)
    logs = []
    result = asyncio.run(EventBuilder(lambda message, level: logs.append((message, level))).run_many(
        game, [event_create_spec()], {'cookies': [], 'origins': []}))[0]
    assert (result['saved'], result['made_id'], result['error']) == (
        True, '11111111-2222-4333-8444-555555555555', None)
    assert any(level == 'SUCCESS' and '11111111-2222-4333-8444-555555555555' in message
               for message, level in logs)
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['submits'] == ['1']
    assert traffic == [('GET', create_url), ('POST', endpoint + '?owner=form')]


@pytest.mark.parametrize(('game', 'create_url', 'endpoint'), GAME_CASES)
@pytest.mark.parametrize('payload', (
    {'success': 1, 'data': {'data': {
        'id': '11111111-2222-4333-8444-555555555555', 'slug': 'requested-event'}}},
    {'success': True, 'data': {
        'id': '11111111-2222-4333-8444-555555555555', 'slug': 'requested-event'}},
    {'success': True, 'data': {'data': [{'id': '11111111-2222-4333-8444-555555555555'}]}},
    {'success': True, 'data': {'data': {'id': 1001, 'slug': 'requested-event'}}},
    {'success': True, 'data': {'data': {'id': '1001', 'slug': 'requested-event'}}},
    {'success': True, 'data': {'data': {'id': '00000000-0000-0000-0000-000000000000',
                                     'slug': 'requested-event'}}},
    {'success': True, 'data': {'data': {'id': '{11111111-2222-4333-8444-555555555555}',
                                     'slug': 'requested-event'}}},
    {'success': True, 'data': {'data': {'id': '11111111-2222-4333-8444-555555555555',
                                     'slug': 'another-event'}}},
    {'success': True, 'data': {'data': {'id': '11111111-2222-4333-8444-555555555555'}}},
    {'success': True, 'data': {'data': {'slug': 'requested-event',
                                     'rewards': [{'id': '11111111-2222-4333-8444-555555555555'}]}}},
), ids=('nonboolean-success', 'wrong-wrapper', 'list-record', 'numeric-id',
        'numeric-string', 'nil-uuid', 'noncanonical-uuid', 'wrong-slug', 'missing-slug', 'nested-reward-id'))
def test_unknown_response_keeps_saved_result_without_id_or_resubmit(monkeypatch, game, create_url, endpoint, payload):
    traffic, snapshots = routed_runner_browser(
        monkeypatch, event_result_html(endpoint), preview_urls=CREATE_URLS,
        synthetic_write_url=endpoint, synthetic_write_json=payload)
    logs = []
    result = asyncio.run(EventBuilder(lambda message, level: logs.append((message, level))).run_many(
        game, [event_create_spec()], {'cookies': [], 'origins': []}))[0]
    assert (result['slug'], result['group'], result['saved'], result['made_id'], result['error']) == (
        'requested-event', 'source-group', True, None, None)
    assert any(level == 'WARNING' and 'อ่านเลขไม่ได้' in message for message, level in logs)
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['submits'] == ['1']
    assert traffic == [('GET', create_url), ('POST', endpoint + '?owner=form')]


@pytest.mark.parametrize(('game', 'create_url', 'endpoint'), GAME_CASES)
def test_explicit_negative_result_retains_queue_identity_without_retry(monkeypatch, game, create_url, endpoint):
    payload = {'success': False, 'data': {'data': {
        'id': '11111111-2222-4333-8444-555555555555', 'slug': 'requested-event'}}}
    traffic, snapshots = routed_runner_browser(
        monkeypatch, event_result_html(endpoint), preview_urls=CREATE_URLS,
        synthetic_write_url=endpoint, synthetic_write_json=payload)
    logs = []
    result = asyncio.run(EventBuilder(lambda message, level: logs.append((message, level))).run_many(
        game, [event_create_spec()], {'cookies': [], 'origins': []}))[0]
    assert (result['slug'], result['group'], result['saved'], result['made_id']) == (
        'requested-event', 'source-group', False, None)
    assert 'success=false' in (result['error'] or '') and 'ตรวจบนเว็บ' in result['error']
    assert not any(level == 'SUCCESS' and 'สร้างEventสำเร็จ' in message for message, level in logs)
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['submits'] == ['1']
    assert traffic == [('GET', create_url), ('POST', endpoint + '?owner=form')]


@pytest.mark.parametrize(('game', 'create_url', 'endpoint'), GAME_CASES)
@pytest.mark.parametrize('request_body', ('null', "{slug:'another-event'}"))
def test_response_uuid_requires_matching_json_request_identity(monkeypatch, game, create_url, endpoint, request_body):
    html = event_result_html(endpoint).replace(
        "{slug:document.querySelector('main form input[id=slug]').value}", request_body)
    payload = {'success': True, 'data': {'data': {
        'id': '11111111-2222-4333-8444-555555555555', 'slug': 'requested-event'}}}
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS,
        synthetic_write_url=endpoint, synthetic_write_json=payload)
    result = asyncio.run(EventBuilder(lambda *_: None).run_many(
        game, [event_create_spec()], {'cookies': [], 'origins': []}))[0]
    assert (result['saved'], result['made_id'], result['error']) == (True, None, None)
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['submits'] == ['1']
    assert traffic == [('GET', create_url), ('POST', endpoint + '?owner=form')]
