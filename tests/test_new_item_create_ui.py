"""Operator UI through real local APIs/runner; only external Aztek is routed."""
import pytest
from playwright.sync_api import expect

from test_new_item_create_flow import GAME, boundary, prepare, premium_saved_html, receipt, run
from test_new_item_import_api import workbook_bytes
from test_new_item_ui import operator_page
from test_web_validation import _connect_aztek


@pytest.mark.parametrize('width', [1280, 390])
@pytest.mark.parametrize('game', ['CabalM TH', 'CabalPC TH', 'CabalPC SEA', 'CabalM SEA'])
def test_create_selected_mth_confirm_cancel_then_readback_and_selected_handoff(
        client, test_database, monkeypatch, operator_page, width, game, tmp_path):
    _connect_aztek(client)
    page, local_requests = operator_page
    page.set_viewport_size({'width': width, 'height': 900 if width == 1280 else 844})
    page.goto('http://tool.test/new-items?game=' + game.replace(' ', '%20'))
    content = workbook_bytes([('นำเข้าที่เลือก', [['Synthetic name', 123, 0, 0, 'GENERAL', False,
                                                 'Synthetic description']]),
                              ('ไม่เอา', [['Not selected', 999, 0, 0, 'GENERAL', False]])])
    page.get_by_label('ไฟล์ Excel').set_input_files({'name': 'synthetic.xlsx', 'mimeType':
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'buffer': content})
    page.get_by_role('button', name='ดู Sheet ก่อนนำเข้า', exact=True).click()
    sheets = page.get_by_role('dialog', name='เลือก Sheet ที่จะเพิ่มร่าง')
    sheets.get_by_label('นำเข้าที่เลือก · 1 แถว', exact=True).check()
    sheets.get_by_role('button', name='เพิ่มร่างที่เลือก', exact=True).click()
    page.get_by_label('เลือกร่าง', exact=True).check()
    page.get_by_role('button', name='ยืนยันร่างที่เลือก', exact=True).click()
    page.get_by_role('dialog', name='ยืนยันร่าง', exact=True).get_by_role(
        'button', name='ยืนยันร่าง', exact=True).click()
    from test_new_item_existing_api import boundary as search_boundary
    search_requests, unexpected = search_boundary(monkeypatch, game, empty=True)
    page.get_by_role('button', name='ค้นหา Item เดิม', exact=True).click()
    expect(page.get_by_text('ไม่พบ Item เดิมที่ตรงสามค่า หากต้องการสร้างใหม่ ให้เลือกและยืนยันเองด้านล่าง', exact=True)).to_be_visible()
    assert search_requests and not unexpected
    pick = page.get_by_role('checkbox', name='เลือกสร้างใหม่ Synthetic name', exact=True)
    expect(pick).not_to_be_checked()
    create = page.get_by_role('button', name='สร้าง Item ที่เลือก', exact=True)
    expect(create).to_be_disabled()
    identity = client.get('/api/new-items/history').json()['rows'][0]['id']
    observed = boundary(monkeypatch, test_database, identity, game=game)
    pick.focus()
    pick.press('Space')
    create.focus()
    create.press('Enter')
    dialog = page.get_by_role('dialog', name='ยืนยันสร้าง Item ใหม่', exact=True)
    expect(dialog).to_contain_text(game)
    expect(dialog).to_contain_text('1 รายการ')
    expect(dialog).to_contain_text('Synthetic name')
    expect(dialog).to_contain_text('Kind 123 / Option 0 / Duration 0')
    expect(dialog).to_contain_text('คำอธิบาย: Synthetic description')
    expect(dialog.get_by_role('button', name='ยืนยันสร้าง', exact=True)).to_be_focused()
    page.screenshot(path=str(tmp_path / f'create-confirm-{width}.png'), full_page=True)
    page.keyboard.press('Escape')
    expect(dialog).not_to_be_visible()
    expect(create).to_be_focused()
    assert not any(method == 'POST' and path.endswith('/run') for method, path in local_requests)
    assert not observed['posts']
    create.click()
    dialog.get_by_role('button', name='ยืนยันสร้าง', exact=True).click()
    expect(page.locator('#historyRows').get_by_text('Item ID: 91', exact=True)).to_be_visible(timeout=15000)
    expect(page.locator('#historyRows').get_by_text('ตรวจผ่านครบ', exact=True)).to_be_visible()
    assert len(observed['posts']) == 1 and not observed['unexpected']
    before = len(observed['posts'])
    page.reload()
    expect(page.locator('#historyRows').get_by_text('Item ID: 91', exact=True)).to_be_visible()
    assert len(observed['posts']) == before
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(tmp_path / f'create-result-{width}.png'), full_page=True)
    page.get_by_role('checkbox', name='เลือกแถว นำเข้าที่เลือก:2 — จำนวน ไม่ระบุ', exact=True).check()
    page.get_by_role('button', name='ส่งแถวที่เลือกไป Finder', exact=True).click()
    page.wait_for_url('http://tool.test/')
    assert len(observed['posts']) == 1


