# -*- coding: utf-8 -*-
"""Static and visible contracts for the Product operator page."""
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PRODUCTS = ROOT / 'web' / 'static' / 'products.html'
CONSOLE_JS = ROOT / 'web' / 'static' / 'console.js'


def _tool_page(browser):
    html = PRODUCTS.read_text(encoding='utf-8').replace(
        '<script src="/static/console.js"></script>',
        '<script>%s</script>' % CONSOLE_JS.read_text(encoding='utf-8'),
    )
    context = browser.new_context()
    page = context.new_page()
    page.route(
        'http://tool.test/products',
        lambda route: route.fulfill(
            status=200, content_type='text/html; charset=utf-8', body=html),
    )
    page.goto('http://tool.test/products', wait_until='domcontentloaded')
    page.wait_for_function("typeof addDrafts === 'function'")
    return page


def test_product_page_has_shared_workspace_queue_contract(client):
    html = PRODUCTS.read_text(encoding='utf-8')
    assert 'id="productQueue"' in html
    assert 'afc.productQueue.v1' in html
    assert '/api/workspaces/' in html
    assert 'href="/products"' in html
    assert client.get('/products').status_code == 200


def test_product_queue_loads_workspace_drafts_once_and_survives_reload():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.evaluate("""addDrafts([
          {source_group_key:'g1', source_sheet:'Promotion 15.7',
           name_th:'Orb Pack', name_en:'Orb Pack'}
        ], 'workspace-1')""")
        page.reload(wait_until='domcontentloaded')
        page.wait_for_function("typeof addDrafts === 'function'")
        assert page.evaluate("productQueue.items.length") == 1
        assert page.evaluate(
            "productQueue.items[0].source_group_key") == 'g1'
        page.evaluate("""addDrafts([
          {source_group_key:'g1', source_sheet:'Promotion 15.7',
           name_th:'Orb Pack', name_en:'Orb Pack'}
        ], 'workspace-1')""")
        assert page.evaluate("productQueue.items.length") == 1
        browser.close()


def test_future_currency_matches_fetched_data_without_a_catalog():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        matched = page.evaluate("""matchFetchedOption(
          ' Future Token ',
          [{id:'91', slug:'future-token', label:'Future Token'}]
        )""")
        assert matched == {
            'id': '91',
            'slug': 'future-token',
            'label': 'Future Token',
        }
        assert 'THB' not in page.content()
        assert 'Forcegem' not in page.content()
        browser.close()


def test_ambiguous_option_is_not_selected():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        assert page.evaluate("""matchFetchedOption(
          'coin',
          [{id:'1',slug:'coin',label:'Coin'},
           {id:'2',slug:'coin',label:'Coin'}]
        )""") is None
        browser.close()


def test_option_cache_is_separate_per_server_and_kind():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        keys = page.evaluate("""[
          optionCacheKey('CabalPC TH', 'currencies'),
          optionCacheKey('CabalPC TH', 'categories'),
          optionCacheKey('CabalPC SEA', 'currencies')
        ]""")
        assert len(set(keys)) == 3
        assert all(key.startswith('afc.productOptions.v1:') for key in keys)
        browser.close()


def test_cached_options_are_reused_and_refresh_calls_only_requested_kind():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.evaluate("""() => {
          const game = 'CabalPC TH';
          document.querySelector('#game').add(new Option(game, game));
          document.querySelector('#game').value = game;
          localStorage.setItem(optionCacheKey(game, 'currencies'),
            JSON.stringify({fetched_at:'2026-07-30T00:00:00.000Z',
              options:[{id:'1',slug:'cached',label:'Cached Coin'}]}));
        }""")
        calls = []

        def fulfill_options(route):
            calls.append(route.request.post_data_json)
            route.fulfill(
                status=200,
                content_type='application/json',
                body='{"options":{"currencies":['
                     '{"id":"2","slug":"fresh","label":"Fresh Coin"}]}}')

        page.route(
            '**/api/products/options',
            fulfill_options,
        )

        cached = page.evaluate(
            "() => ensureOptions('currencies').then(rows => rows[0].label)")
        assert cached == 'Cached Coin'
        assert calls == []
        fresh = page.evaluate(
            "() => ensureOptions('currencies', true)"
            ".then(rows => rows[0].label)")
        assert fresh == 'Fresh Coin'
        assert calls == [{
            'game': 'CabalPC TH',
            'kinds': ['currencies'],
        }]
        browser.close()


