"""Public Product filling against network-isolated, audited-shape forms."""
import asyncio

import pytest
from playwright.async_api import async_playwright

from web.aztek_locator import AztekLocatorError
from web.product_runner import ProductBuilder
from test_web_itemcode_id_first import routed_runner_browser


CREATE_URL = 'https://aztek-tools-v2.combo-interactive.com/combo/cabalm/shop/products/create'
CREATE_URLS = (
    CREATE_URL,
    'https://aztek-tools-v2.combo-interactive.com/combo/cabalmsea/shop/products/create',
    'https://aztek-tools-v2.combo-interactive.com/combo/cabalpc/shop/products/create',
    'https://aztek-tools-v2.combo-interactive.com/combo/cabalpcsea/shop/products/create',
)
BASIC_DISPLAY = '''<button id="is_enabled" type="button" role="switch" aria-checked="false"
 onclick="this.setAttribute('aria-checked',this.getAttribute('aria-checked')==='true'?'false':'true')"></button>
<button id="is_test_mode" type="button" role="switch" aria-checked="true"
 onclick="this.setAttribute('aria-checked',this.getAttribute('aria-checked')==='true'?'false':'true')"></button>
<button id="is_hidden" type="button" role="switch" aria-checked="false"
 onclick="this.setAttribute('aria-checked',this.getAttribute('aria-checked')==='true'?'false':'true')"></button>
<input id="position" name="changed-position" type="number" value="0">'''
HEADER_HTML = '''<aside>
  <input id="th_name" value="outside-th"><input id="en_name" value="outside-en">
</aside><main><h1>เปลี่ยนข้อความหัวข้อแล้ว</h1><form
  onsubmit="event.preventDefault();this.dataset.submits='1'">
  <input name="th_name" data-decoy value="keep-th">
  <input name="en_name" data-decoy value="keep-en">
  <section><div><input id="en_name" name="renamed-en"></div></section>
  <div><input id="th_name" name="renamed-th"></div>
  <input name="position" type="number" value="0">
  <button type="submit">สร้าง Product</button>
</form></main>'''
HEADER_HTML = HEADER_HTML.replace('<input name="position" type="number" value="0">', BASIC_DISPLAY)
SPEC = {'name_th': 'สินค้าที่ขอ', 'name_en': 'Requested product'}


def exercise_form(html=HEADER_HTML, *, url=CREATE_URL, spec=None):
    async def exercise():
        async with async_playwright() as driver:
            browser = await driver.chromium.launch(headless=True)
            context = await browser.new_context(service_workers='block')
            unexpected = []

            async def serve(route):
                if route.request.method == 'GET' and route.request.url == url:
                    await route.fulfill(body=html, content_type='text/html; charset=utf-8')
                else:
                    unexpected.append((route.request.method, route.request.url))
                    await route.abort()

            await context.route('**/*', serve)
            page = await context.new_page()
            await page.goto(url)
            error = None
            try:
                missing = await ProductBuilder(lambda *_: None).fill_form(
                    page, dict(SPEC if spec is None else spec))
            except Exception as caught:
                error, missing = caught, None
            values = await page.evaluate('''async () => ({
                names: ['th_name','en_name'].map(id=>document.querySelector('main form [id="'+id+'"]')?.value),
                decoys: [...document.querySelectorAll('[data-decoy]')].map(e=>e.value),
                outside: [...document.querySelectorAll('aside input')].map(e=>e.value),
                chosenOptions: [...document.querySelectorAll('main form [data-chosen]')].map(e=>e.dataset.chosen),
                prices: [...document.querySelectorAll('main form input[name^="prices."]')].map(e=>[e.name,e.value]),
                display: ['is_enabled','is_test_mode','is_hidden','position'].map(id=>{
                    const e=document.querySelector('main form [id="'+id+'"]');
                    return e?.getAttribute('role')==='switch' ? e.getAttribute('aria-checked') : e?.value;
                }),
                displayDecoys: [...document.querySelectorAll('[data-display-decoy]')].map(e=>
                    e.getAttribute('role')==='switch' ? e.getAttribute('aria-checked') : e.value),
                dates: ['show_at','hide_at','limit_reset_at'].map(id=>document.querySelector('main form [id="'+id+'"]')?.textContent),
                numbers: ['limit_per','limit_reset_interval_days'].map(id=>document.querySelector('main form [id="'+id+'"]')?.value),
                limitMode: document.querySelector('main form [id="purchase_limit_type"]')?.textContent,
                limitDecoys: [...document.querySelectorAll('[data-limit-decoy]')].map(e=>e.value),
                dateDecoyClicks: document.body.dataset.dateDecoyClicks || '0',
                calendarDecoys: [...document.querySelectorAll('[data-calendar-decoy]')].map(e=>e.value),
                mediaFiles: Object.fromEntries(await Promise.all([...document.querySelectorAll('[data-fixture-slot]')].map(async e=>[
                    e.dataset.fixtureSlot, await Promise.all([...e.files].map(async f=>({name:f.name,type:f.type,size:f.size,
                        bytes:[...new Uint8Array(await f.arrayBuffer())]})))
                ]))),
                editorTexts: Object.fromEntries([...document.querySelectorAll('[data-fixture-editor]')].map(e=>[
                    e.dataset.fixtureEditor,e.contentDocument?.body?.innerText])),
                bundles: [...document.querySelectorAll('main form [data-fixture-bundle]')].map(e=>({
                    id:e.dataset.fixtureBundle,primary:e.querySelector('[role="checkbox"]')?.getAttribute('aria-checked')})),
                bundleDecoyChanges: document.body.dataset.bundleDecoyChanges || '0',
                submits: [...document.querySelectorAll('form')].map(e=>e.dataset.submits || '0')
            })''')
            await browser.close()
            assert unexpected == []
            return missing, error, values
    return asyncio.run(exercise())


