"""Event confirmation and captured-endpoint guards; every request is fulfilled locally.

The live aborted POST proves the route, not its response JSON shape. Numeric
fixture IDs below distinguish synthetic responses only; live Event IDs are UUIDs.
"""
import asyncio

import pytest

from web.event_runner import EventBuilder
from test_web_event_id_first import (
    CREATE_URLS, EVENT_WRITE_URLS, MTH_EVENT_WRITE, SYNTHETIC_EVENT_WRITE,
    event_create_spec, event_mth_confirmation_html,
)
from test_web_itemcode_id_first import routed_runner_browser


@pytest.mark.parametrize(('game', 'endpoint'), tuple(EVENT_WRITE_URLS.items())[1:])
def test_remaining_game_ignores_unrelated_response_before_own_confirmation(monkeypatch, game, endpoint):
    html = event_mth_confirmation_html().replace(MTH_EVENT_WRITE, endpoint).replace(
        "document.getElementById('runtime-event-dialog').hidden=false",
        "document.getElementById('runtime-event-dialog').hidden=false;"
        "fetch('https://afc-synthetic.invalid/event-write?owner=outside',{method:'POST'})")
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS,
        synthetic_write_url=(endpoint, SYNTHETIC_EVENT_WRITE))
    result = asyncio.run(EventBuilder(lambda *_: None).run_many(
        game, [event_create_spec()], {'cookies': [], 'origins': []}))[0]
    assert (result['saved'], result['made_id'], result['error']) == (True, None, None)
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['submits'] == ['1']
    assert traffic[-1] == ('POST', endpoint + '?owner=form')


@pytest.mark.parametrize(('game', 'endpoint'), tuple(EVENT_WRITE_URLS.items())[1:])
def test_remaining_game_broken_confirmation_never_writes(monkeypatch, game, endpoint):
    html = event_mth_confirmation_html().replace(MTH_EVENT_WRITE, endpoint).replace(
        'aria-describedby="runtime-event-description"', '')
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=endpoint)
    result = asyncio.run(EventBuilder(lambda *_: None).run_many(
        game, [event_create_spec()], {'cookies': [], 'origins': []}))[0]
    assert (result['saved'], result['made_id']) == (False, None)
    assert snapshots[0]['confirms'] == '0' and snapshots[0]['submits'] == ['1']
    assert [method for method, _ in traffic] == ['GET']


@pytest.mark.parametrize(('wrong_url', 'method'), (
    ('https://wrong-api.example.invalid/cabalm/event/events', 'POST'),
    ('https://admin-api-v2.combo-interactive.com/cabalpc/event/events', 'POST'),
    ('https://admin-api-v2.combo-interactive.com/cabalm/event/events/other', 'POST'),
    ('https://admin-api-v2.combo-interactive.com/cabalm/event/events', 'PUT'),
    ('https://admin-api-v2.combo-interactive.com/cabalm/event/events', 'PATCH'),
), ids=('wrong-host', 'wrong-game', 'wrong-path', 'put', 'patch'))
def test_mth_confirmation_ignores_unrelated_responses(monkeypatch, wrong_url, method):
    html = event_mth_confirmation_html().replace(
        "document.getElementById('runtime-event-dialog').hidden=false",
        "document.getElementById('runtime-event-dialog').hidden=false;"
        "fetch('%s?owner=outside',{method:'%s'})" % (wrong_url, method))
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS,
        synthetic_write_url=(MTH_EVENT_WRITE, wrong_url))
    result = asyncio.run(EventBuilder(lambda *_: None).run_many(
        'CabalM TH', [event_create_spec()], {'cookies': [], 'origins': []}))[0]
    assert (result['saved'], result['made_id'], result['error']) == (True, None, None)
    assert snapshots[0]['submits'] == ['1'] and snapshots[0]['confirms'] == '1'
    assert (method, wrong_url + '?owner=outside') in traffic
    assert traffic[-1] == ('POST', MTH_EVENT_WRITE + '?owner=form')


def test_mth_confirmation_ignores_same_endpoint_in_another_frame(monkeypatch):
    html = event_mth_confirmation_html().replace(
        "document.getElementById('runtime-event-dialog').hidden=false",
        "document.getElementById('runtime-event-dialog').hidden=false;"
        "document.getElementById('foreign-event-frame').contentWindow.postMessage('go','*')")
    html += '''<iframe id="foreign-event-frame" srcdoc="<script>
      addEventListener('message',()=>fetch('https://admin-api-v2.combo-interactive.com/cabalm/event/events?owner=outside',
        {method:'POST'}));</script>"></iframe>'''
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=MTH_EVENT_WRITE)
    result = asyncio.run(EventBuilder(lambda *_: None).run_many(
        'CabalM TH', [event_create_spec()], {'cookies': [], 'origins': []}))[0]
    assert (result['saved'], result['made_id'], result['error']) == (True, None, None)
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['submits'] == ['1']
    assert ('POST', MTH_EVENT_WRITE + '?owner=outside') in traffic
    assert traffic[-1] == ('POST', MTH_EVENT_WRITE + '?owner=form')


