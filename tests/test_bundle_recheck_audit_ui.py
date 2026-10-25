"""Operator-visible Recheck audit regressions; all traffic stays in fixtures."""
import asyncio

import pytest
from playwright.sync_api import expect, sync_playwright

from test_web_product_ui import _route_live_game_tools
from web.bundle_recheck import recheck_saved_bundle


@pytest.mark.parametrize('width', [360, 1280])
@pytest.mark.parametrize('surface', ['latest', 'history'])
def test_problem_filter_keeps_unverified_currency_code_without_history_limitations(
        monkeypatch, width, surface):
    reference = dict(game='Cabal PC', items=[], rewards=[dict(
        type='DEBIT', value='cabalpcth-pirate-coin - Pirate Coin', qty='2', tier='Common')])
    submitted = dict(game='Cabal PC', type='FIXED', items=[], rewards=reference['rewards'])
    async def saved(*_):
        return dict(items=[], rewards=[dict(type='DEBIT', value='Pirate Coin', qty='2', tier='Common')],
                    complete=True, unsupported=[])
    monkeypatch.setattr('web.bundle_recheck.read_saved_bundle', saved)
    checked = asyncio.run(recheck_saved_bundle(None, 'https://aztek.test/bundles/42', reference, submitted))
    assert checked['outcome'] == 'partial' and checked['incomplete']
    assert checked['rows'][0]['different'] == []
    # Current history serialization persists rows/actual but not limitations/differences.
    attempt = {key: checked[key] for key in ('outcome', 'incomplete', 'rows', 'actual',
                                             'document_reference', 'submitted_values')}
    attempt.update(bundle_id='42', game='Cabal PC', checked_at='2026-10-25T07:00:00Z')
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={'width': width, 'height': 800})
        _route_live_game_tools(context)
        context.route('**/api/bundles/run', lambda _: pytest.fail('filter must not create'))
        page = context.new_page()
        page.goto('http://tool.test/bundles')
        page.wait_for_load_state('networkidle')
        page.evaluate("""data => {
          state.results=[{name:'Currency',submitted_values:data.checked.submitted_values,recheck:data.checked}];
          state.history=[{name:'Currency',game:'Cabal PC',history:[data.attempt]}];
          renderResults(state.results,false);renderRecheckHistory();
        }""", dict(checked=checked, attempt=attempt))
        before = page.evaluate('JSON.stringify([state.results,state.history])')
        panel = page.locator('#bundleResults > details.submitted-reference' if surface == 'latest'
                             else '#recheckHistory > details')
        panel.locator(':scope > summary').click()
        expect(panel.locator('.recheck-comparison tbody tr')).to_have_count(1)
        panel.get_by_role('checkbox', name='แสดงเฉพาะแถวที่มีปัญหาหรือข้อมูลไม่ครบ').check()
        expect(panel.locator('.recheck-comparison tbody tr')).to_have_count(1)
        expect(panel.locator('.recheck-comparison')).to_contain_text('Pirate Coin')
        expect(panel.get_by_text('ยังตรวจไม่ครบทุกส่วน — ห้ามถือว่าผ่านครบ', exact=True)).to_be_visible()
        assert page.evaluate('JSON.stringify([state.results,state.history])') == before
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        browser.close()


@pytest.mark.parametrize('width', [360, 1280])
def test_legacy_history_without_aligned_rows_keeps_original_snapshots(width):
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={'width': width, 'height': 800})
        _route_live_game_tools(context)
        page = context.new_page()
        page.goto('http://tool.test/bundles')
        page.wait_for_load_state('networkidle')
        page.evaluate("""() => {
          state.history=[{name:'Legacy',game:'CabalM TH',history:[{
            bundle_id:'42',outcome:'partial',incomplete:true,
            document_reference:{items:[{kind:'123',option:'0',duration:'9',qty:'1'}],rewards:[]},
            submitted_values:{items:[{id:'91',qty:'1'}],rewards:[]},
            actual:{items:[{id:'91',kind:'123',option:'0',duration:'9',qty:'1'}],rewards:[]}
          }]}];renderRecheckHistory();
        }""")
        panel = page.locator('#recheckHistory > details')
        panel.locator(':scope > summary').click()
        for label in ('ต้นฉบับ', 'ค่าที่ส่งสร้าง', 'ค่าที่บันทึกจริง'):
            expect(panel).to_contain_text(label)
        expect(panel.locator('.recheck-comparison')).to_have_count(0)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        browser.close()


