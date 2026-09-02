# -*- coding: utf-8 -*-
"""Static and visible contracts for the Product operator page."""
from pathlib import Path
import re

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PRODUCTS = ROOT / 'web' / 'static' / 'products.html'
BUNDLES = ROOT / 'web' / 'static' / 'bundles.html'
EVENTS = ROOT / 'web' / 'static' / 'events.html'
ITEMCODES = ROOT / 'web' / 'static' / 'itemcodes.html'
ITEM_FINDER = ROOT / 'web' / 'static' / 'index.html'
CONSOLE_JS = ROOT / 'web' / 'static' / 'console.js'
GAME_SYNC_JS = ROOT / 'web' / 'static' / 'game_sync.js'
SHEET_PICKER_JS = ROOT / 'web' / 'static' / 'sheet_picker.js'


def _page_html(path):
    html = re.sub(
        r'<script src="/static/console\.js(?:\?[^\"]*)?"></script>',
        lambda _match: '<script>%s</script>' %
        CONSOLE_JS.read_text(encoding='utf-8'),
        path.read_text(encoding='utf-8'),
    )
    return html.replace(
        '<script src="/static/game_sync.js"></script>',
        '<script>%s</script>' % GAME_SYNC_JS.read_text(encoding='utf-8'),
    ).replace(
        '<script src="/static/sheet_picker.js"></script>',
        '<script>%s</script>' % SHEET_PICKER_JS.read_text(encoding='utf-8'),
    )


def _tool_page(browser):
    html = _page_html(PRODUCTS)
    context = browser.new_context()
    page = context.new_page()
    page.route(
        'http://tool.test/products',
        lambda route: route.fulfill(
            status=200, content_type='text/html; charset=utf-8', body=html),
    )
    page.goto('http://tool.test/products', wait_until='domcontentloaded')
    page.wait_for_function("typeof addDrafts === 'function'")
    page.wait_for_function("productPageReady === true")
    return page


def _route_live_game_tools(context, workspace=None):
    def route_tool(route):
        url = route.request.url
        tool_pages = {
            'http://tool.test/': ITEM_FINDER,
            'http://tool.test/bundles': BUNDLES,
            'http://tool.test/events': EVENTS,
            'http://tool.test/itemcodes': ITEMCODES,
            'http://tool.test/products': PRODUCTS,
        }
        if url in tool_pages:
            route.fulfill(
                status=200, content_type='text/html; charset=utf-8',
                body=tool_pages[url].read_text(encoding='utf-8'))
        elif '/static/console.js' in url:
            route.fulfill(
                content_type='application/javascript',
                body=CONSOLE_JS.read_text(encoding='utf-8'))
        elif url.endswith('/static/game_sync.js'):
            route.fulfill(
                content_type='application/javascript',
                body=GAME_SYNC_JS.read_text(encoding='utf-8'))
        elif url.endswith('/static/sheet_picker.js'):
            route.fulfill(
                content_type='application/javascript',
                body=SHEET_PICKER_JS.read_text(encoding='utf-8'))
        elif url.endswith('/api/auth/me'):
            route.fulfill(json={
                'username': 'operator', 'role': 'member',
                'local_mode': True,
            })
        elif url.endswith('/api/games'):
            route.fulfill(json={'games': [
                'CabalM TH', 'CabalM SEA', 'CabalPC TH',
            ]})
        elif url.endswith('/api/modes'):
            route.fulfill(json={
                'event': {'web_mode': 'any', 'web_locked': False},
                'itemcode': {'web_mode': 'no', 'web_locked': True},
                'shop': {'web_mode': 'any', 'web_locked': False},
            })
        elif url.endswith('/api/capabilities'):
            route.fulfill(json={'allow_headed': False})
        elif url.endswith('/api/aztek/status'):
            route.fulfill(json={'status': 'active'})
        elif url.endswith('/api/products/options'):
            route.fulfill(json={'options': {
                'categories': [], 'currencies': [],
            }})
        elif workspace and '/api/workspaces/' in url \
                and url.endswith('/products'):
            route.fulfill(json=workspace)
        elif '/static/' in url:
            route.fulfill(content_type='text/css', body='')
        else:
            route.abort()

    context.route('http://tool.test/**', route_tool)


def test_product_page_has_shared_workspace_queue_contract(client):
    html = PRODUCTS.read_text(encoding='utf-8')
    assert 'id="productQueue"' in html
    assert 'afc.productQueue.v1' in html
    assert '/api/workspaces/' in html
    assert 'href="/products"' in html
    assert client.get('/products').status_code == 200


