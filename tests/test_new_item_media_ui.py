"""Real attachment/acknowledgement UI; no remote images or Aztek writes."""
import pytest
from playwright.sync_api import expect

from web.models import Job
from test_new_item_import_api import one_draft
from test_new_item_recheck_api import saved_checkpoint
from test_new_item_ui import operator_page
from test_new_item_media import image_bytes


@pytest.mark.parametrize('width', [1280, 390])
def test_image_attachment_and_removal_survive_reload(client, operator_page, width):
    one_draft(client)
    page, requests = operator_page
    page.set_viewport_size({'width': width, 'height': 900 if width == 1280 else 844})
    page.goto('http://tool.test/new-items')
    row = page.locator('#draftRows tr')
    row.get_by_label('รูปสำหรับร่าง').set_input_files({'name': 'private.png', 'mimeType': 'image/png', 'buffer': image_bytes()})
    row.get_by_role('button', name='แนบรูปในเครื่อง', exact=True).click()
    expect(row.get_by_text('แนบรูปแล้ว · ยังไม่ส่ง Aztek', exact=True)).to_be_visible()
    page.reload()
    expect(row.get_by_text('แนบรูปแล้ว · ยังไม่ส่ง Aztek', exact=True)).to_be_visible()
    image = row.get_by_alt_text('รูปที่แนบในร่าง')
    expect(image).to_be_visible()
    assert image.evaluate('image => image.complete && image.naturalWidth > 0')
    row.get_by_role('button', name='นำรูปออกจากร่าง', exact=True).click()
    expect(row.get_by_text('ไม่มีรูป · ไม่บังคับแนบ', exact=True)).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not any(path.endswith('/run') for method, path in requests if method == 'POST')
    page.screenshot(path=f'build-cache/new-item-media-ui-{width}.png', full_page=True)


def test_attachment_does_not_discard_unsaved_other_row_edits(client, operator_page):
    one_draft(client, ['First', 123, 0, 0, 'GENERAL', False])
    one_draft(client, ['Second', 777, 0, 0, 'GENERAL', False])
    page, _ = operator_page
    page.goto('http://tool.test/new-items')
    first, second = page.locator('#draftRows tr').nth(0), page.locator('#draftRows tr').nth(1)
    first.get_by_label('Name', exact=True).fill('Unsaved local edit')
    second.get_by_label('รูปสำหรับร่าง').set_input_files({'name': 'private.png', 'mimeType': 'image/png', 'buffer': image_bytes()})
    second.get_by_role('button', name='แนบรูปในเครื่อง', exact=True).click()
    expect(second.get_by_text('แนบรูปแล้ว · ยังไม่ส่ง Aztek', exact=True)).to_be_visible()
    expect(first.get_by_label('Name', exact=True)).to_have_value('Unsaved local edit')
    assert client.get('/api/new-items/drafts').json()['drafts'][0]['values']['name'] == 'First'


def test_dirty_same_row_requires_save_before_attachment(client, operator_page):
    one_draft(client)
    page, requests = operator_page
    page.goto('http://tool.test/new-items')
    row = page.locator('#draftRows tr')
    row.get_by_label('Name', exact=True).fill('Unsaved')
    row.get_by_label('รูปสำหรับร่าง').set_input_files({'name': 'private.png', 'mimeType': 'image/png', 'buffer': image_bytes()})
    row.get_by_role('button', name='แนบรูปในเครื่อง', exact=True).click()
    expect(page.locator('#newNotice')).to_contain_text('บันทึกร่างก่อนแนบรูป')
    expect(row.get_by_label('Name', exact=True)).to_have_value('Unsaved')
    assert not any(path.endswith('/image') for method, path in requests if method == 'POST')


def test_acknowledge_ui_keeps_problem_and_handoff_blocked(client, test_database, operator_page):
    identity, _, creation = saved_checkpoint(client, test_database)
    with test_database.session() as db:
        record = db.get(Job, identity)
        record.result = {'creation': creation, 'recheck': {'outcome': 'mismatch', 'incomplete': True}}
    page, _ = operator_page
    page.goto('http://tool.test/new-items')
    page.get_by_role('button', name='รับทราบ/ข้ามรายการนี้', exact=True).click()
    expect(page.get_by_text('รับทราบแล้ว — ผลตรวจและสิทธิ์ส่งต่อไม่เปลี่ยน', exact=True)).to_be_visible()
    expect(page.locator('#historyRows').get_by_text('ข้อมูลไม่ตรง', exact=True)).to_be_visible()
    expect(page.get_by_text('ยังตรวจไม่ครบทุกส่วน', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='ส่งแถวที่เลือกไป Finder')).to_be_disabled()
    row = client.get('/api/new-items/history').json()['rows'][0]
    assert row['result']['creation'] == creation and row['result']['recheck']['outcome'] == 'mismatch'
