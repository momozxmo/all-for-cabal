# -*- coding: utf-8 -*-
"""Pure Event-plan drafts shared by direct import and Item Finder handoff."""
from datetime import datetime
import os
import tempfile

import event_tool
import openpyxl
from web import event_plan
from web.workspaces import WorkspaceRepository


NOW = datetime(2026, 7, 26, 15, 30)
TH = 'CabalPC TH'
SEA = 'CabalM SEA'


def _event(**extra):
    event = {
        'name': 'Summer Event',
        'rewards': [
            {'name': 'Lucky Draw', 'items': [{'kind': '1'}]},
            {'name': 'Participation', 'items': [{'kind': '2'}]},
        ],
        'end_date': datetime(2026, 8, 31, 10, 15),
    }
    event.update(extra)
    return event


def test_one_sheet_is_one_event_with_all_reward_sets():
    drafts = event_plan.build_event_drafts(
        [('Activity A', _event())], TH, now=NOW)

    assert len(drafts) == 1
    assert drafts[0]['sheet'] == 'Activity A'
    assert drafts[0]['name_th'] == 'Summer Event'
    assert [reward['group'] for reward in drafts[0]['rewards']] == [
        'Lucky Draw', 'Participation',
    ]


def test_a_single_reward_set_uses_the_event_name():
    draft = event_plan.build_event_drafts([
        ('Activity A', _event(
            name='Summer Event',
            rewards=[{
                'name': 'WINNER REWARDS',
                'items': [{'kind': '1'}],
            }],
        )),
    ], TH, now=NOW)[0]

    reward = draft['rewards'][0]
    assert (reward['name_th'], reward['name_en']) == (
        'Summer Event', 'Summer Event')
    assert reward['group'] == 'WINNER REWARDS'


def test_multiple_reward_sets_keep_their_document_names():
    draft = event_plan.build_event_drafts(
        [('Activity A', _event())], TH, now=NOW)[0]

    assert [reward['name_th'] for reward in draft['rewards']] == [
        'Lucky Draw', 'Participation']


def test_dates_start_today_and_end_at_the_servers_end_of_day():
    th = event_plan.build_event_drafts(
        [('A', _event())], TH, now=NOW)[0]
    sea = event_plan.build_event_drafts(
        [('A', _event())], SEA, now=NOW)[0]

    assert th['start_event'] == '2026-07-26T00:00:00'
    assert th['end_event'] == '2026-08-31T23:59:59'
    assert sea['end_event'] == '2026-08-31T22:59:59'
    assert (th['start_claim'], th['end_claim']) == (
        th['start_event'], th['end_event'])
    assert th['same_window'] is True


def test_missing_end_stays_blank_and_is_reported():
    draft = event_plan.build_event_drafts(
        [('A', _event(end_date=None))], TH, now=NOW)[0]

    assert draft['end_event'] == ''
    assert draft['end_claim'] == ''
    assert any('วันสิ้นสุด' in warning for warning in draft['warnings'])


def test_past_end_is_kept_and_reported():
    draft = event_plan.build_event_drafts(
        [('A', _event(end_date=datetime(2026, 7, 1)))], SEA, now=NOW)[0]

    assert draft['end_event'] == '2026-07-01T22:59:59'
    assert any('ผ่านมาแล้ว' in warning for warning in draft['warnings'])


def test_sheet_and_group_keys_do_not_collide_on_repeated_visible_names():
    drafts = event_plan.build_event_drafts([
        ('Activity A', _event(rewards=[{'name': 'Lucky Draw', 'items': []}])),
        ('Activity B', _event(rewards=[{'name': 'Lucky Draw', 'items': []}])),
    ], TH, now=NOW)

    assert drafts[0]['sheet_key'] != drafts[1]['sheet_key']
    assert drafts[0]['rewards'][0]['group_key'] != \
        drafts[1]['rewards'][0]['group_key']


def test_slug_has_the_selected_server_exactly_once():
    draft = event_plan.build_event_drafts(
        [('A', _event(name='Summer Event PCTH'))], TH, now=NOW)[0]

    assert draft['slug'] == 'summer-event-pcth'


def test_workspace_metadata_groups_rewards_back_into_their_sheets():
    a_key = event_plan.make_sheet_key('Activity A')
    b_key = event_plan.make_sheet_key('Activity B')
    metadata = {
        'ga': {
            'sheet': 'Activity A', 'sheet_key': a_key, 'group_key': 'ga',
            'event_name': 'Event A', 'reward': 'Lucky Draw',
            'end_date': '2026-08-31',
        },
        'gb': {
            'sheet': 'Activity B', 'sheet_key': b_key, 'group_key': 'gb',
            'event_name': 'Event B', 'reward': 'Lucky Draw',
            'end_date': '2026-09-30',
        },
    }

    drafts = event_plan.build_workspace_events(metadata, SEA, now=NOW)

    assert [draft['sheet'] for draft in drafts] == ['Activity A', 'Activity B']
    assert [draft['rewards'][0]['group_key'] for draft in drafts] == ['ga', 'gb']
    assert [draft['end_event'] for draft in drafts] == [
        '2026-08-31T22:59:59', '2026-09-30T22:59:59',
    ]


def test_event_draft_routes_need_a_session(anonymous_client):
    assert anonymous_client.post('/api/events/import').status_code == 401
    assert anonymous_client.get(
        '/api/workspaces/not-mine/events').status_code == 401