def test_server_picker_syncs_live_across_all_open_tool_tabs():
    """Changing any visible picker must update every other open tool tab."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        _route_live_game_tools(context)
        pages = []
        for path in ('/', '/bundles', '/itemcodes', '/events', '/products'):
            page = context.new_page()
            page.goto('http://tool.test' + path, wait_until='domcontentloaded')
            page.wait_for_function(
                "document.querySelectorAll('#game option').length === 3")
            pages.append(page)

        for index, source in enumerate(pages):
            game = 'CabalPC TH' if index % 2 == 0 else 'CabalM SEA'
            source.select_option('#game', game)
            for target in pages:
                target.wait_for_function(
                    "game => document.querySelector('#game').value === game",
                    arg=game)
                assert target.locator('#game').input_value() == game
        browser.close()


def test_restored_product_workspace_broadcasts_its_game_to_other_tabs():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        _route_live_game_tools(context, workspace={
            'workspace_id': 'workspace-1',
            'game': 'CabalPC TH',
            'products': [],
        })
        event_page = context.new_page()
        product_page = context.new_page()
        event_page.goto(
            'http://tool.test/events', wait_until='domcontentloaded')
        event_page.wait_for_function(
            "document.querySelectorAll('#game option').length === 3")
        event_page.evaluate(
            "localStorage.setItem('afc.productWorkspace', 'workspace-1')")

        product_page.goto(
            'http://tool.test/products', wait_until='domcontentloaded')
        product_page.wait_for_function(
            "document.querySelector('#game').value === 'CabalPC TH'")

        assert event_page.locator('#game').input_value() == 'CabalPC TH'
        browser.close()


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


def test_product_source_refresh_merges_pristine_fields_and_keeps_local_edits():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        result = page.evaluate("""() => {
          addDrafts([{
            source_group_key:'g1',source_sheet:'Old Sheet',name_th:'Old Name',
            name_en:'Old Name',category_source:'Old Category',
            start_at:'2026-08-01 00:00:00',end_at:'2026-08-02 07:59:00',
            bundle_ids:['223930','223931'],composite_required:true,
            bundle_id:'',bundle_source:'',
            price_candidates:[{source_label:'Wallet Point',original_price:10,sale_price:10}],
            limit_type:'PLAYER',limit_quantity:'1',
            limit_reset_interval_days:'1',limit_reset_at:'2026-07-31 04:30:00',
            tags:['NEW'],warnings:['old warning']
          }], 'workspace-1');
          const entry = productQueue.current();
          entry.selected = true;
          entry.image_names = {thumbnail_th:'kept.png'};
          entry.category_id = '77';
          entry.category_label = 'Manual Category';
          entry.category_slug = 'manual-category';
          entry.prices = [{source_label:'Wallet Point',currency_id:'91',
            currency_label:'Wallet Point',original_price:8,price:7}];
          applyBundleHandoff({workspace_id:'workspace-1',rows:[
            {source_group_key:'g1',bundle_id:'900001',name:'Old Name'}]});
          previewedProductKeys.add(entry.key);
          const name = document.querySelector('#nameTh');
          name.value = 'Operator Name';
          name.dispatchEvent(new Event('input', {bubbles:true}));
          addDrafts([{
            source_group_key:'g1',source_sheet:'New Sheet',name_th:'New Source Name',
            name_en:'New Source English',category_source:'New Category',
            start_at:'2026-08-03 00:00:00',end_at:'2026-08-31 07:59:00',
            bundle_ids:['223930','223931','223932'],composite_required:true,
            bundle_id:'',bundle_source:'',
            price_candidates:[{source_label:'Wallet Point',original_price:20,sale_price:15}],
            limit_type:'CHARACTER',limit_quantity:'5',
            limit_reset_interval_days:'7',limit_reset_at:'2026-07-31 09:15:00',
            tags:['SALE'],warnings:['new warning']
          }], 'workspace-1');
          const merged = productQueue.current();
          return {
            key:merged.key,name_th:merged.name_th,name_en:merged.name_en,
            source_sheet:merged.source_sheet,category_source:merged.category_source,
            start_at:merged.start_at,end_at:merged.end_at,
            bundle_ids:merged.bundle_ids,composite_required:merged.composite_required,
            primary_bundle_id:merged.primary_bundle_id,
            bundle_id:merged.bundle_id,bundle_source:merged.bundle_source,
            price_candidates:merged.price_candidates,prices:merged.prices,
            limit_type:merged.limit_type,limit_quantity:merged.limit_quantity,
            reset_interval:merged.limit_reset_interval_days,
            reset_at:merged.limit_reset_at,tags:merged.tags,warnings:merged.warnings,
            selected:merged.selected,image_names:merged.image_names,
            category:[merged.category_id,merged.category_label,merged.category_slug],
            dirty:merged.source_dirty || {},
            snapshotName:merged.source_snapshot?.name_th || '',
            previewed:previewedProductKeys.has(merged.key)
          };
        }""")

        assert result['name_th'] == 'Operator Name'
        assert result['name_en'] == 'New Source English'
        assert result['source_sheet'] == 'New Sheet'
        assert result['category_source'] == 'New Category'
        assert result['start_at'] == '2026-08-03 00:00:00'
        assert result['end_at'] == '2026-08-31 07:59:59'
        assert result['bundle_ids'] == [
            '223930', '223931', '900001', '223932']
        assert result['composite_required'] is False
        assert result['primary_bundle_id'] == '223930'
        assert (result['bundle_id'], result['bundle_source']) == (
            '223930', 'created')
        assert result['price_candidates'][0]['sale_price'] == 15
        assert result['prices'][0]['currency_id'] == '91'
        assert (result['limit_type'], result['limit_quantity']) == (
            'CHARACTER', '5')
        assert (result['reset_interval'], result['reset_at']) == (
            '7', '2026-07-31 09:15:00')
        assert result['warnings'] == ['new warning']
        assert result['selected'] is True
        assert result['image_names'] == {'thumbnail_th': 'kept.png'}
        assert result['category'] == ['77', 'Manual Category', 'manual-category']
        assert result['dirty']['name_th'] is True
        assert result['snapshotName'] == 'New Source Name'
        assert result['previewed'] is False
        browser.close()


def test_legacy_product_refresh_fills_only_missing_source_values():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        result = page.evaluate("""() => {
          const legacy = withDefaults({
            workspace_id:'workspace-1',source_group_key:'g1',
            name_th:'Legacy Name',name_en:'',start_at:'',
            end_at:'2026-08-15 07:59:00',price_candidates:[],
            bundle_ids:[],bundle_id:'777',bundle_source:'manual'
          });
          productQueue.add(legacy);
          productQueue.save();
          renderQueue();
          addDrafts([{
            source_group_key:'g1',name_th:'Source Name',name_en:'Source English',
            start_at:'2026-08-09 00:00:00',end_at:'2026-08-31 07:59:00',
            bundle_ids:['223930','223931'],composite_required:true,
            bundle_id:'',price_candidates:[{source_label:'Wallet Point',
              original_price:20,sale_price:20}]
          }], 'workspace-1');
          return productQueue.current();
        }""")

        assert result['name_th'] == 'Legacy Name'
        assert result['name_en'] == 'Source English'
        assert result['start_at'] == '2026-08-09 00:00:00'
        assert result['end_at'] == '2026-08-15 07:59:59'
        assert result['bundle_ids'] == ['777', '223930', '223931']
        assert result['primary_bundle_id'] == '777'
        assert result['bundle_id'] == '777'
        assert result['bundle_source'] == 'manual'
        assert result['price_candidates'][0]['sale_price'] == 20
        assert result['source_snapshot']['end_at'] == '2026-08-31 07:59:59'
        browser.close()


def test_partial_source_refresh_ignores_missing_and_null_but_applies_empty_clear():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        result = page.evaluate("""() => {
          addDrafts([{
            source_group_key:'g1',name_th:'Old Thai',name_en:'Old English',
            category_source:'Highlight',start_at:'2026-08-01 00:00:00',
            end_at:'2026-08-31 07:59:00',bundle_ids:['11','12'],
            composite_required:true,bundle_id:'',bundle_source:'',
            price_candidates:[{source_label:'Wallet Point',
              original_price:100,sale_price:90}],
            limit_type:'PLAYER',limit_quantity:'5',
            limit_reset_interval_days:'7',limit_reset_at:'2026-07-31 09:15:00',
            tags:['SALE'],warnings:['old warning']
          }], 'workspace-1');
          const entry = productQueue.current();
          entry.selected = true;
          entry.category_id = '77';
          entry.category_label = 'Manual Category';
          entry.prices = [{source_label:'Wallet Point',currency_id:'91',
            original_price:100,price:90}];
          applyBundleHandoff({workspace_id:'workspace-1',rows:[{
            source_group_key:'g1',bundle_id:'900001'}]});
          const name = document.querySelector('#nameTh');
          name.value = 'Operator Thai';
          name.dispatchEvent(new Event('input', {bubbles:true}));
          previewedProductKeys.add(entry.key);

          addDrafts([{
            source_group_key:'g1',name_th:'New source Thai',name_en:null,
            end_at:'',price_candidates:null,limit_quantity:'',
            tags:undefined,warnings:null
          }], 'workspace-1');
          const merged = productQueue.current();
          return {
            name_th:merged.name_th,name_en:merged.name_en,
            category_source:merged.category_source,start_at:merged.start_at,
            end_at:merged.end_at,bundle_ids:merged.bundle_ids,
            composite_required:merged.composite_required,
            bundle_id:merged.bundle_id,bundle_source:merged.bundle_source,
            price_candidates:merged.price_candidates,
            limit_type:merged.limit_type,limit_quantity:merged.limit_quantity,
            reset_interval:merged.limit_reset_interval_days,
            reset_at:merged.limit_reset_at,tags:merged.tags,
            warnings:merged.warnings,selected:merged.selected,
            category_id:merged.category_id,prices:merged.prices,
            snapshot:merged.source_snapshot,
            previewed:previewedProductKeys.has(merged.key)
          };
        }""")

        assert result['name_th'] == 'Operator Thai'
        assert result['name_en'] == 'Old English'
        assert result['category_source'] == 'Highlight'
        assert result['start_at'] == '2026-08-01 00:00:00'
        assert result['end_at'] == ''
        assert result['bundle_ids'] == ['11', '12', '900001']
        assert result['composite_required'] is False
        assert (result['bundle_id'], result['bundle_source']) == (
            '11', 'created')
        assert result['price_candidates'][0]['sale_price'] == 90
        assert result['limit_type'] == 'PLAYER'
        assert result['limit_quantity'] == ''
        assert (result['reset_interval'], result['reset_at']) == (
            '7', '2026-07-31 09:15:00')
        assert result['warnings'] == ['old warning']
        assert result['selected'] is True
        assert result['category_id'] == '77'
        assert result['prices'][0]['currency_id'] == '91'
        assert result['snapshot']['name_th'] == 'New source Thai'
        assert result['snapshot']['name_en'] == 'Old English'
        assert result['snapshot']['end_at'] == ''
        assert result['snapshot']['price_candidates'][0]['sale_price'] == 90
        assert result['previewed'] is False
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
        assert page.evaluate("""matchFetchedOption(
          'Highlight',
          [{id:'8',slug:'',label:'Main Shop - Highlight'}]
        )""") == {
            'id': '8',
            'slug': '',
            'label': 'Main Shop - Highlight',
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
        assert all(key.startswith('afc.productOptions.v2:') for key in keys)
        browser.close()


def test_legacy_wrong_option_cache_is_not_reused_after_aztek_dropdown_change():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.evaluate("""() => {
          const game = 'CabalPC TH';
          document.querySelector('#game').add(new Option(game, game));
          document.querySelector('#game').value = game;
          localStorage.setItem(
            `afc.productOptions.v1:${game}:currencies`,
            JSON.stringify({fetched_at:'2026-08-01T00:00:00.000Z',
              options:[{id:'PLAYER',slug:'',label:'PLAYER'}]}));
        }""")
        calls = []

        def fresh_options(route):
            calls.append(route.request.post_data_json)
            route.fulfill(
                status=200, content_type='application/json',
                body='{"options":{"currencies":['
                     '{"id":"91","slug":"wallet-point",'
                     '"label":"Wallet Point"}]}}')

        page.route('**/api/products/options', fresh_options)
        label = page.evaluate(
            "() => ensureOptions('currencies').then(rows => rows[0].label)")
        assert label == 'Wallet Point'
        assert calls == [{
            'game': 'CabalPC TH',
            'kinds': ['currencies'],
        }]
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


def test_stale_limit_ids_are_removed_then_live_options_are_matched():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        result = page.evaluate("""() => {
          optionState.categories.options = [
            {id:'8',slug:'',label:'Main Shop - Highlight'}];
          optionState.currencies.options = [
            {id:'91',slug:'wallet-point',label:'Wallet Point'}];
          const entry = {
            category_source:'Highlight', category_id:'PLAYER',
            price_candidates:[
              {source_label:'Wallet Point',original_price:100,sale_price:66}],
            prices:[{source_label:'Wallet Point',currency_id:'PLAYER',
              currency_slug:'',currency_label:'PLAYER',
              original_price:100,price:66}]
          };
          applyOptionMatches(entry);
          return entry;
        }""")
        assert result['category_id'] == '8'
        assert result['prices'] == [{
            'source_label': 'Wallet Point',
            'currency_id': '91',
            'currency_slug': 'wallet-point',
            'currency_label': 'Wallet Point',
            'original_price': 100,
            'price': 66,
        }]
        browser.close()


def test_product_run_reports_missing_category_and_currency_before_api_call():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        assert page.evaluate("""runnableError([{
          name_th:'Gold Merit X', category_id:'', prices:[]
        }])""") == (
            'Gold Merit X: กรุณาเลือกหมวดหมู่บน Aztek')
        assert page.evaluate("""runnableError([{
          name_th:'Gold Merit X', category_id:'8', prices:[]
        }])""") == (
            'Gold Merit X: กรุณาเลือก Currency อย่างน้อย 1 รายการ')
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


def test_product_live_actions_show_three_buttons_without_mode_controls():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        assert page.get_by_role(
            'heading', name='สร้างบนเว็บจริง').is_visible()
        assert page.locator('#btnPreview').is_visible()
        assert page.locator('#btnCreateOne').is_visible()
        assert page.locator('#btnCreateAll').is_visible()
        assert page.locator('#runModePreview').count() == 0
        assert page.locator('#runModeCreate').count() == 0
        assert page.locator('#selectForRun').count() == 0
        browser.close()


def test_product_preview_gate_follows_active_key_and_invalidates_on_edit():
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
             prices:[{currency_id:'91',original_price:10,price:10}]},
            {source_group_key:'g2',name_th:'B',name_en:'B',
             category_id:'12',bundle_id:'200',
             start_at:'2026-07-30 00:00:00',
             end_at:'2026-08-30 07:59:00',
             limit_type:'UNLIMITED',price_candidates:[],
             prices:[{currency_id:'91',original_price:20,price:20}]}
          ], 'workspace-1');
          const first = productQueue.items[0];
          const second = productQueue.items[1];
          productQueue.active = first.key;
          renderQueue();
          window.sent = [];
          submitProducts = async (entries, doSave) => {
            window.sent.push({
              groups: entries.map(entry => entry.source_group_key), doSave});
            return {
              ok: true,
              json: async () => ({
                results:[{
                  client_key:entries[0].key,name:entries[0].name_th,
                  saved:false,made_id:'',missing:[],error:null
                }],
                logs:[],created:0,planned:1
              })
            };
          };
          const before = document.querySelector('#btnCreateOne').disabled;
          await runPreviewProduct();
          const afterPreview =
            document.querySelector('#btnCreateOne').disabled;
          productQueue.active = second.key;
          renderQueue();
          const afterSwitch =
            document.querySelector('#btnCreateOne').disabled;
          productQueue.active = first.key;
          renderQueue();
          const afterReturn =
            document.querySelector('#btnCreateOne').disabled;
          const name = document.querySelector('#nameTh');
          name.value = 'A edited';
          name.dispatchEvent(new Event('input', {bubbles:true}));
          const afterEdit =
            document.querySelector('#btnCreateOne').disabled;
          return {
            before, afterPreview, afterSwitch, afterReturn, afterEdit,
            sent: window.sent
          };
        }""")

        assert result['sent'] == [{'groups': ['g1'], 'doSave': False}]
        assert result['before'] is True
        assert result['afterPreview'] is False
        assert result['afterSwitch'] is True
        assert result['afterReturn'] is False
        assert result['afterEdit'] is True
        browser.close()


