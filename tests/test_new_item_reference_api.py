"""References are server-derived from immutable original rows, never client passed flags."""
import pytest

from test_new_item_import_api import GAME, apply_preview, one_draft, preview


def confirm(client, draft, *, game=GAME):
    result = client.post('/api/new-items/confirm', json={
        'selected': [{'id': draft['draft_id'], 'revision': draft['revision']}], 'game': game})
    assert result.status_code == 200, result.text
    return result.json()['items'][0]


def test_manual_fill_preserves_blank_original(client):
    draft = one_draft(client, ['Missing', 123, 0, None, 'GENERAL', False])
    patched = client.patch('/api/new-items/drafts/' + draft['draft_id'], json={
        'revision': draft['revision'], 'values': {'duration': '9'}})
    assert patched.status_code == 200, patched.text
    frozen = confirm(client, patched.json())
    reference = frozen['references'][0]
    assert reference['original']['duration'] is None
    assert reference['values']['duration'] == '9'
    assert reference['provenance']['duration'] == 'manual'


def test_edit_does_not_rewrite_reference(client):
    draft = one_draft(client)
    patched = client.patch('/api/new-items/drafts/' + draft['draft_id'], json={
        'revision': draft['revision'], 'values': {'duration': '0', 'name': 'Intended edit'}})
    assert patched.status_code == 200
    frozen = confirm(client, patched.json())
    assert frozen['submitted_values']['duration'] == '0'
    assert frozen['references'][0]['values']['duration'] == '9'
    assert frozen['references'][0]['values']['name'] == 'Potion x2'
    assert frozen['references'][0]['original']['name'] == 'Potion x2'


def test_implicit_general_and_bound_require_explicit_confirmation(client):
    draft = one_draft(client, ['Missing defaults', 123, 0, 0, None, None])
    assert draft['values']['item_type'] == 'GENERAL'
    assert draft['values']['tradeable'] is False
    assert draft['ready'] is False
    patched = client.patch('/api/new-items/drafts/' + draft['draft_id'], json={
        'revision': draft['revision'], 'values': {},
        'confirmed_fields': ['item_type', 'tradeable']})
    assert patched.status_code == 200
    assert patched.json()['ready'] is True
    frozen = confirm(client, patched.json())
    assert frozen['references'][0]['original']['item_type'] is None
    assert frozen['references'][0]['provenance']['item_type'] == 'confirmed_default'
    assert frozen['references'][0]['provenance']['tradeable'] == 'confirmed_default'


def test_m_premium_is_not_silently_changed(client):
    draft = one_draft(client, ['Premium', 123, 0, 9, 'CABALPC_PREMIUM', False], game='CabalM TH')
    assert draft['values']['item_type'] == 'CABALPC_PREMIUM'
    assert draft['ready'] is False
    rejected = client.post('/api/new-items/confirm', json={
        'selected': [{'id': draft['draft_id'], 'revision': draft['revision']}], 'game': 'CabalM TH'})
    assert rejected.status_code == 400


def test_grouping_preserves_each_occurrence(client):
    pending = preview(client, [('A', [['Same', 123, 0, 0, 'GENERAL', False]]),
                               ('B', [['Same', 123, 0, 0, 'GENERAL', False]])])
    drafts = apply_preview(client, pending, ['A', 'B'])
    assert len(drafts) == 1
    assert [o['sheet'] for o in drafts[0]['occurrences']] == ['A', 'B']
    frozen = confirm(client, drafts[0])
    assert len(frozen['references']) == 2
    assert len({o['occurrence_id'] for o in frozen['occurrences']}) == 2


@pytest.mark.parametrize('field,value', [(0, 'Different'), (4, 'CABALPC_PREMIUM'),
                                        (5, True), (6, 'Different description')])
def test_equal_triples_with_different_create_values_are_not_merged(client, field, value):
    first = ['Same', 123, 0, 0, 'GENERAL', False, 'Description']
    second = list(first)
    second[field] = value
    pending = preview(client, [('A', [first, second])])
    drafts = apply_preview(client, pending, ['A'])
    assert len(drafts) == 2


def test_stale_revision_cannot_edit_or_confirm(client):
    draft = one_draft(client)
    edit = client.patch('/api/new-items/drafts/' + draft['draft_id'], json={
        'revision': draft['revision'], 'values': {'name': 'New'}})
    assert edit.status_code == 200
    assert client.patch('/api/new-items/drafts/' + draft['draft_id'], json={
        'revision': draft['revision'], 'values': {'name': 'Lost update'}}).status_code == 409
    assert client.post('/api/new-items/confirm', json={
        'selected': [{'id': draft['draft_id'], 'revision': draft['revision']}], 'game': GAME}).status_code == 409
    saved = client.get('/api/new-items/drafts').json()['drafts'][0]
    assert saved['values']['name'] == 'New'
    assert saved['occurrences'][0]['original']['name'] == 'Potion x2'


def test_client_cannot_replace_original_or_passed_status(client):
    draft = one_draft(client)
    result = client.patch('/api/new-items/drafts/' + draft['draft_id'], json={
        'revision': draft['revision'], 'values': {'duration': '0'},
        'original': {'duration': '0'}, 'passed': True})
    assert result.status_code == 422
    assert client.get('/api/new-items/drafts').json()['drafts'][0]['revision'] == draft['revision']


@pytest.mark.parametrize('bad', [True, ['not', 'a', 'name'], {'text': 'object'}])
def test_non_scalar_name_cannot_become_ready_item(client, bad):
    draft = one_draft(client)
    result = client.patch('/api/new-items/drafts/' + draft['draft_id'], json={
        'revision': draft['revision'], 'values': {'name': bad}})
    assert result.status_code in (400, 422)
    assert client.get('/api/new-items/drafts').json()['drafts'][0]['values']['name'] == 'Potion x2'
