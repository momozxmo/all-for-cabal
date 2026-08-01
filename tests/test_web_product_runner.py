# -*- coding: utf-8 -*-
"""Product live-form URL, option cleaning, and read-only API gates."""
import asyncio
import json

import pytest
from playwright.async_api import async_playwright
from sqlalchemy import select

from web import app as web_app
from web import aztek_form, itemcode_runner
from web import product_runner
from web.app import ProductRunRequest
from web.models import AuditLog


GAME = 'CabalM TH'


CUSTOM_PRODUCT_FORM = r'''
<label>หมวดหมู่</label>
<button type="button" role="combobox" data-slot="popover-trigger"
        data-kind="categories">เลือก Category</button>
<input name="th_name"><input name="en_name">
<button type="button" id="addCurrency">เพิ่มสกุลเงิน</button>
<div id="priceRows"></div>
<label>รูปแบบการจำกัดการซื้อ</label>
<select id="limitType">
  <option value="NONE">ไม่จำกัด</option>
  <option value="PLAYER">PLAYER</option>
  <option value="CHARACTER">CHARACTER</option>
</select>
<script>
window.chosen = {};
const liveOptions = {
  categories: [
    {id:'category-8', text:'Main Shop - Highlight'},
    {id:'category-9', text:'Bonus Shop - General - Bonus'}],
  currencies: [
    {id:'currency-91', text:'cabal-wallet-point - Wallet Point'},
    {id:'currency-92', text:'cabal-force-gem - Force Gem'}]
};
function openPicker(kind, trigger) {
  document.querySelector('[role="dialog"]')?.remove();
  const dialog = document.createElement('div');
  dialog.setAttribute('role', 'dialog');
  for (const row of liveOptions[kind]) {
    const option = document.createElement('div');
    option.setAttribute('role', 'option');
    option.setAttribute('data-value', `${row.text}\u0000${row.id}`);
    option.textContent = row.text;
    option.onclick = () => {
      window.chosen[kind] = row.id;
      trigger.textContent = row.text;
      dialog.remove();
    };
    dialog.appendChild(option);
  }
  document.body.appendChild(dialog);
}
document.querySelector('[data-kind="categories"]').onclick = event =>
  openPicker('categories', event.currentTarget);
document.querySelector('#addCurrency').onclick = () => {
  const index = document.querySelectorAll(
    'input[name$=".original_price"]').length;
  const row = document.createElement('div');
  row.innerHTML = `<button type="button" role="combobox"
    data-slot="popover-trigger" data-kind="currencies">เลือกสกุลเงิน</button>
    <input name="prices.${index}.original_price">
    <input name="prices.${index}.price">`;
  row.querySelector('[data-kind="currencies"]').onclick = event =>
    openPicker('currencies', event.currentTarget);
  document.querySelector('#priceRows').appendChild(row);
};
</script>
'''


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


def _product(**extra):
    spec = {
        'client_key': 'p1',
        'source_group_key': 'g1',
        'name_th': 'Orb Pack',
        'name_en': 'Orb Pack',
        'category_id': '12',
        'category_label': 'Highlight',
        'start_at': '2026-07-30 00:00:00',
        'end_at': '2026-08-30 07:59:00',
        'bundle_id': '223553',
        'prices': [{
            'currency_id': '91',
            'currency_slug': 'future-token',
            'currency_label': 'Future Token',
            'original_price': 6600,
            'price': 6600,
        }],
        'limit_type': 'PLAYER',
        'limit_quantity': '10',
        'limit_reset_interval_days': '',
        'limit_reset_at': '',
        'tags': ['SALE'],
    }
    spec.update(extra)
    return spec


def _run_products(client, products, *, do_save=False, files=None, game=GAME):
    payload = {'game': game, 'products': products, 'do_save': do_save}
    return client.post(
        '/api/products/run',
        data={'payload': json.dumps(payload, ensure_ascii=False)},
        files=files or [],
    )


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