def test_product_edit_during_preview_does_not_unlock_stale_submission():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        unlocked = page.evaluate("""async () => {
          addDrafts([{
            source_group_key:'g1',name_th:'A',name_en:'A',
            category_id:'12',bundle_id:'100',
            start_at:'2026-07-30 00:00:00',
            end_at:'2026-08-30 07:59:00',
            limit_type:'UNLIMITED',price_candidates:[],
            prices:[{currency_id:'91',original_price:10,price:10}]
          }], 'workspace-1');
          let finishPreview;
          submitProducts = async entries => new Promise(resolve => {
            finishPreview = () => resolve({
              ok:true,
              json:async () => ({
                results:[{
                  client_key:entries[0].key,name:'A',saved:false,
                  made_id:'',missing:[],error:null
                }],
                logs:[],created:0,planned:1
              })
            });
          });
          const pending = runPreviewProduct();
          await Promise.resolve();
          const name = document.querySelector('#nameTh');
          name.value = 'A edited while waiting';
          name.dispatchEvent(new Event('input', {bubbles:true}));
          finishPreview();
          await pending;
          return !document.querySelector('#btnCreateOne').disabled;
        }""")

        assert unlocked is False
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


def test_product_sheet_picker_can_clear_and_select_every_sheet():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.evaluate("""openProductSheetPicker({
          pending_id:'pending-1', workspace_id:'workspace-1',
          sheets:[
            {name:'Promotion',count:6,product_count:2},
            {name:'Cash Shop',count:3,product_count:1}]
        })""")

        assert page.locator('#sheetList input:checked').count() == 2
        page.locator('#btnClearSheets').click()
        assert page.locator('#sheetList input:checked').count() == 0
        page.locator('#btnSelectAllSheets').click()
        assert page.locator('#sheetList input:checked').count() == 2
        browser.close()


