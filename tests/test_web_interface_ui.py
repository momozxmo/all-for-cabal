"""Rendered interface contracts; isolated browser data, no real Aztek calls."""
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import sync_playwright, expect
from test_web_product_ui import _route_live_game_tools

STATIC = Path(__file__).resolve().parents[1] / 'web' / 'static'


@pytest.fixture
def ui():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 360, 'height': 800})
        _route_live_game_tools(context)

        def asset(route):
            name = Path(urlsplit(route.request.url).path).name
            file = STATIC / name
            if not file.is_file():
                return route.abort()
            route.fulfill(path=str(file))

        context.route('**/static/**', asset)
        for name in ('account', 'login', 'local-start'):
            file = STATIC / (name.replace('-', '_') + '.html')
            context.route('http://tool.test/' + name + '*', lambda route, request, file=file:
                          route.fulfill(path=str(file)))
        page = context.new_page()
        yield page
        context.close()
        browser.close()


def test_mobile_product_prices_have_visible_and_accessible_labels(ui):
    ui.goto('http://tool.test/products')
    ui.wait_for_function('productPageReady === true')
    ui.locator('#btnQueueNew').click()
    ui.locator('#btnAddManualPrice').click()
    expect(ui.get_by_role('spinbutton', name='ราคาปกติ', exact=True)).to_be_visible()
    expect(ui.get_by_role('spinbutton', name='ราคาขาย', exact=True)).to_be_visible()
    expect(ui.locator('#priceMatches label').filter(has_text='ราคาปกติ')).to_be_visible()
    ui.get_by_role('spinbutton', name='ราคาปกติ', exact=True).fill('120')
    ui.get_by_role('spinbutton', name='ราคาขาย', exact=True).fill('99')
    assert ui.evaluate('productQueue.current().price_candidates[0].original_price') == '120'
    assert ui.evaluate('productQueue.current().price_candidates[0].sale_price') == '99'


def test_calendar_escape_closes_from_inside_and_restores_focus(ui):
    ui.goto('http://tool.test/products')
    ui.wait_for_function('productPageReady === true')
    ui.locator('#btnQueueNew').click()
    field = ui.locator('#endAt')
    before = field.input_value()
    field.press('Enter')
    pop = field.locator('..').locator('.dtpop')
    expect(pop).to_be_visible()
    pop.get_by_role('button', name='เดือนถัดไป').press('Escape')
    expect(pop).to_be_hidden()
    expect(field).to_be_focused()
    assert field.input_value() == before


@pytest.mark.parametrize('width', [360, 768, 1280, 1600])
@pytest.mark.parametrize('path', ['/', '/bundles', '/itemcodes', '/events', '/products'])
def test_navigation_keyboard_and_page_overflow(ui, path, width):
    ui.set_viewport_size({'width': width, 'height': 900})
    ui.goto('http://tool.test' + path)
    expect(ui.locator('#game option')).to_have_count(3)
    ui.keyboard.press('Tab')
    expect(ui.get_by_role('link', name='ข้ามไปพื้นที่ทำงาน')).to_be_focused()
    ui.keyboard.press('Enter')
    expect(ui.locator('#main-content')).to_be_focused()
    assert ui.evaluate('document.documentElement.scrollWidth <= innerWidth')
    expect(ui.locator('.spine [aria-current="page"]')).to_have_count(1)


def test_bundle_results_can_scroll_without_clipping(ui):
    ui.goto('http://tool.test/bundles')
    expect(ui.locator('#game option')).to_have_count(3)
    ui.evaluate("renderResults([{name:'ตัวอย่างชื่อบันเดิลที่ยาวสำหรับตรวจหน้าจอ',bundle_id:'225285',saved:true,added:1,total:1,rewards_total:0}],false)")
    box = ui.locator('#bundleResults')
    assert box.evaluate("e => getComputedStyle(e).overflowX") == 'auto'
    expect(box).to_have_attribute('tabindex', '0')
    assert ui.evaluate('document.documentElement.scrollWidth <= innerWidth')


def test_restored_product_failure_is_explained_next_to_queue(ui):
    ui.goto('http://tool.test/products')
    ui.wait_for_function('productPageReady === true')
    ui.evaluate("""addDrafts([{name_th:'ตัวอย่างทดสอบ',status:'failed',
        last_result:{saved:false,error:'ไม่พบ Bundle 42',missing:[]}}], '')""")
    expect(ui.locator('#selectedFeedback')).to_contain_text('ไม่พบ Bundle 42')
    assert ui.locator('#selectedFeedback').bounding_box()['y'] < ui.locator('#editor').bounding_box()['y']
    expect(ui.locator('#btnCreateAll')).to_be_enabled()
    ui.locator('#btnQueueNew').click()
    expect(ui.locator('#selectedFeedback')).not_to_contain_text('ไม่พบ Bundle 42')