def test_product_options_read_custom_popovers_not_purchase_limit_select():
    async def scenario():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.set_content(CUSTOM_PRODUCT_FORM)
                return await product_runner._harvest_product_options(
                    page, {'categories', 'currencies'})
            finally:
                await browser.close()

    assert asyncio.run(scenario()) == {
        'categories': [
            {'id': 'category-8', 'slug': '',
             'label': 'Main Shop - Highlight'},
            {'id': 'category-9', 'slug': '',
             'label': 'Bonus Shop - General - Bonus'},
        ],
        'currencies': [
            {'id': 'currency-91', 'slug': 'cabal-wallet-point',
             'label': 'Wallet Point'},
            {'id': 'currency-92', 'slug': 'cabal-force-gem',
             'label': 'Force Gem'},
        ],
    }


def test_product_builder_selects_custom_category_and_currency_ids():
    async def scenario():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.set_content(CUSTOM_PRODUCT_FORM)
                missing = []
                await product_runner.ProductBuilder(
                    lambda *_: None)._fill_general(page, {
                        'name_th': 'สินค้า',
                        'name_en': 'Product',
                        'category_id': 'category-8',
                    }, missing)
                await product_runner.ProductBuilder(
                    lambda *_: None)._fill_prices(page, {
                        'prices': [{
                            'currency_id': 'currency-91',
                            'original_price': 100,
                            'price': 66,
                        }],
                    }, missing)
                return await page.evaluate('window.chosen'), missing
            finally:
                await browser.close()

    chosen, missing = asyncio.run(scenario())
    assert chosen == {
        'categories': 'category-8',
        'currencies': 'currency-91',
    }
    assert missing == []


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


def test_product_run_defaults_to_preview():
    assert ProductRunRequest(game=GAME).do_save is False


def test_product_run_requires_authentication(anonymous_client):
    response = _run_products(anonymous_client, [_product()])
    assert response.status_code == 401


def test_product_preview_is_one_at_a_time_and_queue_cannot_be_empty(client):
    assert _run_products(client, []).status_code == 400
    response = _run_products(client, [_product(), _product(client_key='p2')])
    assert response.status_code == 400
    assert 'ทีละรายการ' in response.text


def test_product_unknown_game_and_invalid_fields_stop_before_pairing(client):
    assert _run_products(
        client, [_product()], game='Unknown Cabal').status_code == 400
    for changed in (
        {'name_th': ''}, {'name_en': ''}, {'category_id': ''},
        {'prices': []}, {'bundle_id': ''}, {'start_at': ''}, {'end_at': ''},
    ):
        response = _run_products(client, [_product(**changed)])
        assert response.status_code in (400, 422), (changed, response.text)


def test_valid_product_still_requires_paired_aztek_session(client):
    response = _run_products(client, [_product()])
    assert response.status_code == 409
    assert 'Aztek' in response.text


@pytest.mark.parametrize('changed', [
    {'end_at': '2026-07-29 23:59:59'},
    {'bundle_id': 'bundle-223553'},
    {'prices': [{
        'currency_id': '91', 'original_price': -1, 'price': 1,
    }]},
    {'prices': [{
        'currency_id': '91', 'original_price': 'not-a-number', 'price': 1,
    }]},
    {'limit_type': 'PLAYER', 'limit_quantity': '0'},
    {'position': 'left'},
])
def test_product_values_are_validated_before_browser(client, changed):
    response = _run_products(client, [_product(**changed)])
    assert response.status_code in (400, 422), response.text


def test_product_rejects_duplicate_currency_ids(client):
    price = {
        'currency_id': '91', 'original_price': 100, 'price': 80,
    }
    response = _run_products(client, [_product(prices=[price, price])])
    assert response.status_code == 400
    assert 'Currency' in response.text


