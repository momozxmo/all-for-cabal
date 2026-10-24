"""Product confirmation/write attribution via the public, fully intercepted runner.

Dialog and request routes were independently read in all four games on Oct20.
Response bodies are synthetic markers, NOT evidence of Product result schemas.
"""
import asyncio
import json
from html import escape

import pytest

from web.product_runner import ProductBuilder
from test_web_itemcode_id_first import routed_runner_browser
from test_web_product_id_first import CREATE_URLS
from test_web_product_create_id_first import create_html, REQUEST, WRITE_URL, WRITE_URLS


def confirmation_html(game='CabalM TH'):
    endpoint = WRITE_URLS[game]
    html = create_html().replace('data-create-audit', 'data-create-audit data-confirm-audit')
    html = html.replace("fetch('%s?owner=form',{method:'POST'})" % WRITE_URL,
                        "document.querySelector('[data-product-confirmation]').hidden=false")
    html = html.replace('<aside>', '''<aside><button type="button" onclick="
      document.body.dataset.outsideConfirms=String(1+Number(document.body.dataset.outsideConfirms||0));
      fetch('%s?owner=outside',{method:'POST'})">ยืนยัน</button>''' % endpoint)
    html += '''<div data-product-confirmation role="alertdialog" data-state="open" hidden
      aria-labelledby="runtime-product-title" aria-describedby="runtime-product-description">
      <h2 id="runtime-product-title">ยืนยันการสร้าง</h2>
      <p id="runtime-product-description">ต้องการสร้าง Product ใช่หรือไม่?</p>
      <button type="button">ยกเลิก</button><button type="button" data-product-confirm-action onclick="
        document.body.dataset.confirms=String(1+Number(document.body.dataset.confirms||0));
        fetch('%s?owner=form',{method:'POST'})">ยืนยัน</button></div>''' % endpoint
    return html


@pytest.mark.parametrize('game', WRITE_URLS)
def test_product_confirms_only_its_own_dialog_not_outside_confirm(monkeypatch, game):
    endpoint = WRITE_URLS[game]
    traffic, snapshots = routed_runner_browser(
        monkeypatch, confirmation_html(game), preview_urls=CREATE_URLS, synthetic_write_url=endpoint)
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many(game, [dict(REQUEST)], {}))[0]
    assert snapshots[0]['outsideConfirms'] == '0'
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['submits'] == ['1']
    assert (result['slug'], result['group'], result['saved'], result['made_id'], result['error']) == (
        'keep-product', 'keep-group', True, None, None)
    assert traffic == [('GET', ProductBuilder(lambda *_: None).create_url(game)),
                       ('POST', endpoint + '?owner=form')]


@pytest.mark.parametrize('game', WRITE_URLS)
def test_product_unrelated_response_cannot_skip_own_confirmation(monkeypatch, game):
    endpoint = WRITE_URLS[game]
    wrong = 'https://afc-synthetic.invalid/product-background'
    html = confirmation_html(game).replace(
        "document.querySelector('[data-product-confirmation]').hidden=false",
        "document.querySelector('[data-product-confirmation]').hidden=false;"
        "fetch('%s?owner=outside',{method:'POST'});"
        "document.querySelector('[data-product-confirm-action]').disabled=true;"
        "setTimeout(()=>document.querySelector('[data-product-confirm-action]').disabled=false,400)" % wrong)
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=(endpoint, wrong))
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many(game, [dict(REQUEST)], {}))[0]
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['outsideConfirms'] == '0'
    assert snapshots[0]['submits'] == ['1']
    assert (result['saved'], result['made_id'], result['error']) == (True, None, None)
    assert traffic[-1] == ('POST', endpoint + '?owner=form')


