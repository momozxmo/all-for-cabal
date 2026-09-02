# -*- coding: utf-8 -*-
"""Pure Product-draft mapping from persisted Shop workspace metadata."""
import datetime as dt

from web import item_service
from web import product_plan
from web.models import WorkspaceRecord


NOW = dt.datetime(2026, 7, 30, 19, 0, 0)


def _meta(**overrides):
    product = {
        'source_sheet': 'Promotion 15.7',
        'name': 'Limited Orb x30+5',
        'bundle_id': '223553',
        'category_label': 'Highlight',
        'shop_label': '20% Off / ลด 20%',
        'start_at': '2026-07-30 00:00:00',
        'end_at': '2026-07-30 07:59:00',
        'limit_text': '10 ครั้ง/ไอดี',
        'reset_day': 'No Reset',
        'reset_time': '',
        'price_candidates': [{
            'source_label': 'Future Coin',
            'original_price': 6600,
            'sale_price': 6600,
        }],
        'warnings': [],
    }
    product.update(overrides)
    return {'is_shop': True, 'product_meta': product}


def test_product_draft_uses_same_name_end_time_and_limits_without_tags():
    draft = product_plan.build_products(
        {'g1': _meta()}, 'CabalPC TH', now=NOW)[0]

    assert (draft['name_th'], draft['name_en']) == (
        'Limited Orb x30+5', 'Limited Orb x30+5')
    assert draft['source_group_key'] == 'g1'
    assert draft['source_sheet'] == 'Promotion 15.7'
    assert draft['start_at'] == '2026-07-30 00:00:00'
    assert draft['end_at'] == '2026-07-30 07:59:59'
    assert draft['limit_type'] == 'PLAYER'
    assert draft['limit_quantity'] == '10'
    assert draft['limit_reset_interval_days'] == ''
    assert draft['limit_reset_at'] == ''
    assert 'tags' not in draft
    assert draft['prices'] == []
    assert draft['price_candidates'][0]['source_label'] == 'Future Coin'


def test_product_draft_defaults_are_safe_and_bundle_origin_is_visible():
    draft = product_plan.build_products(
        {'g1': _meta(bundle_ids=['223553'])}, 'CabalPC TH', now=NOW)[0]
    assert draft['category_id'] == ''
    assert draft['category_label'] == ''
    assert draft['details_th'] == draft['details_en'] == ''
    assert draft['bundle_id'] == '223553'
    assert draft['bundle_ids'] == ['223553']
    assert draft['composite_required'] is False
    assert draft['bundle_source'] == 'workbook'
    assert draft['is_enabled'] is False
    assert draft['is_test_mode'] is True
    assert draft['is_hidden'] is False
    assert draft['position'] == '0'


def test_multiple_source_bundles_become_direct_product_bundles():
    draft = product_plan.build_products({
        'g1': _meta(
            bundle_id='', bundle_ids=['223930', '223931'],
            start_at='', reset_day='Friday', reset_time='09:15:00'),
    }, 'CabalPC TH', now=NOW)[0]

    assert draft['bundle_ids'] == ['223930', '223931']
    assert draft['primary_bundle_id'] == '223930'
    assert draft['composite_required'] is False
    assert draft['bundle_id'] == '223930'
    assert draft['bundle_source'] == 'workbook'
    assert draft['start_at'] == '2026-07-30 00:00:00'
    assert draft['end_at'] == '2026-07-30 07:59:59'
    assert draft['category_source'] == 'Highlight'
    assert draft['price_candidates'][0]['source_label'] == 'Future Coin'
    assert draft['limit_type'] == 'PLAYER'
    assert draft['limit_quantity'] == '10'
    assert draft['limit_reset_interval_days'] == '7'
    assert draft['limit_reset_at'] == '2026-07-24 09:15:00'
    assert not any('Composite Bundle' in warning for warning in draft['warnings'])


def test_product_draft_normalizes_numeric_and_delimited_source_bundle_ids():
    draft = product_plan.build_products({
        'g1': _meta(
            bundle_id='',
            bundle_ids=[223930.0, '223931,223932', '223,933']),
    }, 'CabalPC TH', now=NOW)[0]

    assert draft['bundle_ids'] == [
        '223930', '223931', '223932', '223933']
    assert draft['primary_bundle_id'] == '223930'
    assert draft['bundle_id'] == '223930'
    assert draft['composite_required'] is False


