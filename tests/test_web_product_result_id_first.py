"""Product result IDs via the public runner with every HTTP request intercepted.

Separate approved creates in all four games observed success:true/data.data.id
as UUID strings and data.data.name matching submitted th[name]/en[name] (identical
on each live draft). Each game's evidence is independent. IDs here are synthetic.
"""
import asyncio

import pytest

from web.product_runner import ProductBuilder
from test_web_itemcode_id_first import routed_runner_browser
from test_web_product_id_first import CREATE_URLS
from test_web_product_create_id_first import REQUEST, WRITE_URL, WRITE_URLS
from test_web_product_confirmation_id_first import confirmation_html


PRODUCT_ID = '11111111-2222-4333-8444-555555555555'


def result_html():
    html = confirmation_html()
    return html.replace("fetch('%s?owner=form',{method:'POST'})" % WRITE_URL,
        "sendProductResult()") + '''<script>function sendProductResult(){
      const body=new FormData();
      body.append('th[name]',document.querySelector('main form input[id=th_name]').value);
      body.append('en[name]',document.querySelector('main form input[id=en_name]').value);
      fetch('%s?owner=form',{method:'POST',body});
    }</script>''' % WRITE_URL


def test_mth_product_reports_own_nested_uuid_and_preserves_queue_identity(monkeypatch):
    payload = {'success': True, 'data': {'data': {
        'id': PRODUCT_ID, 'name': REQUEST['name_th'],
        'category_id': 'another-category', 'bundles': [{'bundle_id': 888}],
    }}}
    traffic, snapshots = routed_runner_browser(
        monkeypatch, result_html(), preview_urls=CREATE_URLS,
        synthetic_write_url=WRITE_URL, synthetic_write_json=payload)
    logs = []
    result = asyncio.run(ProductBuilder(lambda message, level: logs.append((message, level))).run_many(
        'CabalM TH', [dict(REQUEST)], {}))[0]
    assert (result['slug'], result['group'], result['saved'], result['made_id'], result['error']) == (
        'keep-product', 'keep-group', True, PRODUCT_ID, None)
    assert any(level == 'SUCCESS' and PRODUCT_ID in message for message, level in logs)
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['submits'] == ['1']
    assert traffic == [('GET', CREATE_URLS[0]), ('POST', WRITE_URL + '?owner=form')]


@pytest.mark.parametrize('body_change', ('wrong-name', 'duplicate-name', 'no-name', 'empty-name', 'file-name'))
def test_mth_product_uuid_requires_unambiguous_submitted_name(monkeypatch, body_change):
    html = result_html()
    field = "body.append('th[name]',document.querySelector('main form input[id=th_name]').value);"
    if body_change == 'wrong-name':
        html = html.replace(field, "body.append('th[name]','other-product');")
    elif body_change == 'duplicate-name':
        html = html.replace(field, field + "body.append('th[name]','other-product');")
    elif body_change == 'empty-name':
        html = html.replace(field, "body.append('th[name]','');")
    elif body_change == 'file-name':
        html = html.replace(field, "body.append('th[name]',new Blob(['other-product']),'name.txt');")
    else:
        html = html.replace(field, '')
    payload = {'success': True, 'data': {'data': {'id': PRODUCT_ID, 'name': REQUEST['name_th']}}}
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS,
        synthetic_write_url=WRITE_URL, synthetic_write_json=payload)
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many('CabalM TH', [dict(REQUEST)], {}))[0]
    assert (result['slug'], result['group'], result['saved'], result['made_id'], result['error']) == (
        'keep-product', 'keep-group', True, None, None)
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['submits'] == ['1']
    assert traffic == [('GET', CREATE_URLS[0]), ('POST', WRITE_URL + '?owner=form')]


@pytest.mark.parametrize('payload', (
    {'success': 1, 'data': {'data': {'id': PRODUCT_ID, 'name': REQUEST['name_th']}}},
    {'data': {'data': {'id': PRODUCT_ID, 'name': REQUEST['name_th']}}},
    {'success': True, 'data': {'id': PRODUCT_ID, 'name': REQUEST['name_th']}},
    {'success': True, 'data': {'data': [{'id': PRODUCT_ID, 'name': REQUEST['name_th']}]}},
    {'success': True, 'data': {'data': {'id': 888, 'name': REQUEST['name_th']}}},
    {'success': True, 'data': {'data': {'id': '888', 'name': REQUEST['name_th']}}},
    {'success': True, 'data': {'data': {'id': '00000000-0000-0000-0000-000000000000',
                                     'name': REQUEST['name_th']}}},
    {'success': True, 'data': {'data': {'id': '{11111111-2222-4333-8444-555555555555}',
                                     'name': REQUEST['name_th']}}},
    {'success': True, 'data': {'data': {'id': PRODUCT_ID, 'name': 'another-product'}}},
    {'success': True, 'data': {'data': {'id': PRODUCT_ID}}},
    {'success': True, 'data': {'data': {'name': REQUEST['name_th'], 'bundles': [{'id': PRODUCT_ID}]}}},
    ['unexpected-envelope'], 'unexpected-text',
), ids=('nonboolean-success', 'missing-success', 'wrong-wrapper', 'list-record', 'numeric-id',
        'numeric-string', 'nil-uuid', 'noncanonical-uuid', 'wrong-name', 'missing-name',
        'nested-bundle-id', 'list-envelope', 'string-envelope'))