def test_mismatch_requires_ack_then_new_unselected_scope_not_auto_next(
        client, test_database, monkeypatch, operator_page):
    from test_new_item_reader import saved_html
    first, frozen = prepare(client)
    second, _ = prepare(client, name='Second item')
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, first['id'], saved=saved_html(GAME).replace(
        'value="Synthetic name"', 'value="Changed"').replace('aria-checked="false"', 'aria-checked="mixed"'))
    # First create through the public API to exercise the exact stopped-queue state.
    response = run(client, first, second)
    assert response.status_code == 200, response.text
    page, requests = operator_page
    page.goto('http://tool.test/new-items?game=CabalM%20TH')
    expect(page.get_by_text('ข้อมูลไม่ตรง', exact=True)).to_be_visible()
    expect(page.get_by_text('ยังตรวจไม่ครบทุกส่วน', exact=True)).to_be_visible()
    next_pick = page.get_by_role('checkbox', name='เลือกสร้างใหม่ Second item', exact=True)
    expect(next_pick).not_to_be_checked()
    next_pick.check()
    create = page.get_by_role('button', name='สร้าง Item ที่เลือก', exact=True)
    expect(create).to_be_disabled()
    page.get_by_role('button', name='รับทราบ/ข้ามรายการนี้', exact=True).click()
    expect(page.get_by_text('รับทราบแล้ว — ผลตรวจและสิทธิ์ส่งต่อไม่เปลี่ยน', exact=True)).to_be_visible()
    expect(next_pick).not_to_be_checked()
    assert len(observed['posts']) == 1
    next_pick.check()
    expect(create).to_be_enabled()
    create.click()
    page.get_by_role('dialog', name='ยืนยันสร้าง Item ใหม่', exact=True).get_by_role(
        'button', name='ยกเลิก', exact=True).click()
    assert len(observed['posts']) == 1
    row = {r['id']: r for r in client.get('/api/new-items/history').json()['rows']}[first['id']]
    assert row['frozen'] == frozen and row['result']['recheck']['outcome'] == 'mismatch'
    assert not any(method == 'POST' and path.endswith('/run') for method, path in requests)


def test_lost_tool_response_and_double_click_do_not_repeat_create(
        client, test_database, monkeypatch, operator_page):
    entry, _ = prepare(client)
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entry['id'])
    page, requests = operator_page
    def lose_tool_response(route):
        request = route.request
        requests.append((request.method, '/api/new-items/run'))
        # The real endpoint/runner completes, but the operator's HTTP response is lost.
        result = client.post('/api/new-items/run', content=request.post_data_buffer,
                             headers={'Content-Type': 'application/json'})
        assert result.status_code == 200, result.text
        route.abort()
    page.route('http://tool.test/api/new-items/run', lose_tool_response)
    page.goto('http://tool.test/new-items?game=CabalM%20TH')
    page.get_by_role('checkbox', name='เลือกสร้างใหม่ Synthetic name', exact=True).check()
    page.get_by_role('button', name='สร้าง Item ที่เลือก', exact=True).click()
    page.get_by_role('button', name='ยืนยันสร้าง', exact=True).evaluate('el=>{el.click();el.click();}')
    expect(page.get_by_text('ยังสรุปผลคำขอไม่ได้', exact=True)).to_be_visible(timeout=15000)
    expect(page.locator('#newNotice')).to_contain_text('อย่ากดสร้างซ้ำ')
    expect(page.locator('#newNotice')).not_to_contain_text('ลองใหม่')
    expect(page.get_by_text('Item ID: 91', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='สร้าง Item ที่เลือก', exact=True)).to_be_disabled()
    page.get_by_role('button', name='โหลดประวัติใหม่', exact=True).click()
    expect(page.get_by_text('Item ID: 91', exact=True)).to_be_visible()
    page.reload()
    expect(page.get_by_text('Item ID: 91', exact=True)).to_be_visible()
    assert requests.count(('POST', '/api/new-items/run')) == 1
    assert len(observed['posts']) == 1 and not observed['unexpected']


