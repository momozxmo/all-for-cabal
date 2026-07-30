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
