# -*- coding: utf-8 -*-
"""Visible browser regressions for searchable workbook sheet pickers."""
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SHARED_JS = ROOT / 'web' / 'static' / 'sheet_picker.js'
SHARED_CSS = ROOT / 'web' / 'static' / 'sheet_picker.css'
CONSOLE_JS = ROOT / 'web' / 'static' / 'console.js'
PAGES = {
    'products': ROOT / 'web' / 'static' / 'products.html',
    'events': ROOT / 'web' / 'static' / 'events.html',
    'itemcodes': ROOT / 'web' / 'static' / 'itemcodes.html',
    'index': ROOT / 'web' / 'static' / 'index.html',
}


def _shared_source():
    return SHARED_JS.read_text(encoding='utf-8') if SHARED_JS.exists() else ''


def _shared_css():
    return SHARED_CSS.read_text(encoding='utf-8') if SHARED_CSS.exists() else ''


def _synthetic_picker_html(names=None):
    names = names or ('Promotion July', 'Cash Shop July', 'Guild Reward')
    rows = ''.join(
        '<label class="sheet-row" data-sheet-name="{name}">'
        '<input type="checkbox" checked>'
        '<span class="sheet-name">{name}</span></label>'.format(name=name)
        for name in names
    )
    return f"""<!doctype html>
    <html><head><style>
      :root{{--muted:#777}}
      #sheetList{{display:grid;gap:6px;width:280px}}
      .sheet-row{{display:flex;gap:8px;padding:8px;border:1px solid #555}}
      {_shared_css()}
    </style></head><body>
      <div class="sheet-search-tools">
        <input id="sheetSearch" type="search">
        <span id="sheetSearchCount"></span>
      </div>
      <button id="sheetAll" type="button">all</button>
      <button id="sheetNone" type="button">none</button>
      <div id="sheetList">{rows}</div>
      <div id="sheetSearchEmpty" hidden>ไม่พบ Sheet ที่ค้นหา</div>
      <script>
        function createPickerForTest() {{
          window.sheetPickerSearch = createSheetPickerSearch({{
            list: document.getElementById('sheetList'),
            input: document.getElementById('sheetSearch'),
            count: document.getElementById('sheetSearchCount'),
            empty: document.getElementById('sheetSearchEmpty'),
            selectAllButton: document.getElementById('sheetAll'),
            clearButton: document.getElementById('sheetNone')
          }});
          sheetPickerSearch.refresh(true);
        }}
      </script>
    </body></html>"""


def _open_synthetic(browser, names=None):
    page = browser.new_page()
    page.set_content(_synthetic_picker_html(names))
    page.evaluate(_shared_source())
    page.evaluate("createPickerForTest()")
    return page


def _real_page_html(page_name):
    html = PAGES[page_name].read_text(encoding='utf-8')
    html = html.replace(
        '<link rel="stylesheet" href="/static/sheet_picker.css">',
        '<style>%s</style>' % _shared_css(),
    )
    if '/static/sheet_picker.css' not in html:
        html = html.replace('</head>', '<style>%s</style></head>' % _shared_css())
    html = html.replace(
        '<script src="/static/console.js"></script>',
        '<script>%s</script>' % CONSOLE_JS.read_text(encoding='utf-8'),
    )
    helper_tag = '<script src="/static/sheet_picker.js"></script>'
    if helper_tag in html:
        html = html.replace(helper_tag, '<script>%s</script>' % _shared_source())
    else:
        html = html.replace('<script>', '<script>%s</script><script>' % _shared_source(), 1)
    return html