def test_product_bundle_id_is_plain_numeric_text_without_spinner():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.evaluate("""addDrafts([{
          source_group_key:'g1',name_th:'A',bundle_id:'223553'
        }], 'workspace-1')""")
        field = page.locator('.bundle-id-input')
        field_type = field.get_attribute('type')
        assert field_type == 'text'
        assert field.get_attribute('inputmode') == 'numeric'
        browser.close()


def test_imported_product_bundles_render_directly_with_first_primary():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.evaluate("""addDrafts([{
          source_group_key:'g1',name_th:'Multi Bundle',name_en:'Multi Bundle',
          bundle_ids:['223930','223931'],composite_required:true,bundle_id:'',
          price_candidates:[],prices:[]
        }], 'workspace-1')""")

        rows = page.locator('#bundleRows .bundle-row')
        assert rows.locator('.bundle-id-input').evaluate_all(
            '(nodes) => nodes.map(node => node.value)') == ['223930', '223931']
        assert rows.locator('.bundle-primary').evaluate_all(
            '(nodes) => nodes.map(node => node.checked)') == [True, False]
        assert page.locator('#bundleCount').inner_text() == '2 / 20'
        assert page.locator('#compositeNotice').count() == 0
        assert page.evaluate('productQueue.current().composite_required') is False
        browser.close()


def test_operator_can_add_edit_select_and_remove_product_bundles():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.evaluate("""addDrafts([{
          source_group_key:'g1',name_th:'Manual Bundles',name_en:'Manual Bundles',
          bundle_ids:['223930'],primary_bundle_id:'223930',bundle_id:'223930',
          price_candidates:[],prices:[]
        }], 'workspace-1')""")

        page.locator('#btnAddBundle').click()
        rows = page.locator('#bundleRows .bundle-row')
        rows.nth(1).locator('.bundle-id-input').fill('223931')
        rows.nth(1).locator('.bundle-primary').check()
        assert page.evaluate('productQueue.current().primary_bundle_id') == '223931'

        rows.nth(1).locator('.bundle-remove').click()
        assert page.locator('.bundle-id-input').evaluate_all(
            '(nodes) => nodes.map(node => node.value)') == ['223930']
        assert page.locator('.bundle-primary').is_checked()
        entry = page.evaluate('productQueue.current()')
        assert entry['primary_bundle_id'] == '223930'
        assert entry['bundle_id'] == '223930'
        browser.close()


def test_wallet_point_price_is_editable_and_manual_price_can_be_added():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.evaluate("""() => {
          optionState.currencies.options = [
            {id:'91',slug:'wallet-point',label:'Wallet Point'},
            {id:'92',slug:'force-gem',label:'Force Gem'}];
          addDrafts([{
            source_group_key:'g1',name_th:'Time Reducer - Platinum Insignia',
            name_en:'Time Reducer - Platinum Insignia',
            price_candidates:[{source_label:'Wallet Point',
              original_price:75,sale_price:75}],prices:[]
          }], 'workspace-1');
        }""")

        inputs = page.locator('#priceMatches input[type="number"]')
        assert inputs.count() == 2
        assert inputs.nth(0).input_value() == '75'
        assert inputs.nth(1).input_value() == '75'
        inputs.nth(1).fill('70')
        assert page.evaluate(
            "productQueue.current().prices[0].price") == '70'

        page.locator('#btnAddManualPrice').click()
        assert page.locator('#priceMatches .price-match-row').count() == 2
        page.locator('#priceMatches .price-match-row').nth(1).locator(
            'select').select_option('92')
        manual_inputs = page.locator(
            '#priceMatches .price-match-row').nth(1).locator(
                'input[type="number"]')
        manual_inputs.nth(0).fill('30')
        manual_inputs.nth(1).fill('25')
        manual = page.evaluate("""() => productQueue.current().prices.find(
          price => price.currency_id === '92')""")
        assert manual['original_price'] == '30'
        assert manual['price'] == '25'
        browser.close()


def test_bundle_handoff_matches_exact_keys_and_merges_bundle_ids():
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
        assert by_key['same']['bundle_ids'] == ['200']
        assert by_key['conflict']['bundle_id'] == '100'
        assert by_key['conflict']['bundle_ids'] == ['100', '300']
        assert by_key['conflict']['primary_bundle_id'] == '100'
        assert 'bundle_conflict' not in by_key['conflict']
        assert by_key['other']['bundle_id'] == ''
        browser.close()


def test_legacy_bundle_conflict_does_not_block_direct_multi_bundle_product():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        result = page.evaluate("""() => {
          const entry = withDefaults({
            name_th:'Legacy',name_en:'Legacy',category_id:'12',
            prices:[{currency_id:'91',original_price:10,price:10}],
            bundle_ids:['100','300'],bundle_id:'100',
            bundle_conflict:{workbook_id:'100',created_id:'300'}
          });
          return {entry, error:runnableError([entry])};
        }""")

        assert 'bundle_conflict' not in result['entry']
        assert 'เลือกเลข Bundle' not in result['error']
        browser.close()


