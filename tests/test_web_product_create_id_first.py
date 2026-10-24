"""Product create-action contract via public runner; every HTTP request intercepted.

Routes below were captured with HTTP blocked. Response JSON stays synthetic;
the Product response schema is still unverified.
"""
import asyncio

import pytest

from web.product_runner import ProductBuilder
from test_web_itemcode_id_first import routed_runner_browser
from test_web_product_id_first import SPEC, CREATE_URLS
from test_web_product_options_id_first import OPTIONS_HTML
from test_web_product_display_id_first import limit_html
from test_web_product_bundle_id_first import bundle_html


WRITE_URLS = {
    'CabalM TH': 'https://admin-api-v2.combo-interactive.com/cabalm/shop/products',
    'CabalM SEA': 'https://admin-api-v2.combo-interactive.com/cabalmsea/shop/products',
    'CabalPC TH': 'https://admin-api-v2.combo-interactive.com/cabalpc/shop/products',
    'CabalPC SEA': 'https://admin-api-v2.combo-interactive.com/cabalpcsea/shop/products',
}
WRITE_URL = WRITE_URLS['CabalM TH']
GAMES = tuple(WRITE_URLS)
REQUEST = {
    **SPEC, 'category_id': 'category-9',
    'prices': [{'currency_id': 'gem:92', 'original_price': '0', 'price': '10'}],
    'start_at': '2026-10-17 00:00:00', 'end_at': '2027-09-28 23:59:59',
    'limit_type': 'UNLIMITED', 'bundle_ids': ['2081', '2082'], 'primary_bundle_id': '2082',
    'slug': 'keep-product', 'group': 'keep-group',
}


def create_html(write_url=WRITE_URL):
    html = bundle_html(limit_html(OPTIONS_HTML))
    html = html.replace('<aside>', '''<aside><button type="button"
      onclick="document.body.dataset.outsideCreates='1'">สร้าง Product</button>''')
    html = html.replace("event.preventDefault();this.dataset.submits='1'",
        "event.preventDefault();this.dataset.submits=String(1+Number(this.dataset.submits||0));"
        "fetch('%s?owner=form',{method:'POST'})" % write_url)
    return '<body data-create-audit>' + html + '</body>'


@pytest.mark.parametrize('game', GAMES)
def test_product_create_submits_only_own_form_not_outside_named_button(monkeypatch, game):
    endpoint = WRITE_URLS[game]
    traffic, snapshots = routed_runner_browser(
        monkeypatch, create_html(endpoint), preview_urls=CREATE_URLS, synthetic_write_url=endpoint)
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many(game, [dict(REQUEST)], {}))[0]
    assert (result['slug'], result['group'], result['saved'], result['made_id'], result['error']) == (
        'keep-product', 'keep-group', True, None, None)
    assert snapshots[0]['outsideCreates'] == '0' and snapshots[0]['submits'] == ['1']
    assert traffic == [('GET', ProductBuilder(lambda *_: None).create_url(game)),
                       ('POST', endpoint + '?owner=form')]


@pytest.mark.parametrize('replacement', (
    '', '<button type="submit">สร้าง Product เพิ่มเติม</button>',
    '<button type="submit">สร้าง Product</button>' * 2,
    '<button type="submit" hidden>สร้าง Product</button><button type="submit">สร้าง Product</button>',
    '<button type="button">สร้าง Product</button>', '<button>สร้าง Product</button>',
    '<button type="submit" role="link">สร้าง Product</button>',
    '<button type="submit" disabled>สร้าง Product</button>',
    '<button type="submit" form="other-form">สร้าง Product</button>',
), ids=('missing', 'partial-label', 'duplicate', 'hidden-duplicate', 'wrong-type',
        'implicit-type', 'wrong-role', 'disabled', 'wrong-owner'))
def test_product_broken_create_contract_preserves_queue_without_submit(monkeypatch, replacement):
    html = create_html().replace('<button type="submit">สร้าง Product</button>',
        '<button type="button" onclick="document.body.dataset.alternativeCreates=1">บันทึกและสร้างต่อ</button>'
        + replacement)
    html += '<form id="other-form" onsubmit="event.preventDefault();this.dataset.submits=1"></form>'
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=WRITE_URL)
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many('CabalM TH', [dict(REQUEST)], {}))[0]
    assert (result['name'], result['slug'], result['group'], result['saved'], result['made_id']) == (
        'สินค้าที่ขอ', 'keep-product', 'keep-group', False, None)
    assert 'สร้าง Product' in result['error']
    assert snapshots[0]['submits'] == ['0', '0']
    assert snapshots[0]['outsideCreates'] == '0' and snapshots[0]['alternativeCreates'] == '0'
    assert traffic == [('GET', CREATE_URLS[0])]


def test_product_preview_never_activates_create(monkeypatch):
    traffic, snapshots = routed_runner_browser(
        monkeypatch, create_html(), preview_urls=CREATE_URLS, synthetic_write_url=WRITE_URL)
    result = asyncio.run(ProductBuilder(lambda *_: None).run('CabalM TH', dict(REQUEST), {}))
    assert result['missing'] == []
    assert snapshots[0]['submits'] == ['0'] and snapshots[0]['outsideCreates'] == '0'
    assert traffic == [('GET', CREATE_URLS[0])]