@pytest.mark.parametrize('game', WRITE_URLS)
def test_product_unknown_response_cannot_borrow_bundle_or_currency_id(monkeypatch, game):
    endpoint = WRITE_URLS[game]
    traffic, snapshots = routed_runner_browser(
        monkeypatch, confirmation_html(game), preview_urls=CREATE_URLS,
        synthetic_write_url=endpoint,
        synthetic_write_json={'bundle_id': 888, 'category': {'id': 777}, 'prices': [{'currency_id': 666}]})
    logs = []
    result = asyncio.run(ProductBuilder(lambda message, level: logs.append(message)).run_many(
        game, [dict(REQUEST)], {}))[0]
    assert result['made_id'] is None
    assert (result['slug'], result['group'], result['saved']) == ('keep-product', 'keep-group', True)
    assert any('อ่านเลขไม่ได้' in line for line in logs)
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['submits'] == ['1']
    assert traffic == [('GET', ProductBuilder(lambda *_: None).create_url(game)), ('POST', endpoint + '?owner=form')]


@pytest.mark.parametrize('game', WRITE_URLS)
def test_product_explicit_failure_does_not_report_saved_or_retry(monkeypatch, game):
    endpoint = WRITE_URLS[game]
    traffic, snapshots = routed_runner_browser(
        monkeypatch, confirmation_html(game), preview_urls=CREATE_URLS,
        synthetic_write_url=endpoint, synthetic_write_json={'success': False, 'bundle_id': 888})
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many(game, [dict(REQUEST)], {}))[0]
    assert (result['saved'], result['made_id']) == (False, None)
    assert 'success=false' in result['error']
    assert (result['slug'], result['group']) == ('keep-product', 'keep-group')
    assert snapshots[0]['submits'] == ['1'] and snapshots[0]['confirms'] == '1'
    assert traffic == [('GET', ProductBuilder(lambda *_: None).create_url(game)), ('POST', endpoint + '?owner=form')]


@pytest.mark.parametrize('game', WRITE_URLS)
def test_product_broken_confirmation_relation_stops_without_any_write(monkeypatch, game):
    html = confirmation_html(game).replace('aria-describedby="runtime-product-description"', '')
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=WRITE_URLS[game])
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many(game, [dict(REQUEST)], {}))[0]
    assert (result['slug'], result['group'], result['saved'], result['made_id']) == (
        'keep-product', 'keep-group', False, None)
    assert 'Product' in result['error']
    assert snapshots[0]['submits'] == ['1'] and snapshots[0]['confirms'] == '0'
    assert snapshots[0]['outsideConfirms'] == '0'
    assert traffic == [('GET', ProductBuilder(lambda *_: None).create_url(game))]


@pytest.mark.parametrize('fault', ('duplicate-action', 'submit-action', 'form-owner', 'nested-dialog', 'duplicate-title-id'))
def test_product_malformed_confirmation_never_borrows_outside_confirm(monkeypatch, fault):
    html = confirmation_html()
    if fault == 'duplicate-action':
        html = html.replace('<button type="button" data-product-confirm-action',
                            '<button type="button">ยืนยัน</button><button type="button" data-product-confirm-action')
    elif fault == 'submit-action':
        html = html.replace('type="button" data-product-confirm-action', 'type="submit" data-product-confirm-action')
    elif fault == 'form-owner':
        html = html.replace('data-product-confirm-action', 'form="other-form" data-product-confirm-action')
        html += '<form id="other-form" onsubmit="event.preventDefault();this.dataset.submits=1"></form>'
    elif fault == 'nested-dialog':
        html = html.replace('<h2 id="runtime-product-title">', '<div role="dialog"></div><h2 id="runtime-product-title">')
    else:
        html += '<h2 id="runtime-product-title">ยืนยันการสร้าง</h2>'
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=WRITE_URL)
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many('CabalM TH', [dict(REQUEST)], {}))[0]
    assert result['saved'] is False and result['made_id'] is None and 'Product' in result['error']
    assert snapshots[0]['confirms'] == '0' and snapshots[0]['outsideConfirms'] == '0'
    assert snapshots[0]['submits'] == (['1', '0'] if fault == 'form-owner' else ['1'])
    assert traffic == [('GET', CREATE_URLS[0])]


