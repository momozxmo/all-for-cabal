from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, expect

from test_web_bundle_import import workbook_bytes
from test_web_product_ui import _route_live_game_tools, PRODUCTS

STATIC = Path(__file__).resolve().parents[1] / 'web' / 'static'


def test_recheck_mismatch_pauses_remaining_queue_until_explicit_continue():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context()
        _route_live_game_tools(context)
        calls = []
        def saved(route):
            payload = route.request.post_data_json
            calls.append(payload)
            if len(calls) == 2:
                assert [row['client_key'] for row in payload['bundles']] == ['b']
                route.fulfill(json={'created': 1, 'planned': 1, 'results': [{
                    'client_key': 'b', 'name': 'Later', 'saved': True, 'bundle_id': '43',
                    'added': 1, 'total': 1, 'rewards_total': 0,
                    'recheck': {'outcome': 'passed', 'incomplete': False}}]})
                return
            assert payload['bundles'][0]['document_reference']['filename'] == 'source.xlsx'
            route.fulfill(json={'created': 1, 'planned': 2, 'results': [{
                'client_key': 'a', 'name': 'First', 'saved': True, 'bundle_id': '42',
                'added': 1, 'total': 1, 'rewards_total': 0,
                'recheck': {'outcome': 'mismatch', 'incomplete': False,
                            'actual': {'items': [{'id': '99', 'qty': '1'}]},
                            'coverage': {'properties': '4/4', 'saved_rows': '1/1'},
                            'rows': [{'source_row': 7, 'original': {'kind': '123', 'option': '0', 'duration': '9', 'qty': '1'},
                                      'submitted': {'id': '11', 'qty': '1'},
                                      'actual': {'id': '99', 'kind': '999', 'option': '0', 'duration': '9', 'qty': '1'},
                                      'different': ['kind', 'id']}]}}]})
        context.route('**/api/bundles/run', saved)
        page = context.new_page()
        page.goto('http://tool.test/bundles')
        page.wait_for_function("document.querySelectorAll('#game option').length === 3")
        page.evaluate("""localStorage.setItem('afc.bundleQueue', JSON.stringify([
          {key:'a',name:'First',type:'FIXED',deliver:true,rewards:[],items:[{id:'11',qty:'1'}],document_reference:{filename:'source.xlsx',items:[]}},
          {key:'b',name:'Later',type:'FIXED',deliver:true,rewards:[],items:[{id:'12',qty:'1'}]}
        ]))""")
        page.reload()
        page.on('dialog', lambda dialog: dialog.accept())
        page.click('#btnCreateAll')
        expect(page.locator('#queueCount')).to_have_text('1')
        expect(page.locator('#bundleResults')).to_contain_text('ไม่ตรง')
        expect(page.locator('#bundleResults')).to_contain_text('แถว 7')
        expect(page.locator('#bundleResults')).to_contain_text('ItemKind, Item ID')
        expect(page.locator('#bundleResults')).to_contain_text('4/4')
        expect(page.locator('#btnCreateAll')).to_be_disabled()
        expect(page.locator('#handoff')).to_be_hidden()
        page.reload()
        expect(page.locator('#btnCreateAll')).to_be_disabled()
        page.click('#btnContinueQueue')
        expect(page.locator('#btnCreateAll')).to_be_enabled()
        assert page.evaluate("JSON.parse(localStorage.getItem('afc.bundleResults'))[0].recheck.outcome") == 'mismatch'
        page.click('#btnCreateAll')
        expect(page.locator('#queueCount')).to_have_text('0')
        results = page.evaluate("JSON.parse(localStorage.getItem('afc.bundleResults'))")
        assert [(r['client_key'], r['recheck']['outcome']) for r in results] == [
            ('a', 'mismatch'), ('b', 'passed')]
        made = page.evaluate("JSON.parse(localStorage.getItem('afc.bundleMade'))")
        assert [r['bundle_id'] for r in made] == ['43']
        browser.close()