def test_direct_bundle_rows_and_exact_handoff_preserve_primary():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        before = page.evaluate("""() => {
          addDrafts([{
            source_group_key:'group-1',name_th:'Multi Product',
            name_en:'Multi Product',bundle_ids:['223930','223931'],
            composite_required:true,bundle_id:'',bundle_source:'',
            price_candidates:[],prices:[]
          }], 'workspace-1');
          const entry = productQueue.current();
          previewedProductKeys.add(entry.key);
          return {
            ids:entry.bundle_ids,primary:entry.primary_bundle_id,
            inputs:[...document.querySelectorAll('.bundle-id-input')]
              .map(node => node.value),
            composite:entry.composite_required,
            noticeCount:document.querySelectorAll('#compositeNotice').length,
            queueText:document.querySelector('#productQueue').selectedOptions[0].textContent,
            previewed:previewedProductKeys.has(entry.key)
          };
        }""")

        assert before['ids'] == ['223930', '223931']
        assert before['primary'] == '223930'
        assert before['inputs'] == ['223930', '223931']
        assert before['composite'] is False
        assert before['noticeCount'] == 0
        assert 'Composite Bundle' not in before['queueText']

        after_wrong_key = page.evaluate("""() => {
          applyBundleHandoff({workspace_id:'workspace-1',rows:[{
            source_group_key:'group-10',bundle_id:'900000',name:'Wrong'}]});
          return productQueue.current().bundle_id;
        }""")
        assert after_wrong_key == '223930'

        without_workspace = page.evaluate("""() => {
          applyBundleHandoff({rows:[{
            source_group_key:'group-1',bundle_id:'900000',name:'Ambiguous'}]});
          return productQueue.current().bundle_id;
        }""")
        assert without_workspace == '223930'

        after = page.evaluate("""() => {
          applyBundleHandoff({workspace_id:'workspace-1',rows:[{
            source_group_key:'group-1',bundle_id:'900001',name:'Created'}]});
          const entry = productQueue.current();
          return {
            bundle_id:entry.bundle_id,primary:entry.primary_bundle_id,
            bundle_source:entry.bundle_source,
            bundle_ids:entry.bundle_ids,composite_required:entry.composite_required,
            queueText:document.querySelector('#productQueue').selectedOptions[0].textContent,
            previewed:previewedProductKeys.has(entry.key)
          };
        }""")

        assert after['bundle_id'] == '223930'
        assert after['primary'] == '223930'
        assert after['bundle_source'] == 'created'
        assert after['bundle_ids'] == ['223930', '223931', '900001']
        assert after['composite_required'] is False
        assert 'Composite Bundle' not in after['queueText']
        assert after['previewed'] is False
        browser.close()


def test_bundle_handoff_rejects_legacy_empty_workspace_identity():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        bundle_id = page.evaluate("""() => {
          addDrafts([{
            source_group_key:'legacy-group',name_th:'Legacy Product',
            bundle_ids:['11','12'],composite_required:true,bundle_id:'',
            price_candidates:[],prices:[]
          }], '');
          applyBundleHandoff({rows:[{
            source_group_key:'legacy-group',bundle_id:'900001'}]});
          return productQueue.current().bundle_id;
        }""")

        assert bundle_id == '11'
        browser.close()


def _legacy_pending_composite_action_hands_only_exact_group_bundle_to_review_queue():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.evaluate("""() => addDrafts([{
          source_group_key:'group-a',name_th:'Product A',name_en:'Product A',
          bundle_ids:['223930','223931'],composite_required:true,
          bundle_id:'',price_candidates:[],prices:[]
        }], 'workspace-1')""")

        assert page.locator('#btnReviewComposite').count() == 1

        requests = []

        def preview(route):
            requests.append(route.request.post_data_json)
            route.fulfill(
                status=200, content_type='application/json',
                body='{"bundles":[{"name":"Product A Composite",'
                     '"group":"Product A","group_key":"group-a","items":['
                     '{"id":"11","name":"A only","qty":"2"},'
                     '{"id":"12","name":"Shared","qty":"3"}]}],'
                     '"mode":"shop","game":"CabalPC TH",'
                     '"event_drafts":[],"itemcode_drafts":[],"not_found":[]}')

        page.route('**/api/workspaces/workspace-1/bundles', preview)
        page.context.route(
            'http://tool.test/bundles',
            lambda route: route.fulfill(
                status=200, content_type='text/html; charset=utf-8',
                body=_page_html(BUNDLES)),
        )

        page.locator('#btnReviewComposite').click()
        page.wait_for_url('http://tool.test/bundles')
        page.wait_for_function(
            "typeof state === 'object' && state.queue.length === 1")

        assert requests == [{'source_group_key': 'group-a'}]
        assert page.evaluate("""() => state.queue.map(bundle => ({
          workspace_id:bundle.workspace_id,group_key:bundle.group_key,
          ids:bundle.items.map(item => item.id)
        }))""") == [{
            'workspace_id': 'workspace-1',
            'group_key': 'group-a',
            'ids': ['11', '12'],
        }]
        assert page.locator('#btnCreateOne').is_disabled()
        browser.close()


