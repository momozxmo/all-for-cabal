# -*- coding: utf-8 -*-
"""Item Code and Event: what is checked before a browser opens, and what it
takes for one of them to actually be written to the live Aztek site.

Both forms can create something real, so the paths that press the button run
against fakes rather than a browser.
"""
from __future__ import annotations

import asyncio
import inspect
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pytest  # noqa: E402

from web import activity_runner, aztek_form, event_runner, itemcode_runner  # noqa: E402
from web.app import (EventRunRequest, ItemCodeRunRequest,  # noqa: E402
                     _clean_event_rewards, _clean_itemcode_rewards)

#: A game the site really has — the routes check this before anything opens.
GAME = 'CabalM TH'


def _reward(**extra):
    base = {'name_th': 'รางวัล', 'name_en': 'Reward', 'bundle_id': '208106'}
    base.update(extra)
    return base


def _itemcode(**extra):
    spec = {'name_th': 'โค้ดทดสอบ', 'name_en': 'Test Code', 'slug': 'test-code',
            'start_time': '2026-08-01 00:00:00', 'end_time': '2026-08-31 23:59:59',
            'rewards': [_reward(code_type='FIX', code_list='A\nB')]}
    spec.update(extra)
    return spec


def _event(**extra):
    spec = {'name_th': 'อีเวนต์ทดสอบ', 'name_en': 'Test Event', 'slug': 'test-event',
            'start_event': '2026-08-01 00:00:00', 'end_event': '2026-08-31 23:59:59',
            'start_claim': '2026-08-01 00:00:00', 'end_claim': '2026-09-07 23:59:59',
            'rewards': [_reward()]}
    spec.update(extra)
    return spec


# ------------------------------ date and time ------------------------------

@pytest.mark.parametrize('text, expected', [
    ('2026-08-03 09:30:00', ('2026-08-03', '09', '30', '00')),
    # What an <input type="datetime-local"> hands over, with and without seconds.
    ('2026-08-03T09:30', ('2026-08-03', '09', '30', '00')),
    ('2026-08-03T09:30:45', ('2026-08-03', '09', '30', '45')),
    ('2026-12-31 9:05:00', ('2026-12-31', '09', '05', '00')),
])
def test_a_date_is_read_the_way_the_picker_needs_it(text, expected):
    assert aztek_form.parse_datetime(text) == expected


@pytest.mark.parametrize('text', ['', None, '2 เดือน', '31/08/2026', '2026-08-03',
                                  'tomorrow', '2026-13-01 00:00:00garbage'])
def test_an_unreadable_date_is_refused_rather_than_guessed(text):
    """The desktop tool meets 'CODE EXPIRE DATE: 2 เดือน' in real plans. Guessing
    a date there would put a wrong one on the live site."""
    assert aztek_form.parse_datetime(text) is None


def test_the_calendar_is_not_even_opened_for_an_unreadable_date():
    class Trigger:
        clicked = False

        async def click(self, **kwargs):
            Trigger.clicked = True

    assert asyncio.run(aztek_form.set_datetime(
        page=None, trigger=Trigger(), value='ไม่ใช่วันที่')) is False
    assert Trigger.clicked is False


# ------------------------------- code types -------------------------------

@pytest.mark.parametrize('given, expected', [
    ('SERVER', '2'), ('Server Generate Codes', '2'), ('2', '2'),
    ('FIX', '1'), ('Fix Codes', '1'), ('1', '1'), ('', '1'), (None, '1'),
])
def test_code_type_maps_to_the_select_value(given, expected):
    assert itemcode_runner.code_type_value(given) == expected


# ------------------------------ reward sets ------------------------------

def test_reward_sets_without_a_name_are_dropped_and_order_is_kept():
    cleaned = _clean_itemcode_rewards([
        {'name_th': 'หนึ่ง', 'bundle_id': ' 1 ', 'code_type': 'SERVER',
         'num_codes': ' 25 '},
        {'name_th': '  ', 'name_en': '', 'bundle_id': '2'},   # nameless
        {'name_en': 'Two', 'bundle_id': '3'},
    ])
    assert [r['name_th'] or r['name_en'] for r in cleaned] == ['หนึ่ง', 'Two']
    assert cleaned[0]['code_type'] == '2'
    assert (cleaned[0]['bundle_id'], cleaned[0]['num_codes']) == ('1', '25')
    # Fix is the safe default: it needs codes the operator supplied, so it
    # cannot quietly ask the server to generate any.
    assert cleaned[1]['code_type'] == '1'


def test_an_event_reward_set_carries_no_codes():
    """Events hand out bundles; codes belong to Item Code alone."""
    cleaned = _clean_event_rewards([_reward(code_list='SHOULD-NOT-TRAVEL')])
    assert 'code_list' not in cleaned[0]
    assert cleaned[0]['bundle_id'] == '208106'


