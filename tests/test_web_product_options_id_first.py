"""Public Product option/catalog boundaries with all external traffic intercepted."""
import asyncio
from contextlib import asynccontextmanager

import pytest
from playwright.async_api import Locator, async_playwright

from web import product_runner
from web.aztek_locator import AztekLocatorError
from test_web_itemcode_id_first import routed_runner_browser
from test_web_product_id_first import BASIC_DISPLAY, exercise_form


CREATE_URL = 'https://aztek-tools-v2.combo-interactive.com/combo/cabalm/shop/products/create'
OPTIONS_HTML = r'''<aside>
  <input name="th_name" value="outside-name">
  <button type="button" role="combobox" data-slot="popover-trigger"
    onclick="openOptions(this,'wrong')">เลือก Category</button>
  <div><button type="button" role="combobox" data-slot="popover-trigger"
    onclick="openOptions(this,'wrong')">เลือกสกุลเงิน</button>
    <input name="prices.0.original_price" type="number" value="901">
    <input name="prices.0.price" type="number" value="902"></div>
</aside><main><form onsubmit="event.preventDefault();this.dataset.submits='1'">
  <section><header><h2>ข้อมูลทั่วไป</h2></header><div>
    <button type="button" role="combobox" data-slot="popover-trigger"
      onclick="openOptions(this,'categories')">หมวดหมู่ที่พร้อมแล้ว</button>
    <input id="th_name" name="changed-th"><input id="en_name" name="changed-en">
  </div></section>
  <section><header><h2>สกุลเงิน</h2>
    <button type="button" onclick="addPriceRow()">เพิ่มสกุลเงิน</button></header>
    <div data-price-rows></div>
  </section>
  <section><h2>จำกัดการซื้อ</h2><select>
    <option value="NONE">ไม่จำกัด</option><option value="PLAYER">PLAYER</option>
  </select></section>
  <input name="position" type="number" value="0">
  <button type="submit">สร้าง Product</button>
</form></main><script>
const catalogs={
  categories:[['category-8','Main Shop - Highlight'],['category-9','Bonus Shop - General']],
  currencies:[['wallet:91','cabal-wallet-point - Wallet Point'],['gem:92','cabal-force-gem - Force Gem']],
  wrong:[['wrong-id','Wrong outside catalog']]
};
function openOptions(trigger,kind){
  const dialog=document.createElement('div');dialog.setAttribute('role','dialog');
  dialog.dataset.slot='popover-content';dialog.id='runtime-options-'+kind;
  trigger.setAttribute('aria-controls',dialog.id);trigger.setAttribute('aria-expanded','true');
  const search=document.createElement('input');search.setAttribute('role','combobox');dialog.append(search);
  for(const [id,text] of catalogs[kind]){
    const option=document.createElement('div');option.setAttribute('role','option');
    option.setAttribute('data-value',text+'\u0000'+id);option.textContent=text;
    option.onclick=()=>{trigger.dataset.chosen=id;trigger.textContent=text;dialog.remove();};
    dialog.append(option);
  }
  dialog.onkeydown=e=>{if(e.key==='Escape'){trigger.setAttribute('aria-expanded','false');dialog.remove();}};
  document.body.append(dialog);search.focus();
}
function addPriceRow(){
  const rows=document.querySelector('[data-price-rows]');const n=rows.children.length;
  const row=document.createElement('div');row.innerHTML=
    '<p>สกุลเงินที่ '+(n+1)+'</p><button type="button" role="combobox" data-slot="popover-trigger" '+
    'onclick="openOptions(this,\'currencies\')">เลือกสกุลเงิน</button>'+
    '<div><input name="prices.'+n+'.original_price" type="number" value="1"></div>'+
    '<div><input name="prices.'+n+'.price" type="number" value="1"></div>';
  rows.append(row);
}
</script>'''
OPTIONS_HTML = OPTIONS_HTML.replace('<input name="position" type="number" value="0">', BASIC_DISPLAY)