def _legacy_direct_product_import_hands_exact_group_to_item_finder_before_bundle():
    """No search is auto-started and no create runner is called by the fallback."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.evaluate("""() => addDrafts([{
          source_group_key:'group-a',name_th:'Product A',name_en:'Product A',
          bundle_ids:['223930','223931'],composite_required:true,
          bundle_id:'',price_candidates:[],prices:[]
        }], 'workspace-1')""")

        calls = []

        def preview(route):
            calls.append((route.request.method, route.request.url))
            route.fulfill(
                status=200, content_type='application/json', body='''{
                  "bundles":[],"needs_search":true,
                  "mode":"shop","game":"CabalPC TH",
                  "search_handoff":{
                    "workspace_id":"workspace-1",
                    "source_group_key":"group-a",
                    "criteria":[
                      {"kind":"11","name":"A only",
                       "sources":["Product A"],"group_keys":["group-a"]},
                      {"kind":"12","name":"Shared",
                       "sources":["Product A"],"group_keys":["group-a"]}
                    ]
                  }
                }''')

        def item_finder_app(route):
            url = route.request.url
            calls.append((route.request.method, url))
            if url.startswith('http://tool.test/?'):
                route.fulfill(
                    status=200, content_type='text/html; charset=utf-8',
                    body=_page_html(ITEM_FINDER))
            elif url.endswith('/api/auth/me'):
                route.fulfill(json={'username': 'tester', 'role': 'member',
                                    'local_mode': True})
            elif url.endswith('/api/games'):
                route.fulfill(json={'games': ['CabalPC TH']})
            elif url.endswith('/api/modes'):
                route.fulfill(json={
                    'shop': {'web_mode': 'any', 'web_locked': False,
                             'read_desc': True},
                    'event': {'web_mode': 'no', 'web_locked': False,
                              'read_desc': False},
                    'itemcode': {'web_mode': 'no', 'web_locked': True,
                                 'read_desc': False},
                })
            elif url.endswith('/api/capabilities'):
                route.fulfill(json={'allow_headed': False})
            elif url.endswith('/api/aztek/status'):
                route.fulfill(json={'status': 'active'})
            elif url.endswith('/api/workspaces/workspace-1'):
                route.fulfill(json={
                    'workspace_id': 'workspace-1', 'mode': 'shop',
                    'game': 'CabalPC TH', 'filename': 'direct-plan.xlsx',
                    'count': 3, 'occurrence_count': 3, 'result_count': 0,
                    'items': [
                        {'kind': '11', 'name': 'A only',
                         'sources': ['Product A'],
                         'group_keys': ['group-a']},
                        {'kind': '12', 'name': 'Shared',
                         'sources': ['Product A', 'Product B'],
                         'group_keys': ['group-a', 'group-b']},
                        {'kind': '99', 'name': 'B only',
                         'sources': ['Product B'],
                         'group_keys': ['group-b']},
                    ],
                    'results': [], 'not_found': [],
                })
            else:
                route.abort()

        page.route('**/api/workspaces/workspace-1/bundles', preview)
        page.context.route('http://tool.test/**', item_finder_app)

        page.locator('#btnReviewComposite').click()
        page.wait_for_url(
            'http://tool.test/?workspace_id=workspace-1&source_group_key=group-a')
        page.wait_for_function(
            "typeof state === 'object' && state.criteria.length === 2")

        assert page.evaluate(
            "state.criteria.map(row => [row.kind,row.sources,row.group_keys])"
        ) == [
            ['11', ['Product A'], ['group-a']],
            ['12', ['Product A'], ['group-a']],
        ]
        notice = page.locator('#searchHandoffNotice')
        assert notice.is_visible()
        assert 'Item Finder' in notice.inner_text()
        assert 'Bundle' in notice.inner_text()
        assert page.evaluate("state.searchSourceGroupKey") == 'group-a'
        assert not any('/api/bundles/run' in url or '/api/products/run' in url
                       for _, url in calls)
        assert not any('/ws/search' in url for _, url in calls)
        browser.close()


def test_stale_item_finder_handoff_is_consumed_and_normal_workspace_restores():
    """A missing scoped workspace cannot replay or erase a valid normal one."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        workspace_requests = []

        def item_finder_app(route):
            url = route.request.url
            if url == 'http://tool.test/seed':
                route.fulfill(status=200, content_type='text/html',
                              body='<html></html>')
            elif (route.request.resource_type == 'document'
                  and url.startswith('http://tool.test/')):
                route.fulfill(
                    status=200, content_type='text/html; charset=utf-8',
                    body=_page_html(ITEM_FINDER))
            elif url.endswith('/api/auth/me'):
                route.fulfill(json={'username': 'tester', 'role': 'member',
                                    'local_mode': True})
            elif url.endswith('/api/games'):
                route.fulfill(json={'games': ['CabalPC TH']})
            elif url.endswith('/api/modes'):
                route.fulfill(json={
                    'shop': {'web_mode': 'any', 'web_locked': False,
                             'read_desc': True},
                    'event': {'web_mode': 'no', 'web_locked': False,
                              'read_desc': False},
                    'itemcode': {'web_mode': 'no', 'web_locked': True,
                                 'read_desc': False},
                })
            elif url.endswith('/api/capabilities'):
                route.fulfill(json={'allow_headed': False})
            elif url.endswith('/api/aztek/status'):
                route.fulfill(json={'status': 'active'})
            elif '/api/workspaces/' in url:
                workspace_id = url.rsplit('/', 1)[-1]
                workspace_requests.append(workspace_id)
                if workspace_id.startswith('missing'):
                    route.fulfill(status=403, json={'detail': 'forbidden'})
                elif workspace_id == 'normal-workspace':
                    route.fulfill(json={
                        'workspace_id': 'normal-workspace', 'mode': 'shop',
                        'game': 'CabalPC TH', 'filename': 'normal.xlsx',
                        'count': 1, 'occurrence_count': 1, 'result_count': 0,
                        'items': [{'kind': '77', 'name': 'Normal item',
                                   'sources': ['Normal']}],
                        'results': [], 'not_found': [],
                    })
                else:
                    route.abort()
            else:
                route.abort()

        context.route('http://tool.test/**', item_finder_app)
        page.goto('http://tool.test/seed')
        page.evaluate("""() => {
          localStorage.setItem('afc.workspaceId', 'normal-workspace');
          sessionStorage.setItem('afc.itemFinderHandoff', JSON.stringify({
            workspace_id:'missing-workspace',source_group_key:'group-a'
          }));
        }""")

        page.goto(
            'http://tool.test/?workspace_id=missing-workspace&source_group_key=group-a')
        page.wait_for_function(
            "typeof state === 'object' && state.workspaceId === 'normal-workspace'")

        assert workspace_requests == ['missing-workspace', 'normal-workspace']
        assert page.url == 'http://tool.test/'
        assert page.evaluate(
            "sessionStorage.getItem('afc.itemFinderHandoff')") is None
        assert page.evaluate(
            "localStorage.getItem('afc.workspaceId')") == 'normal-workspace'
        assert page.evaluate(
            "state.criteria.map(row => row.name)") == ['Normal item']
        assert page.locator('#searchHandoffNotice').is_hidden()

        page.reload(wait_until='domcontentloaded')
        page.wait_for_function(
            "typeof state === 'object' && state.workspaceId === 'normal-workspace'")
        assert workspace_requests == [
            'missing-workspace', 'normal-workspace', 'normal-workspace']

        # A partial query identity must not borrow its missing half from a stale
        # session payload. Both are consumed and the normal workspace wins.
        page.evaluate("""() => sessionStorage.setItem(
          'afc.itemFinderHandoff', JSON.stringify({
            workspace_id:'missing-second',source_group_key:'group-b'
          }))""")
        page.goto('http://tool.test/?workspace_id=missing-partial')
        page.wait_for_function(
            "typeof state === 'object' && state.workspaceId === 'normal-workspace'")
        assert 'missing-partial' not in workspace_requests
        assert page.url == 'http://tool.test/'
        assert page.evaluate(
            "sessionStorage.getItem('afc.itemFinderHandoff')") is None
        assert page.evaluate(
            "localStorage.getItem('afc.workspaceId')") == 'normal-workspace'
        browser.close()