def test_recheck_history_recovery_and_read_only_retry():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context()
        _route_live_game_tools(context)
        calls = []
        job = {'id': 'job42', 'game': 'CabalM TH', 'client_key': 'one',
               'name': 'Recovered', 'bundle_id': '42',
               'submitted_values': {'game': 'CabalM TH', 'items': [], 'rewards': []},
               'result': {'name': 'Recovered', 'saved': True, 'bundle_id': '42',
                          'recheck': {'outcome': 'mismatch', 'incomplete': False}},
               'history': [{'checked_at': '2026-09-23T01:00:00Z', 'bundle_id': '42',
                            'game': 'CabalM TH', 'name': 'Recovered', 'outcome': 'mismatch',
                            'coverage': {'saved_rows': '1/1'},
                            'document_reference': {'items': [], 'rewards': []},
                            'submitted_values': {'items': [], 'rewards': []},
                            'actual': {'items': [], 'rewards': []}}]}
        context.route('**/api/bundles/rechecks',
                      lambda route: route.fulfill(json={'rows': [job]}))
        def retry(route):
            calls.append(route.request.post_data_json)
            job['result'] = {'name': 'Recovered', 'saved': True, 'bundle_id': '42',
                             'recheck': {'outcome': 'passed', 'incomplete': False}}
            job['history'].append({'checked_at': '2026-09-23T02:00:00Z',
                                   'bundle_id': '42', 'name': 'Recovered',
                                   'game': 'CabalM TH', 'outcome': 'passed'})
            route.fulfill(json=job['result'])
        context.route('**/api/bundles/rechecks/job42/retry', retry)
        context.route('**/api/bundles/run',
                      lambda _route: pytest.fail('retry must not create a Bundle'))
        page = context.new_page()
        page.goto('http://tool.test/bundles')
        expect(page.locator('#bundleResults')).to_contain_text('Recovered')
        expect(page.locator('#handoff')).to_be_hidden()
        expect(page.locator('#recheckHistory')).to_contain_text('mismatch')
        page.select_option('#recheckFilter', 'passed')
        expect(page.locator('#recheckHistory')).to_contain_text('ยังไม่มีประวัติ')
        page.select_option('#recheckFilter', 'all')
        page.locator('#bundleResults .submitted-reference > summary').click()
        page.locator('#bundleResults .submitted-reference > button').first.click()
        expect(page.locator('#runMsg')).to_contain_text('passed')
        expect(page.locator('#handoff')).to_be_visible()
        assert calls == [{'bundle_id': '42'}]
        browser.close()


def test_recheck_failure_from_another_game_does_not_pause_current_queue():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context()
        _route_live_game_tools(context)
        page = context.new_page()
        page.goto('http://tool.test/bundles')
        page.wait_for_function("document.querySelectorAll('#game option').length === 3")
        page.select_option('#game', 'CabalPC TH')
        page.evaluate("""() => {
          state.results=[{client_key:'old',name:'Other game',
            submitted_values:{game:'CabalPC TH'},
            recheck:{outcome:'mismatch',incomplete:false}}];
          state.queue=[{key:'new',name:'Current game',type:'FIXED',deliver:true,
            items:[{id:'91',qty:'1'}],rewards:[]}];
          state.active='new';paintRunButtons();
        }""")
        expect(page.locator('#btnCreateAll')).to_be_disabled()
        page.select_option('#game', 'CabalM TH')
        expect(page.locator('#btnCreateAll')).to_be_enabled()
        expect(page.locator('#btnContinueQueue')).to_be_hidden()
        browser.close()


def test_nonpass_handoff_requires_separate_confirmation():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context()
        _route_live_game_tools(context)
        page = context.new_page()
        page.goto('http://tool.test/bundles')
        page.wait_for_function("document.querySelectorAll('#game option').length === 3")
        page.evaluate("""localStorage.setItem('afc.bundleResults', JSON.stringify([{
          client_key:'one',name:'Not verified',saved:true,bundle_id:'42',
          submitted_values:{game:'CabalM TH',items:[],rewards:[]},
          recheck:{outcome:'partial',incomplete:true}
        }]))""")
        page.reload()
        expect(page.locator('#handoff')).to_be_hidden()
        page.locator('#bundleResults .submitted-reference > summary').click()
        override=page.locator('#bundleResults .submitted-reference > button')
        expect(override).to_be_visible()
        page.once('dialog', lambda dialog: dialog.dismiss())
        override.click()
        expect(page.locator('#handoff')).to_be_hidden()
        page.once('dialog', lambda dialog: dialog.accept())
        override.click()
        expect(page.locator('#handoff')).to_be_visible()
        assert page.evaluate("JSON.parse(localStorage.getItem('afc.bundleResults'))[0].recheck.outcome") == 'partial'
        browser.close()