@pytest.mark.parametrize(('before', 'after'), (
    ('id="runtime-event-description"', 'id="unlinked-description"'),
    ('<button type="button">ยกเลิก</button>',
     '<button type="button" hidden>ยืนยัน</button><button type="button">ยกเลิก</button>'),
    ('<button type="button" onclick="document.body.dataset.confirms=',
     '<button type="submit" onclick="document.body.dataset.confirms='),
    ('<button type="button" onclick="document.body.dataset.confirms=',
     '<button type="button" form="other-form" onclick="document.body.dataset.confirms='),
    ('role="alertdialog"', 'role="region"'),
))
def test_mth_broken_confirmation_preserves_queue_without_write(monkeypatch, before, after):
    html = event_mth_confirmation_html().replace(before, after)
    assert html != event_mth_confirmation_html()
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=MTH_EVENT_WRITE)
    result = asyncio.run(EventBuilder(lambda *_: None).run_many(
        'CabalM TH', [event_create_spec()], {'cookies': [], 'origins': []}))[0]
    assert (result['slug'], result['group'], result['saved'], result['made_id']) == (
        'requested-event', 'source-group', False, None)
    assert 'Event' in (result['error'] or '')
    assert snapshots[0]['confirms'] == '0' and snapshots[0]['submits'] == ['1']
    assert snapshots[0]['rewards'][0]['bundle_id'] == '1001'
    assert traffic == [('GET', CREATE_URLS[0])]


def test_mth_confirmation_preview_never_submits(monkeypatch):
    traffic, snapshots = routed_runner_browser(
        monkeypatch, event_mth_confirmation_html(), preview_urls=CREATE_URLS,
        synthetic_write_url=MTH_EVENT_WRITE)
    result = asyncio.run(EventBuilder(lambda *_: None).run(
        'CabalM TH', event_create_spec(), {'cookies': [], 'origins': []}))
    assert result['missing'] == []
    assert snapshots[0]['submits'] == ['0'] and snapshots[0]['confirms'] == '0'
    assert traffic == [('GET', CREATE_URLS[0])]


def test_mth_confirmation_waits_for_lazy_dialog_without_second_create(monkeypatch):
    html = event_mth_confirmation_html().replace(
        "document.getElementById('runtime-event-dialog').hidden=false",
        "setTimeout(()=>document.getElementById('runtime-event-dialog').hidden=false,4000)")
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=MTH_EVENT_WRITE)
    result = asyncio.run(EventBuilder(lambda *_: None).run_many(
        'CabalM TH', [event_create_spec()], {'cookies': [], 'origins': []}))[0]
    assert (result['saved'], result['made_id'], result['error']) == (True, None, None)
    assert snapshots[0]['submits'] == ['1'] and snapshots[0]['confirms'] == '1'
    assert traffic == [('GET', CREATE_URLS[0]), ('POST', MTH_EVENT_WRITE + '?owner=form')]


@pytest.mark.parametrize('source', ('nested-bundle', 'numeric-url'))
def test_mth_unverified_result_does_not_borrow_another_records_numeric_id(monkeypatch, source):
    html = event_mth_confirmation_html()
    payload = {'id': '11111111-2222-4333-8444-555555555555',
               'rewards': [{'bundle_id': 1001}]}
    if source == 'numeric-url':
        payload = {}
        html = html.replace("{method:'POST'})\">ยืนยัน</button>",
                            "{method:'POST'}).then(()=>history.pushState({},'',"
                            "'/combo/cabalm/events/1001/edit'))\">ยืนยัน</button>")
        assert html != event_mth_confirmation_html()
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=MTH_EVENT_WRITE,
        synthetic_write_json=payload)
    logs = []
    result = asyncio.run(EventBuilder(lambda message, level: logs.append((message, level))).run_many(
        'CabalM TH', [event_create_spec()], {'cookies': [], 'origins': []}))[0]
    assert (result['saved'], result['made_id'], result['error']) == (True, None, None)
    assert any(level == 'WARNING' and 'อ่านเลขไม่ได้' in message for message, level in logs)
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['submits'] == ['1']
    assert traffic == [('GET', CREATE_URLS[0]), ('POST', MTH_EVENT_WRITE + '?owner=form')]
