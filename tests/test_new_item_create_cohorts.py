"""One selected final payload, one POST, all immutable references survive."""
from io import BytesIO

from openpyxl import Workbook
from playwright.sync_api import expect
import pytest

from test_new_item_create_flow import GAME, boundary, creation_entry, prepare
from test_new_item_import_api import apply_preview, one_draft
from test_new_item_reader import ORIGIN, saved_html
from test_new_item_recovery_api import reopen
from web.models import Job
from web.new_item_store import NewItemRepository
from test_new_item_reference_api import confirm
from test_new_item_ui import operator_page
from test_web_validation import _connect_aztek


def converged(client, *, original_duration=0):
    book = Workbook()
    book.remove(book.active)
    for sheet_name, duration, amount in [('A', None, 2), ('B', original_duration, 3)]:
        sheet = book.create_sheet(sheet_name)
        for row in [['Event Name', 'Plan'], ['Reward: Group ' + sheet_name],
                    ['ItemKind', 'ItemOption', 'DurationIndex', 'Display Name', 'Amt'],
                    [123, 0, duration, 'Synthetic name', amount]]:
            sheet.append(row)
    stream = BytesIO()
    book.save(stream)
    book.close()
    response = client.post('/api/new-items/import', data={'game': GAME, 'mode': 'event'},
                           files={'file': ('cohort.xlsx', stream.getvalue())})
    assert response.status_code == 200, response.text
    drafts = apply_preview(client, response.json(), ['A', 'B'], game=GAME)
    assert len(drafts) == 2
    entries, frozen = [], []
    for draft in drafts:
        changed = client.patch('/api/new-items/drafts/' + draft['draft_id'], json={
            'revision': draft['revision'], 'values': {'duration': '0', 'description': 'Synthetic description'},
            'confirmed_fields': ['item_type', 'tradeable']})
        assert changed.status_code == 200, changed.text
        snapshot = confirm(client, changed.json(), game=GAME)
        frozen.append(snapshot)
        entries.append(creation_entry(client, draft['draft_id'], snapshot))
    return entries, frozen


def grouped_run(client, entries):
    return client.post('/api/new-items/run', json={
        'game': GAME, 'selected': entries, 'group_identical': True})


def test_converged_selected_drafts_share_one_post_and_keep_each_reference(
        client, test_database, monkeypatch):
    entries, frozen = converged(client)
    _connect_aztek(client)
    identities = [entry['id'] for entry in entries]
    observed = boundary(monkeypatch, test_database, identities[0], cohort_ids=identities)
    response = grouped_run(client, entries)
    assert response.status_code == 200, response.text
    assert response.json()['remaining_ids'] == []
    rows = {row['id']: row for row in client.get('/api/new-items/history').json()['rows']}
    assert len(observed['posts']) == 1 and not observed['unexpected']
    assert observed['cohort_post'] == [('submitting', 'submitting'), ('submitting', 'submitting')]
    assert observed['cohort_saved'] == [('saved', '91'), ('saved', '91')]
    for entry, original in zip(entries, frozen):
        row = rows[entry['id']]
        assert row['frozen'] == original  # No rewriting a confirmed reference to merge Jobs.
        assert row['result']['creation']['item_id'] == '91'
        assert row['result']['recheck']['outcome'] == 'passed'
        assert len(row['history']) == 1
    assert [rows[key]['frozen']['references'][0]['original']['duration'] for key in identities] == [None, '0']
    assert grouped_run(client, entries).status_code == 409
    assert len(observed['posts']) == 1
    handoff = client.post('/api/new-items/handoff', json={'game': GAME,
        'selected_ids': identities, 'occurrence_ids': [o['occurrence_id'] for f in frozen for o in f['occurrences']]})
    assert handoff.status_code == 200, handoff.text
    bundles = client.post('/api/workspaces/' + handoff.json()['workspace_id'] + '/bundles', json={}).json()['bundles']
    assert sorted((item['id'], item['qty']) for b in bundles for item in b['items']) == [('91', '2'), ('91', '3')]


