"""A legacy import must not silently become a different Finder tool mode."""
from io import BytesIO

from openpyxl import Workbook
import pytest

from web.models import Job
from test_new_item_import_api import apply_preview
from test_new_item_reference_api import confirm
from test_new_item_reader import ORIGIN, saved_html
from test_new_item_recheck_api import browser_boundary
from test_new_item_handoff import payload
from test_web_validation import _connect_aztek


@pytest.mark.parametrize('mode', ['shop', 'itemcode', 'event'])
def test_legacy_import_handoff_preserves_finder_mode(client, test_database, monkeypatch, mode):
    book = Workbook()
    sheet = book.active
    sheet.title = 'Original source'
    for row in [['Product Name', 'Plan'], ['Event Name', 'Plan'], ['Reward: Group A'],
                ['ItemKind', 'ItemOption', 'DurationIndex', 'Item Name' if mode == 'shop' else 'Display Name', 'Amt'],
                [123, 0, 0, 'Synthetic name', 2]]:
        sheet.append(row)
    stream = BytesIO()
    book.save(stream)
    book.close()
    response = client.post('/api/new-items/import', data={'game': 'CabalPC TH', 'mode': mode},
                           files={'file': ('legacy.xlsx', stream.getvalue())})
    assert response.status_code == 200, response.text
    draft = apply_preview(client, response.json(), ['Original source'])[0]
    patched = client.patch('/api/new-items/drafts/' + draft['draft_id'], json={
        'revision': draft['revision'], 'values': {}, 'confirmed_fields': ['item_type', 'tradeable']})
    assert patched.status_code == 200, patched.text
    frozen = confirm(client, patched.json())
    with test_database.session() as db:
        record = db.get(Job, draft['draft_id'])
        record.status = 'saved'
        record.result = {'creation': {'state': 'saved', 'item_id': '91', 'evidence': {
            'detail_url': f'{ORIGIN}/combo/cabalpc/shop/items/91'}}}
    _connect_aztek(client)
    browser_boundary(monkeypatch, saved_html('CabalPC TH'))
    checked = client.post('/api/new-items/' + draft['draft_id'] + '/recheck', json={})
    assert checked.status_code == 200 and checked.json()['recheck']['outcome'] == 'passed', checked.text
    transferred = client.post('/api/new-items/handoff', json=payload(draft['draft_id'], frozen))
    assert transferred.status_code == 200, transferred.text
    workspace = client.get('/api/workspaces/' + transferred.json()['workspace_id']).json()
    assert workspace['mode'] == mode
    assert workspace['results'][0]['amt'] == '2'