@pytest.mark.parametrize('width', [360, 1280])
def test_recheck_history_filter_keyboard_and_overflow(width):
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={'width': width, 'height': 800})
        _route_live_game_tools(context)
        page = context.new_page()
        page.goto('http://tool.test/bundles')
        page.evaluate("""state.history=[{name:'Long Bundle Name '.repeat(15),game:'CabalM TH',
          history:[{checked_at:'2026-09-23T01:00:00Z',bundle_id:'42',outcome:'partial',
          error:'อ่านแถวที่ 2 ไม่สำเร็จ',
          coverage:{saved_rows:'1/2'},document_reference:{items:[{id:'91',qty:'1'}],rewards:[]},
          submitted_values:{items:[{id:'91',qty:'1'}],rewards:[]},
          actual:{items:[{id:'91',qty:'1'}],rewards:[]}}]}];renderRecheckHistory()""")
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.locator('#recheckFilter').focus()
        page.keyboard.press('End')
        page.locator('#recheckFilter').select_option('partial')
        expect(page.locator('#recheckHistory > details')).to_have_count(1)
        page.locator('#recheckHistory > details > summary').focus()
        page.keyboard.press('Enter')
        expect(page.locator('#recheckHistory > details')).to_have_attribute('open', '')
        expect(page.locator('#recheckHistory')).to_contain_text('ค่าที่บันทึกจริง')
        expect(page.locator('#recheckHistory')).to_contain_text('อ่านแถวที่ 2 ไม่สำเร็จ')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        browser.close()


@pytest.mark.parametrize('target,button', [
    ('/itemcodes', '#btnToItemCode'), ('/events', '#btnToEvent'),
    ('/products', '#btnToProduct'),
])
def test_passed_bundle_handoff_reaches_each_next_tool(target, button):
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context()
        _route_live_game_tools(context)
        context.route('http://tool.test/products?*', lambda route: route.fulfill(
            status=200, content_type='text/html; charset=utf-8',
            body=PRODUCTS.read_text(encoding='utf-8')))
        page = context.new_page()
        page.goto('http://tool.test/bundles')
        page.wait_for_function("document.querySelectorAll('#game option').length === 3")
        page.evaluate("""state.results=[{client_key:'one',name:'Passed',saved:true,bundle_id:'42',
          submitted_values:{game:'CabalM TH'},recheck:{outcome:'passed',incomplete:false}}];
          offerHandoff(state.results)""")
        expect(page.locator('#handoff')).to_be_visible()
        page.locator(button).click()
        page.wait_for_url(lambda url: url.startswith('http://tool.test' + target))
        browser.close()


def test_restart_with_unknown_create_id_requires_manual_recovery_not_create():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context()
        _route_live_game_tools(context)
        job = {'id': 'pending42', 'client_key': 'one', 'game': 'CabalM TH',
               'name': 'Pending', 'bundle_id': None,
               'submitted_values': {'game': 'CabalM TH', 'name': 'Pending',
                                    'items': [{'id': '91', 'qty': '1'}], 'rewards': []},
               'result': {'name': 'Pending', 'saved': False, 'bundle_id': None,
                          'creation_uncertain': True,
                          'recheck': {'outcome': 'pending', 'incomplete': True}},
               'history': []}
        context.route('**/api/bundles/rechecks',
                      lambda route: route.fulfill(json={'rows': [job]}))
        calls = []
        def retry(route):
            calls.append(route.request.post_data_json)
            job['result'] = {'name': 'Pending', 'saved': True, 'bundle_id': '42',
                             'creation_uncertain': False,
                             'recheck': {'outcome': 'passed', 'incomplete': False}}
            route.fulfill(json=job['result'])
        context.route('**/api/bundles/rechecks/pending42/retry', retry)
        context.route('**/api/bundles/run',
                      lambda _route: pytest.fail('recovery must not call create'))
        page = context.new_page()
        page.goto('http://tool.test/bundles')
        page.wait_for_function("document.querySelectorAll('#game option').length === 3")
        page.evaluate("""localStorage.setItem('afc.bundleQueue', JSON.stringify([{
          key:'one',name:'Pending',type:'FIXED',deliver:true,creation_pending:true,
          items:[{id:'91',qty:'1'}],rewards:[]
        }]))""")
        page.reload()
        expect(page.locator('#btnCreateAll')).to_be_disabled()
        expect(page.locator('#bundleResults')).to_contain_text('Pending')
        page.locator('#bundleResults .submitted-reference > summary').click()
        page.once('dialog', lambda dialog: dialog.accept('42'))
        page.locator('#bundleResults .submitted-reference > button').click()
        expect(page.locator('#queueCount')).to_have_text('0')
        expect(page.locator('#handoff')).to_be_visible()
        assert calls == [{'bundle_id': '42'}]
        browser.close()


