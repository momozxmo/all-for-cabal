# -*- coding: utf-8 -*-
"""Browser-level Mastercode WR behavior through the Item Code page seam."""
import re
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
ITEMCODES = ROOT / 'web' / 'static' / 'itemcodes.html'
CONSOLE = ROOT / 'web' / 'static' / 'console.js'
SHEET_PICKER = ROOT / 'web' / 'static' / 'sheet_picker.js'
GAME_SYNC = ROOT / 'web' / 'static' / 'game_sync.js'


def _page(browser):
    html = ITEMCODES.read_text(encoding='utf-8')
    scripts = {
        r'<script src="/static/console\.js(?:\?[^\"]*)?"></script>':
            CONSOLE.read_text(encoding='utf-8'),
        r'<script src="/static/sheet_picker\.js"></script>':
            SHEET_PICKER.read_text(encoding='utf-8'),
        r'<script src="/static/game_sync\.js"></script>':
            GAME_SYNC.read_text(encoding='utf-8'),
    }
    for pattern, source in scripts.items():
        html = re.sub(pattern, lambda _match, code=source:
                      '<script>%s</script>' % code, html)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    page.set_content(html, wait_until='domcontentloaded')
    page.wait_for_function("typeof showSheets === 'function'")
    page.evaluate("""() => {
      const game = document.getElementById('game');
      if (![...game.options].some(option => option.value === 'CabalM TH')) {
        game.add(new Option('CabalM TH', 'CabalM TH'));
      }
      game.value = 'CabalM TH';
    }""")
    return page


def _draft(name, *, mastercode='ALPHA001', bundle_id='224728',
           usage_limit='200', source_id='pending:0:1:2'):
    return {
        'name_th': name, 'name_en': name,
        'slug': '1-master-code-120726-code-1-alpha001-mth',
        'uses_per_user': '1', 'limited': bool(usage_limit),
        'quantity': usage_limit, 'remaining': usage_limit,
        'start_time': '2026-07-12T00:00:00',
        'end_time': '2026-07-12T23:59:59', 'group': '',
        'rewards': [{
            'name_th': name, 'name_en': name, 'uses_per_user': '1',
            'limited': bool(usage_limit), 'quantity': usage_limit,
            'remaining': usage_limit, 'code_type': '1',
            'code_list': mastercode, 'prefix': '', 'num_codes': '',
            'bundle_id': bundle_id,
        }],
        'wr_base_header': 'Master Code 12/07/26 - Code 1',
        'wr_sequence': 1, 'wr_game': 'CabalM TH',
        'wr_auto_names': True, 'wr_auto_slug': True,
        'wr_source_id': source_id,
    }


def _row(name, *, game='CabalM TH', ready=True, selectable=True,
         selected=True, mastercode='ALPHA001', bundle_id='224728',
         usage_limit='200', source_id='pending:0:1:2'):
    issues = [] if ready else ['ยังไม่มี Mastercode']
    return {
        'source_id': source_id, 'sheet': '12.07 M', 'block': 'Code 1',
        'game': game, 'name': name,
        'start_time': '2026-07-12T00:00:00',
        'end_time': '2026-07-12T23:59:59',
        'mastercode': mastercode, 'bundle_id': bundle_id,
        'usage_limit': usage_limit, 'ready': ready,
        'selectable': selectable, 'selected': selected,
        'issues': issues, 'warnings': [],
        'disabled_reason': '' if selectable else 'เกมไม่ตรงกับหน้าปัจจุบัน',
        'draft': _draft(
            name, mastercode=mastercode, bundle_id=bundle_id,
            usage_limit=usage_limit, source_id=source_id),
    }


