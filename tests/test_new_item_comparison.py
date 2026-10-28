"""New Item comparator public boundary, using real server-frozen references."""
from copy import deepcopy
import importlib

import pytest

from test_new_item_import_api import GAME, one_draft
from test_new_item_reference_api import confirm


def compare(frozen, actual, *, expected_item_id='91'):
    # Missing feature is an assertion failure, not a collection/import error.
    module = importlib.import_module('web.new_item_domain')
    function = getattr(module, 'compare_new_item', None)
    assert function is not None, 'New Item reference comparison has not been implemented'
    return function(frozen, actual, expected_item_id=expected_item_id)


def actual_item(frozen):
    return {'game': frozen['game'], 'item_id': '91',
            'values': deepcopy(frozen['submitted_values']),
            'readable_fields': ['name', 'kind', 'option', 'duration',
                                'item_type', 'tradeable', 'description'],
            'image_present': None, 'evidence': {'source': 'synthetic comparison input'}}


@pytest.mark.parametrize('field,value', [
    ('name', 'Other'), ('kind', '999'), ('option', '1'), ('duration', '0'),
    ('item_type', 'CABALPC_PREMIUM'), ('tradeable', True), ('description', 'Other text')])
def test_each_property_difference_is_mismatch(client, field, value):
    frozen = confirm(client, one_draft(client))
    actual = actual_item(frozen)
    actual['values'][field] = value
    before = deepcopy((frozen, actual))
    checked = compare(frozen, actual)
    assert checked['outcome'] == 'mismatch'
    assert field in checked['differences']
    assert checked['incomplete'] is False
    assert (frozen, actual) == before


@pytest.mark.parametrize('field', ['name', 'kind', 'option', 'duration', 'item_type', 'tradeable'])
def test_missing_required_actual_is_not_a_default_or_pass(client, field):
    frozen = confirm(client, one_draft(client))
    actual = actual_item(frozen)
    actual['values'][field] = None
    actual['readable_fields'].remove(field)
    checked = compare(frozen, actual)
    assert checked['outcome'] == 'failed'
    assert checked['incomplete'] is True
    assert checked['actual']['values'][field] is None


def test_difference_and_unreadable_both_visible(client):
    frozen = confirm(client, one_draft(client))
    actual = actual_item(frozen)
    actual['values']['duration'] = None
    actual['readable_fields'].remove('duration')
    actual['values']['name'] = 'Different'
    checked = compare(frozen, actual)
    assert checked['outcome'] == 'mismatch'
    assert checked['incomplete'] is True
    assert checked['differences'] == ['name']


@pytest.mark.parametrize('field,value', [('game', 'CabalM TH'), ('item_id', '92')])
def test_wrong_game_or_item_id_cannot_pass(client, field, value):
    frozen = confirm(client, one_draft(client))
    actual = actual_item(frozen)
    actual[field] = value
    checked = compare(frozen, actual)
    assert checked['outcome'] == 'mismatch'
    assert field in checked['differences']


@pytest.mark.parametrize('identity', ['', None, '0', 'unknown'])
def test_unknown_checkpoint_identity_cannot_pass(client, identity):
    frozen = confirm(client, one_draft(client))
    checked = compare(frozen, actual_item(frozen), expected_item_id=identity)
    assert checked['outcome'] == 'failed'
    assert checked['incomplete'] is True


def test_correct_values_without_readable_evidence_cannot_pass(client):
    frozen = confirm(client, one_draft(client))
    actual = actual_item(frozen)
    actual['readable_fields'] = []
    checked = compare(frozen, actual)
    assert checked['outcome'] == 'failed'
    assert checked['incomplete'] is True


def test_changed_draft_does_not_make_original_difference_pass(client):
    draft = one_draft(client)
    edited = client.patch('/api/new-items/drafts/' + draft['draft_id'], json={
        'revision': draft['revision'], 'values': {'duration': '0'}}).json()
    frozen = confirm(client, edited)
    actual = actual_item(frozen)
    checked = compare(frozen, actual)
    assert checked['outcome'] == 'mismatch'
    assert checked['per_occurrence'][0]['reference']['duration'] == '9'
    assert checked['per_occurrence'][0]['submitted']['duration'] == '0'


def test_manual_fill_can_pass_without_replacing_original_blank(client):
    draft = one_draft(client, ['Manual', 123, 0, None, 'GENERAL', False])
    edited = client.patch('/api/new-items/drafts/' + draft['draft_id'], json={
        'revision': draft['revision'], 'values': {'duration': '9'}}).json()
    frozen = confirm(client, edited)
    checked = compare(frozen, actual_item(frozen))
    assert checked['outcome'] == 'passed'
    assert checked['per_occurrence'][0]['original']['duration'] is None
    assert checked['per_occurrence'][0]['provenance']['duration'] == 'manual'


def test_numeric_zero_and_bound_false_are_real_verified_values(client):
    frozen = confirm(client, one_draft(client, ['Zero', 123, 0, 0, 'GENERAL', False]))
    checked = compare(frozen, actual_item(frozen))
    assert checked['outcome'] == 'passed'
    assert checked['incomplete'] is False


@pytest.mark.parametrize('present,expected', [(True, 'passed'), (False, 'mismatch'), (None, 'failed')])
def test_image_presence_is_not_pixel_proof(client, present, expected):
    frozen = confirm(client, one_draft(client))
    # This tests the comparator input contract, not an unimplemented upload or runner.
    frozen['submitted_values']['image_key'] = 'owned-image-digest'
    actual = actual_item(frozen)
    actual['image_present'] = present
    checked = compare(frozen, actual)
    assert checked['outcome'] == expected
    if present is True:
        assert checked['image_status'] == 'present_not_content_verified'


def test_empty_reference_or_no_occurrences_cannot_pass(client):
    frozen = confirm(client, one_draft(client))
    actual = actual_item(frozen)
    frozen['references'] = []
    checked = compare(frozen, actual)
    assert checked['outcome'] == 'failed'
    assert checked['incomplete'] is True


def test_manual_repair_of_unreadable_kind_keeps_original_without_impossible_reference(client):
    draft = one_draft(client, ['Unreadable', 'not readable', 0, 9, 'GENERAL', False])
    edited = client.patch('/api/new-items/drafts/' + draft['draft_id'], json={
        'revision': draft['revision'], 'values': {'kind': '123'}}).json()
    frozen = confirm(client, edited)
    reference = frozen['references'][0]
    assert reference['original']['kind'] == 'not readable'
    assert reference['values']['kind'] == '123'
    assert reference['provenance']['kind'] == 'manual'
    assert compare(frozen, actual_item(frozen))['outcome'] == 'passed'