def test_refresh_failure_keeps_last_good_options_and_marks_warning():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.evaluate("""() => {
          const game = 'CabalPC TH';
          document.querySelector('#game').add(new Option(game, game));
          document.querySelector('#game').value = game;
          localStorage.setItem(optionCacheKey(game, 'categories'),
            JSON.stringify({fetched_at:'2026-07-30T00:00:00.000Z',
              options:[{id:'8',slug:'',label:'Last Good'}]}));
        }""")
        page.route(
            '**/api/products/options',
            lambda route: route.fulfill(
                status=502,
                content_type='application/json',
                body='{"detail":"temporary failure"}'),
        )
        label = page.evaluate(
            "() => ensureOptions('categories', true)"
            ".then(rows => rows[0].label)")
        assert label == 'Last Good'
        assert page.evaluate(
            "optionState.categories.warning.includes('temporary failure')")
        browser.close()


def test_unique_matches_fill_draft_and_unmatched_sources_remain_visible():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        result = page.evaluate("""() => {
          optionState.categories.options = [
            {id:'8',slug:'highlight',label:'Highlight'}];
          optionState.currencies.options = [
            {id:'91',slug:'future-token',label:'Future Token'}];
          const entry = {
            category_source:'Highlight', category_id:'',
            price_candidates:[
              {source_label:'Future Token',original_price:100,sale_price:66},
              {source_label:'Unknown Token',original_price:50,sale_price:50}],
            prices:[]
          };
          applyOptionMatches(entry);
          return entry;
        }""")
        assert result['category_id'] == '8'
        assert result['prices'] == [{
            'source_label': 'Future Token',
            'currency_id': '91',
            'currency_slug': 'future-token',
            'currency_label': 'Future Token',
            'original_price': 100,
            'price': 66,
        }]
        assert result['price_candidates'][1]['source_label'] == 'Unknown Token'
        browser.close()


def test_manual_selection_uses_only_fetched_option_ids():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.evaluate("""() => {
          optionState.categories.options = [
            {id:'1',slug:'coin-a',label:'Coin'},
            {id:'2',slug:'coin-b',label:'Coin'}];
          optionState.currencies.options = [
            {id:'11',slug:'coin-a',label:'Coin'},
            {id:'12',slug:'coin-b',label:'Coin'}];
          addDrafts([{
            source_group_key:'g1', name_th:'Pack', name_en:'Pack',
            category_source:'Coin', category_id:'',
            price_candidates:[
              {source_label:'Coin',original_price:100,sale_price:80}],
            prices:[]
          }], 'workspace-1');
        }""")

        page.locator('#categorySelect').select_option('2')
        page.locator('#priceMatches select').select_option('12')

        entry = page.evaluate("productQueue.current()")
        assert entry['category_id'] == '2'
        assert entry['category_slug'] == 'coin-b'
        assert entry['prices'][0]['currency_id'] == '12'
        assert entry['prices'][0]['currency_slug'] == 'coin-b'
        browser.close()


def test_product_editor_matches_aztek_columns_and_collapses():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.evaluate("""addDrafts([{
          source_group_key:'g1', name_th:'Pack', name_en:'Pack',
          price_candidates:[], prices:[]
        }], 'workspace-1')""")
        page.set_viewport_size({'width': 1500, 'height': 1000})
        desktop = page.evaluate("""() => {
          const box = key => document.querySelector(
            `[data-product-section="${key}"]`).getBoundingClientRect();
          const general = box('general'), display = box('display');
          return {generalRight: general.right, displayLeft: display.left};
        }""")
        page.set_viewport_size({'width': 800, 'height': 1000})
        mobile = page.evaluate("""() => {
          const box = key => document.querySelector(
            `[data-product-section="${key}"]`).getBoundingClientRect();
          const general = box('general'), currency = box('currency');
          const display = box('display');
          return {generalLeft: general.left, generalTop: general.top,
                  currencyTop: currency.top, displayLeft: display.left,
                  displayTop: display.top};
        }""")
        assert desktop['displayLeft'] > desktop['generalRight']
        assert abs(mobile['generalLeft'] - mobile['displayLeft']) < 1
        assert mobile['generalTop'] < mobile['currencyTop'] < mobile['displayTop']
        browser.close()


