"""New Item UI uses real HTTP/storage; only remote Aztek pages are simulated."""
from copy import deepcopy
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import sync_playwright, expect

from test_new_item_import_api import one_draft, workbook_bytes
from test_new_item_recheck_api import saved_checkpoint, browser_boundary
from test_new_item_handoff import passed_occurrences
from test_new_item_reader import saved_html
from test_web_validation import _connect_aztek


@pytest.fixture
def operator_page(client):
    requests = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(reduced_motion='reduce')
        context.route('https://**', lambda route: route.abort())
        def serve(route):
            request = route.request
            url = urlsplit(request.url)
            requests.append((request.method, url.path))
            response = client.request(request.method, url.path + ('?' + url.query if url.query else ''),
                content=request.post_data_buffer,
                headers={'Content-Type': request.headers.get('content-type', 'application/json')})
            route.fulfill(status=response.status_code, body=response.content,
                          headers=dict(response.headers))
        context.route('http://tool.test/**', serve)
        page = context.new_page()
        yield page, requests
        context.close()
        browser.close()


@pytest.mark.parametrize('width', [1280, 390])
def test_import_edit_confirm_without_enabling_live_create(client, operator_page, width, tmp_path):
    page, requests = operator_page
    page.set_viewport_size({'width': width, 'height': 900 if width == 1280 else 844})
    page.goto('http://tool.test/new-items')
    expect(page.get_by_role('heading', name='New Item — เตรียมรายการและตรวจผล')).to_be_visible()
    content = workbook_bytes([('รายการไทย', [['ชื่อไทยยาว ' * 20, 123, 0, None, None, None]]),
                              ('ไม่เลือก', [['Other', 999, 0, 0, 'GENERAL', False]])])
    page.get_by_label('ไฟล์ Excel').set_input_files({'name': 'source.xlsx', 'mimeType':
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'buffer': content})
    page.get_by_role('button', name='ดู Sheet ก่อนนำเข้า', exact=True).click()
    dialog = page.get_by_role('dialog', name='เลือก Sheet ที่จะเพิ่มร่าง')
    expect(dialog).to_be_visible()
    dialog.get_by_label('ค้นหา Sheet').fill('ไทย')
    dialog.get_by_role('button', name='เลือกที่แสดง').click()
    dialog.get_by_role('button', name='เพิ่มร่างที่เลือก').click()
    row = page.locator('#draftRows tr')
    expect(row).to_have_count(1)
    row.get_by_label('Duration').fill('0')
    row.get_by_label('ยืนยันค่า Type').check()
    row.get_by_label('ยืนยันค่า Tradeable').check()
    row.get_by_role('button', name='บันทึกร่าง', exact=True).click()
    expect(row.get_by_text('พร้อมยืนยัน', exact=True)).to_be_visible()
    row.get_by_label('เลือกร่าง').check()
    page.get_by_role('button', name='ยืนยันร่างที่เลือก', exact=True).click()
    confirm = page.get_by_role('dialog', name='ยืนยันร่าง')
    expect(confirm).to_contain_text('CabalPC TH')
    expect(confirm).to_contain_text('1 รายการ')
    confirm.get_by_role('button', name='ยืนยันร่าง', exact=True).click()
    expect(page.locator('#draftRows').get_by_text('ยืนยันร่างแล้ว', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='สร้าง Item ที่เลือก', exact=True)).to_be_disabled()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth') is True
    assert len(client.get('/api/new-items/drafts').json()['drafts']) == 1
    assert not any(path.endswith('/run') for method, path in requests if method == 'POST')
    page.screenshot(path=str(tmp_path / f'import-confirmed-{width}.png'), full_page=True)


def test_keyboard_cancel_returns_focus(client, operator_page):
    one_draft(client)
    page, _ = operator_page
    page.goto('http://tool.test/new-items')
    box = page.get_by_label('เลือกร่าง')
    box.focus()
    box.press('Space')
    button = page.get_by_role('button', name='ยืนยันร่างที่เลือก', exact=True)
    button.focus()
    button.press('Enter')
    dialog = page.get_by_role('dialog', name='ยืนยันร่าง')
    expect(dialog).to_be_visible()
    page.keyboard.press('Escape')
    expect(dialog).not_to_be_visible()
    expect(button).to_be_focused()
    assert client.get('/api/new-items/drafts').json()['drafts'][0]['state'] == 'draft'