def test_product_images_reject_unknown_type_size_and_client(
        client, monkeypatch):
    bad_type = _run_products(client, [_product()], files=[(
        'image__p1__thumb_th',
        ('thumb.txt', b'not image', 'text/plain'),
    )])
    assert bad_type.status_code == 400

    monkeypatch.setattr(web_app, 'MAX_PRODUCT_IMAGE_BYTES', 4)
    too_large = _run_products(client, [_product()], files=[(
        'image__p1__thumb_th',
        ('thumb.png', b'12345', 'image/png'),
    )])
    assert too_large.status_code == 400

    unknown = _run_products(client, [_product()], files=[(
        'image__other__thumb_th',
        ('thumb.png', b'1234', 'image/png'),
    )])
    assert unknown.status_code == 400


def test_product_preview_calls_fill_only_and_returns_client_key(
        client, monkeypatch):
    _connect_aztek(client)
    calls = []

    class Builder:
        def __init__(self, on_log):
            self.on_log = on_log

        async def run(self, **kwargs):
            calls.append(('run', kwargs))
            return {
                'missing': [], 'kept_open': False, 'screenshot': None,
            }

        async def run_many(self, **kwargs):
            raise AssertionError('preview must not create')

    monkeypatch.setattr(product_runner, 'ProductBuilder', Builder)
    response = _run_products(client, [_product()])

    assert response.status_code == 200, response.text
    assert [kind for kind, _kwargs in calls] == ['run']
    body = response.json()
    assert body['created'] == 0
    assert body['results'][0]['client_key'] == 'p1'
    assert body['results'][0]['made_id'] is None


def test_product_create_keeps_per_entry_results_and_audit_has_no_payload_bytes(
        client, monkeypatch, test_database):
    _connect_aztek(client)
    calls = []

    class Builder:
        def __init__(self, on_log):
            self.on_log = on_log

        async def run_many(self, **kwargs):
            calls.append(kwargs)
            return [
                {'name': 'Orb Pack', 'slug': '', 'group': 'g1',
                 'saved': True, 'made_id': '501', 'missing': [],
                 'error': None},
                {'name': 'Second', 'slug': '', 'group': 'g2',
                 'saved': False, 'made_id': None, 'missing': [],
                 'error': 'live form changed'},
            ]

    monkeypatch.setattr(product_runner, 'ProductBuilder', Builder)
    products = [_product(), _product(
        client_key='p2', source_group_key='g2',
        name_th='Second', name_en='Second')]
    response = _run_products(
        client, products, do_save=True, files=[(
            'image__p1__thumb_th',
            ('thumb.png', b'pixels', 'image/png'),
        )])

    assert response.status_code == 200, response.text
    assert len(calls) == 1
    assert calls[0]['specs'][0]['images']['thumbnail_th']['bytes'] == b'pixels'
    body = response.json()
    assert (body['created'], body['planned']) == (1, 2)
    assert [row['client_key'] for row in body['results']] == ['p1', 'p2']
    assert body['results'][0]['made_id'] == '501'
    with test_database.session() as db:
        summaries = [row.summary or '' for row in db.scalars(
            select(AuditLog).where(AuditLog.action == 'product.create'))]
    assert summaries
    joined = '\n'.join(summaries)
    assert 'Orb Pack' in joined and '501' in joined
    assert 'pixels' not in joined
    assert 'future-token' not in joined


class _Locator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    @property
    def first(self):
        return self

    @property
    def content_frame(self):
        return self

    def locator(self, selector):
        return _Locator(self.page, '%s >> %s' % (self.selector, selector))

    def filter(self, **kwargs):
        return self

    def nth(self, _index):
        return self

    async def count(self):
        if 'data-slot="popover-trigger"' in self.selector:
            return 0
        return 1

    async def wait_for(self, **kwargs):
        return None

    async def fill(self, value):
        self.page.fills.append((self.selector, str(value)))

    async def select_option(self, **kwargs):
        self.page.selects.append((self.selector, kwargs))

    async def set_input_files(self, payload):
        self.page.files.append((self.selector, payload))

    async def click(self, **kwargs):
        self.page.clicks.append(self.selector)


