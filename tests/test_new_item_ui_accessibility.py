"""Supported workflow keyboard/large-list checks, not a full accessibility claim."""
from playwright.sync_api import expect

from test_new_item_import_api import one_draft, preview, apply_preview
from test_new_item_ui import operator_page


def test_tab_navigation_and_modal_cancel_keep_draft(client, operator_page):
    one_draft(client)
    page, requests = operator_page
    page.goto('http://tool.test/new-items')
    row = page.locator('#draftRows tr')
    row.get_by_label('เลือกร่าง').focus()
    page.keyboard.press('Space')
    page.keyboard.press('Tab')
    expect(row.get_by_label('Name', exact=True)).to_be_focused()
    confirm = page.get_by_role('button', name='ยืนยันร่างที่เลือก', exact=True)
    for _ in range(32):
        if confirm.evaluate('node => document.activeElement === node'):
            break
        page.keyboard.press('Tab')
    expect(confirm).to_be_focused()
    page.keyboard.press('Enter')
    dialog = page.get_by_role('dialog', name='ยืนยันร่าง')
    expect(dialog.get_by_role('button', name='ยืนยันร่าง', exact=True)).to_be_focused()
    page.keyboard.press('Tab')
    expect(dialog.get_by_role('button', name='ยกเลิก', exact=True)).to_be_focused()
    page.keyboard.press('Escape')
    expect(confirm).to_be_focused()
    assert client.get('/api/new-items/drafts').json()['drafts'][0]['state'] == 'draft'
    assert ('POST', '/api/new-items/confirm') not in requests


def test_hundred_long_named_rows_scroll_inside_table_on_mobile(client, operator_page):
    pending = preview(client, [('รายการจำนวนมาก', [[
        ('ชื่อไอเทมภาษาไทยที่ยาว ' * 12) + str(index), 1000 + index, 0, 0, 'GENERAL', False
    ] for index in range(100)])])
    assert len(apply_preview(client, pending, ['รายการจำนวนมาก'])) == 100
    page, _ = operator_page
    page.set_viewport_size({'width': 390, 'height': 844})
    page.goto('http://tool.test/new-items')
    rows = page.locator('#draftRows tr')
    expect(rows).to_have_count(100, timeout=10000)
    table = page.get_by_label('ตารางร่าง เลื่อนซ้ายขวาได้', exact=True)
    assert table.evaluate('node => node.scrollHeight > node.clientHeight && node.scrollWidth > node.clientWidth')
    last = rows.last
    identity = last.locator('input[data-pick]').get_attribute('data-pick')
    last.get_by_label('Name', exact=True).fill('แก้เฉพาะแถวสุดท้าย')
    last.get_by_role('button', name='บันทึกร่าง', exact=True).click()
    expect(last.get_by_label('Name', exact=True)).to_have_value('แก้เฉพาะแถวสุดท้าย')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    saved = client.get('/api/new-items/drafts').json()['drafts']
    assert len(saved) == 100
    assert [draft['values']['name'] for draft in saved if draft['draft_id'] == identity] == ['แก้เฉพาะแถวสุดท้าย']
    page.screenshot(path='build-cache/new-item-hundred-rows-mobile.png', full_page=True)