def test_incomplete_warning_survives_mismatch(client, test_database, monkeypatch, operator_page):
    saved_checkpoint(client, test_database)
    _connect_aztek(client)
    browser_boundary(monkeypatch, saved_html('CabalPC TH').replace('value="Synthetic name"',
        'value="Different"').replace('aria-checked="false"', 'aria-checked="mixed"'))
    identity = client.get('/api/new-items/drafts').json()['drafts'][0]['draft_id']
    assert client.post(f'/api/new-items/{identity}/recheck', json={}).status_code == 200
    page, _ = operator_page
    page.goto('http://tool.test/new-items')
    history = page.locator('#historyRows')
    expect(history.get_by_text('ข้อมูลไม่ตรง', exact=True)).to_be_visible()
    expect(history.get_by_text('ยังตรวจไม่ครบทุกส่วน', exact=True)).to_be_visible()
    expect(history.get_by_text('บันทึกแล้ว', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='ส่งแถวที่เลือกไป Finder')).to_be_disabled()


def test_selected_passed_occurrence_handoff(client, test_database, member, monkeypatch, operator_page):
    passed_occurrences(client, test_database, member, monkeypatch)
    page, _ = operator_page
    page.goto('http://tool.test/new-items')
    box = page.get_by_role('checkbox', name='เลือกแถว B:8 — จำนวน 3')
    box.check()
    page.get_by_role('button', name='ส่งแถวที่เลือกไป Finder').click()
    page.wait_for_url('http://tool.test/')
    workspace_id = page.evaluate("localStorage.getItem('afc.workspaceId')")
    workspace = client.get('/api/workspaces/' + workspace_id).json()
    assert len(workspace['results']) == 1 and workspace['results'][0]['amt'] == '3'
    expect(page.locator('#resultsTable tbody tr')).to_have_count(1)


def test_reload_does_not_submit(client, operator_page):
    one_draft(client)
    page, requests = operator_page
    page.goto('http://tool.test/new-items')
    expect(page.locator('#draftRows tr')).to_have_count(1)
    before = [r for r in requests if r[0] == 'POST']
    page.reload()
    expect(page.locator('#draftRows tr')).to_have_count(1)
    assert [r for r in requests if r[0] == 'POST'] == before