class _Page:
    def __init__(self):
        self.fills = []
        self.selects = []
        self.files = []
        self.clicks = []

    def locator(self, selector):
        return _Locator(self, selector)

    def get_by_text(self, text, **_kwargs):
        return _Locator(self, text)

    async def wait_for_timeout(self, _ms):
        return None


def _builder():
    return product_runner.ProductBuilder(lambda *_: None)


def test_activity_builder_uses_an_overridable_create_url():
    builder = _builder()
    assert builder.create_url(GAME).endswith('/shop/products/create')
    assert itemcode_runner.ItemCodeBuilder(
        lambda *_: None).create_url(GAME).endswith('/itemcodes/create')


def test_select_after_label_uses_the_hidden_select_value():
    page = _Page()
    assert asyncio.run(aztek_form.select_after_label(
        page, 'หมวดหมู่', '12')) is True
    assert page.selects == [(
        'xpath=//label[contains(normalize-space(.),"หมวดหมู่")]'
        '/following::select[1]',
        {'value': '12'},
    )]


def test_product_general_uses_names_and_fetched_category_id(monkeypatch):
    page = _Page()
    fills = []
    selects = []

    async def fake_fill(_page, selector, value, *_args, **_kwargs):
        fills.append((selector, value))
        return True

    async def fake_select(_page, label, value, *_args, **_kwargs):
        selects.append((label, value))
        return True

    monkeypatch.setattr(aztek_form, 'fill', fake_fill)
    monkeypatch.setattr(aztek_form, 'select_after_label', fake_select)
    missing = []
    asyncio.run(_builder()._fill_general(page, {
        'name_th': 'สินค้า', 'name_en': 'Product', 'category_id': '12',
    }, missing))

    assert fills == [
        ('input[name="th_name"]', 'สินค้า'),
        ('input[name="en_name"]', 'Product'),
    ]
    assert selects == [('หมวดหมู่', '12')]
    assert missing == []


def test_product_price_row_is_scoped_and_keeps_both_prices(monkeypatch):
    page = _Page()
    fills = []

    async def fake_fill(_page, selector, value, *_args, **_kwargs):
        fills.append((selector, value))
        return True

    monkeypatch.setattr(aztek_form, 'fill', fake_fill)
    missing = []
    asyncio.run(_builder()._fill_prices(page, {
        'prices': [{
            'currency_id': '91',
            'original_price': 100,
            'price': 66,
        }],
    }, missing))

    assert page.selects == [(
        'input[name="prices.0.original_price"]'
        ' >> xpath=ancestor::*[.//select][1] >> select',
        {'value': '91'},
    )]
    assert fills == [
        ('input[name="prices.0.original_price"]', 100),
        ('input[name="prices.0.price"]', 66),
    ]
    assert missing == []


def test_product_images_are_uploaded_only_from_memory_payloads():
    page = _Page()
    images = {
        slot: {
            'name': '%s.png' % slot,
            'content_type': 'image/png',
            'bytes': b'pixels',
        }
        for slot in ('thumbnail_th', 'banner_th',
                     'thumbnail_en', 'banner_en')
    }
    missing = []
    asyncio.run(_builder()._fill_images(
        page, {'images': images}, missing))

    assert [selector for selector, _payload in page.files] == [
        'input[name="thumbnail_th"]',
        'input[name="banner_th"]',
        'input[name="thumbnail_en"]',
        'input[name="banner_en"]',
    ]
    assert all(payload['buffer'] == b'pixels'
               for _selector, payload in page.files)


def test_product_details_fill_only_nonempty_languages():
    builder = _builder()
    calls = []

    async def record(_page, language, value):
        calls.append((language, value))
        return True

    builder._fill_rich_text = record
    asyncio.run(builder._fill_details(_Page(), {
        'details_th': '',
        'details_en': 'English details',
    }))
    assert calls == [('en', 'English details')]