@pytest.mark.parametrize('response_kind', ['http_failure', 'api_uncertain'])
def test_unknown_create_response_keeps_queue_locked_across_reload(response_kind):
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context()
        _route_live_game_tools(context)
        requests = []
        def failed(route):
            requests.append(route.request.url)
            if response_kind == 'http_failure':
                route.fulfill(status=502, json={'detail': 'ผลการสร้างไม่ชัดเจน'})
            else:
                route.fulfill(json={'created': 0, 'planned': 1, 'results': [{
                    'client_key': 'a', 'name': 'First', 'saved': False, 'bundle_id': None,
                    'creation_uncertain': True, 'recheck': {'outcome': 'pending', 'incomplete': True},
                    'added': 1, 'total': 1, 'rewards_added': 0, 'rewards_total': 0}]})
        context.route('**/api/bundles/run', failed)
        page = context.new_page()
        page.goto('http://tool.test/bundles')
        page.wait_for_function("document.querySelectorAll('#game option').length === 3")
        page.evaluate("""localStorage.setItem('afc.bundleQueue', JSON.stringify([
          {key:'a',name:'First',type:'FIXED',deliver:true,rewards:[],items:[{id:'11',qty:'1'}]}
        ]))""")
        page.reload()
        page.on('dialog', lambda dialog: dialog.accept())
        page.click('#btnCreateAll')
        expect(page.locator('#queueCount')).to_have_text('1')
        assert page.evaluate("JSON.parse(localStorage.getItem('afc.bundleQueue'))[0].creation_pending") is True
        page.reload()
        expect(page.locator('#btnCreateAll')).to_be_disabled()
        expect(page.locator('#btnContinueQueue')).to_be_hidden()
        assert len(requests) == 1
        browser.close()


def test_only_fully_rechecked_bundle_is_offered_for_handoff():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context()
        _route_live_game_tools(context)
        context.route('**/api/bundles/run', lambda route: route.fulfill(json={
            'created': 1, 'planned': 1, 'results': [{
                'client_key': 'a', 'name': 'First', 'saved': True, 'bundle_id': '42',
                'added': 1, 'total': 1, 'rewards_total': 0,
                'recheck': {'outcome': 'passed', 'incomplete': False}}]}))
        page = context.new_page()
        page.goto('http://tool.test/bundles')
        page.wait_for_function("document.querySelectorAll('#game option').length === 3")
        page.evaluate("""localStorage.setItem('afc.bundleQueue', JSON.stringify([
          {key:'a',name:'First',type:'FIXED',deliver:true,rewards:[],items:[{id:'11',qty:'1'}]}
        ]))""")
        page.reload()
        page.on('dialog', lambda dialog: dialog.accept())
        page.click('#btnCreateAll')
        expect(page.locator('#handoff')).to_be_visible()
        page.reload()
        expect(page.locator('#handoff')).to_be_visible()
        browser.close()