def test_new_item_page_requires_login(anonymous_client):
    response = anonymous_client.get('/new-items', follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers['location'] == '/login'


@pytest.mark.parametrize('width', [1280, 390])
def test_historical_mismatch_keeps_its_values_after_later_pass(
        client, test_database, monkeypatch, operator_page, width):
    identity, _, _ = saved_checkpoint(client, test_database)
    _connect_aztek(client)
    old_name = 'Old <img src=x onerror=window.historyInjected=true>'
    old_html = saved_html('CabalPC TH').replace('value="123"', 'value="456"').replace(
        'value="Synthetic name"', 'value="Old &lt;img src=x onerror=window.historyInjected=true&gt;"').replace(
        'aria-checked="false"', 'aria-checked="mixed"')
    first_remote, unexpected_first = browser_boundary(monkeypatch, old_html)
    first = client.post(f'/api/new-items/{identity}/recheck', json={})
    assert first.status_code == 200, first.text
    assert first.json()['recheck']['outcome'] == 'mismatch' and first.json()['recheck']['incomplete']
    acknowledgement = client.post(f'/api/new-items/{identity}/acknowledge', json={
        'action': 'skip', 'expected_history_count': 1})
    assert acknowledgement.status_code == 200, acknowledgement.text
    second_remote, unexpected_second = browser_boundary(monkeypatch, saved_html('CabalPC TH'))
    second = client.post(f'/api/new-items/{identity}/recheck', json={})
    assert second.status_code == 200 and second.json()['recheck']['outcome'] == 'passed'
    before = deepcopy(client.get('/api/new-items/history').json())
    remote_before = (list(first_remote), list(second_remote))
    page, requests = operator_page
    page.set_viewport_size({'width': width, 'height': 900 if width == 1280 else 844})
    page.goto('http://tool.test/new-items')
    record = page.locator('#historyRows > article')
    expect(record.get_by_text('ตรวจผ่านครบ', exact=True)).to_be_visible()
    expect(record.locator('input[data-occurrence]')).to_have_count(1)
    expect(record.locator('input[data-occurrence]')).not_to_be_checked()
    requests_before = list(requests)
    page.get_by_text('ประวัติ 3 ครั้ง', exact=True).click()
    old = record.get_by_role('heading', name='รอบตรวจที่ 1 · ข้อมูลไม่ตรง', exact=True).locator('..')
    expect(old.get_by_text('รอบนี้ยังตรวจไม่ครบทุกส่วน', exact=True)).to_be_visible()
    expect(old).to_contain_text('เกม: CabalPC TH · Item ID: 91')
    expect(old).to_contain_text(before['rows'][0]['history'][0]['checked_at'])
    control = old.get_by_text('ดูค่าที่เปรียบเทียบรอบที่ 1', exact=True)
    control.focus(); control.press('Enter')
    expect(old.get_by_role('cell', name=old_name, exact=True)).to_be_visible()
    old.get_by_role('cell', name=old_name, exact=True).scroll_into_view_if_needed()
    expect(old.get_by_role('cell', name=old_name, exact=True)).to_be_in_viewport()
    if width == 390:
        assert old.locator('.table-wrap').evaluate('table => table.scrollLeft > 0')
    kind = old.get_by_role('row').filter(has=page.get_by_role('cell', name='Kind', exact=True))
    assert kind.locator('td').all_text_contents() == ['Kind', '123', '123', '123', '456', 'document']
    current = record.get_by_role('heading', name='รอบตรวจที่ 2 · ตรวจผ่านครบ', exact=True).locator('..')
    current.get_by_text('ดูค่าที่เปรียบเทียบรอบที่ 2', exact=True).click()
    kind = current.get_by_role('row').filter(has=page.get_by_role('cell', name='Kind', exact=True))
    assert kind.locator('td').all_text_contents() == ['Kind', '123', '123', '123', '123', 'document']
    expect(record.get_by_text('รับทราบปัญหา (ผลเดิมไม่เปลี่ยน)', exact=False)).to_be_visible()
    expect(record.locator('h4')).to_have_count(2)  # Acknowledgement is not a recheck.
    assert page.locator('#historyRows img').count() == 0
    assert page.evaluate('window.historyInjected') is None
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert requests == requests_before and (first_remote, second_remote) == remote_before
    assert not unexpected_first and not unexpected_second
    assert client.get('/api/new-items/history').json() == before
    page.screenshot(path=f'build-cache/new-item-history-detail-{width}.png', full_page=True)


@pytest.mark.parametrize('width', [1280, 390])
def test_historical_pass_cannot_enable_handoff_after_latest_mismatch(
        client, test_database, monkeypatch, operator_page, width):
    identity, _, _ = saved_checkpoint(client, test_database)
    _connect_aztek(client)
    first_remote, unexpected_first = browser_boundary(monkeypatch, saved_html('CabalPC TH'))
    first = client.post(f'/api/new-items/{identity}/recheck', json={})
    assert first.status_code == 200 and first.json()['recheck']['outcome'] == 'passed'
    second_remote, unexpected_second = browser_boundary(monkeypatch, saved_html('CabalPC TH').replace(
        'value="123"', 'value="456"'))
    second = client.post(f'/api/new-items/{identity}/recheck', json={})
    assert second.status_code == 200 and second.json()['recheck']['outcome'] == 'mismatch'
    before = deepcopy(client.get('/api/new-items/history').json())
    page, requests = operator_page
    page.set_viewport_size({'width': width, 'height': 900 if width == 1280 else 844})
    page.goto('http://tool.test/new-items')
    record = page.locator('#historyRows > article')
    expect(page.get_by_text('ประวัติ 2 ครั้ง', exact=True)).to_be_visible()
    requests_before = list(requests)
    page.get_by_text('ประวัติ 2 ครั้ง', exact=True).click()
    old = record.get_by_role('heading', name='รอบตรวจที่ 1 · ตรวจผ่านครบ', exact=True).locator('..')
    old.get_by_text('ดูค่าที่เปรียบเทียบรอบที่ 1', exact=True).click()
    kind = old.get_by_role('row').filter(has=page.get_by_role('cell', name='Kind', exact=True))
    assert kind.locator('td').all_text_contents() == ['Kind', '123', '123', '123', '123', 'document']
    expect(record.get_by_text('ข้อมูลไม่ตรง', exact=True)).to_be_visible()
    expect(record.locator('input[data-occurrence]')).to_have_count(0)
    expect(page.get_by_role('button', name='ส่งแถวที่เลือกไป Finder', exact=True)).to_be_disabled()
    assert requests == requests_before
    assert len(first_remote) == len(second_remote) == 1 and not unexpected_first and not unexpected_second
    assert client.get('/api/new-items/history').json() == before


@pytest.mark.parametrize('width', [1280, 390])
def test_historical_failed_readback_keeps_error_and_image_qualification(
        client, test_database, monkeypatch, operator_page, width):
    from web.models import Job
    from test_new_item_media import attach
    from test_new_item_reference_api import confirm
    from test_new_item_reader import ORIGIN
    draft = one_draft(client, ['Synthetic name', 123, 0, 0, 'GENERAL', False,
                              'Synthetic description'], game='CabalPC TH')
    uploaded = attach(client, draft)
    assert uploaded.status_code == 200, uploaded.text
    confirm(client, uploaded.json(), game='CabalPC TH')
    identity = draft['draft_id']
    with test_database.session() as db:
        record = db.get(Job, identity)
        record.status = 'saved'
        record.result = {'creation': {'state': 'saved', 'item_id': '91', 'evidence': {
            'detail_url': ORIGIN + '/combo/cabalpc/shop/items/91'}}}
    _connect_aztek(client)
    browser_boundary(monkeypatch, saved_html('CabalPC TH').replace('id="item-option"', 'id="broken-option"'))
    first = client.post(f'/api/new-items/{identity}/recheck', json={})
    assert first.status_code == 200 and first.json()['recheck']['outcome'] == 'failed'
    assert first.json()['recheck']['image_status'] == 'unreadable'
    remote, unexpected = browser_boundary(monkeypatch, saved_html('CabalPC TH', image=True))
    second = client.post(f'/api/new-items/{identity}/recheck', json={})
    assert second.status_code == 200 and second.json()['recheck']['outcome'] == 'passed'
    before = deepcopy(client.get('/api/new-items/history').json())
    page, requests = operator_page
    page.set_viewport_size({'width': width, 'height': 900 if width == 1280 else 844})
    page.goto('http://tool.test/new-items')
    expect(page.get_by_text('ประวัติ 2 ครั้ง', exact=True)).to_be_visible()
    requests_before = list(requests)
    page.get_by_text('ประวัติ 2 ครั้ง', exact=True).click()
    old = page.get_by_role('heading', name='รอบตรวจที่ 1 · ตรวจไม่สำเร็จ', exact=True).locator('..')
    expect(old).to_contain_text(first.json()['recheck']['error'])
    expect(old.get_by_text('รอบนี้ยังตรวจไม่ครบทุกส่วน', exact=True)).to_be_visible()
    expect(old.get_by_text('สถานะรูป: ยังอ่านสถานะรูปไม่ได้', exact=True)).to_be_visible()
    later = page.get_by_role('heading', name='รอบตรวจที่ 2 · ตรวจผ่านครบ', exact=True).locator('..')
    expect(later.get_by_text('สถานะรูป: พบรูป แต่ยังไม่ได้ยืนยันว่าเนื้อภาพตรงกัน', exact=True)).to_be_visible()
    old.get_by_text('ดูค่าที่เปรียบเทียบรอบที่ 1', exact=True).click()
    expect(old.get_by_role('table')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert requests == requests_before and len(remote) == 1 and not unexpected
    assert client.get('/api/new-items/history').json() == before


def test_legacy_history_does_not_borrow_latest_identity_or_invent_comparison(
        client, test_database, operator_page):
    from web.models import Job
    identity, _, creation = saved_checkpoint(client, test_database)
    with test_database.session() as db:
        record = db.get(Job, identity)
        record.result = {'creation': creation, 'recheck': {'outcome': 'mismatch', 'incomplete': True}}
        record.log = [{'recheck': {'outcome': 'passed', 'incomplete': False}}]
    before = deepcopy(client.get('/api/new-items/history').json())
    page, requests = operator_page
    page.goto('http://tool.test/new-items')
    expect(page.get_by_text('ประวัติ 1 ครั้ง', exact=True)).to_be_visible()
    requests_before = list(requests)
    page.get_by_text('ประวัติ 1 ครั้ง', exact=True).click()
    old = page.get_by_role('heading', name='รอบตรวจที่ 1 · ตรวจผ่านครบ', exact=True).locator('..')
    expect(old).to_contain_text('เวลา: ไม่มีข้อมูล')
    expect(old).to_contain_text('เกม: ไม่มีข้อมูล · Item ID: ไม่มีข้อมูล')
    expect(old).not_to_contain_text('Item ID: 91')
    old.get_by_text('ดูค่าที่เปรียบเทียบรอบที่ 1', exact=True).click()
    expect(old.get_by_text('ไม่มีข้อมูลเปรียบเทียบที่เก็บไว้สำหรับรอบนี้', exact=True)).to_be_visible()
    expect(old.get_by_role('table')).to_have_count(0)
    expect(page.get_by_role('button', name='ส่งแถวที่เลือกไป Finder', exact=True)).to_be_disabled()
    assert requests == requests_before
    assert client.get('/api/new-items/history').json() == before