def test_product_no_write_response_does_not_report_saved_or_retry(monkeypatch):
    html = create_html().replace("fetch('%s?owner=form',{method:'POST'})" % WRITE_URL, '')
    traffic, snapshots = routed_runner_browser(monkeypatch, html, preview_urls=CREATE_URLS)
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many('CabalM TH', [dict(REQUEST)], {}))[0]
    assert (result['slug'], result['group'], result['saved'], result['made_id']) == (
        'keep-product', 'keep-group', False, None)
    assert snapshots[0]['submits'] == ['1'] and snapshots[0]['outsideCreates'] == '0'
    assert traffic == [('GET', CREATE_URLS[0])]


def after_bundles_script(action):
    return '''<script>
      const ready=new MutationObserver(()=>{
        if(document.querySelectorAll('main form [data-fixture-bundle]').length===2){
          ready.disconnect();setTimeout(()=>{ACTION},250);
        }
      });ready.observe(document.querySelector('[data-selected-bundles]'),{childList:true});
    </script>'''.replace('ACTION', action)


@pytest.mark.parametrize('fault', ('lazy', 'changed-type', 'duplicate-anchor', 'wrong-anchor-type'))
def test_product_create_rechecks_after_readiness(monkeypatch, fault):
    html = create_html().replace('<button type="submit">สร้าง Product</button>',
        '<button type="submit" disabled data-create-target>สร้าง Product</button>')
    action = "const b=document.querySelector('[data-create-target]');b.disabled=false;"
    action += {
        'lazy': '',
        'changed-type': "b.type='button';",
        'duplicate-anchor': "document.querySelector('main form').insertAdjacentHTML('beforeend','<input id=th_name>');",
        'wrong-anchor-type': "document.querySelector('main form [id=th_name]').type='number';",
    }[fault]
    html += after_bundles_script(action)
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=WRITE_URL)
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many('CabalM TH', [dict(REQUEST)], {}))[0]
    assert result['saved'] is (fault == 'lazy')
    assert snapshots[0]['submits'] == (['1'] if fault == 'lazy' else ['0'])
    assert snapshots[0]['outsideCreates'] == '0'
    if fault != 'lazy':
        assert 'Product' in result['error'] and result['made_id'] is None
        assert traffic == [('GET', CREATE_URLS[0])]


def test_product_create_rechecks_owner_after_actionability(monkeypatch):
    html = create_html().replace('<button type="submit">สร้าง Product</button>',
        '<button type="submit" data-create-target style="position:fixed;top:0;right:0;width:180px;height:60px">สร้าง Product</button>')
    html += '''<form id="other-form" onsubmit="event.preventDefault();this.dataset.submits=1"></form>
      <div id="obstruction" style="position:fixed;top:0;right:0;width:190px;height:65px;z-index:9999"></div>'''
    html += after_bundles_script("document.querySelector('[data-create-target]').setAttribute('form','other-form');"
                                 "document.querySelector('#obstruction').remove();")
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=WRITE_URL)
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many('CabalM TH', [dict(REQUEST)], {}))[0]
    assert result['saved'] is False and result['made_id'] is None
    assert 'สร้าง Product' in result['error']
    assert snapshots[0]['submits'] == ['0', '0'] and snapshots[0]['outsideCreates'] == '0'
    assert traffic == [('GET', CREATE_URLS[0])]


@pytest.mark.parametrize('game', GAMES)
@pytest.mark.parametrize('fault', ('hidden-button', 'hidden-form', 'visibility-hidden', 'visibility-collapse'))
def test_product_create_stops_if_visibility_changes_after_actionability(monkeypatch, game, fault):
    """A passed trial is not permission to submit a control that rendering then hides."""
    from playwright.async_api import Locator

    real_click = Locator.click
    changed_dom = []

    async def click_with_render_change(locator, *args, **kwargs):
        result = await real_click(locator, *args, **kwargs)
        if kwargs.get('trial') and await locator.evaluate(
                "(b) => b.tagName==='BUTTON' && b.type==='submit' && b.textContent.trim()==='สร้าง Product'"):
            changed_dom.append(await locator.evaluate("""(b, fault) => {
                if(fault==='hidden-button') b.hidden=true;
                else if(fault==='hidden-form') b.closest('form').hidden=true;
                else b.style.visibility=fault==='visibility-hidden'?'hidden':'collapse';
                return !b.getClientRects().length ||
                    ['hidden','collapse'].includes(getComputedStyle(b).visibility);
            }""", fault))
        return result

    monkeypatch.setattr(Locator, 'click', click_with_render_change)
    endpoint = WRITE_URLS[game]
    traffic, snapshots = routed_runner_browser(
        monkeypatch, create_html(endpoint), preview_urls=CREATE_URLS,
        synthetic_write_url=endpoint, context_options={'service_workers': 'block'})
    result = asyncio.run(ProductBuilder(lambda *_: None).run_many(game, [dict(REQUEST)], {}))[0]
    assert changed_dom == [True]  # The real DOM changed after a successful real trial.
    assert (result['name'], result['slug'], result['group'], result['saved'], result['made_id']) == (
        'สินค้าที่ขอ', 'keep-product', 'keep-group', False, None)
    assert 'สร้าง Product' in (result['error'] or '')
    assert snapshots[0]['submits'] == ['0'] and snapshots[0]['outsideCreates'] == '0'
    assert traffic == [('GET', ProductBuilder(lambda *_: None).create_url(game))]