def test_product_language_tabs_support_arrow_keys(ui):
    ui.goto('http://tool.test/products')
    ui.wait_for_function('productPageReady === true')
    ui.locator('#btnQueueNew').click()
    ui.locator('#detailTabs [data-tab=th]').press('ArrowRight')
    expect(ui.locator('#detailsEn')).to_be_visible()
    expect(ui.locator('#detailTabs [data-tab=en]')).to_be_focused()
    expect(ui.locator('#detailTabs [data-tab=en]')).to_have_attribute('aria-selected','true')


def test_populated_product_layout_and_calendar_fit_each_viewport(ui, tmp_path):
    ui.goto('http://tool.test/products')
    ui.wait_for_function('productPageReady === true')
    ui.evaluate("""addDrafts([{name_th:'ตัวอย่างทดสอบ แพ็กกิจกรรมประจำเดือน (ผูกมัด)',
      name_en:'Sample monthly pack',source_sheet:'ตัวอย่างสำหรับตรวจ Interface',
      start_at:'2026-09-01 00:00:00',end_at:'2026-09-30 23:59:59',
      bundle_ids:['225237','225238'],primary_bundle_id:'225237',
      price_candidates:[{source_label:'Wallet Point',original_price:'990',sale_price:'890'}],
      status:'failed',last_result:{error:'ตัวอย่างสถานะ: กรุณาตรวจ Currency',missing:[]}}], '')""")
    for width in (360,768,1280,1600):
        ui.set_viewport_size({'width':width,'height':900})
        assert ui.evaluate('document.documentElement.scrollWidth <= innerWidth')
        ui.locator('h1').scroll_into_view_if_needed()
        ui.screenshot(path=str(tmp_path / f'product-{width}.png'))
        ui.locator('[data-product-section=currency]').screenshot(path=str(tmp_path / f'prices-{width}.png'))
        field = ui.locator('#endAt')
        assert field.bounding_box()['width'] >= 220
        field.press('Enter')
        pop = field.locator('..').locator('.dtpop')
        expect(pop).to_be_visible()
        box = pop.bounding_box()
        assert box['x'] >= 0 and box['x'] + box['width'] <= width
        pop.get_by_role('button',name='เดือนถัดไป').press('Escape')
    print(f'Visual evidence: {tmp_path}')


@pytest.mark.parametrize('path', ['/account','/login','/local-start'])
def test_utility_pages_fit_mobile(ui, path, tmp_path):
    ui.goto('http://tool.test' + path)
    assert ui.evaluate('document.documentElement.scrollWidth <= innerWidth')
    ui.screenshot(path=str(tmp_path / 'utility.png'))
    if path == '/local-start':
        expect(ui.locator('h1')).to_have_text('เปิดโปรแกรมผ่าน Launcher')
        expect(ui.locator('#recovery')).to_be_visible()


@pytest.mark.parametrize('path', ['/bundles','/itemcodes','/events'])
def test_populated_editors_controls_are_not_clipped(ui, path, tmp_path):
    ui.goto('http://tool.test' + path)
    expect(ui.locator('#game option')).to_have_count(3)
    ui.locator('#btnQueueNew').click()
    expect(ui.locator('#editor')).to_be_visible()
    for width in (360,768,1280):
        ui.set_viewport_size({'width':width,'height':900})
        clipped = ui.locator('#editor input,#editor select,#editor button').evaluate_all('''nodes => nodes.filter(e => {
          const r = e.getBoundingClientRect();
          if (!r.width || !r.height || e.closest('.table-wrap')) return false;
          return r.right > innerWidth || r.left < 0;
        }).map(e=>e.id || e.outerHTML.slice(0,120))''')
        assert not clipped, clipped
        assert ui.evaluate('document.documentElement.scrollWidth <= innerWidth')
        if path == '/itemcodes':
            assert ui.locator('#editor textarea').first.bounding_box()['width'] >= 220
        if path == '/events':
            for field in ui.locator('#editor .dtpick').all():
                assert field.bounding_box()['width'] >= 220
        ui.locator('#editor').screenshot(path=str(tmp_path / f'editor-{width}.png'))
    print(f'Editor evidence {path}: {tmp_path}')


def test_account_return_link_preserves_tool_and_rejects_external_target(ui):
    ui.goto('http://tool.test/products')
    ui.locator('[data-account-link]').click()
    expect(ui.locator('.topbar > a')).to_have_attribute('href','/products')
    ui.goto('http://tool.test/account?from=https%3A%2F%2Fexample.org')
    expect(ui.locator('.topbar > a')).to_have_attribute('href','/')


def test_log_errors_open_disclosure_and_keyboard_can_toggle_it(ui):
    ui.goto('http://tool.test/itemcodes')
    expect(ui.locator('.log-details')).not_to_have_attribute('open','')
    ui.evaluate("log('ข้อความทดสอบข้อผิดพลาด', 'ERROR')")
    expect(ui.locator('.log-details')).to_have_attribute('open','')
    expect(ui.locator('#log')).to_contain_text('ข้อความทดสอบข้อผิดพลาด')
    ui.locator('.log-details summary').press('Enter')
    expect(ui.locator('#log')).to_be_hidden()