@pytest.mark.parametrize('width', [1280, 390])
def test_group_confirmation_counts_unique_items_without_losing_selected_drafts(
        client, test_database, monkeypatch, operator_page, width):
    entries, _ = converged(client)
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entries[0]['id'], cohort_ids=[e['id'] for e in entries])
    page, requests = operator_page
    page.set_viewport_size({'width': width, 'height': 900 if width == 1280 else 844})
    page.goto('http://tool.test/new-items?game=CabalM%20TH')
    picks = page.locator('#historyRows input[data-create]')
    expect(picks).to_have_count(2)
    for pick in picks.all():
        pick.check()
    button = page.get_by_role('button', name='สร้าง Item ที่เลือก', exact=True)
    button.click()
    dialog = page.get_by_role('dialog', name='ยืนยันสร้าง Item ใหม่', exact=True)
    expect(dialog).to_contain_text('1 รายการ')
    expect(dialog).to_contain_text('2 ร่าง')
    expect(page.locator('#createSummary li')).to_have_count(1)
    page.screenshot(path=f'build-cache/new-item-cohort-confirm-{width}.png', full_page=True)
    page.keyboard.press('Escape')
    expect(button).to_be_focused()
    assert not observed['posts'] and not any(method == 'POST' and path.endswith('/run') for method, path in requests)
    button.click()
    dialog.get_by_role('button', name='ยืนยันสร้าง', exact=True).click()
    expect(page.get_by_text('Item ID: 91', exact=True)).to_have_count(2, timeout=15000)
    expect(page.get_by_text('ตรวจผ่านครบ', exact=True)).to_have_count(2)
    expect(page.get_by_text('กลุ่มสร้างร่วมกัน 2 ร่าง — เก็บผลตรวจแยกตามต้นฉบับ', exact=True)).to_have_count(2)
    page.screenshot(path=f'build-cache/new-item-cohort-result-{width}.png', full_page=True)
    assert len(observed['posts']) == 1 and not observed['unexpected']
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')


def histories(client):
    return {row['id']: row for row in client.get('/api/new-items/history').json()['rows']}


def test_lost_response_marks_every_member_uncertain_and_never_replays(
        client, test_database, monkeypatch):
    entries, frozen = converged(client)
    other, _ = prepare(client, name='Not selected')
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entries[0]['id'], lose=True,
                        cohort_ids=[entry['id'] for entry in entries])
    response = grouped_run(client, entries)
    assert response.status_code == 200, response.text
    assert response.json()['remaining_ids'] == []
    rows = histories(client)
    creations = [rows[entry['id']]['result']['creation'] for entry in entries]
    assert len({c['attempt_id'] for c in creations}) == 1
    for entry, original in zip(entries, frozen):
        row = rows[entry['id']]
        assert row['state'] == row['result']['creation']['state'] == 'unconfirmed'
        assert not row['result']['creation'].get('item_id')
        assert row['frozen'] == original and not row['result'].get('recheck')
    assert rows[other['id']]['state'] == 'confirmed'
    with reopen(client, test_database) as restored:
        assert histories(restored) == rows
        assert grouped_run(restored, entries).status_code == 409
        first = entries[0]['id']
        ack = restored.post('/api/new-items/' + first + '/acknowledge', json={
            'action': 'skip', 'expected_history_count': len(rows[first]['history'])})
        assert ack.status_code == 200, ack.text
        assert grouped_run(restored, [other]).status_code == 409  # Peer still unresolved.
    assert len(observed['posts']) == 1 and not observed['unexpected']
    assert observed['cohort_post'] == [('submitting', 'submitting')] * 2
    assert len(observed['gets']) == 1


def test_noncontiguous_group_keeps_independent_reference_mismatch_and_remaining_ids(
        client, test_database, monkeypatch):
    entries, frozen = converged(client, original_duration=1)
    middle, _ = prepare(client, name='Middle unique payload')
    selected = [entries[0], middle, entries[1]]
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entries[0]['id'],
                        cohort_ids=[entry['id'] for entry in entries])
    response = grouped_run(client, selected)
    assert response.status_code == 200, response.text
    assert response.json()['remaining_ids'] == [middle['id']]
    rows = histories(client)
    assert rows[entries[0]['id']]['result']['recheck']['outcome'] == 'passed'
    assert rows[entries[1]['id']]['result']['recheck']['outcome'] == 'mismatch'
    for entry, original in zip(entries, frozen):
        row = rows[entry['id']]
        assert row['frozen'] == original and len(row['result']['recheck']['per_occurrence']) == 1
        assert row['result']['creation']['item_id'] == '91'
    assert rows[middle['id']]['state'] == 'confirmed'
    assert len(observed['posts']) == 1 and not observed['unexpected']