def test_only_the_selected_execution_mode_button_is_visible():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.locator('#runModePreview').check()
        assert page.locator('#btnPreview').is_visible()
        assert not page.locator('#btnCreateSelected').is_visible()
        page.locator('#runModeCreate').check()
        assert not page.locator('#btnPreview').is_visible()
        assert page.locator('#btnCreateSelected').is_visible()
        browser.close()


def test_candidate_sheets_show_product_counts_and_apply_existing_endpoints():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.evaluate("""openProductSheetPicker({
          pending_id:'pending-1', workspace_id:'workspace-1',
          sheets:[
            {name:'Promotion 15.7',count:6,product_count:2},
            {name:'Cash Shop 15.7',count:3,product_count:1}]
        })""")
        labels = page.locator('#sheetList .sheet-row').all_text_contents()
        assert any('Promotion 15.7' in label and '2 Product' in label
                   for label in labels)
        assert any('Cash Shop 15.7' in label and '1 Product' in label
                   for label in labels)

        calls = []

        def route_api(route):
            calls.append((route.request.method, route.request.url))
            if route.request.url.endswith('/api/import-plan/apply'):
                route.fulfill(
                    status=200, content_type='application/json',
                    body='{"workspace_id":"workspace-1","mode":"shop"}')
            else:
                route.fulfill(
                    status=200, content_type='application/json',
                    body='{"workspace_id":"workspace-1","game":"CabalPC TH",'
                         '"products":[]}')

        page.route('**/api/import-plan/apply', route_api)
        page.route('**/api/workspaces/workspace-1/products', route_api)
        page.evaluate("() => applySelectedSheets()")
        assert calls == [
            ('POST', 'http://tool.test/api/import-plan/apply'),
            ('GET', 'http://tool.test/api/workspaces/workspace-1/products'),
        ]
        browser.close()


def test_bundle_handoff_matches_exact_keys_and_exposes_conflicts():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        result = page.evaluate("""() => {
          addDrafts([
            {source_group_key:'same',name_th:'A',bundle_id:'',
             price_candidates:[],prices:[]},
            {source_group_key:'conflict',name_th:'B',bundle_id:'100',
             price_candidates:[],prices:[]},
            {source_group_key:'other',name_th:'C',bundle_id:'',
             price_candidates:[],prices:[]}
          ], 'workspace-1');
          applyBundleHandoff({workspace_id:'workspace-1',rows:[
            {source_group_key:'same',bundle_id:'200',name:'A'},
            {source_group_key:'conflict',bundle_id:'300',name:'B'},
            {source_group_key:'missing',bundle_id:'400',name:'X'}
          ]});
          return productQueue.items;
        }""")
        by_key = {entry['source_group_key']: entry for entry in result}
        assert by_key['same']['bundle_id'] == '200'
        assert by_key['conflict']['bundle_id'] == '100'
        assert by_key['conflict']['bundle_conflict'] == {
            'workbook_id': '100',
            'created_id': '300',
        }
        assert by_key['other']['bundle_id'] == ''
        browser.close()


def test_images_stay_in_memory_and_workspace_delete_is_scoped():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.evaluate("""() => {
          addDrafts([
            {source_group_key:'g1',name_th:'A',
             price_candidates:[],prices:[]},
            {source_group_key:'g2',name_th:'B',
             price_candidates:[],prices:[]}
          ], 'workspace-1');
          addDrafts([
            {source_group_key:'g3',name_th:'C',
             price_candidates:[],prices:[]}
          ], 'workspace-2');
          const first = productQueue.items[0];
          rememberImage(first.key, 'thumbnail_th',
            new File(['secret bytes'], 'thumb.png', {type:'image/png'}));
        }""")
        assert 'secret bytes' not in page.evaluate(
            "localStorage.getItem('afc.productQueue.v1')")

        calls = []

        def delete_workspace(route):
            calls.append((route.request.method, route.request.url))
            route.fulfill(status=204, body='')

        page.route('**/api/workspaces/workspace-1', delete_workspace)
        page.evaluate("() => deleteActiveWorkspace('workspace-1')")
        assert calls == [
            ('DELETE', 'http://tool.test/api/workspaces/workspace-1')]
        assert page.evaluate("""productQueue.items.map(
          entry => entry.workspace_id)""") == ['workspace-2']
        browser.close()


