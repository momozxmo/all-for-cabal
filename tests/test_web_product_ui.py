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
