"""Synthetic result-identity regressions; every Aztek request is intercepted.

Flat numeric id is existing tested compatibility, not a newly verified live
Item Code response schema. Bundle/Reward identifiers cannot identify a code.
"""
import asyncio

import pytest

from web.itemcode_runner import ItemCodeBuilder
from test_web_itemcode_id_first import (
    create_action_spec, itemcode_confirmation_html, routed_runner_browser,
)


GAME_CASES = (
    ('CabalM TH', '/cabalm/itemcode/events',
     'https://aztek-tools-v2.combo-interactive.com/combo/cabalm/itemcodes/create'),
    ('CabalM SEA', '/cabalmsea/itemcode/events',
     'https://aztek-tools-v2.combo-interactive.com/combo/cabalmsea/itemcodes/create'),
    ('CabalPC TH', '/cabalpc/itemcode/events',
     'https://aztek-tools-v2.combo-interactive.com/combo/cabalpc/itemcodes/create'),
    ('CabalPC SEA', '/cabalpcsea/itemcode/events',
     'https://aztek-tools-v2.combo-interactive.com/combo/cabalpcsea/itemcodes/create'),
)


@pytest.mark.parametrize(('game', 'write_path', 'create_url'), GAME_CASES)
@pytest.mark.parametrize(('payload', 'expected_id'), (
    ({'id': 501, 'rewards': [{'bundle_id': 1001}]}, '501'),
    ({'rewards': [{'bundle_id': 1001}]}, None),
    ({'rewards': [{'id': 7343}]}, None),
), ids=('own-id-before-bundle', 'bundle-only-is-not-code', 'reward-only-is-not-code'))
def test_itemcode_result_never_borrows_bundle_or_reward_id(
        monkeypatch, game, write_path, create_url, payload, expected_id):
    endpoint = 'https://admin-api-v2.combo-interactive.com' + write_path
    html = itemcode_confirmation_html().replace('/synthetic-itemcode-write', endpoint)
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=(create_url,),
        synthetic_write_url=endpoint, synthetic_write_json=payload,
        context_options={'service_workers': 'block'})
    logs = []
    result = asyncio.run(ItemCodeBuilder(lambda message, level: logs.append((message, level))).run_many(
        game, [{**create_action_spec(), 'group': 'source-group'}],
        {'cookies': [], 'origins': []}))[0]

    assert (result['slug'], result['group'], result['saved'], result['made_id'], result['error']) == (
        'requested-code', 'source-group', True, expected_id, None)
    assert snapshots[0]['confirms'] == '1'
    assert snapshots[0]['submits'] == ['1']
    assert traffic == [
        ('GET', create_url),
        ('POST', endpoint + '?owner=form'),
    ]
    if expected_id is None:
        assert any(level == 'WARNING' and 'อ่านเลขไม่ได้' in message for message, level in logs)
        assert not any(level == 'SUCCESS' and ' — เลข:' in message for message, level in logs)
