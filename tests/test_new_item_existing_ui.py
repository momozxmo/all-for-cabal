"""Real UI to candidate API to routed Aztek and fresh readback; no runner stub."""
import pytest
from playwright.sync_api import expect

from test_new_item_existing_api import boundary, confirmed
from test_new_item_ui import operator_page
from test_web_validation import _connect_aztek


@pytest.mark.parametrize('width', [1280, 390])
def test_explicit_existing_choice_cancel_reload_then_fresh_readback(client, monkeypatch, operator_page, width, tmp_path):
    confirmed(client)
    _connect_aztek(client)
    remote, unexpected = boundary(monkeypatch, 'CabalPC TH')
    page, requests = operator_page
    page.set_viewport_size({'width': width, 'height': 844})
    page.goto('http://tool.test/new-items')
    page.get_by_role('button', name='ค้นหา Item เดิม', exact=True).click()
    choice = page.get_by_role('button', name='ใช้ ID เดิมและตรวจข้อมูล', exact=True)
    expect(choice).to_be_disabled()
    expect(page.get_by_label('เลือก Item ID 91', exact=True)).not_to_be_checked()
    expect(page.get_by_label('เลือก Item ID 92', exact=True)).not_to_be_checked()
    page.screenshot(path=str(tmp_path / f'existing-candidates-{width}.png'), full_page=True)
    page.get_by_label('เลือก Item ID 91', exact=True).check()
    choice.click()
    dialog = page.get_by_role('dialog', name='ใช้ Item เดิม', exact=True)
    expect(dialog).to_contain_text('91')
    expect(dialog).to_contain_text('ไม่สร้าง Item ใหม่')
    page.screenshot(path=str(tmp_path / f'existing-confirm-{width}.png'), full_page=True)
    page.keyboard.press('Escape')
    expect(choice).to_be_focused()
    assert not any(path.endswith('/use-existing') for method, path in requests if method == 'POST')
    before = len(remote)
    page.reload()
    expect(page.get_by_label('เลือก Item ID 91', exact=True)).not_to_be_checked()
    assert len(remote) == before
    page.get_by_label('เลือก Item ID 91', exact=True).check()
    page.get_by_role('button', name='ใช้ ID เดิมและตรวจข้อมูล', exact=True).click()
    dialog.get_by_role('button', name='อ่านและตรวจ ID นี้', exact=True).click()
    expect(page.locator('#historyRows').get_by_text('ใช้ Item เดิม — ไม่ได้สร้างใหม่', exact=True)).to_be_visible()
    expect(page.locator('#historyRows').get_by_text('ตรวจผ่านครบ', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='สร้าง Item ที่เลือก', exact=True)).to_be_disabled()
    assert not any(path.endswith('/run') for method, path in requests if method == 'POST')
    assert all(method == 'GET' for method, _ in remote) and not unexpected
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(tmp_path / f'existing-result-{width}.png'), full_page=True)


def test_existing_choice_does_not_hide_mismatch_or_enable_handoff(client, monkeypatch, operator_page):
    confirmed(client)
    _connect_aztek(client)
    boundary(monkeypatch, 'CabalPC TH', changed=True)
    page, _ = operator_page
    page.goto('http://tool.test/new-items')
    page.get_by_role('button', name='ค้นหา Item เดิม', exact=True).click()
    page.get_by_label('เลือก Item ID 91', exact=True).check()
    page.get_by_role('button', name='ใช้ ID เดิมและตรวจข้อมูล', exact=True).click()
    page.get_by_role('dialog', name='ใช้ Item เดิม', exact=True).get_by_role('button', name='อ่านและตรวจ ID นี้', exact=True).click()
    expect(page.locator('#historyRows').get_by_text('ข้อมูลไม่ตรง', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='ส่งแถวที่เลือกไป Finder', exact=True)).to_be_disabled()
