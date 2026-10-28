"""Only a retained response exposes read-only recovery, never a create retry."""
import pytest
from playwright.sync_api import expect

from test_new_item_create_flow import boundary, prepare, run
from test_new_item_resolve_api import history_row, interrupted_create
from test_new_item_ui import operator_page
from test_web_validation import _connect_aztek


@pytest.mark.parametrize('width,game', [(1280, 'CabalPC SEA'), (390, 'CabalM SEA')])
def test_operator_recovers_exact_response_id_without_new_create(
        client, test_database, monkeypatch, operator_page, tmp_path, width, game):
    entry, frozen, observed = interrupted_create(client, test_database, monkeypatch, game=game)
    page, requests = operator_page
    page.set_viewport_size({'width': width, 'height': 900 if width == 1280 else 844})
    page.goto('http://tool.test/new-items?game=' + game.replace(' ', '%20'))
    expect(page.get_by_role('checkbox', name='เลือกสร้างใหม่ Synthetic name', exact=True)).to_have_count(0)
    recover = page.get_by_role('button', name='กู้ Item ID 91 จากคำตอบเดิมและตรวจ (ไม่สร้างใหม่)', exact=True)
    expect(recover).to_be_visible()
    recover.focus()
    recover.press('Enter')
    expect(page.get_by_text('Item ID: 91', exact=True)).to_be_visible(timeout=15000)
    expect(page.get_by_text('ตรวจผ่านครบ', exact=True)).to_be_visible()
    expect(recover).to_have_count(0)
    assert requests.count(('POST', '/api/new-items/' + entry['id'] + '/resolve')) == 1
    assert not any(method == 'POST' and path.endswith('/run') for method, path in requests)
    assert history_row(client, entry['id'])['frozen'] == frozen
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=str(tmp_path / f'recovered-{width}.png'), full_page=True)
    before = list(observed['attempts'])
    page.reload()
    expect(page.get_by_text('Item ID: 91', exact=True)).to_be_visible()
    assert observed['attempts'] == before
    assert len(observed['posts']) == 1 and not observed['unexpected']


def test_no_receipt_offers_no_name_based_recovery_or_create_retry(
        client, test_database, monkeypatch, operator_page):
    entry, _ = prepare(client)
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entry['id'], lose=True)
    assert run(client, entry).status_code == 200
    page, _ = operator_page
    page.goto('http://tool.test/new-items?game=CabalM%20TH')
    expect(page.get_by_text('อย่าสร้างซ้ำ ต้องยืนยันรายการจากหลักฐานเดิมก่อน', exact=True)).to_be_visible()
    expect(page.get_by_role('button', name='กู้ Item ID', exact=False)).to_have_count(0)
    expect(page.get_by_role('checkbox', name='เลือกสร้างใหม่ Synthetic name', exact=True)).to_have_count(0)
    assert len(observed['posts']) == 1