def _open_real_picker(browser, page_name, sheets):
    page = browser.new_page(viewport={'width': 900, 'height': 760})
    page.set_content(_real_page_html(page_name), wait_until='domcontentloaded')
    if page_name == 'products':
        page.wait_for_function("typeof openProductSheetPicker === 'function'")
        page.evaluate("sheets => openProductSheetPicker({pending_id:'p1', "
                      "workspace_id:'w1', sheets})", sheets)
    elif page_name in ('events', 'itemcodes'):
        page.wait_for_function("typeof showSheets === 'function'")
        page.evaluate("sheets => showSheets(sheets)", sheets)
    else:
        page.wait_for_function("typeof openSheetPicker === 'function'")
        page.evaluate("sheets => openSheetPicker(sheets)", sheets)
    return page


def test_shared_picker_filters_immediately_and_reports_visible_count():
    """Removing the helper must break live filtering, not merely a source check."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _open_synthetic(browser)

        page.locator('#sheetSearch').fill('cash')

        assert page.locator('.sheet-row:visible').all_text_contents() == [
            'Cash Shop July'
        ]
        assert page.locator('#sheetSearchCount').inner_text() == '1 / 3 Sheet'
        browser.close()


def test_shared_picker_bulk_buttons_change_only_visible_rows():
    """A filtered bulk action must not change checked sheets outside the view."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _open_synthetic(browser)

        page.locator('#sheetSearch').fill('cash')
        page.locator('#sheetNone').click()
        page.locator('#sheetSearch').fill('')

        assert page.locator('.sheet-row input').evaluate_all(
            '(boxes) => boxes.map(box => box.checked)') == [True, False, True]
        browser.close()