def test_scoped_handoff_does_not_attach_to_an_unscoped_running_search():
    """Restore must not open a websocket that could replay sibling rows."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_init_script("""
          window.createdSearchSockets = [];
          window.WebSocket = class {
            constructor(url) { this.url = url; window.createdSearchSockets.push(url); }
            send() {}
            close() {}
          };
        """)
        page = context.new_page()

        def item_finder_app(route):
            url = route.request.url
            if (route.request.resource_type == 'document'
                    and url.startswith('http://tool.test/')):
                route.fulfill(
                    status=200, content_type='text/html; charset=utf-8',
                    body=_page_html(ITEM_FINDER))
            elif url.endswith('/api/auth/me'):
                route.fulfill(json={'username': 'tester', 'role': 'member',
                                    'local_mode': True})
            elif url.endswith('/api/games'):
                route.fulfill(json={'games': ['CabalPC TH']})
            elif url.endswith('/api/modes'):
                route.fulfill(json={
                    'shop': {'web_mode': 'any', 'web_locked': False,
                             'read_desc': True}})
            elif url.endswith('/api/capabilities'):
                route.fulfill(json={'allow_headed': False})
            elif url.endswith('/api/aztek/status'):
                route.fulfill(json={'status': 'active'})
            elif url.endswith('/api/workspaces/workspace-1'):
                route.fulfill(json={
                    'workspace_id': 'workspace-1', 'mode': 'shop',
                    'game': 'CabalPC TH', 'filename': 'products.xlsx',
                    'count': 1, 'occurrence_count': 1, 'result_count': 0,
                    'items': [{'kind': '11', 'name': 'A',
                               'sources': ['Product A'],
                               'group_keys': ['group-a']}],
                    'results': [], 'not_found': [],
                    'running_job': {'job_id': 'job-1', 'status': 'running',
                                    'source_group_key': ''},
                })
            else:
                route.abort()

        context.route('http://tool.test/**', item_finder_app)
        page.goto(
            'http://tool.test/?workspace_id=workspace-1&source_group_key=group-a')
        page.wait_for_function(
            "typeof state === 'object' && state.workspaceId === 'workspace-1'")
        page.wait_for_timeout(100)

        assert page.evaluate('window.createdSearchSockets') == []
        assert page.evaluate('state.searchSourceGroupKey') == 'group-a'
        assert 'คนละ' in page.locator('#log').inner_text()
        browser.close()


def test_scoped_retry_renders_only_target_group_live_results():
    """A reset/replay must not make sibling or group-less rows selectable."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_init_script("""
          window.WebSocket = class {
            constructor(url) { this.url = url; window.lastSearchSocket = this; }
            send() {}
            close() {}
          };
        """)
        page = context.new_page()

        def item_finder_app(route):
            url = route.request.url
            if (route.request.resource_type == 'document'
                    and url.startswith('http://tool.test/')):
                route.fulfill(
                    status=200, content_type='text/html; charset=utf-8',
                    body=_page_html(ITEM_FINDER))
            elif url.endswith('/api/auth/me'):
                route.fulfill(json={'username': 'tester', 'role': 'member',
                                    'local_mode': True})
            elif url.endswith('/api/games'):
                route.fulfill(json={'games': ['CabalPC TH']})
            elif url.endswith('/api/modes'):
                route.fulfill(json={
                    'shop': {'web_mode': 'any', 'web_locked': False,
                             'read_desc': True}})
            elif url.endswith('/api/capabilities'):
                route.fulfill(json={'allow_headed': False})
            elif url.endswith('/api/aztek/status'):
                route.fulfill(json={'status': 'active'})
            elif url.endswith('/api/workspaces/workspace-1'):
                route.fulfill(json={
                    'workspace_id': 'workspace-1', 'mode': 'shop',
                    'game': 'CabalPC TH', 'filename': 'products.xlsx',
                    'count': 1, 'occurrence_count': 1, 'result_count': 1,
                    'items': [{'kind': '2', 'name': 'A recovered',
                               'sources': ['Product A'],
                               'group_keys': ['group-a']}],
                    'results': [{'aztek_id': '10', 'item_name': 'A old',
                                 'sources': ['Product A'],
                                 'group_keys': ['group-a']}],
                    'not_found': [['#1 Kind=2', 'missing']],
                    'running_job': None,
                })
            else:
                route.abort()

        context.route('http://tool.test/**', item_finder_app)
        page.goto(
            'http://tool.test/?workspace_id=workspace-1&source_group_key=group-a')
        page.wait_for_function(
            "typeof state === 'object' && state.workspaceId === 'workspace-1'")
        page.evaluate('startSearch(false,true)')
        page.evaluate("""() => {
          const send = message => window.lastSearchSocket.onmessage({
            data: JSON.stringify(message)});
          send({type:'reset_results'});
          send({type:'result',item:{aztek_id:'20',item_name:'A recovered',
            sources:['Product A'],group_keys:['group-a']}});
          send({type:'result',item:{aztek_id:'30',item_name:'B sibling',
            sources:['Product B'],group_keys:['group-b']}});
          send({type:'result',item:{aztek_id:'40',item_name:'Unscoped',
            sources:[],group_keys:[]}});
          send({type:'done',count:4,not_found:[]});
        }""")

        assert page.evaluate('state.results.map(row => row.aztek_id)') == ['20']
        assert page.locator('#resultsTable tbody tr').count() == 1
        assert page.locator('#resultsTable tbody').inner_text().count('B sibling') == 0
        assert page.locator('#resultsTable tbody').inner_text().count('Unscoped') == 0
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
        page.locator('#btnAddBundle').click()
        bundle = page.locator('.bundle-id-input')
        assert bundle.get_attribute('type') == 'text'
        assert bundle.get_attribute('inputmode') == 'numeric'
        assert bundle.is_visible()
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
            category_id:'12',bundle_ids:['223930','223931'],
            primary_bundle_id:'223931',bundle_id:'223931',
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
        assert b'"bundle_ids":["223930","223931"]' in body
        assert b'"primary_bundle_id":"223931"' in body
        assert b'"bundle_id":"223931"' in body
        browser.close()


def test_create_active_product_uses_only_matching_previewed_entry():
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
             prices:[{currency_id:'91',original_price:10,price:10}]},
            {source_group_key:'g2',name_th:'B',name_en:'B',
             category_id:'12',bundle_id:'200',
             start_at:'2026-07-30 00:00:00',
             end_at:'2026-08-30 07:59:00',
             limit_type:'UNLIMITED',price_candidates:[],
             prices:[{currency_id:'91',original_price:20,price:20}]}
          ], 'workspace-1');
          productQueue.active = productQueue.items[0].key;
          renderQueue();
          window.confirmText = '';
          window.confirm = text => { window.confirmText = text; return true; };
          window.sent = [];
          submitProducts = async (entries, doSave) => {
            window.sent.push({
              groups: entries.map(entry => entry.source_group_key), doSave});
            return {
              ok: true,
              json: async () => ({
                results:[{
                  client_key:entries[0].key,name:'A',saved:doSave,
                  made_id:doSave ? '501' : '',missing:[],error:null
                }],
                logs:[],created:doSave ? 1 : 0,planned:1
              })
            };
          };
          await runPreviewProduct();
          const unlocked = !document.querySelector('#btnCreateOne').disabled;
          await runActiveProduct();
          const first = productQueue.items.find(
            entry => entry.source_group_key === 'g1');
          return {
            confirmText: window.confirmText,
            sent: window.sent,
            unlocked,
            first: {status:first.status,product_id:first.product_id}
          };
        }""")

        assert '1 Product' in result['confirmText']
        assert result['unlocked'] is True
        assert result['sent'] == [
            {'groups': ['g1'], 'doSave': False},
            {'groups': ['g1'], 'doSave': True},
        ]
        assert result['first'] == {'status': 'created', 'product_id': '501'}
        browser.close()