@pytest.mark.parametrize(('wrong', 'method'), (
    ('https://wrong-api.example.invalid/cabalm/shop/products', 'POST'),
    ('https://admin-api-v2.combo-interactive.com/cabalm/shop/products/other', 'POST'),
    ('https://admin-api-v2.combo-interactive.com/cabalm/shop/products-extra', 'POST'),
    (WRITE_URL, 'PUT'), (WRITE_URL, 'PATCH'),
), ids=('wrong-host', 'child-path', 'suffix-path', 'put', 'patch'))
def test_product_other_operation_response_does_not_skip_confirmation(monkeypatch, wrong, method):
    html = confirmation_html().replace(
        "document.querySelector('[data-product-confirmation]').hidden=false",
        "document.querySelector('[data-product-confirmation]').hidden=false;"
        "fetch('%s?owner=outside',{method:'%s'});"
        "document.querySelector('[data-product-confirm-action]').disabled=true;"
        "setTimeout(()=>document.querySelector('[data-product-confirm-action]').disabled=false,400)" % (wrong, method))
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=(WRITE_URL, wrong))
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many('CabalM TH', [dict(REQUEST)], {}))[0]
    assert (result['saved'], result['made_id'], result['error']) == (True, None, None)
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['outsideConfirms'] == '0'
    assert snapshots[0]['submits'] == ['1'] and traffic[-1] == ('POST', WRITE_URL + '?owner=form')
    assert all(url.split('?')[0] in (CREATE_URLS[0], WRITE_URL, wrong) for _, url in traffic)


@pytest.mark.parametrize(('game', 'other'), (
    ('CabalM TH', 'CabalM SEA'), ('CabalM SEA', 'CabalPC TH'),
    ('CabalPC TH', 'CabalPC SEA'), ('CabalPC SEA', 'CabalM TH'),
))
def test_product_different_game_response_does_not_skip_confirmation(monkeypatch, game, other):
    endpoint, wrong = WRITE_URLS[game], WRITE_URLS[other]
    html = confirmation_html(game).replace(
        "document.querySelector('[data-product-confirmation]').hidden=false",
        "document.querySelector('[data-product-confirmation]').hidden=false;"
        "fetch('%s?owner=outside',{method:'POST'});"
        "document.querySelector('[data-product-confirm-action]').disabled=true;"
        "setTimeout(()=>document.querySelector('[data-product-confirm-action]').disabled=false,400)" % wrong)
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=(endpoint, wrong))
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many(game, [dict(REQUEST)], {}))[0]
    assert (result['saved'], result['made_id'], result['error']) == (True, None, None)
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['outsideConfirms'] == '0'
    assert snapshots[0]['submits'] == ['1'] and traffic[-1] == ('POST', endpoint + '?owner=form')
    assert traffic == [('GET', ProductBuilder(lambda *_: None).create_url(game)),
                       ('POST', wrong + '?owner=outside'), ('POST', endpoint + '?owner=form')]


def test_product_child_frame_response_does_not_skip_main_form_confirmation(monkeypatch):
    code = "<script>fetch('%s?owner=outside',{method:'POST'})</script>" % WRITE_URL
    html = confirmation_html().replace(
        "document.querySelector('[data-product-confirmation]').hidden=false",
        "document.querySelector('[data-product-confirmation]').hidden=false;spawnProductFrame()")
    html += '''<script>function spawnProductFrame(){
      const frame=document.createElement('iframe');frame.srcdoc=FRAME;document.body.append(frame);
      document.querySelector('[data-product-confirm-action]').disabled=true;
      setTimeout(()=>document.querySelector('[data-product-confirm-action]').disabled=false,400);
    }</script>'''.replace('FRAME', json.dumps(code).replace('</', '<\\/'))
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=WRITE_URL)
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many('CabalM TH', [dict(REQUEST)], {}))[0]
    assert (result['saved'], result['made_id'], result['error']) == (True, None, None)
    assert snapshots[0]['submits'] == ['1'] and snapshots[0]['confirms'] == '1'
    assert traffic == [('GET', CREATE_URLS[0]), ('POST', WRITE_URL + '?owner=outside'),
                       ('POST', WRITE_URL + '?owner=form')]