def route_product_fetch(monkeypatch, html=OPTIONS_HTML):
    traffic, snapshots = [], []

    @asynccontextmanager
    async def intercepted_playwright():
        async with async_playwright() as driver:
            real_launch = driver.chromium.launch

            async def launch(**kwargs):
                browser = await real_launch(**kwargs)
                real_new_context = browser.new_context

                async def new_context(**kwargs):
                    context = await real_new_context(**kwargs)

                    async def serve(route):
                        traffic.append((route.request.method, route.request.url))
                        if route.request.method == 'GET' and route.request.url == CREATE_URL:
                            await route.fulfill(body=html, content_type='text/html; charset=utf-8')
                        else:
                            await route.abort()

                    await context.route('**/*', serve)
                    real_close = context.close

                    async def close():
                        for page in context.pages:
                            if not page.is_closed():
                                snapshots.append(await page.evaluate('''() => ({
                                  priceRows: document.querySelector('[data-price-rows]').children.length,
                                  outsidePrices: [...document.querySelectorAll('aside input[type="number"]')].map(e=>e.value),
                                  dialogs: document.querySelectorAll('[role="dialog"]').length,
                                  chosen: [...document.querySelectorAll('[data-chosen]')].map(e=>e.dataset.chosen),
                                  submits: [...document.querySelectorAll('form')].map(e=>e.dataset.submits||'0')
                                })'''))
                        await real_close()

                    context.close = close
                    return context

                browser.new_context = new_context
                return browser

            driver.chromium.launch = launch
            yield driver

    monkeypatch.setattr(product_runner, 'async_playwright', intercepted_playwright)
    return traffic, snapshots


def test_product_fetch_uses_own_sections_and_preserves_opaque_catalog_ids(monkeypatch):
    traffic, snapshots = route_product_fetch(monkeypatch)
    options = asyncio.run(product_runner.fetch_options('CabalM TH', {}, ['categories', 'currencies']))
    assert options == {
        'categories': [
            {'id': 'category-8', 'slug': '', 'label': 'Main Shop - Highlight'},
            {'id': 'category-9', 'slug': '', 'label': 'Bonus Shop - General'},
        ],
        'currencies': [
            {'id': 'wallet:91', 'slug': 'cabal-wallet-point', 'label': 'Wallet Point'},
            {'id': 'gem:92', 'slug': 'cabal-force-gem', 'label': 'Force Gem'},
        ],
    }
    assert snapshots[-1] == {'priceRows': 1, 'outsidePrices': ['901', '902'],
                             'dialogs': 0, 'chosen': [], 'submits': ['0']}
    assert traffic == [('GET', CREATE_URL)]


def test_product_fetch_rejects_ambiguous_open_popovers(monkeypatch):
    html = OPTIONS_HTML.replace('<main>', '''<div role="dialog" data-slot="popover-content">
      <div role="option" data-unrelated-option>Unrelated</div></div><main>''')
    html = html.replace('<script>', '<script>document.querySelector("[data-unrelated-option]").setAttribute("data-value","Unrelated\\u0000outside-id");')
    traffic, snapshots = route_product_fetch(monkeypatch, html)
    with pytest.raises(AztekLocatorError, match='ตัวเลือก Product'):
        asyncio.run(product_runner.fetch_options('CabalM TH', {}, ['categories']))
    assert snapshots[-1]['chosen'] == []
    assert snapshots[-1]['submits'] == ['0']
    assert traffic == [('GET', CREATE_URL)]


@pytest.mark.parametrize('failure', ['missing-id', 'duplicate-id', 'malformed-value'])
def test_product_fetch_rejects_untrustworthy_option_identity(monkeypatch, failure):
    if failure == 'missing-id':
        html = OPTIONS_HTML + "<script>catalogs.categories.push(['','Missing identity']);</script>"
    elif failure == 'duplicate-id':
        html = OPTIONS_HTML + "<script>catalogs.categories.push(['category-8','Duplicate label']);</script>"
    else:
        html = OPTIONS_HTML.replace(r"text+'\u0000'+id", r"text+'\u0000unexpected\u0000'+id")
    traffic, snapshots = route_product_fetch(monkeypatch, html)
    with pytest.raises(AztekLocatorError, match='ค่าตัวเลือก Product'):
        asyncio.run(product_runner.fetch_options('CabalM TH', {}, ['categories']))
    assert snapshots[-1]['chosen'] == []
    assert snapshots[-1]['submits'] == ['0']
    assert traffic == [('GET', CREATE_URL)]