def test_language_tabs_keep_both_descriptions_and_manual_bundle_is_numeric():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.evaluate("""addDrafts([{
          source_group_key:'g1',name_th:'A',details_th:'รายละเอียดเดิม',
          details_en:'Existing details',bundle_id:'',
          price_candidates:[],prices:[]
        }], 'workspace-1')""")

        page.locator('[data-tab-group="details"][data-tab="en"]').click()
        page.locator('#detailsEn').fill('English edited')
        page.locator('[data-tab-group="details"][data-tab="th"]').click()
        page.locator('#detailsTh').fill('ไทยแก้แล้ว')

        entry = page.evaluate("productQueue.current()")
        assert entry['details_th'] == 'ไทยแก้แล้ว'
        assert entry['details_en'] == 'English edited'
        assert page.locator('#bundleId').get_attribute('type') == 'number'
        assert page.locator('#bundleId').is_visible()
        browser.close()


def test_submit_products_sends_json_and_memory_images_as_multipart():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.evaluate("""() => {
          const game = document.querySelector('#game');
          game.add(new Option('CabalM TH', 'CabalM TH'));
          game.value = 'CabalM TH';
          addDrafts([{
            source_group_key:'g1',name_th:'Pack',name_en:'Pack',
            category_id:'12',bundle_id:'223553',
            start_at:'2026-07-30 00:00:00',
            end_at:'2026-08-30 07:59:00',
            limit_type:'UNLIMITED',
            price_candidates:[],
            prices:[{currency_id:'91',original_price:100,price:66}]
          }], 'workspace-1');
          const entry = productQueue.current();
          rememberImage(entry.key, 'thumbnail_th',
            new File(['secret pixels'], 'thumb.png', {type:'image/png'}));
        }""")
        bodies = []

        def capture(route):
            bodies.append(route.request.post_data_buffer)
            route.fulfill(
                status=200, content_type='application/json',
                body='{"results":[],"logs":[],"created":0,"planned":1}')

        page.route('**/api/products/run', capture)
        page.evaluate("""() => submitProducts(
          [productQueue.current()], false).then(response => response.json())""")

        body = bodies[0]
        assert b'image__' in body and b'__thumb_th' in body
        assert b'secret pixels' in body
        assert b'"do_save":false' in body
        assert b'"category_id":"12"' in body
        browser.close()


def test_create_uses_checked_entries_confirms_and_updates_product_ids():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        result = page.evaluate("""async () => {
          addDrafts([
            {source_group_key:'g1',name_th:'A',name_en:'A',
             category_id:'12',bundle_id:'100',
             start_at:'2026-07-30 00:00:00',
             end_at:'2026-08-30 07:59:00',
             limit_type:'UNLIMITED',price_candidates:[],
             prices:[{currency_id:'91',original_price:10,price:10}],
             selected:true},
            {source_group_key:'g2',name_th:'B',name_en:'B',
             category_id:'12',bundle_id:'200',
             start_at:'2026-07-30 00:00:00',
             end_at:'2026-08-30 07:59:00',
             limit_type:'UNLIMITED',price_candidates:[],
             prices:[{currency_id:'91',original_price:20,price:20}],
             selected:false}
          ], 'workspace-1');
          window.confirmText = '';
          window.confirm = text => { window.confirmText = text; return true; };
          window.sent = null;
          submitProducts = async (entries, doSave) => {
            window.sent = {keys: entries.map(entry => entry.key), doSave};
            return {
              ok: true,
              json: async () => ({
                results:[{
                  client_key:entries[0].key,name:'A',saved:true,
                  made_id:'501',missing:[],error:null
                }],
                logs:[],created:1,planned:1
              })
            };
          };
          await runSelectedProducts();
          const first = productQueue.items.find(
            entry => entry.source_group_key === 'g1');
          const second = productQueue.items.find(
            entry => entry.source_group_key === 'g2');
          second.status = 'failed';
          return {
            confirmText: window.confirmText,
            sent: window.sent,
            first: {status:first.status,product_id:first.product_id},
            retry: retryableProducts().map(entry => entry.source_group_key)
          };
        }""")

        assert '1 Product' in result['confirmText']
        assert result['sent']['doSave'] is True
        assert len(result['sent']['keys']) == 1
        assert result['first'] == {'status': 'created', 'product_id': '501'}
        assert result['retry'] == ['g2']
        browser.close()