@pytest.mark.parametrize('width', [360, 1280])
@pytest.mark.parametrize('explanation', ['differences', 'error', 'limitations'])
def test_incomplete_warning_is_separate_from_other_recheck_explanation(width, explanation):
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={'width': width, 'height': 800})
        _route_live_game_tools(context)
        context.route('**/api/bundles/run', lambda _: pytest.fail('render must not create'))
        page = context.new_page()
        page.goto('http://tool.test/bundles')
        page.wait_for_function("document.querySelectorAll('#game option').length === 3")
        page.wait_for_load_state('networkidle')
        page.evaluate("""kind => {
          const checked={outcome:'mismatch',incomplete:true,rows:[]};
          if(kind==='differences')checked.differences=['document_items'];
          if(kind==='error')checked.error='อ่านรายการที่สองไม่ได้';
          if(kind==='limitations')checked.limitations=['saved_currency_code_not_visible'];
          state.results=[{name:'Incomplete result',submitted_values:{game:'CabalM TH',items:[],rewards:[]},recheck:checked}];
          renderResults(state.results,false);
        }""", explanation)
        detail = page.locator('#bundleResults > details.submitted-reference')
        detail.locator(':scope > summary').click()
        expect(detail.get_by_text('ยังตรวจไม่ครบทุกส่วน — ห้ามถือว่าผ่านครบ', exact=True)).to_be_visible()
        expected = {'differences': 'คุณสมบัติหรือจำนวนต่างจากเอกสาร',
                    'error': 'อ่านรายการที่สองไม่ได้',
                    'limitations': 'จึงยืนยันรหัส Currency ไม่ได้'}
        expect(detail).to_contain_text(expected[explanation])
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        browser.close()


@pytest.mark.parametrize('width', [360, 1280])
@pytest.mark.parametrize('surface', ['latest', 'history'])
def test_problem_row_filter_preserves_unknowns_and_saved_history(width, surface, tmp_path):
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={'width': width, 'height': 800})
        _route_live_game_tools(context)
        context.route('**/api/bundles/run', lambda _: pytest.fail('filter must not create'))
        page = context.new_page()
        page.goto('http://tool.test/bundles')
        page.wait_for_function("document.querySelectorAll('#game option').length === 3")
        page.wait_for_load_state('networkidle')
        page.evaluate("""() => {
          const rows=[
            {source_row:7,original:{kind:'123',option:'0',duration:'9',qty:'1',tier:'Common'},
             submitted:{id:'91',qty:'1',tier:'Common'},actual:{id:'91',kind:'123',option:'0',duration:'9',qty:'1',tier:'Common'},different:[]},
            {source_row:8,original:{kind:'456',option:'0',duration:'9',qty:'1',tier:'Common'},
             submitted:{id:'92',qty:'1',tier:'Common'},actual:{id:'92',kind:'456',option:'0',duration:'9',qty:'2',tier:'Common'},different:['qty']},
            {source_row:9,original:{kind:'789',option:'0',duration:'9',qty:'1',tier:'Rare'},
             submitted:{id:'93',qty:'1',tier:'Rare'},actual:{id:'93',kind:'789',option:'0',duration:'9',qty:'1'},different:[]}
          ];
          const reference={game:'CabalM TH',items:rows.map(r=>r.original),rewards:[]};
          const submitted={game:'CabalM TH',items:rows.map(r=>r.submitted),rewards:[]};
          const checked={outcome:'mismatch',incomplete:true,differences:['document_items'],rows,
            actual:{items:rows.map(r=>r.actual),rewards:[],complete:false,unsupported:[]},
            document_reference:reference,submitted_values:submitted};
          state.results=[{name:'Row comparison',document_reference:reference,submitted_values:submitted,recheck:checked}];
          state.history=[{name:'Row comparison',game:'CabalM TH',history:[{...checked,bundle_id:'42',checked_at:'2026-10-25T07:00:00Z'}]}];
          renderResults(state.results,false);renderRecheckHistory();
        }""")
        before = page.evaluate('JSON.stringify([state.results,state.history,localStorage.getItem("afc.bundleResults")])')
        panel = page.locator('#bundleResults > details.submitted-reference' if surface == 'latest'
                             else '#recheckHistory > details')
        panel.locator(':scope > summary').click()
        toggle = panel.get_by_role('checkbox', name='แสดงเฉพาะแถวที่มีปัญหาหรือข้อมูลไม่ครบ')
        expect(toggle).to_be_visible()
        table_rows = panel.locator('.recheck-comparison tbody tr')
        expect(table_rows).to_have_count(3)
        toggle.focus()
        page.keyboard.press('Space')
        expect(toggle).to_be_checked()
        expect(table_rows).to_have_count(2)
        expect(table_rows.nth(0)).to_contain_text('แถว 8')
        expect(table_rows.nth(1)).to_contain_text('แถว 9')
        expect(panel.get_by_text('ยังตรวจไม่ครบทุกส่วน — ห้ามถือว่าผ่านครบ', exact=True)).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(tmp_path / f'recheck-{surface}-{width}.png'), full_page=True)
        page.keyboard.press('Space')
        expect(table_rows).to_have_count(3)
        assert page.evaluate('JSON.stringify([state.results,state.history,localStorage.getItem("afc.bundleResults")])') == before
        # Filtered empty is an explicit state, not a blank table or deleted history.
        page.evaluate("""() => {
          state.results[0].recheck.rows=state.results[0].recheck.rows.slice(0,1);
          state.history[0].history[0].rows=state.history[0].history[0].rows.slice(0,1);
          renderResults(state.results,false);renderRecheckHistory();
        }""")
        panel.locator(':scope > summary').click()
        panel.get_by_role('checkbox', name='แสดงเฉพาะแถวที่มีปัญหาหรือข้อมูลไม่ครบ').check()
        expect(panel.locator('.recheck-comparison tbody tr')).to_have_count(0)
        expect(panel.get_by_text('ไม่มีแถวที่มีปัญหาหรือข้อมูลไม่ครบ', exact=True)).to_be_visible()
        browser.close()