def test_product_fetch_waits_for_late_category_trigger(monkeypatch):
    html = OPTIONS_HTML.replace('onclick="openOptions(this,\'categories\')"',
                                'data-late-category onclick="openOptions(this,\'categories\')"')
    html += '''<script>const trigger=document.querySelector('[data-late-category]');
      const parent=trigger.parentElement;trigger.remove();setTimeout(()=>parent.append(trigger),150);</script>'''
    traffic, snapshots = route_product_fetch(monkeypatch, html)
    options = asyncio.run(product_runner.fetch_options('CabalM TH', {}, ['categories']))
    assert options['categories'] == [
        {'id': 'category-8', 'slug': '', 'label': 'Main Shop - Highlight'},
        {'id': 'category-9', 'slug': '', 'label': 'Bonus Shop - General'},
    ]
    assert snapshots[-1]['submits'] == ['0']
    assert snapshots[-1]['dialogs'] == 0
    assert traffic == [('GET', CREATE_URL)]


def test_product_fills_exact_catalog_id_and_price_only_in_own_row():
    html = OPTIONS_HTML.replace("openOptions(this,'wrong')\">เลือก Category", "openOptions(this,'categories')\">เลือก Category")
    html = html.replace("openOptions(this,'wrong')\">เลือกสกุลเงิน", "openOptions(this,'currencies')\">เลือกสกุลเงิน")
    html += '''<script>
      catalogs.categories.unshift(['prefix-category-8','Wrong suffix category']);
      catalogs.currencies.unshift(['prefix-wallet:91','wrong-suffix-wallet - Wrong wallet']);
    </script>'''
    missing, error, values = exercise_form(html, spec={
        'name_th': 'สินค้า', 'name_en': 'Product', 'category_id': 'category-8',
        'prices': [{'currency_id': 'wallet:91', 'original_price': 100, 'price': 66}],
    })
    assert error is None
    assert values['chosenOptions'] == ['category-8', 'wallet:91']
    assert values['prices'] == [['prices.0.original_price', '100'], ['prices.0.price', '66']]
    assert values['outside'] == ['outside-name', '901', '902']
    assert values['submits'] == ['0']
    assert missing == ['วันเริ่มขาย', 'วันสิ้นสุด', 'ประเภทการจำกัด', 'Bundle']


def test_product_option_readback_mismatch_reports_control_and_stops():
    html = OPTIONS_HTML.replace('trigger.textContent=text;dialog.remove();',
                                "trigger.textContent='Wrong selected value';dialog.remove();")
    _missing, error, values = exercise_form(html, spec={
        'name_th': 'สินค้า', 'name_en': 'Product', 'category_id': 'category-8',
    })
    assert isinstance(error, AztekLocatorError)
    assert 'ตัวเลือก Product' in str(error)
    assert values['prices'] == []
    assert values['submits'] == ['0']


@pytest.mark.parametrize('kind', ['category', 'currency'])
@pytest.mark.parametrize('hidden_style', ['display', 'visibility'])
def test_product_option_hidden_after_actionability_stops_without_selecting(monkeypatch, kind, hidden_style):
    # Keep Playwright's real actionability checks, then reproduce a DOM update
    # between the await and the runner's atomic option activation. Removing the
    # final visibility guard would select this now-hidden option again.
    real_click = Locator.click
    mutation_applied = False
    wanted = 'category-8' if kind == 'category' else 'wallet:91'

    async def click_then_hide_option(locator, *args, **kwargs):
        nonlocal mutation_applied
        result = await real_click(locator, *args, **kwargs)
        if (kwargs.get('trial') and await locator.get_attribute('role') == 'option'
                and (await locator.get_attribute('data-value') or '').endswith('\x00' + wanted)):
            await locator.evaluate('(node, style) => node.style.setProperty(style, '
                                   'style === "display" ? "none" : "hidden")', hidden_style)
            mutation_applied = True
        return result

    monkeypatch.setattr(Locator, 'click', click_then_hide_option)
    spec = {'name_th': 'สินค้า', 'name_en': 'Product'}
    if kind == 'category':
        spec['category_id'] = 'category-8'
    else:
        spec['prices'] = [{'currency_id': 'wallet:91', 'original_price': 100, 'price': 66}]
    _missing, error, values = exercise_form(OPTIONS_HTML, spec=spec)
    assert mutation_applied
    assert values['chosenOptions'] == []
    assert isinstance(error, AztekLocatorError)
    assert 'ตัวเลือก Product' in str(error)
    assert values['prices'] == ([] if kind == 'category' else [
        ['prices.0.original_price', '1'], ['prices.0.price', '1']])
    assert values['submits'] == ['0']