def test_mth_unknown_product_response_preserves_result_without_id_or_retry(monkeypatch, payload):
    traffic, snapshots = routed_runner_browser(
        monkeypatch, result_html(), preview_urls=CREATE_URLS,
        synthetic_write_url=WRITE_URL, synthetic_write_json=payload)
    logs = []
    result = asyncio.run(ProductBuilder(lambda message, level: logs.append((message, level))).run_many(
        'CabalM TH', [dict(REQUEST)], {}))[0]
    assert (result['slug'], result['group'], result['saved'], result['made_id'], result['error']) == (
        'keep-product', 'keep-group', True, None, None)
    assert any(level == 'WARNING' and 'อ่านเลขไม่ได้' in message for message, level in logs)
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['submits'] == ['1']
    assert traffic == [('GET', CREATE_URLS[0]), ('POST', WRITE_URL + '?owner=form')]


@pytest.mark.parametrize('body', (
    "JSON.stringify({'th[name]':document.querySelector('main form input[id=th_name]').value})",
    "'malformed-multipart'",
))
def test_mth_product_unobserved_request_encoding_does_not_supply_identity(monkeypatch, body):
    html = result_html().replace("{method:'POST',body}", "{method:'POST',body:%s}" % body)
    payload = {'success': True, 'data': {'data': {'id': PRODUCT_ID, 'name': REQUEST['name_th']}}}
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS,
        synthetic_write_url=WRITE_URL, synthetic_write_json=payload)
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many('CabalM TH', [dict(REQUEST)], {}))[0]
    assert (result['saved'], result['made_id'], result['error']) == (True, None, None)
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['submits'] == ['1']
    assert traffic == [('GET', CREATE_URLS[0]), ('POST', WRITE_URL + '?owner=form')]


@pytest.mark.parametrize('game', tuple(WRITE_URLS)[1:])
def test_remaining_games_read_their_independently_verified_product_response(monkeypatch, game):
    endpoint = WRITE_URLS[game]
    payload = {'success': True, 'data': {'data': {'id': PRODUCT_ID, 'name': REQUEST['name_th']}}}
    traffic, snapshots = routed_runner_browser(
        monkeypatch, result_html().replace(WRITE_URL, endpoint), preview_urls=CREATE_URLS,
        synthetic_write_url=endpoint, synthetic_write_json=payload)
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many(game, [dict(REQUEST)], {}))[0]
    assert (result['saved'], result['made_id'], result['error']) == (True, PRODUCT_ID, None)
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['submits'] == ['1']
    assert traffic == [('GET', ProductBuilder(lambda *_: None).create_url(game)),
                       ('POST', endpoint + '?owner=form')]


@pytest.mark.parametrize('game', tuple(WRITE_URLS)[1:])
@pytest.mark.parametrize('fault', ('another-name', 'numeric-id'))
def test_remaining_games_keep_unknown_id_without_retry_for_unmatched_record(monkeypatch, game, fault):
    endpoint = WRITE_URLS[game]
    record = {'id': PRODUCT_ID, 'name': REQUEST['name_th']}
    record.update({'name': 'other-product'} if fault == 'another-name' else {'id': 208106})
    traffic, snapshots = routed_runner_browser(
        monkeypatch, result_html().replace(WRITE_URL, endpoint), preview_urls=CREATE_URLS,
        synthetic_write_url=endpoint, synthetic_write_json={'success': True, 'data': {'data': record}})
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many(game, [dict(REQUEST)], {}))[0]
    assert (result['slug'], result['group'], result['saved'], result['made_id'], result['error']) == (
        'keep-product', 'keep-group', True, None, None)
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['submits'] == ['1']
    assert traffic == [('GET', ProductBuilder(lambda *_: None).create_url(game)),
                       ('POST', endpoint + '?owner=form')]


def test_mth_explicit_product_failure_keeps_identity_without_retry(monkeypatch):
    payload = {'success': False, 'data': {'data': {'id': PRODUCT_ID, 'name': REQUEST['name_th']}}}
    traffic, snapshots = routed_runner_browser(
        monkeypatch, result_html(), preview_urls=CREATE_URLS,
        synthetic_write_url=WRITE_URL, synthetic_write_json=payload)
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many('CabalM TH', [dict(REQUEST)], {}))[0]
    assert (result['slug'], result['group'], result['saved'], result['made_id']) == (
        'keep-product', 'keep-group', False, None)
    assert 'success=false' in result['error'] and 'ตรวจบนเว็บ' in result['error']
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['submits'] == ['1']
    assert traffic == [('GET', CREATE_URLS[0]), ('POST', WRITE_URL + '?owner=form')]


def test_product_identity_uses_sent_name_not_later_dom_and_allows_image_parts(monkeypatch):
    html = result_html().replace("fetch('%s?owner=form',{method:'POST',body});" % WRITE_URL,
        "body.append('th[thumbnail]',new Blob(['synthetic-image']),'image.png');"
        "fetch('%s?owner=form',{method:'POST',body});" % WRITE_URL +
        "document.querySelector('main form input[id=th_name]').value='edited-after-send';")
    payload = {'success': True, 'data': {'data': {'id': PRODUCT_ID, 'name': REQUEST['name_th']}}}
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS,
        synthetic_write_url=WRITE_URL, synthetic_write_json=payload)
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many('CabalM TH', [dict(REQUEST)], {}))[0]
    assert (result['saved'], result['made_id'], result['error']) == (True, PRODUCT_ID, None)
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['submits'] == ['1']
    assert traffic == [('GET', CREATE_URLS[0]), ('POST', WRITE_URL + '?owner=form')]