def test_product_display_dates_limit_tags_and_bundle_use_stable_helpers(
        monkeypatch):
    page = _Page()
    switches = []
    dates = []
    selects = []
    bundles = []
    fills = []

    async def fake_switch(_page, label, value, *_args, **_kwargs):
        switches.append((label, value))
        return True

    async def fake_datetime(_page, _trigger, value, *_args, **kwargs):
        dates.append((kwargs.get('label', ''), value))
        return True

    async def fake_select(_page, label, value, *_args, **_kwargs):
        selects.append((label, value))
        return True

    async def fake_bundle(_page, _scope, value, *_args, **_kwargs):
        bundles.append(value)
        return True

    async def fake_fill(_page, selector, value, *_args, **_kwargs):
        fills.append((selector, value))
        return True

    monkeypatch.setattr(aztek_form, 'set_switch', fake_switch)
    monkeypatch.setattr(aztek_form, 'set_datetime', fake_datetime)
    monkeypatch.setattr(aztek_form, 'select_after_label', fake_select)
    monkeypatch.setattr(aztek_form, 'pick_bundle', fake_bundle)
    monkeypatch.setattr(aztek_form, 'fill', fake_fill)
    builder = _builder()
    missing = []
    spec = {
        'is_enabled': True, 'is_test_mode': False, 'is_hidden': True,
        'position': '3',
        'start_at': '2026-07-30 00:00:00',
        'end_at': '2026-08-30 07:59:00',
        'limit_type': 'PLAYER', 'limit_quantity': '10',
        'limit_reset_interval_days': '7',
        'limit_reset_at': '2026-07-31 09:15:00',
        'tags': ['SALE', 'LIMITED'], 'bundle_id': '223553',
    }
    asyncio.run(builder._fill_display(page, spec, missing))
    asyncio.run(builder._fill_limit(page, spec, missing))
    asyncio.run(builder._fill_tags(page, spec))
    asyncio.run(builder._fill_bundle(page, spec, missing))

    assert switches[:3] == [
        ('เปิดใช้งาน', True), ('โหมดทดสอบ', False), ('ซ่อน', True)]
    assert ('วันเริ่มขาย', spec['start_at']) in dates
    assert ('วันสิ้นสุด', spec['end_at']) in dates
    assert ('ประเภทการจำกัด', 'PLAYER') in selects
    assert bundles == ['223553']
    assert 'SALE' in page.clicks and 'LIMITED' in page.clicks
    assert ('input[name="position"]', '3') in fills
    assert missing == []


@pytest.mark.parametrize('field, label', [
    ('name_th', 'ชื่อ Product (ไทย)'),
    ('name_en', 'ชื่อ Product (อังกฤษ)'),
    ('category_id', 'หมวดหมู่'),
    ('prices', 'สกุลเงิน'),
    ('bundle_id', 'Bundle'),
    ('start_at', 'วันเริ่มขาย'),
    ('end_at', 'วันสิ้นสุด'),
])
def test_missing_product_requirements_are_reported(
        field, label, monkeypatch):
    async def okay(*_args, **_kwargs):
        return True

    monkeypatch.setattr(aztek_form, 'fill', okay)
    monkeypatch.setattr(aztek_form, 'select_after_label', okay)
    monkeypatch.setattr(aztek_form, 'set_switch', okay)
    monkeypatch.setattr(aztek_form, 'set_datetime', okay)
    monkeypatch.setattr(aztek_form, 'pick_bundle', okay)
    spec = {
        'name_th': 'สินค้า', 'name_en': 'Product', 'category_id': '12',
        'prices': [{'currency_id': '91', 'original_price': 100, 'price': 66}],
        'bundle_id': '223553',
        'start_at': '2026-07-30 00:00:00',
        'end_at': '2026-08-30 07:59:00',
        'limit_type': 'UNLIMITED', 'tags': [],
    }
    spec[field] = [] if field == 'prices' else ''
    missing = asyncio.run(_builder().fill_form(_Page(), spec))
    assert label in missing