def test_a_queue_of_reward_sets_cannot_grow_without_bound():
    many = [_reward(name_th='r%d' % n) for n in range(60)]
    assert len(_clean_event_rewards(many)) == 20


# ------------------------------ the API gate ------------------------------

def test_creating_is_off_unless_asked():
    assert ItemCodeRunRequest(game=GAME).do_save is False
    assert EventRunRequest(game=GAME).do_save is False


def test_an_event_defaults_to_what_the_plan_always_says():
    """Type WINNER with both counters at zero — every plan Event is like this,
    so it is the default rather than something to fill in each time."""
    payload = EventRunRequest(game=GAME, events=[{'slug': 'x'}])
    spec = payload.events[0]
    assert (spec.kind, spec.quantity, spec.remaining) == ('WINNER', '0', '0')


def test_item_code_limit_defaults_to_unlimited():
    payload = ItemCodeRunRequest(game=GAME, itemcodes=[{}])
    spec = payload.itemcodes[0]
    assert spec.limited is False
    assert (spec.quantity, spec.remaining) == ('', '')


def test_enabled_item_code_limit_requires_both_positive_counts(client):
    response = client.post('/api/itemcodes/run', json={
        'game': GAME,
        'itemcodes': [_itemcode(limited=True, quantity='', remaining='40')],
        'do_save': False,
    })
    assert response.status_code == 400
    assert 'จำนวนครั้งที่สามารถใช้งานได้' in response.json()['detail']


@pytest.mark.parametrize('path', ['/itemcodes', '/events'])
def test_the_pages_need_a_session(anonymous_client, path):
    response = anonymous_client.get(path, follow_redirects=False)
    assert response.status_code in (302, 303, 307)
    assert response.headers['location'] == '/login'


@pytest.mark.parametrize('path', ['/api/itemcodes/run', '/api/events/run'])
def test_the_run_apis_need_a_session(anonymous_client, path):
    assert anonymous_client.post(path, json={'game': GAME}).status_code == 401


@pytest.mark.parametrize('path, key, spec', [
    ('/api/itemcodes/run', 'itemcodes', _itemcode()),
    ('/api/events/run', 'events', _event()),
])
def test_an_unknown_game_never_opens_a_browser(client, path, key, spec):
    response = client.post(path, json={'game': 'Cabal Z', key: [spec]})
    assert response.status_code == 400
    assert 'ไม่รู้จักเกม' in response.json()['detail']


@pytest.mark.parametrize('path, key', [('/api/itemcodes/run', 'itemcodes'),
                                       ('/api/events/run', 'events')])
def test_an_empty_queue_is_refused(client, path, key):
    response = client.post(path, json={'game': GAME, key: []})
    assert response.status_code == 400


@pytest.mark.parametrize('path, key, spec', [
    ('/api/itemcodes/run', 'itemcodes', _itemcode()),
    ('/api/events/run', 'events', _event()),
])
def test_a_preview_takes_one_at_a_time(client, path, key, spec):
    """Preview leaves a window standing, and there is only one browser slot."""
    response = client.post(path, json={'game': GAME, key: [spec, spec]})
    assert response.status_code == 400
    assert 'ทีละรายการ' in response.json()['detail']


@pytest.mark.parametrize('slug', ['Test-Code', 'test code', 'โค้ด', '', 'a_b'])
def test_a_slug_aztek_would_reject_is_caught_here(client, slug):
    """Aztek only takes a-z, digits and hyphens, and only says so after the trip."""
    response = client.post('/api/itemcodes/run', json={
        'game': GAME, 'itemcodes': [_itemcode(slug=slug)]})
    assert response.status_code == 400
    assert 'slug' in response.json()['detail']


@pytest.mark.parametrize('field', ['start_time', 'end_time'])
def test_an_item_code_without_a_readable_date_is_refused(client, field):
    response = client.post('/api/itemcodes/run', json={
        'game': GAME, 'itemcodes': [_itemcode(**{field: '2 เดือน'})]})
    assert response.status_code == 400
    assert 'วันเวลา' in response.json()['detail']


@pytest.mark.parametrize('field', ['start_event', 'end_event',
                                   'start_claim', 'end_claim'])
def test_an_event_needs_all_four_dates(client, field):
    """Two windows, four ends. A missing one is not a blank field on the site —
    the page keeps its own default, which is this week."""
    response = client.post('/api/events/run', json={
        'game': GAME, 'events': [_event(**{field: ''})]})
    assert response.status_code == 400


@pytest.mark.parametrize('path, key, spec', [
    ('/api/itemcodes/run', 'itemcodes', _itemcode()),
    ('/api/events/run', 'events', _event()),
])
def test_a_valid_request_still_needs_a_paired_aztek_session(client, path, key, spec):
    response = client.post(path, json={'game': GAME, key: [spec]})
    assert response.status_code == 409
    assert 'Aztek' in response.json()['detail']