def test_shared_picker_shows_empty_state_without_losing_checks():
    """No-match feedback must not clear any selected sheet."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _open_synthetic(browser)

        page.locator('#sheetSearch').fill('missing')

        assert page.locator('#sheetSearchCount').inner_text() == '0 / 3 Sheet'
        assert page.locator('#sheetSearchEmpty').is_visible()
        assert page.locator('.sheet-row input').evaluate_all(
            '(boxes) => boxes.map(box => box.checked)') == [True, True, True]
        browser.close()


def test_long_sheet_name_wraps_without_ellipsis_or_horizontal_overflow():
    """A long visible sheet name must wrap instead of being clipped."""
    long_name = (
        'SEA Community Mission War '
        'ExtremelyLongActivityNameThatMustRemainFullyReadableWithoutClipping2026'
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _open_synthetic(browser, (long_name,))
        name = page.locator('.sheet-name')

        metrics = name.evaluate("""node => {
          const style = getComputedStyle(node);
          return {
            text: node.textContent,
            scrollHeight: node.scrollHeight,
            lineHeight: parseFloat(style.lineHeight) || 16,
            scrollWidth: node.scrollWidth,
            clientWidth: node.clientWidth,
            whiteSpace: style.whiteSpace,
            overflowWrap: style.overflowWrap,
            textOverflow: style.textOverflow
          };
        }""")

        assert metrics['text'] == long_name
        assert metrics['scrollHeight'] > metrics['lineHeight'] * 1.5
        assert metrics['scrollWidth'] <= metrics['clientWidth'] + 1
        assert metrics['whiteSpace'] == 'normal'
        assert metrics['overflowWrap'] == 'anywhere'
        assert metrics['textOverflow'] != 'ellipsis'
        browser.close()


@pytest.mark.parametrize('page_name', ['products', 'events', 'itemcodes'])
def test_tool_sheet_picker_searches_as_the_operator_types(page_name):
    """Every creation page must expose and apply the same live search."""
    sheets = [
        {'name': 'Promotion July', 'count': 2, 'product_count': 2},
        {'name': 'Cash Shop July', 'count': 1, 'product_count': 1},
        {'name': 'Guild Reward', 'count': 3, 'product_count': 1},
    ]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _open_real_picker(browser, page_name, sheets)

        assert page.locator('#sheetSearch').count() == 1
        page.locator('#sheetSearch').fill('CASH')

        assert page.locator('#sheetList .sheet-row:visible').count() == 1
        assert 'Cash Shop July' in page.locator(
            '#sheetList .sheet-row:visible').inner_text()
        assert page.locator('#sheetSearchCount').inner_text() == '1 / 3 Sheet'
        browser.close()


@pytest.mark.parametrize('page_name', ['index', 'products', 'events', 'itemcodes'])
def test_sheet_picker_displays_searches_and_submits_exact_sheet_name(page_name):
    """The visible and submitted identity must be the real worksheet tab."""
    tab_name = 'ID COM Cabal Community Quiz ! "'
    derived_name = 'Cabal Community Quiz ! "Where am i now?"'
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _open_real_picker(browser, page_name, [{
            'name': tab_name,
            'display_name': derived_name,
            'count': 5,
            'product_count': 1,
        }])

        visible = page.locator('#sheetList .sheet-name').inner_text()
        assert tab_name in visible
        assert derived_name not in visible
        page.locator('#sheetSearch').fill('where am i now')
        assert page.locator('#sheetList .sheet-row:visible').count() == 0
        page.locator('#sheetSearch').fill('ID COM Cabal')
        assert page.locator('#sheetList .sheet-row:visible').count() == 1
        assert page.locator('#sheetList input').get_attribute('value') == tab_name
        browser.close()


def test_product_filtered_clear_changes_only_the_visible_sheet():
    """Product bulk controls must not clear checked hidden sheets."""
    sheets = [
        {'name': 'Promotion July', 'count': 2, 'product_count': 2},
        {'name': 'Cash Shop July', 'count': 1, 'product_count': 1},
        {'name': 'Guild Reward', 'count': 3, 'product_count': 1},
    ]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _open_real_picker(browser, 'products', sheets)

        assert page.locator('#sheetSearch').count() == 1
        page.locator('#sheetSearch').fill('cash')
        page.locator('#btnClearSheets').click()
        page.locator('#sheetSearch').fill('')

        assert page.locator('#sheetList input').evaluate_all(
            '(boxes) => boxes.map(box => box.checked)') == [True, False, True]
        browser.close()


def test_item_finder_sheet_picker_searches_as_the_operator_types():
    """Item Finder must share the same immediate sheet filter."""
    sheets = [
        {'name': 'Promotion July', 'count': 2},
        {'name': 'Cash Shop July', 'count': 1},
        {'name': 'Guild Reward', 'count': 3},
    ]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _open_real_picker(browser, 'index', sheets)

        assert page.locator('#sheetSearch').count() == 1
        page.locator('#sheetSearch').fill('guild')

        assert page.locator('#sheetList .sheet-row:visible').count() == 1
        assert 'Guild Reward' in page.locator(
            '#sheetList .sheet-row:visible').inner_text()
        assert page.locator('#sheetSearchCount').inner_text() == '1 / 3 Sheet'
        browser.close()


def test_item_finder_shows_the_complete_long_sheet_name():
    """The real Item Finder dialog must visibly wrap the complete sheet name."""
    long_name = (
        'SEA Community Mission War '
        'ExtremelyLongActivityNameThatMustRemainFullyReadableWithoutClipping2026'
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _open_real_picker(browser, 'index', [
            {'name': long_name, 'count': 8},
        ])
        page.set_viewport_size({'width': 520, 'height': 720})
        name = page.locator('#sheetList .sheet-name')

        assert name.count() == 1
        metrics = name.evaluate("""node => {
          const style = getComputedStyle(node);
          return {
            text: node.textContent,
            scrollHeight: node.scrollHeight,
            lineHeight: parseFloat(style.lineHeight) || 16,
            scrollWidth: node.scrollWidth,
            clientWidth: node.clientWidth,
            overflowWrap: style.overflowWrap,
            textOverflow: style.textOverflow
          };
        }""")

        assert long_name in metrics['text']
        assert metrics['scrollHeight'] > metrics['lineHeight'] * 1.5
        assert metrics['scrollWidth'] <= metrics['clientWidth'] + 1
        assert metrics['overflowWrap'] == 'anywhere'
        assert metrics['textOverflow'] != 'ellipsis'
        browser.close()