@pytest.mark.parametrize('fault', ['revision', 'search', 'duplicate', 'decision', 'boolean', 'owner'])
def test_invalid_group_scope_opens_no_browser(
        client, client_for, other_member, test_database, monkeypatch, fault):
    entries, _ = converged(client)
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entries[0]['id'])
    requester, consent, expected = client, True, 409
    if fault == 'revision':
        entries[1] = dict(entries[1], revision=99)
    elif fault == 'search':
        entries[1] = dict(entries[1], search_id=entries[0]['search_id'])
    elif fault == 'duplicate':
        entries.append(entries[0]); expected = 400
    elif fault == 'decision':
        entries[1] = dict(entries[1], decision='use_existing'); expected = 422
    elif fault == 'boolean':
        consent = 'true'; expected = 422
    else:
        requester, expected = client_for(other_member), 404
    response = requester.post('/api/new-items/run', json={
        'game': GAME, 'selected': entries, 'group_identical': consent})
    assert response.status_code == expected, response.text
    assert not observed['gets'] and not observed['posts']
    assert all(row['state'] == 'confirmed' for row in histories(client).values())


@pytest.mark.parametrize('when', ['waiting_gate', 'before_post'])
def test_group_changed_member_aborts_every_claim_before_post(
        client, application, test_database, monkeypatch, when):
    from contextlib import asynccontextmanager
    entries, _ = converged(client)
    _connect_aztek(client)
    def change_state():
        with test_database.session() as db:
            db.get(Job, entries[1]['id']).status = 'unconfirmed'
    if when == 'waiting_gate':
        @asynccontextmanager
        async def slot():
            change_state()
            yield
        monkeypatch.setattr(application.state.browser_gate, 'slot', slot)
    observed = boundary(monkeypatch, test_database, entries[0]['id'],
                        on_create=change_state if when == 'before_post' else None)
    assert grouped_run(client, entries).status_code == 409
    rows = histories(client)
    assert rows[entries[0]['id']]['state'] == 'confirmed'
    assert not rows[entries[0]['id']]['result'].get('creation')
    assert not observed['posts'] and not observed['unexpected']
    if when == 'waiting_gate':
        assert not observed['gets']


@pytest.mark.parametrize('saved_identity', [False, True])
def test_group_storage_failure_rolls_back_all_members(
        client, member, test_database, saved_identity):
    from sqlalchemy import event
    entries, frozen = converged(client)
    members = [(e['id'], f) for e, f in zip(entries, frozen)]
    with test_database.session() as db:
        repo = NewItemRepository(db)
        if saved_identity:
            attempt = repo.claim_submission_group(member.id, members)
        before = histories(client)
        updates = []
        def fail_second_update(_conn, _cursor, statement, _parameters, _context, _many):
            if statement.lstrip().upper().startswith('UPDATE JOBS'):
                updates.append(statement)
                if len(updates) == 2:
                    raise RuntimeError('Synthetic second member storage failure')
        event.listen(test_database.engine, 'before_cursor_execute', fail_second_update)
        try:
            with pytest.raises(RuntimeError, match='Synthetic second member'):
                if saved_identity:
                    repo.finish_submission_group(member.id, members, attempt, item_id='91',
                        detail_url=ORIGIN + '/combo/cabalm/shop/items/91')
                else:
                    repo.claim_submission_group(member.id, members)
        finally:
            event.remove(test_database.engine, 'before_cursor_execute', fail_second_update)
        assert len(updates) == 2
        assert histories(client) == before


@pytest.mark.parametrize('state', ['submitting', 'saved'])
def test_group_restart_preserves_all_checkpoints_without_replay(
        client, member, test_database, state):
    entries, frozen = converged(client)
    members = [(e['id'], f) for e, f in zip(entries, frozen)]
    with test_database.session() as db:
        repo = NewItemRepository(db)
        attempt = repo.claim_submission_group(member.id, members)
        if state == 'saved':
            repo.finish_submission_group(member.id, members, attempt, item_id='91',
                                         detail_url=ORIGIN + '/combo/cabalm/shop/items/91')
    with reopen(client, test_database) as restored:
        rows = histories(restored)
        for entry, original in zip(entries, frozen):
            row = rows[entry['id']]
            assert row['frozen'] == original
            assert row['result']['creation']['attempt_id'] == attempt
            assert row['result']['creation']['cohort_ids'] == [e['id'] for e in entries]
            if state == 'saved':
                assert row['state'] == 'saved'
                assert row['result']['creation']['item_id'] == '91'
                assert row['result']['recheck']['incomplete']
                assert row['result']['recheck']['outcome'] == 'failed'
            else:
                assert row['state'] == 'unconfirmed'
                assert not row['result'].get('recheck')
        assert grouped_run(restored, entries).status_code == 409
    with reopen(client, test_database) as again:
        assert histories(again) == rows