def test_submitted_values_survive_successful_queue_removal():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        _route_live_game_tools(context)
        def saved(route):
            page.fill('#bundleName', 'Edited while creating')
            route.fulfill(json={'created': 1, 'planned': 1, 'results': [
                {'name': 'Pack', 'saved': True, 'bundle_id': '123', 'added': 1, 'total': 1}]})
        context.route('**/api/bundles/run', saved)
        page = context.new_page()
        page.goto('http://tool.test/bundles')
        page.wait_for_function("document.querySelectorAll('#game option').length === 3")
        page.evaluate("""localStorage.setItem('afc.bundleQueue', JSON.stringify([{
          key:'a',name:'Pack',type:'FIXED',deliver:true,rewards:[],
          items:[{id:'11',qty:'2',tier:'Rare'}],
          document_reference:{version:1,game:'CabalM TH',filename:'old.xlsx',items:[{id:'11',qty:'1'}],rewards:[]}
        }]))""")
        page.reload()
        page.on('dialog', lambda dialog: dialog.accept())
        page.click('#btnCreateAll')
        expect(page.locator('#queueCount')).to_have_text('0')
        page.reload()
        page.get_by_text('ข้อมูลที่ส่งสร้าง: Pack', exact=True).click()
        expect(page.locator('.submitted-reference')).to_contain_text('old.xlsx')
        submitted_row = page.locator('.submitted-reference details').filter(has=page.get_by_text('ค่าที่ส่งสร้าง', exact=True)).locator('tbody tr').first
        expect(submitted_row.locator('td').nth(2)).to_have_text('2')
        result = page.evaluate("JSON.parse(localStorage.getItem('afc.bundleResults'))[0]")
        assert result['submitted_values']['items'][0]['qty'] == '2'
        assert result['document_reference']['items'][0]['qty'] == '1'
        assert result['document_reference']['filename'] == 'old.xlsx'
        browser.close()