@pytest.mark.parametrize('path, key, spec, labels', [
    ('/api/itemcodes/run', 'itemcodes',
     _itemcode(start_time='2026-09-01 00:00:00', end_time='2026-08-01 00:00:00'),
     'เวลาเริ่มใช้งาน'),
    ('/api/events/run', 'events',
     _event(start_event='2026-09-01 00:00:00', end_event='2026-08-01 00:00:00'),
     'วันเริ่มกิจกรรม'),
])
def test_an_end_before_its_start_is_refused(client, path, key, spec, labels):
    """Plan files are re-used for the next run of the same activity, so a date
    that has already passed reaches this more often than it should."""
    response = client.post(path, json={'game': GAME, key: [spec]})
    assert response.status_code == 400
    assert labels in response.json()['detail']


# ------------------------- drafts from the plan file -------------------------

def test_the_draft_api_needs_a_session(anonymous_client):
    assert anonymous_client.get(
        '/api/workspaces/w1/itemcodes').status_code == 401


def test_a_file_with_no_conditions_has_nothing_to_draft(client, workspace_for_member):
    response = client.get('/api/workspaces/%s/itemcodes' % workspace_for_member.id)
    assert response.status_code == 400
    assert 'Event/Prize' in response.json()['detail']


def test_each_group_of_the_plan_comes_back_as_its_own_draft(
        client, test_database, workspace_for_member):
    from web.models import WorkspaceRecord

    with test_database.session() as db:
        record = db.get(WorkspaceRecord, workspace_for_member.id)
        record.game = 'CabalM SEA'
        record.group_meta = {
            'Storm Chaser WINNER REWARDS': {
                'activity': 'Storm Chaser', 'reward': 'WINNER REWARDS',
                'expire': '2026-08-31 00:00:00', 'codes_per_set': '35',
                'set_count': '1', 'total': '35', 'unique_code': True,
                'cannot_repeat': True},
            'Storm Chaser Audience Reward': {
                'activity': 'Storm Chaser', 'reward': 'Audience Reward',
                'expire': '2026-08-31 00:00:00', 'codes_per_set': '400',
                'set_count': '1', 'total': '400', 'unique_code': True,
                'cannot_repeat': True},
        }

    body = client.get('/api/workspaces/%s/itemcodes'
                      % workspace_for_member.id).json()
    assert [d['name_th'] for d in body['itemcodes']] == [
        'Storm Chaser - WINNER REWARDS', 'Storm Chaser - Audience Reward']
    assert body['itemcodes'][0]['rewards'][0]['num_codes'] == '40'
    assert body['game'] == 'CabalM SEA'


def test_a_draft_belongs_to_someone_else_is_not_readable(
        client_for, other_member, workspace_for_member):
    stranger = client_for(other_member)
    assert stranger.get('/api/workspaces/%s/itemcodes'
                        % workspace_for_member.id).status_code == 404


# --------------------------- filling and saving ---------------------------

class FakePage:
    """Enough page for run_many: it navigates and waits, nothing more."""

    def __init__(self, url='https://x/itemcodes/create'):
        self.url = url

    async def goto(self, url, **kwargs):
        return None

    async def wait_for_timeout(self, ms):
        return None


def _drive(builder, specs):
    """Run run_many with the browser stack stubbed out."""
    page = FakePage()

    class Ctx:
        async def new_page(self):
            return page

        async def close(self):
            return None

    class Browser:
        async def new_context(self, **kwargs):
            return Ctx()

        async def close(self):
            return None

    class Driver:
        chromium = type('C', (), {'launch': staticmethod(
            lambda **kwargs: _value(Browser()))})()

        async def stop(self):
            return None

    real = activity_runner.async_playwright
    activity_runner.async_playwright = lambda: type(
        'P', (), {'start': staticmethod(lambda: _value(Driver()))})()
    try:
        return asyncio.run(builder.run_many(
            game=GAME, specs=specs, storage_state={}))
    finally:
        activity_runner.async_playwright = real


async def _value(value):
    return value


def _builder(cls=itemcode_runner.ItemCodeBuilder):
    return cls(lambda message, level='INFO': None)


def test_a_form_that_is_missing_a_required_field_is_not_saved():
    """Half an Item Code on the live site is worse than none: it looks made."""
    builder = _builder()
    saved = []
    builder.fill_form = lambda page, spec: _value(['เวลาสิ้นสุด'])
    builder._save = lambda page: saved.append(page) or _value((True, '1'))
    results = _drive(builder, [{'name_th': 'a', 'slug': 'a'}])
    assert saved == []
    assert results[0]['saved'] is False
    assert results[0]['missing'] == ['เวลาสิ้นสุด']
    assert 'เวลาสิ้นสุด' in results[0]['error']


