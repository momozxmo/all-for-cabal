"""Finder missing-row selection creates local drafts, never an Aztek record."""
from web.workspaces import WorkspaceRepository
from test_new_item_ui import operator_page


def source_workspace(member, test_database):
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(member.id, 'event', 'missing.xlsx')
        workspace.game = 'CabalM TH'
        workspace.criteria = [{'kind': '123', 'opt': '0', 'dur': '0', 'name': 'Missing A'},
                              {'kind': '777', 'opt': '0', 'dur': '9', 'name': 'Missing B'},
                              {'kind': '999', 'opt': '0', 'dur': '0', 'name': 'Found'}]
        workspace.results = [{'aztek_id': '90', 'item_kind': '999', 'item_option': '0',
                              'duration_index': '0', 'item_name': 'Found'}]
        workspace.not_found = [['row1', 'Missing A'], ['row2', 'Missing B']]
        workspace.occurrences = [dict(workspace.criteria[0], amt='2', source_sheet='A',
            source_row=2, group_keys=['g1']), dict(workspace.criteria[1], amt='3',
            source_sheet='B', source_row=8, group_keys=['g2'])]
        return workspace.id


def test_only_selected_missing_row_becomes_draft(client, member, test_database, operator_page):
    identity = source_workspace(member, test_database)
    page, requests = operator_page
    page.set_viewport_size({'width': 390, 'height': 844})
    page.add_init_script("localStorage.setItem('afc.workspaceId', %r)" % identity)
    page.goto('http://tool.test/')
    page.locator('#notFoundList .missing-pick').first.wait_for()
    page.locator('#btnMissingNone').click()
    button = page.get_by_role('button', name='เพิ่มเป็นร่าง New Item')
    assert button.is_disabled()
    page.locator('#notFoundList .missing-pick').nth(1).check()
    before = client.get('/api/workspaces/' + identity).json()
    page.on('dialog', lambda dialog: dialog.accept())
    button.click()
    page.wait_for_url('http://tool.test/new-items?game=*')
    page.locator('#draftRows tr').wait_for()
    drafts = client.get('/api/new-items/drafts').json()['drafts']
    assert len(drafts) == 1 and drafts[0]['values']['name'] == 'Missing B'
    assert drafts[0]['game'] == 'CabalM TH'
    assert drafts[0]['occurrences'][0]['amount'] == '3'
    assert page.locator('#newGame').input_value() == 'CabalM TH'
    assert client.get('/api/workspaces/' + identity).json() == before
    assert not any(path.endswith('/run') for method, path in requests if method == 'POST')


def test_cancel_missing_handoff_does_not_add_drafts(client, member, test_database, operator_page):
    identity = source_workspace(member, test_database)
    page, requests = operator_page
    page.add_init_script("localStorage.setItem('afc.workspaceId', %r)" % identity)
    page.goto('http://tool.test/')
    page.locator('#notFoundList .missing-pick').first.wait_for()
    page.on('dialog', lambda dialog: dialog.dismiss())
    page.get_by_role('button', name='เพิ่มเป็นร่าง New Item').click()
    assert client.get('/api/new-items/drafts').json()['drafts'] == []
    assert ('POST', '/api/new-items/from-finder') not in requests