def test_create_all_counts_and_submits_only_uncreated_products_in_queue_order():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        result = page.evaluate("""async () => {
          addDrafts([
            {source_group_key:'g1',name_th:'Already made',name_en:'Made',
             category_id:'12',bundle_id:'100',product_id:'500',
             start_at:'2026-07-30 00:00:00',
             end_at:'2026-08-30 07:59:00',
             limit_type:'UNLIMITED',price_candidates:[],
             prices:[{currency_id:'91',original_price:10,price:10}]},
            {source_group_key:'g2',name_th:'Second',name_en:'Second',
             category_id:'12',bundle_id:'200',
             start_at:'2026-07-30 00:00:00',
             end_at:'2026-08-30 07:59:00',
             limit_type:'UNLIMITED',price_candidates:[],
             prices:[{currency_id:'91',original_price:20,price:20}]},
            {source_group_key:'g3',name_th:'Third',name_en:'Third',
             category_id:'12',bundle_id:'300',
             start_at:'2026-07-30 00:00:00',
             end_at:'2026-08-30 07:59:00',
             limit_type:'UNLIMITED',price_candidates:[],
             prices:[{currency_id:'91',original_price:30,price:30}]}
          ], 'workspace-1');
          window.confirmText = '';
          window.confirm = text => { window.confirmText = text; return true; };
          window.sent = null;
          submitProducts = async (entries, doSave) => {
            window.sent = {
              groups:entries.map(entry => entry.source_group_key), doSave};
            return {
              ok:true,
              json:async () => ({
                results:entries.map((entry, index) => ({
                  client_key:entry.key,name:entry.name_th,saved:true,
                  made_id:String(601 + index),missing:[],error:null
                })),
                logs:[],created:entries.length,planned:entries.length
              })
            };
          };
          const buttonText = document.querySelector('#btnCreateAll').textContent;
          await runAllProducts();
          return {
            buttonText,
            confirmText:window.confirmText,
            sent:window.sent,
            ids:productQueue.items.map(entry => entry.product_id || '')
          };
        }""")

        assert '(2)' in result['buttonText']
        assert '2 Product' in result['confirmText']
        assert 'Second' in result['confirmText']
        assert 'Third' in result['confirmText']
        assert 'Already made' not in result['confirmText']
        assert result['sent'] == {
            'groups': ['g2', 'g3'], 'doSave': True}
        assert result['ids'] == ['500', '601', '602']
        browser.close()


def test_item_finder_only_exposes_the_plan_import_action():
    """The removed blue Template import must not return beside Plan import."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        _route_live_game_tools(context)
        page = context.new_page()
        page.goto('http://tool.test/', wait_until='domcontentloaded')

        assert page.locator('#btnImportTemplate').count() == 0
        assert page.locator('#btnImportPlan').count() == 1
        browser.close()


def test_bundle_deleted_item_can_be_restored_at_its_original_position():
    """Undo must restore the full row, not a blank replacement at the end."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        _route_live_game_tools(context)
        page = context.new_page()
        page.goto('http://tool.test/bundles', wait_until='domcontentloaded')
        page.wait_for_function("typeof state === 'object'")
        page.evaluate("""() => {
          state.queue = [{key:'b1',name:'Bundle A',type:'RANDOM',deliver:true,
            rewards:[],items:[
              {id:'101',name:'First',qty:'3',tier:'Epic',rate:'25',
               file_name:'First Doc',params:'เว็บ✓',doc_qty:'3'},
              {id:'202',name:'Second',qty:'1',tier:'Common',rate:'75'}
            ]}];
          select('b1');
        }""")

        page.locator(
            '#itemsTable tbody tr').nth(0).locator(
                'button[title="ตัดออกจากบันเดิลนี้"]').click()
        assert page.evaluate(
            "current().items.map(item => item.id)") == ['202']
        assert page.locator('#btnUndoItem').is_enabled()

        page.locator('#btnUndoItem').click()
        restored = page.evaluate("current().items[0]")
        assert [item['id'] for item in page.evaluate(
            "current().items")] == ['101', '202']
        assert {
            key: restored[key]
            for key in ('name', 'qty', 'tier', 'rate', 'file_name',
                        'params', 'doc_qty')
        } == {
            'name': 'First', 'qty': '3', 'tier': 'Epic', 'rate': '25',
            'file_name': 'First Doc', 'params': 'เว็บ✓', 'doc_qty': '3',
        }
        assert page.locator('#btnUndoItem').is_disabled()
        browser.close()


def test_product_page_has_no_tags_and_end_time_always_uses_second_59():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.evaluate("""() => {
          addDrafts([{source_group_key:'g1',name_th:'A',
            end_at:'2026-09-30 23:59:00',price_candidates:[],prices:[]}],
            'workspace-1');
          const input = document.querySelector('#endAt');
          input.value = '2026-10-31 20:30:00';
          input.dispatchEvent(new Event('input', {bubbles:true}));
        }""")

        assert page.locator('[data-product-section="tags"]').count() == 0
        assert page.locator('#endAt').input_value() == '2026-10-31 20:30:59'
        assert page.evaluate(
            "productQueue.current().end_at") == '2026-10-31 20:30:59'
        browser.close()


def test_thumbnail_name_updates_in_this_tab_and_other_open_product_tabs():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        _route_live_game_tools(context)
        first = context.new_page()
        first.goto('http://tool.test/products', wait_until='domcontentloaded')
        first.wait_for_function("productPageReady === true")
        first.evaluate("""addDrafts([{source_group_key:'g1',name_th:'A',
          image_names:{thumbnail_th:'old.png'},price_candidates:[],prices:[]}],
          'workspace-1')""")

        second = context.new_page()
        second.goto('http://tool.test/products', wait_until='domcontentloaded')
        second.wait_for_function("productPageReady === true")
        first.set_input_files('#thumbnailTh', {
            'name': 'latest-thumbnail.png',
            'mimeType': 'image/png',
            'buffer': b'latest image bytes',
        })

        assert first.locator('#thumbnailThName').inner_text() == (
            'latest-thumbnail.png')
        second.wait_for_function("""() =>
          document.querySelector('#thumbnailThName').textContent
            .includes('latest-thumbnail.png')""")
        assert second.evaluate("""productQueue.current()
          .image_names.thumbnail_th""") == 'latest-thumbnail.png'
        browser.close()


def test_each_product_currency_row_can_search_live_options_and_select_result():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _tool_page(browser)
        page.evaluate("""() => {
          optionState.currencies.options = [
            {id:'10',slug:'cash',label:'Cash'},
            {id:'11',slug:'cabalpcth-leaf-gem',label:'Leaf Gem'},
            {id:'12',slug:'wallet-point',label:'Wallet Point'}
          ];
          addDrafts([{source_group_key:'g1',name_th:'A',
            price_candidates:[{source_label:'กำหนดเอง',sale_price:100,
              original_price:100}],prices:[]}], 'workspace-1');
          renderProductOptions(productQueue.current());
        }""")

        search = page.locator('.currency-search')
        assert search.count() == 1
        search.fill('leaf')
        choices = page.locator('.currency-select option').all_text_contents()
        assert choices == ['เลือก Currency',
                           'cabalpcth-leaf-gem - Leaf Gem']
        page.locator('.currency-select').select_option('11')
        assert page.evaluate("""productQueue.current().prices[0]
          .currency_id""") == '11'
        browser.close()