def test_one_failure_does_not_stop_the_queue():
    builder = _builder(event_runner.EventBuilder)
    fills = iter([[], ['Bundle'], []])

    def fill(page, spec):
        return _value(next(fills))

    made = iter([(True, '11'), (True, '22')])
    builder.fill_form = fill
    builder._save = lambda page: _value(next(made))
    results = _drive(builder, [{'name_th': n, 'slug': n} for n in ('a', 'b', 'c')])
    assert [(r['name'], r['saved'], r['made_id']) for r in results] == [
        ('a', True, '11'), ('b', False, None), ('c', True, '22')]


def test_a_preview_has_no_way_to_press_the_button():
    """``run`` is what a preview calls, and it must not be able to write."""
    source = inspect.getsource(activity_runner.ActivityBuilder.run)
    assert '_save' not in source
    assert '_save' in inspect.getsource(activity_runner.ActivityBuilder.run_many)


def test_the_two_forms_are_told_apart_by_where_they_write():
    """Both live at the game root, not under /shop/ where bundles are."""
    assert activity_runner.create_url(GAME, 'itemcodes').endswith(
        '/cabalm/itemcodes/create')
    assert '/shop/' not in activity_runner.create_url(GAME, 'events')
    # v2 is a different host from the one the desktop tool drives.
    assert 'aztek-tools-v2' in activity_runner.create_url(GAME, 'events')


def test_an_item_code_is_always_all_and_leaves_descriptions_alone():
    """WINNER is the Event's idea and descriptions are still left alone."""
    source = inspect.getsource(itemcode_runner.ItemCodeBuilder._fill_header)
    assert "select_by_options(page, 'ALL'" in source
    assert 'desc_th' not in source and 'desc_en' not in source


def test_itemcode_builder_fills_code_wide_limit_only_when_enabled(monkeypatch):
    calls = []

    async def fake_fill(page, selector, value, log=None, label='', scope=None):
        calls.append(('fill', selector, str(value)))
        return True

    async def fake_switch(page, label, wanted, log=None, occurrence=0):
        calls.append(('switch', label, wanted))
        return True

    async def fake_select(page, wanted, options, log=None, index=0):
        calls.append(('select', wanted))
        return True

    async def fake_datetime(page, trigger, value, log=None, label=''):
        calls.append(('datetime', label, value))
        return True

    monkeypatch.setattr(aztek_form, 'fill', fake_fill)
    monkeypatch.setattr(aztek_form, 'set_switch', fake_switch)
    monkeypatch.setattr(aztek_form, 'select_by_options', fake_select)
    monkeypatch.setattr(aztek_form, 'set_datetime', fake_datetime)

    class Locator:
        @property
        def first(self):
            return self

    class Page:
        def locator(self, selector):
            return Locator()

    builder = itemcode_runner.ItemCodeBuilder(lambda *args: None)
    finite = _itemcode(limited=True, quantity='40', remaining='40')
    asyncio.run(builder._fill_header(Page(), finite, []))
    assert ('switch', 'จำกัดจำนวน', True) in calls
    assert ('fill', 'input[name="quantity"]', '40') in calls
    assert ('fill', 'input[name="remaining"]', '40') in calls

    calls.clear()
    unlimited = _itemcode(limited=False, quantity='99', remaining='99')
    asyncio.run(builder._fill_header(Page(), unlimited, []))
    assert ('switch', 'จำกัดจำนวน', False) in calls
    assert not any(call[:2] == ('fill', 'input[name="quantity"]')
                   for call in calls)
    assert not any(call[:2] == ('fill', 'input[name="remaining"]')
                   for call in calls)


def test_a_reward_set_still_gets_its_own_code_limit():
    """Ticking that one is what makes the two count boxes exist at all."""
    source = inspect.getsource(itemcode_runner.ItemCodeBuilder._fill_reward)
    assert 'จำกัดจำนวน Code' in source
    assert 'rewards.%d.quantity' in source


def test_each_form_knows_its_own_confirm_button():
    assert itemcode_runner.ItemCodeBuilder.SAVE_LABEL == 'สร้าง Item Code'
    assert event_runner.EventBuilder.SAVE_LABEL == 'สร้าง Event'
    assert event_runner.EventBuilder.PATH == 'events'


def test_a_reward_set_is_addressed_through_its_own_block():
    """Reward sets are tabs on v2 — only the open one is on the page, so its
    bundle button has to be found from that set's own field, never by counting
    the buttons on the page."""
    seen = []

    class Page:
        def locator(self, selector):
            seen.append(selector)
            return selector

    aztek_form.reward_card(Page(), 2)
    assert 'rewards.2.name_th' in seen[0]
    assert 'ancestor' in seen[0] and 'เลือก bundle' in seen[0]