def test_no_limit_and_character_limit_are_not_confused():
    drafts = product_plan.build_products({
        'no-limit': _meta(limit_text='No Limit'),
        'character': _meta(limit_text='5 ครั้ง/ตัวละคร'),
    }, 'CabalPC TH', now=NOW)
    assert drafts[0]['limit_type'] == 'UNLIMITED'
    assert drafts[0]['limit_quantity'] == ''
    assert drafts[1]['limit_type'] == 'CHARACTER'
    assert drafts[1]['limit_quantity'] == '5'


def test_ambiguous_limit_stays_unresolved_with_a_warning():
    draft = product_plan.build_products({
        'g1': _meta(limit_text='10 ครั้ง'),
    }, 'CabalPC TH', now=NOW)[0]
    assert draft['limit_type'] == ''
    assert draft['limit_quantity'] == '10'
    assert any('Limit' in warning for warning in draft['warnings'])


def test_everyday_and_weekday_reset_start_one_interval_in_the_past():
    drafts = product_plan.build_products({
        'daily': _meta(
            reset_day='Everyday', reset_time='04:30:00'),
        'weekly': _meta(
            reset_day='Friday', reset_time='09:15:00'),
    }, 'CabalPC TH', now=NOW)
    assert drafts[0]['limit_reset_interval_days'] == '1'
    assert drafts[0]['limit_reset_at'] == '2026-07-29 04:30:00'
    assert drafts[1]['limit_reset_interval_days'] == '7'
    assert drafts[1]['limit_reset_at'] == '2026-07-24 09:15:00'


def test_same_weekday_reset_uses_only_a_candidate_not_after_bangkok_now():
    before_reset = product_plan.build_products({
        'g1': _meta(reset_day='Friday', reset_time='09:15:00'),
    }, 'CabalPC TH', now=dt.datetime(2026, 7, 31, 8, 0))[0]
    after_reset = product_plan.build_products({
        'g1': _meta(reset_day='Friday', reset_time='09:15:00'),
    }, 'CabalPC TH', now=dt.datetime(2026, 7, 31, 10, 0))[0]

    assert before_reset['limit_reset_at'] == '2026-07-24 09:15:00'
    assert after_reset['limit_reset_at'] == '2026-07-31 09:15:00'


def test_missing_end_date_and_existing_parser_warnings_are_preserved():
    draft = product_plan.build_products({
        'g1': _meta(
            end_at='', warnings=['อ่าน End Date/End Time ไม่ครบ']),
    }, 'CabalPC TH', now=NOW)[0]
    assert 'อ่าน End Date/End Time ไม่ครบ' in draft['warnings']
    assert any('End Date' in warning for warning in draft['warnings'])


def test_build_products_keeps_source_order_and_count_products_deduplicates():
    drafts = product_plan.build_products({
        'second': _meta(name='Second'),
        'first': _meta(name='First'),
        'not-product': {'is_shop': True},
    }, 'CabalPC TH', now=NOW)
    assert [draft['source_group_key'] for draft in drafts] == [
        'second', 'first']

    rows = [
        {'sources': ['second'], 'group_meta': _meta(name='Second')},
        {'sources': ['second'], 'group_meta': _meta(name='Second')},
        {'group_keys': ['first'], 'group_meta': _meta(name='First')},
        {'sources': ['ignored'], 'group_meta': {}},
    ]
    assert product_plan.count_products(rows) == 2


def test_workspace_products_are_owned_and_keep_the_selected_game(
        client, test_database, workspace_for_member):
    with test_database.session() as db:
        record = db.get(WorkspaceRecord, workspace_for_member.id)
        record.mode = 'shop'
        record.game = 'CabalPC TH'
        record.group_meta = {'g1': _meta(
            name='Orb Pack',
            start_at='2026-07-30 00:00:00',
            end_at='2026-08-30 07:59:00',
        )}

    response = client.get(
        f'/api/workspaces/{workspace_for_member.id}/products')

    assert response.status_code == 200
    assert response.json()['game'] == 'CabalPC TH'
    assert response.json()['workspace_id'] == workspace_for_member.id
    assert response.json()['products'][0]['source_group_key'] == 'g1'
    assert response.json()['products'][0]['bundle_ids'] == ['223553']
    assert response.json()['products'][0]['composite_required'] is False