@pytest.mark.parametrize('url', CREATE_URLS)
def test_product_names_use_verified_ids_in_own_form_not_name_decoys(url):
    # Catches a regression to name/label/first-match or page-wide ID lookup.
    missing, error, values = exercise_form(url=url)
    assert error is None
    assert values['names'] == ['สินค้าที่ขอ', 'Requested product']
    assert values['decoys'] == ['keep-th', 'keep-en']
    assert values['outside'] == ['outside-th', 'outside-en']
    assert values['submits'] == ['0']
    assert missing == ['หมวดหมู่', 'สกุลเงิน', 'วันเริ่มขาย', 'วันสิ้นสุด',
                       'ประเภทการจำกัด', 'Bundle']


def test_product_preview_readiness_uses_id_when_name_attribute_changes(monkeypatch):
    html = HEADER_HTML.replace('<input name="th_name" data-decoy value="keep-th">', '')
    html = html.replace('<input name="en_name" data-decoy value="keep-en">', '')
    traffic, snapshots = routed_runner_browser(monkeypatch, html, preview_urls=(CREATE_URL,))
    result = asyncio.run(ProductBuilder(lambda *_: None).run('CabalM TH', dict(SPEC), {}))
    assert result['kept_open'] is False
    assert result['url'] == CREATE_URL
    assert 'ชื่อ Product (ไทย)' not in result['missing']
    assert 'ชื่อ Product (อังกฤษ)' not in result['missing']
    assert snapshots[-1]['submits'] == ['0']
    assert traffic == [('GET', CREATE_URL)]


@pytest.mark.parametrize(('element_id', 'label'), [
    ('th_name', 'ชื่อ Product (ไทย)'), ('en_name', 'ชื่อ Product (อังกฤษ)'),
])
@pytest.mark.parametrize('failure', ['missing', 'duplicate', 'wrong-type'])
def test_product_broken_name_id_stops_without_fallback(element_id, label, failure):
    if failure == 'missing':
        html = HEADER_HTML.replace('id="%s"' % element_id, 'data-removed-id="%s"' % element_id)
    elif failure == 'duplicate':
        html = HEADER_HTML.replace('</form>', '<input id="%s"></form>' % element_id)
    else:
        html = HEADER_HTML.replace('id="%s" name=' % element_id,
                                   'id="%s" type="number" name=' % element_id)
    missing, error, values = exercise_form(html)
    assert missing is None
    assert isinstance(error, AztekLocatorError)
    assert label in str(error)
    assert values['decoys'] == ['keep-th', 'keep-en']
    assert values['outside'] == ['outside-th', 'outside-en']
    assert values['submits'] == ['0']


def test_product_multiple_forms_stop_before_filling_either():
    html = HEADER_HTML.replace('</main>', '<form><input id="th_name"><input id="en_name"></form></main>')
    _missing, error, values = exercise_form(html)
    assert isinstance(error, AztekLocatorError)
    assert 'ฟอร์ม Product' in str(error)
    assert values['names'] == ['', '']
    assert values['decoys'] == ['keep-th', 'keep-en']
    assert values['submits'] == ['0', '0']


@pytest.mark.parametrize(('field', 'label'), [
    ('name_th', 'ชื่อ Product (ไทย)'), ('name_en', 'ชื่อ Product (อังกฤษ)'),
])
def test_product_empty_name_is_reported_through_public_form(field, label):
    spec = {**SPEC, field: ''}
    missing, error, _values = exercise_form(spec=spec)
    assert error is None
    assert label in missing


def test_product_waits_for_late_mounted_name_id():
    html = HEADER_HTML.replace('<input id="en_name" name="renamed-en">', '')
    html += '''<script>setTimeout(()=>{
      const input=document.createElement('input');input.id='en_name';
      document.querySelector('main form section div').append(input);
    },150);</script>'''
    _missing, error, values = exercise_form(html)
    assert error is None
    assert values['names'] == ['สินค้าที่ขอ', 'Requested product']
    assert values['decoys'] == ['keep-th', 'keep-en']


def test_product_create_queue_keeps_identity_when_name_contract_breaks(monkeypatch):
    html = HEADER_HTML.replace('id="en_name" name=', 'id="en_name" type="number" name=')
    traffic, snapshots = routed_runner_browser(monkeypatch, html, preview_urls=(CREATE_URL,))
    entries = asyncio.run(ProductBuilder(lambda *_: None).run_many(
        'CabalM TH', [{**SPEC, 'slug': 'keep-product', 'group': 'keep-group'}], {}))
    assert len(entries) == 1
    entry = entries[0]
    assert entry['saved'] is False and entry['made_id'] is None
    assert entry['name'] == 'สินค้าที่ขอ'
    assert entry['slug'] == 'keep-product' and entry['group'] == 'keep-group'
    assert 'ชื่อ Product (อังกฤษ)' in entry['error']
    assert snapshots[-1]['submits'] == ['0']
    assert traffic == [('GET', CREATE_URL)]