def test_select_sheet_preview_then_append_once_and_preserve_existing_queue(client):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        _route_live_game_tools(context)
        context.route('**/static/bundle_import.js', lambda route: route.fulfill(
            content_type='application/javascript',
            body=(STATIC / 'bundle_import.js').read_text(encoding='utf-8')
            if (STATIC / 'bundle_import.js').exists() else ''))

        def import_route(route):
            response = client.post('/api/bundles/import',
                content=route.request.post_data_buffer,
                headers={'content-type': route.request.headers['content-type']})
            route.fulfill(status=response.status_code, json=response.json())

        context.route('**/api/bundles/import', import_route)
        page = context.new_page()
        page.goto('http://tool.test/bundles')
        page.wait_for_function("document.querySelectorAll('#game option').length === 3")
        page.click('#btnQueueNew')
        page.fill('#bundleName', 'Existing')
        page.locator('#bundleName').dispatch_event('input')
        payload = workbook_bytes([
            ('wrong', [['Other', 999, 1]], False),
            ('เลือก แท็บนี้', [['Pack A', 11, 2, 'Rare', '<img src=x onerror=alert(1)>'],
                             ['Pack B', 11, 4]], False)])
        expect(page.locator('#bundleImportFile')).to_have_count(1)
        page.set_input_files('#bundleImportFile', {
            'name': 'bundle.xlsx', 'mimeType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'buffer': payload})
        page.click('#btnBundleImportRead')
        expect(page.locator('#bundleImportSheet option')).to_have_count(2)
        page.select_option('#bundleImportSheet', label='เลือก แท็บนี้')
        page.click('#btnBundleImportPreview')
        expect(page.locator('#bundleImportPreview')).to_contain_text('Pack A')
        expect(page.locator('#bundleImportPreview')).to_contain_text('Pack B')
        expect(page.locator('#bundleImportPreview')).to_contain_text('<img src=x onerror=alert(1)>')
        expect(page.locator('#bundleImportPreview img')).to_have_count(0)
        assert len(page.evaluate("JSON.parse(localStorage.getItem('afc.bundleQueue'))")) == 1
        page.click('#btnBundleImportAdd')
        expect(page.locator('#queueCount')).to_have_text('3')
        expect(page.locator('#btnBundleImportAdd')).to_be_disabled()
        queue = page.evaluate("JSON.parse(localStorage.getItem('afc.bundleQueue'))")
        assert [b['name'] for b in queue] == ['Existing', 'Pack A', 'Pack B']
        assert [b['items'][0]['qty'] for b in queue[1:]] == ['2', '4']
        assert [b['items'][0]['id'] for b in queue[1:]] == ['11', '11']
        expect(page.locator('#documentReference')).to_contain_text('bundle.xlsx')
        expect(page.locator('#documentReference')).to_contain_text('ไม่มีข้อมูลอ้างอิง')
        page.locator('#itemsTable tbody tr').first.locator('input[type=number]').first.fill('9')
        original = page.locator('#documentReference details').filter(has=page.get_by_text('ต้นฉบับ', exact=True))
        expect(original.locator('tbody tr').first.locator('td').nth(2)).to_have_text('2')
        reference = page.evaluate("JSON.parse(localStorage.getItem('afc.bundleQueue'))[1].document_reference")
        assert reference['items'][0]['qty'] == '2'
        assert reference['sheet'] == 'เลือก แท็บนี้'
        assert reference['game']
        page.reload()
        expect(page.locator('#queueCount')).to_have_text('3')
        page.select_option('#queuePick', queue[1]['key'])
        expect(page.locator('#documentReference')).to_contain_text('bundle.xlsx')
        expect(page.locator('#itemsTable tbody tr').first.locator('input[type=number]').first).to_have_value('9')
        assert page.evaluate("JSON.parse(localStorage.getItem('afc.bundleQueue'))[1].document_reference") == reference

        # A valid preview cannot survive switching to an invalid sheet/file/game.
        page.set_input_files('#bundleImportFile', {
            'name': 'invalid.xlsx', 'mimeType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'buffer': workbook_bytes([
                ('Valid', [['Next', 22, 1]], False),
                ('Invalid', [['Bad', '', 1]], False)])})
        page.click('#btnBundleImportRead')
        expect(page.locator('#bundleImportSheet option')).to_have_count(2)
        page.click('#btnBundleImportPreview')
        expect(page.locator('#btnBundleImportAdd')).to_be_enabled()
        page.select_option('#bundleImportSheet', label='Invalid')
        expect(page.locator('#btnBundleImportAdd')).to_be_disabled()
        page.click('#btnBundleImportPreview')
        expect(page.locator('#bundleImportMsg')).to_contain_text('Item ID')
        expect(page.locator('#btnBundleImportAdd')).to_be_disabled()
        page.select_option('#bundleImportSheet', label='Valid')
        page.click('#btnBundleImportPreview')
        page.select_option('#game', 'CabalPC TH')
        expect(page.locator('#btnBundleImportAdd')).to_be_disabled()
        page.click('#btnBundleImportPreview')

        # A full browser store must leave the existing queue untouched.
        page.evaluate("""() => {
          window.originalSetItem = Storage.prototype.setItem;
          Storage.prototype.setItem = function(key, value) {
            if(key === 'afc.bundleQueue') throw new DOMException('Full', 'QuotaExceededError');
            return window.originalSetItem.call(this, key, value);
          };
        }""")
        page.click('#btnBundleImportAdd')
        expect(page.locator('#bundleImportMsg')).to_contain_text('พื้นที่บันทึก')
        expect(page.locator('#queueCount')).to_have_text('3')
        page.evaluate('() => { Storage.prototype.setItem = window.originalSetItem; }')
        page.click('#btnBundleImportAdd')
        expect(page.locator('#queueCount')).to_have_text('4')

        # The existing run workflow identifies completed bundles by name.
        # Import must show a unique name before adding, never discard another bundle.
        page.set_input_files('#bundleImportFile', {
            'name': 'collision.xlsx', 'mimeType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'buffer': workbook_bytes([('Names', [['Existing', 44, 1]], False),
                                      ('Same name', [['Existing', 55, 1]], False)])})
        page.click('#btnBundleImportRead')
        expect(page.locator('#bundleImportSheet option')).to_have_count(2)
        page.click('#btnBundleImportPreview')
        expect(page.locator('#bundleImportPreview')).to_contain_text('Existing (2)')
        # Queue edits during preview must not reintroduce duplicate names.
        page.click('#btnQueueNew')
        page.fill('#bundleName', 'Existing (2)')
        page.locator('#bundleName').dispatch_event('input')
        page.click('#btnBundleImportAdd')
        expect(page.locator('#queueCount')).to_have_text('5')
        expect(page.locator('#btnBundleImportAdd')).to_be_disabled()
        page.click('#btnBundleImportPreview')
        expect(page.locator('#bundleImportPreview')).to_contain_text('Existing (3)')
        page.click('#btnBundleImportAdd')
        expect(page.locator('#queueCount')).to_have_text('6')
        page.select_option('#bundleImportSheet', label='Same name')
        page.click('#btnBundleImportPreview')
        expect(page.locator('#bundleImportPreview')).to_contain_text('Existing (4)')
        page.click('#btnBundleImportAdd')
        expect(page.locator('#queueCount')).to_have_text('7')
        browser.close()