def test_product_confirmation_is_never_activated_in_preview(monkeypatch):
    traffic, snapshots = routed_runner_browser(
        monkeypatch, confirmation_html(), preview_urls=CREATE_URLS, synthetic_write_url=WRITE_URL)
    result = asyncio.run(ProductBuilder(lambda *_: None).run('CabalM TH', dict(REQUEST), {}))
    assert result['missing'] == []
    assert snapshots[0]['submits'] == ['0'] and snapshots[0]['confirms'] == '0'
    assert snapshots[0]['outsideConfirms'] == '0' and traffic == [('GET', CREATE_URLS[0])]


def test_product_write_while_waiting_for_confirmation_does_not_submit_twice(monkeypatch):
    html = confirmation_html().replace(
        "document.querySelector('[data-product-confirmation]').hidden=false",
        "document.querySelector('[data-product-confirmation]').hidden=false;"
        "document.querySelector('[data-product-confirm-action]').disabled=true;"
        "fetch('%s?owner=form',{method:'POST'});"
        "setTimeout(()=>document.querySelector('[data-product-confirm-action]').disabled=false,400)" % WRITE_URL)
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=WRITE_URL)
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many('CabalM TH', [dict(REQUEST)], {}))[0]
    assert (result['saved'], result['made_id'], result['error']) == (True, None, None)
    assert snapshots[0]['submits'] == ['1'] and snapshots[0]['confirms'] == '0'
    assert snapshots[0]['outsideConfirms'] == '0'
    assert traffic == [('GET', CREATE_URLS[0]), ('POST', WRITE_URL + '?owner=form')]


def test_product_confirmation_type_change_during_actionability_stops_without_retry(monkeypatch):
    html = confirmation_html().replace('data-product-confirm-action onclick=',
        'data-product-confirm-action style="position:fixed;top:0;right:0;width:180px;height:60px" onclick=')
    html = html.replace("document.querySelector('[data-product-confirmation]').hidden=false",
        "document.querySelector('[data-product-confirmation]').hidden=false;"
        "setTimeout(()=>{document.querySelector('[data-product-confirm-action]').type='submit';"
        "document.querySelector('[data-obstruction]').remove()},700)")
    html += '<div data-obstruction style="position:fixed;top:0;right:0;width:190px;height:65px;z-index:9999"></div>'
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=WRITE_URL)
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many('CabalM TH', [dict(REQUEST)], {}))[0]
    assert (result['saved'], result['made_id']) == (False, None)
    assert 'Product' in result['error']
    assert snapshots[0]['submits'] == ['1'] and snapshots[0]['confirms'] == '0'
    assert traffic == [('GET', CREATE_URLS[0])]


@pytest.mark.parametrize('path', (
    '/combo/cabalm/shop/products/501', '/combo/cabalpc/shop/products/501',
    '/combo/cabalm/shop/products/create?record=501',
))
def test_product_no_response_never_invents_product_id_from_unverified_url(monkeypatch, path):
    html = confirmation_html().replace("fetch('%s?owner=form',{method:'POST'})" % WRITE_URL,
                                       "history.pushState({},'',%s)" % escape(json.dumps(path), quote=True))
    traffic, snapshots = routed_runner_browser(monkeypatch, html, preview_urls=CREATE_URLS)
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many('CabalM TH', [dict(REQUEST)], {}))[0]
    assert (result['slug'], result['group'], result['saved'], result['made_id']) == (
        'keep-product', 'keep-group', False, None)
    assert snapshots[0]['submits'] == ['1'] and snapshots[0]['confirms'] == '1'
    assert traffic == [('GET', CREATE_URLS[0])]