def test_workspace_events_are_owned_and_use_only_selected_metadata(
        client, client_for, member, other_member, test_database):
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(
            member.id, 'event', 'monthly.xlsx')
        workspace.game = SEA
        workspace.group_meta = {
            'ga': {
                'sheet': 'Activity A',
                'sheet_key': event_plan.make_sheet_key('Activity A'),
                'group_key': 'ga',
                'event_name': 'Event A',
                'reward': 'Lucky Draw',
                'end_date': '2026-08-31',
            },
        }
        workspace_id = workspace.id

    response = client.get('/api/workspaces/%s/events' % workspace_id)

    assert response.status_code == 200, response.text
    assert response.json()['events'][0]['sheet'] == 'Activity A'
    assert response.json()['events'][0]['rewards'][0]['group_key'] == 'ga'
    assert client_for(other_member).get(
        '/api/workspaces/%s/events' % workspace_id).status_code == 404


def test_workspace_event_drafts_use_the_currently_selected_game(
        client, member, test_database):
    with test_database.session() as db:
        workspace = WorkspaceRepository(db).create(
            member.id, 'event', 'monthly.xlsx')
        workspace.group_meta = {
            'ga': {
                'sheet': 'Activity A', 'group_key': 'ga',
                'event_name': 'Event A', 'reward': 'Lucky Draw',
                'end_date': '2026-08-31',
            },
        }
        workspace_id = workspace.id

    response = client.get(
        '/api/workspaces/%s/events?game=%s' % (workspace_id, TH))

    assert response.status_code == 200, response.text
    assert response.json()['events'][0]['slug'] == 'event-a-pcth'
    assert response.json()['events'][0]['end_event'].endswith('23:59:59')


def test_direct_event_import_uses_desktop_parser_and_removes_upload(
        client, monkeypatch):
    seen = {}

    def parse(path):
        seen['path'] = path
        assert os.path.exists(path)
        return [('Activity A', _event())]

    monkeypatch.setattr(event_tool, 'parse_event_plan', parse)
    response = client.post(
        '/api/events/import', data={'game': TH},
        files={'file': (
            'plan.xlsx', b'not really xlsx',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )},
    )

    assert response.status_code == 200, response.text
    assert response.json()['sheets'] == [{
        'name': 'Activity A', 'display_name': 'Summer Event', 'count': 2,
    }]
    assert response.json()['events'][0]['sheet'] == 'Activity A'
    assert response.json()['events'][0]['slug'] == 'summer-event-pcth'
    assert response.json()['skipped'] == []
    assert not os.path.exists(seen['path'])


def test_failed_direct_event_import_still_removes_upload(client, monkeypatch):
    seen = {}

    def fail(path):
        seen['path'] = path
        raise ValueError('broken workbook')

    monkeypatch.setattr(event_tool, 'parse_event_plan', fail)
    response = client.post(
        '/api/events/import', data={'game': TH},
        files={'file': ('bad.xlsx', b'broken', 'application/octet-stream')},
    )

    assert response.status_code == 400
    assert not os.path.exists(seen['path'])


def test_desktop_parser_finds_shifted_start_and_end_columns():
    handle, path = tempfile.mkstemp(suffix='.xlsx')
    os.close(handle)
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = 'Shifted Event'
    rows = [
        [None, None, 'Event Name', 'Shifted Event'],
        [None, None, None, None, 'Start', datetime(2026, 7, 1)],
        [None, None, None, None, 'End', datetime(2026, 8, 31)],
        ['Reward: Lucky Draw'],
        ['ItemKind', 'ItemName'],
        [1, 'Prize'],
    ]
    for row in rows:
        sheet.append(row)
    try:
        book.save(path)
        parsed = event_tool.parse_event_plan(path)
        finder, _ = event_tool.parse_event_plan_workbook(path)

        assert parsed[0][1]['end_date'].date().isoformat() == '2026-08-31'
        assert finder[0][1][0]['group_meta']['end_date'].date().isoformat() == \
            '2026-08-31'
    finally:
        os.unlink(path)


def test_event_reward_tables_keep_the_ranked_package_row_as_the_reward_name():
    rows = [
        ['Date', '', 'Event Name', 'Path of Dusk'],
        ['', '', '', '', '', '', 'อันดับ 1', '',
         'Item Kind', 'Item Index', 'ItemOption', 'DurationIndex',
         'Stackable', 'Display Name', 'Amt'],
        ['', '', '', '', '', '', '60 Code', '',
         '', '', '', '', '', 'Platinum Wing 30 วัน'],
        ['', '', '', '', '', '', '', '',
         111, 1, 0, 30, 'No', 'First item', 1],
        [],
        ['', '', '', '', '', '', 'อันดับ 2', '',
         'Item Kind', 'Item Index', 'ItemOption', 'DurationIndex',
         'Stackable', 'Display Name', 'Amt'],
        ['', '', '', '', '', '', 'อันดับละ 60 Code', '',
         '', '', '', '', '', 'Platinum Wing 15 วัน'],
        ['', '', '', '', '', '', '', '',
         222, 2, 0, 15, 'No', 'Second item', 1],
        [],
        ['', '', '', '', '', '', '', '',
         'Item Kind', 'Item Index', 'ItemOption', 'DurationIndex',
         'Stackable', 'Display Name', 'Amt'],
        ['', '', '', '', '', '', 'รางวัลปลอบใจ', '',
         '', '', '', '', '', 'Platinum Wing 3 วัน'],
        ['', '', '', '', '', '', '30 Code', '',
         333, 3, 0, 3, 'No', 'Consolation item', 1],
    ]

    parsed = event_tool._plan_sheet_items(rows, [])

    assert [item['kind'] for item in parsed] == ['111', '222', '333']
    assert [item['group'] for item in parsed] == [
        'อันดับ 1 Platinum Wing 30 วัน',
        'อันดับ 2 Platinum Wing 15 วัน',
        'รางวัลปลอบใจ Platinum Wing 3 วัน',
    ]
    assert all(item['group_meta']['event_name'] == 'Path of Dusk'
               for item in parsed)