def test_product_prices_keep_currency_and_zero_after_rows_removed_and_reindexed():
    html = OPTIONS_HTML + '''<script>
      addPriceRow();addPriceRow();addPriceRow();
      const list=document.querySelector('[data-price-rows]');list.firstElementChild.remove();
      list.prepend(list.lastElementChild);
      [...list.children].forEach((row,i)=>{
        row.querySelector('[name$=".original_price"]').name='prices.'+i+'.original_price';
        row.querySelector('[name$=".price"]').name='prices.'+i+'.price';
      });
    </script>'''
    missing, error, values = exercise_form(html, spec={
        'name_th': 'สินค้า', 'name_en': 'Product', 'category_id': 'category-8',
        'prices': [
            {'currency_id': 'wallet:91', 'original_price': 100, 'price': 0},
            {'currency_id': 'gem:92', 'original_price': 55, 'price': 22},
        ],
    })
    assert error is None
    assert values['chosenOptions'] == ['category-8', 'wallet:91', 'gem:92']
    assert values['prices'] == [
        ['prices.0.original_price', '100'], ['prices.0.price', '0'],
        ['prices.1.original_price', '55'], ['prices.1.price', '22'],
    ]
    assert values['outside'] == ['outside-name', '901', '902']
    assert values['submits'] == ['0']
    assert missing == ['วันเริ่มขาย', 'วันสิ้นสุด', 'ประเภทการจำกัด', 'Bundle']


@pytest.mark.parametrize('failure', ['category-trigger', 'currency-trigger', 'price-type', 'duplicate-price', 'neighbor-row'])
def test_product_ambiguous_or_wrong_price_controls_stop_without_other_row(failure):
    if failure == 'category-trigger':
        html = OPTIONS_HTML.replace('<input id="th_name"', '''<button type="button" role="combobox"
          data-slot="popover-trigger">Duplicate Category</button><input id="th_name"''')
    elif failure == 'currency-trigger':
        html = OPTIONS_HTML.replace('rows.append(row);',
            "row.append(row.querySelector('button').cloneNode(true));rows.append(row);")
    elif failure == 'price-type':
        html = OPTIONS_HTML.replace('.original_price" type="number" value="1"',
                                    '.original_price" type="text" value="1"')
    elif failure == 'duplicate-price':
        html = OPTIONS_HTML.replace('rows.append(row);',
            "row.append(row.querySelector('input').cloneNode(true));rows.append(row);")
    else:
        html = OPTIONS_HTML + '''<script>addPriceRow();addPriceRow();
          document.querySelector('[data-price-rows] button').remove();</script>'''
    _missing, error, values = exercise_form(html, spec={
        'name_th': 'สินค้า', 'name_en': 'Product', 'category_id': 'category-8',
        'prices': [{'currency_id': 'wallet:91', 'original_price': 100, 'price': 66}],
    })
    assert isinstance(error, AztekLocatorError)
    assert values['outside'] == ['outside-name', '901', '902']
    assert all(value == '1' for _name, value in values['prices'])
    assert values['submits'] == ['0']


def test_product_queue_preserves_identity_on_currency_contract_failure(monkeypatch):
    html = OPTIONS_HTML.replace('rows.append(row);',
        "row.append(row.querySelector('button').cloneNode(true));rows.append(row);")
    traffic, snapshots = routed_runner_browser(monkeypatch, html, preview_urls=(CREATE_URL,))
    entries = asyncio.run(product_runner.ProductBuilder(lambda *_: None).run_many('CabalM TH', [{
        'name_th': 'สินค้า', 'name_en': 'Product', 'category_id': 'category-8',
        'slug': 'preserve-product', 'group': 'preserve-group',
        'prices': [{'currency_id': 'wallet:91', 'original_price': 100, 'price': 66}],
    }], {}))
    assert len(entries) == 1
    assert entries[0]['saved'] is False and entries[0]['made_id'] is None
    assert entries[0]['slug'] == 'preserve-product' and entries[0]['group'] == 'preserve-group'
    assert 'Currency' in entries[0]['error']
    assert snapshots[-1]['submits'] == ['0']
    assert traffic == [('GET', CREATE_URL)]