def test_overlapping_cohorts_forward_once(client, test_database, monkeypatch):
    import asyncio
    import httpx
    entries, _ = converged(client)
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entries[0]['id'],
                        cohort_ids=[e['id'] for e in entries])
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app),
                base_url='http://testserver', cookies=client.cookies) as requests:
            return await asyncio.wait_for(asyncio.gather(*[
                requests.post('/api/new-items/run', json={
                    'game': GAME, 'selected': selected, 'group_identical': True})
                for selected in (entries, list(reversed(entries)))]), timeout=40)
    responses = asyncio.run(scenario())
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    assert len(observed['posts']) == 1 and not observed['unexpected']


@pytest.mark.parametrize('change', ['name', 'kind', 'option', 'duration', 'tradeable', 'description', 'image'])
def test_different_creation_value_never_joins_first_group(
        client, test_database, monkeypatch, change):
    first, _ = prepare(client)
    values = dict(name='Synthetic name', kind=123, option=0, duration=0,
                  item_type='GENERAL', tradeable=False, description='Synthetic description')
    if change != 'image':
        values[change] = dict(name='Different name', kind=124, option=1, duration=1,
                             tradeable=True, description='Different description')[change]
    draft = one_draft(client, list(values.values()), game=GAME)
    if change == 'image':
        from test_new_item_media import attach
        uploaded = attach(client, draft)
        assert uploaded.status_code == 200, uploaded.text
        draft = uploaded.json()
    snapshot = confirm(client, draft, game=GAME)
    second = creation_entry(client, draft['draft_id'], snapshot)
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, first['id'],
        saved=saved_html(GAME).replace('value="Synthetic name"', 'value="Readback mismatch"'))
    response = grouped_run(client, [first, second])
    assert response.status_code == 200, response.text
    assert response.json()['remaining_ids'] == [second['id']]
    rows = histories(client)
    assert rows[second['id']]['state'] == 'confirmed' and not rows[second['id']]['result'].get('creation')
    assert rows[first['id']]['result']['recheck']['outcome'] == 'mismatch'
    assert len(observed['posts']) == 1 and not observed['unexpected']


def test_same_private_image_can_share_one_post_but_unselected_draft_is_untouched(
        client, test_database, monkeypatch):
    from test_new_item_media import attach, image_bytes
    entries, snapshots = [], []
    for _ in range(3):
        draft = one_draft(client, ['Synthetic name', 123, 0, 0, 'GENERAL', False,
                                  'Synthetic description'], game=GAME)
        uploaded = attach(client, draft)
        assert uploaded.status_code == 200, uploaded.text
        snapshot = confirm(client, uploaded.json(), game=GAME)
        snapshots.append(snapshot)
        entries.append(creation_entry(client, draft['draft_id'], snapshot))
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entries[0]['id'], saved=saved_html(GAME, image=True),
                        cohort_ids=[e['id'] for e in entries[:2]])
    response = grouped_run(client, entries[:2])
    assert response.status_code == 200, response.text
    rows = histories(client)
    for entry, snapshot in zip(entries[:2], snapshots):
        row = rows[entry['id']]
        assert row['frozen'] == snapshot
        assert row['result']['creation']['item_id'] == '91'
        assert row['result']['recheck']['image_status'] == 'present_not_content_verified'
    assert rows[entries[2]['id']]['state'] == 'confirmed'
    assert not rows[entries[2]['id']]['result'].get('creation')
    assert len(observed['posts']) == 1 and observed['posts'][0].count(image_bytes()) == 2
    assert not observed['unexpected']


def test_group_readback_failure_keeps_all_saved_ids_and_never_replays(
        client, test_database, monkeypatch):
    entries, frozen = converged(client)
    _connect_aztek(client)
    observed = boundary(monkeypatch, test_database, entries[0]['id'],
        saved=saved_html(GAME).replace('id="item-option"', 'id="broken-option"'),
        cohort_ids=[e['id'] for e in entries])
    response = grouped_run(client, entries)
    assert response.status_code == 200, response.text
    rows = histories(client)
    for entry, original in zip(entries, frozen):
        row = rows[entry['id']]
        assert row['frozen'] == original and row['state'] == 'saved'
        assert row['result']['creation']['item_id'] == '91'
        assert row['result']['recheck']['outcome'] == 'failed' and row['result']['recheck']['incomplete']
    assert observed['cohort_saved'] == [('saved', '91')] * 2
    assert grouped_run(client, entries).status_code == 409
    assert len(observed['posts']) == 1 and not observed['unexpected']