def test_mastercode_wr_import_selects_sheets_previews_and_adds_without_run():
    name = '1. Master Code 12/07/26 - Code 1 - ALPHA001'
    rows = [
        _row(name),
        _row('1. Master Code 12/07/26 - Code 1 - PC001',
             game='CabalPC TH', selectable=False, selected=False,
             mastercode='PC001', source_id='pending:0:20:2'),
        _row('2. Master Code 12/07/26 - Code 2 - [ยังไม่มี Mastercode]',
             ready=False, selected=False, mastercode='',
             source_id='pending:0:38:2'),
    ]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _page(browser)
        page.evaluate("""rows => {
          window.wrApiCalls = [];
          window.apiFetch = async (url, options = {}) => {
            const form = options.body instanceof FormData ? options.body : null;
            wrApiCalls.push({
              url,
              importMode: form ? form.get('import_mode') : null,
              body: typeof options.body === 'string' ? JSON.parse(options.body) : null
            });
            if (url === '/api/itemcodes/import') return {
              ok: true, json: async () => ({
                import_mode: 'mastercode_wr', pending_id: 'pending',
                workspace_id: 'workspace',
                sheets: [{name:'12.07 M', display_name:'12.07 M', count:3}]
              })
            };
            if (url === '/api/itemcodes/import/apply') return {
              ok: true, json: async () => ({
                import_mode: 'mastercode_wr', preview_rows: rows, skipped: []
              })
            };
            throw new Error('unexpected API ' + url);
          };
        }""", rows)

        assert page.locator('#btnImportWr').inner_text().strip() == \
            '📥 Import Mastercode WR'
        page.locator('#wrFile').set_input_files({
            'name': 'wr.xlsx',
            'mimeType': 'application/vnd.openxmlformats-officedocument.'
                        'spreadsheetml.sheet',
            'buffer': b'fake workbook',
        })
        page.locator('#sheetDialog[open]').wait_for()
        assert page.locator('#sheetList input').get_attribute('value') == '12.07 M'
        page.locator('#btnSheetTake').click()
        page.locator('#wrPreviewDialog[open]').wait_for()

        headers = page.locator('#wrPreviewTable thead th').all_inner_texts()
        assert headers == [
            'เลือก', 'Sheet / Block', 'เกม', 'Mastercode WR Name',
            'เริ่ม', 'สิ้นสุด', 'Mastercode', 'Bundle ID', 'Usage Limit',
            'ความพร้อม',
        ]
        checks = page.locator('#wrPreviewTable tbody input[type=checkbox]')
        assert checks.count() == 3
        assert checks.nth(0).is_checked()
        assert checks.nth(1).is_disabled()
        assert not checks.nth(2).is_checked()
        assert not checks.nth(2).is_disabled()
        assert page.locator('#wrCapacity').inner_text() == 'เหลือที่ว่าง 30 รายการ'

        page.evaluate("""() => {
          game.add(new Option('CabalPC TH', 'CabalPC TH'));
          game.value = 'CabalPC TH';
          game.dispatchEvent(new Event('change', {bubbles:true}));
        }""")
        assert page.locator(
            '#wrPreviewTable tbody input[type=checkbox]').nth(0).is_disabled()
        assert not page.locator(
            '#wrPreviewTable tbody input[type=checkbox]').nth(1).is_disabled()
        page.evaluate("""() => {
          game.value = 'CabalM TH';
          game.dispatchEvent(new Event('change', {bubbles:true}));
        }""")
        page.locator(
            '#wrPreviewTable tbody input[type=checkbox]').nth(0).check()

        page.locator('#btnWrAdd').click()
        assert page.evaluate('queue.items.length') == 1
        assert page.evaluate('queue.items[0].rewards[0].bundle_id') == '224728'
        assert page.evaluate('queue.items[0].limited') is True
        assert page.evaluate('queue.items[0].quantity') == '200'
        assert page.evaluate(
            "wrApiCalls.filter(call => call.url === '/api/itemcodes/run').length") == 0
        assert page.evaluate('wrApiCalls[0].importMode') == 'mastercode_wr'
        assert page.evaluate('wrApiCalls[1].body.selected_sheets') == ['12.07 M']

        page.evaluate("""() => {
          game.value = 'CabalPC TH';
          game.dispatchEvent(new Event('change', {bubbles:true}));
        }""")
        page.locator('#btnPreview').click()
        assert page.evaluate(
            "wrApiCalls.filter(call => call.url === '/api/itemcodes/run').length") == 0
        assert 'CabalM TH' in page.locator('#runMsg').inner_text()
        browser.close()


def test_mastercode_wr_incomplete_draft_auto_updates_until_manual_override():
    placeholder = '1. Master Code 12/07/26 - Code 1 - [ยังไม่มี Mastercode]'
    row = _row(
        placeholder, ready=False, selected=False, mastercode='',
        source_id='pending:0:1:2')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _page(browser)
        page.evaluate("rows => openWrPreview(rows)", [row])
        check = page.locator('#wrPreviewTable tbody input[type=checkbox]')
        check.check()
        page.locator('#btnWrAdd').click()

        codes = page.locator('#rsets textarea')
        codes.fill('NEWCODE')
        assert page.locator('#nameTh').input_value().endswith('- NEWCODE')
        assert page.locator('#nameEn').input_value().endswith('- NEWCODE')
        assert page.locator('#slug').input_value().endswith('-newcode-mth')
        reward_names = page.locator('#rsets input[type=text]')
        assert reward_names.nth(0).input_value().endswith('- NEWCODE')
        assert reward_names.nth(1).input_value().endswith('- NEWCODE')

        page.locator('#nameTh').fill('Manual Name')
        codes.fill('NEXTCODE')
        assert page.locator('#nameTh').input_value() == 'Manual Name'
        assert page.locator('#nameEn').input_value().endswith('- NEWCODE')
        assert page.locator('#slug').input_value().endswith('-nextcode-mth')

        page.locator('#slug').fill('manual-slug')
        codes.fill('FINALCODE')
        assert page.locator('#nameTh').input_value() == 'Manual Name'
        assert page.locator('#slug').input_value() == 'manual-slug'
        browser.close()


def test_mastercode_wr_rejects_queue_overflow_and_duplicate_source():
    first = _row('1. Master Code 12/07/26 - Code 1 - ONE')
    second = _row(
        '2. Master Code 12/07/26 - Code 2 - TWO', mastercode='TWO',
        source_id='pending:0:20:2')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = _page(browser)
        page.evaluate("""() => {
          queue.clear();
          for (let i = 0; i < 29; i++) queue.add(blankCode('existing ' + i));
          select(queue.items[0].key);
        }""")
        page.evaluate("rows => openWrPreview(rows)", [first, second])
        assert page.locator('#wrCapacity').inner_text() == 'เหลือที่ว่าง 1 รายการ'
        page.locator('#btnWrAdd').click()
        assert page.evaluate('queue.items.length') == 29
        assert 'เลือกได้อีกไม่เกิน 1 รายการ' in page.locator(
            '#runMsg').inner_text()

        page.evaluate('queue.clear(); select("")')
        page.evaluate("rows => openWrPreview(rows)", [first])
        page.locator('#btnWrAdd').click()
        assert page.evaluate('queue.items.length') == 1
        page.evaluate("rows => openWrPreview(rows)", [first])
        page.locator('#btnWrAdd').click()
        assert page.evaluate('queue.items.length') == 1
        assert 'อยู่ในคิวแล้ว' in page.locator('#runMsg').inner_text()
        browser.close()
