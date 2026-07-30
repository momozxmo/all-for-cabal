# -*- coding: utf-8 -*-
"""Pure Product-draft mapping from persisted Shop workspace metadata."""
import datetime as dt

from web import product_plan


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


def test_product_draft_uses_same_name_end_time_limits_and_tags():
    draft = product_plan.build_products(
        {'g1': _meta()}, 'CabalPC TH', now=NOW)[0]

    assert (draft['name_th'], draft['name_en']) == (
        'Limited Orb x30+5', 'Limited Orb x30+5')
    assert draft['source_group_key'] == 'g1'
    assert draft['source_sheet'] == 'Promotion 15.7'
    assert draft['start_at'] == '2026-07-30 00:00:00'
    assert draft['end_at'] == '2026-07-30 07:59:00'
    assert draft['limit_type'] == 'PLAYER'
    assert draft['limit_quantity'] == '10'
    assert draft['limit_reset_interval_days'] == ''
    assert draft['limit_reset_at'] == ''
    assert draft['tags'] == ['SALE']
    assert draft['prices'] == []
    assert draft['price_candidates'][0]['source_label'] == 'Future Coin'


def test_product_draft_defaults_are_safe_and_bundle_origin_is_visible():
    draft = product_plan.build_products(
        {'g1': _meta()}, 'CabalPC TH', now=NOW)[0]
    assert draft['category_id'] == ''
    assert draft['category_label'] == ''
    assert draft['details_th'] == draft['details_en'] == ''
    assert draft['bundle_id'] == '223553'
    assert draft['bundle_source'] == 'workbook'
    assert draft['is_enabled'] is False
    assert draft['is_test_mode'] is True
    assert draft['is_hidden'] is False
    assert draft['position'] == '0'


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


def test_everyday_and_weekday_reset_are_mapped_deterministically():
    drafts = product_plan.build_products({
        'daily': _meta(
            reset_day='Everyday', reset_time='04:30:00'),
        'weekly': _meta(
            reset_day='Friday', reset_time='09:15:00'),
    }, 'CabalPC TH', now=NOW)
    assert drafts[0]['limit_reset_interval_days'] == '1'
    assert drafts[0]['limit_reset_at'] == '2026-07-31 04:30:00'
    assert drafts[1]['limit_reset_interval_days'] == '7'
    assert drafts[1]['limit_reset_at'] == '2026-07-31 09:15:00'


def test_all_approved_tags_have_stable_order():
    draft = product_plan.build_products({
        'g1': _meta(
            shop_label='Event Popular Must Have Limited New 15% Discount'),
    }, 'CabalPC TH', now=NOW)[0]
    assert draft['tags'] == ['EVENT', 'HOT', 'LIMITED', 'NEW', 'SALE']


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