def test_workspace_without_product_metadata_returns_an_empty_list(
        client, workspace_for_member):
    response = client.get(
        f'/api/workspaces/{workspace_for_member.id}/products')
    assert response.status_code == 200
    assert response.json()['products'] == []


def test_composite_bundle_preview_keeps_only_the_exact_product_group(
        client, test_database, workspace_for_member):
    with test_database.session() as db:
        record = db.get(WorkspaceRecord, workspace_for_member.id)
        record.mode = 'shop'
        record.game = 'CabalPC TH'
        record.group_meta = {
            'group-a': _meta(name='Product A'),
            'group-b': _meta(name='Product B'),
        }
        record.results = [
            {'aztek_id': '11', 'item_name': 'A only', 'amt': '2',
             'sources': ['Product A'], 'group_keys': ['group-a']},
            {'aztek_id': '12', 'item_name': 'Shared', 'amt': '3',
             'sources': ['Product A', 'Product B'],
             'group_keys': ['group-a', 'group-b']},
            {'aztek_id': '99', 'item_name': 'B only', 'amt': '9',
             'sources': ['Product B'], 'group_keys': ['group-b']},
        ]

    response = client.post(
        f'/api/workspaces/{workspace_for_member.id}/bundles',
        json={'source_group_key': 'group-a'},
    )

    assert response.status_code == 200, response.text
    assert [bundle['group_key'] for bundle in response.json()['bundles']] == [
        'group-a']
    assert [(item['id'], item['qty'])
            for item in response.json()['bundles'][0]['items']] == [
        ('11', '2'), ('12', '3')]


def test_composite_preview_without_results_returns_exact_item_finder_handoff(
        client, test_database, workspace_for_member):
    """A direct Product import has criteria but no Item Finder results yet."""
    with test_database.session() as db:
        record = db.get(WorkspaceRecord, workspace_for_member.id)
        record.mode = 'shop'
        record.game = 'CabalPC TH'
        record.group_meta = {
            'group-a': _meta(name='Product A'),
            'group-b': _meta(name='Product B'),
        }
        record.criteria = [
            {'kind': '11', 'name': 'A only',
             'sources': ['Product A'], 'group_keys': ['group-a']},
            {'kind': '12', 'name': 'Shared',
             'sources': ['Product A', 'Product B'],
             'group_keys': ['group-a', 'group-b']},
            {'kind': '99', 'name': 'B only',
             'sources': ['Product B'], 'group_keys': ['group-b']},
        ]
        record.results = []

    response = client.post(
        f'/api/workspaces/{workspace_for_member.id}/bundles',
        json={'source_group_key': 'group-a'},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body['bundles'] == []
    assert body['needs_search'] is True
    assert body['search_handoff']['workspace_id'] == workspace_for_member.id
    assert body['search_handoff']['source_group_key'] == 'group-a'
    assert [row['kind'] for row in body['search_handoff']['criteria']] == [
        '11', '12']
    assert body['search_handoff']['criteria'][1]['group_keys'] == ['group-a']
    assert body['search_handoff']['criteria'][1]['sources'] == ['Product A']


def test_import_plan_reports_product_count_per_candidate_sheet(
        client, monkeypatch):
    monkeypatch.setattr(item_service, 'parser_for_mode', lambda mode: (
        lambda path: ([
            ('Promotion 15.7', [
                {'kind': '1', 'sources': ['g1'],
                 'group_meta': _meta(name='Orb Pack')},
                {'kind': '2', 'sources': ['g1'],
                 'group_meta': _meta(name='Orb Pack')},
            ]),
        ], [])
    ))

    response = client.post(
        '/api/import-plan',
        data={'mode': 'shop'},
        files={'file': (
            'plan.xlsx', b'fake workbook', 'application/octet-stream')},
    )

    assert response.status_code == 200, response.text
    assert response.json()['sheets'] == [{
        'name': 'Promotion 15.7',
        'display_name': 'Orb Pack',
        'count': 2,
        'product_count': 1,
    }]