def test_confirmed_scope_keeps_its_game_when_picker_changes(client, test_database, monkeypatch, operator_page):
    entry, frozen = prepare(client)
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entry['id'])
    page, requests = operator_page
    page.goto('http://tool.test/new-items')
    expect(page.get_by_role('button', name='สร้าง Item ที่เลือก', exact=True)).to_be_disabled()
    expect(page.get_by_role('checkbox', name='เลือกสร้างใหม่ Synthetic name', exact=True)).to_have_count(0)
    page.get_by_label('เกมของรายการ', exact=True).select_option(GAME)
    page.get_by_role('checkbox', name='เลือกสร้างใหม่ Synthetic name', exact=True).check()
    page.get_by_role('button', name='สร้าง Item ที่เลือก', exact=True).click()
    # Another control/state change cannot rewrite the already confirmed scope.
    page.locator('#newGame').evaluate("el=>{el.value='CabalPC SEA';el.dispatchEvent(new Event('change'));}")
    dialog = page.get_by_role('dialog', name='ยืนยันสร้าง Item ใหม่', exact=True)
    expect(dialog).to_contain_text('CabalM TH')
    dialog.get_by_role('button', name='ยืนยันสร้าง', exact=True).click()
    expect(dialog).not_to_be_visible(timeout=15000)
    page.get_by_label('เกมของรายการ', exact=True).select_option(GAME)
    expect(page.get_by_text('Item ID: 91', exact=True)).to_be_visible()
    row = client.get('/api/new-items/history').json()['rows'][0]
    assert row['frozen'] == frozen and row['frozen']['game'] == GAME
    assert requests.count(('POST', '/api/new-items/run')) == 1
    assert len(observed['posts']) == 1 and not observed['unexpected']


@pytest.mark.parametrize('game', ['CabalPC TH', 'CabalPC SEA'])
@pytest.mark.parametrize('width', [1280, 390])
def test_pc_premium_operator_confirms_exact_type_and_reads_it_back(
        client, test_database, monkeypatch, operator_page, tmp_path, game, width):
    entry, frozen = prepare(client, game=game, item_type='CABALPC_PREMIUM')
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entry['id'], game=game,
        response=receipt(game=game, game_item_type='CABALPC_PREMIUM'), saved=premium_saved_html(game))
    page, requests = operator_page
    page.set_viewport_size({'width': width, 'height': 900 if width == 1280 else 844})
    page.goto('http://tool.test/new-items?game=' + game.replace(' ', '%20'))
    pick = page.get_by_role('checkbox', name='เลือกสร้างใหม่ Synthetic name', exact=True)
    expect(pick).not_to_be_checked()
    pick.check()
    create = page.get_by_role('button', name='สร้าง Item ที่เลือก', exact=True)
    create.click()
    dialog = page.get_by_role('dialog', name='ยืนยันสร้าง Item ใหม่', exact=True)
    expect(dialog).to_contain_text(game)
    expect(dialog).to_contain_text('CABALPC_PREMIUM')
    dialog.get_by_role('button', name='ยกเลิก', exact=True).click()
    assert not observed['posts']
    create.click()
    dialog.get_by_role('button', name='ยืนยันสร้าง', exact=True).click()
    expect(page.get_by_text('Item ID: 91', exact=True)).to_be_visible(timeout=15000)
    expect(page.get_by_text('ตรวจผ่านครบ', exact=True)).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(tmp_path / f'premium-result-{width}.png'), full_page=True)
    assert len(observed['posts']) == 1 and not observed['unexpected']
    row = next(r for r in client.get('/api/new-items/history').json()['rows'] if r['id'] == entry['id'])
    assert row['frozen'] == frozen
