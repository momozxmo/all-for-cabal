# -*- coding: utf-8 -*-
"""Bundle creation: reward validation, draw-rate discovery, and save safety.

These cover the parts that can write to the live Aztek site, so they run
against fake pages rather than a real browser.
"""
from __future__ import annotations

import asyncio
import inspect

import pytest

from web import bundle_runner
from web.app import BundleRunRequest, _clean_items, _clean_rewards


# ------------------------------ rewards ------------------------------

def test_clean_rewards_preserve_valid_entries_as_canonical_text():
    cleaned = _clean_rewards([
        {'type': 'credit', 'value': 'Alz', 'qty': '100'},   # lowercase kind
        {'type': 'PLAYER_EXP', 'value': 'Rank 5', 'qty': 1},
    ])
    assert cleaned == [
        {'type': 'CREDIT', 'value': 'Alz', 'qty': '100'},
        {'type': 'PLAYER_EXP', 'value': 'Rank 5', 'qty': '1'},
    ]


@pytest.mark.parametrize('reward', [
    {'type': 'BITCOIN', 'value': 'nope', 'qty': '1'},
    {'type': 'DEBIT', 'value': '', 'qty': '1'},
    {'type': 'MILEAGE', 'value': 'M', 'qty': '0'},
    {'type': 'MILEAGE', 'value': 'M', 'qty': 'ten'},
    {'type': 'MILEAGE', 'value': 'M', 'qty': None},
])
def test_clean_rewards_reject_every_invalid_submitted_entry(reward):
    with pytest.raises(ValueError):
        _clean_rewards([reward])


def test_creating_is_off_unless_asked():
    """A request that omits do_save must never write to the live site."""
    payload = BundleRunRequest(game='Cabal M')
    assert payload.do_save is False
    assert payload.bundles == []


def test_reward_tabs_use_the_v2_wording():
    """v2 tabs are not the v1 accordion headings — reusing those found nothing.

    The one that actually differs is PLAYER_EXP ("Player Exp." vs "Player
    Experience"), so pin the whole map rather than just the shape.
    """
    assert bundle_runner.REWARD_TABS == {
        'CREDIT': 'Credit', 'DEBIT': 'Debit',
        'MILEAGE': 'Mileage', 'PLAYER_EXP': 'Player Exp.'}
    assert set(bundle_runner.REWARD_TABS) == set(bundle_runner.REWARD_KINDS)


def test_preview_does_not_tour_every_reward_tab():
    """Adding one reward used to also open all four tabs to refill a cache.

    The tour costs four page interactions the operator did not ask for, so it
    belongs to the explicit fetch trip alone.
    """
    assert 'read_reward_options' not in inspect.getsource(
        bundle_runner.BundleBuilder.run)
    assert 'read_reward_options' in inspect.getsource(
        bundle_runner.fetch_reward_options)


# --------------------------- create them all ---------------------------

def test_each_bundle_carries_its_own_type_and_rewards():
    """The queue holds bundles from different events; one setting for the run
    would give them all the same type and the same currency."""
    payload = BundleRunRequest(game='Cabal M', bundles=[
        {'name': 'a', 'bundle_type': 'RANDOM',
         'rewards': [{'type': 'CREDIT', 'value': 'Ark Gem', 'qty': '1'}]},
        {'name': 'b'},
    ])
    assert payload.bundles[0].bundle_type == 'RANDOM'
    assert payload.bundles[0].rewards[0]['value'] == 'Ark Gem'
    assert (payload.bundles[1].bundle_type, payload.bundles[1].rewards) == ('FIXED', [])


def test_items_are_canonical_and_keep_the_submitted_order():
    items = _clean_items([
        {'id': ' 200479 ', 'qty': '3', 'tier': 'Epic'},
        {'id': '11', 'rate': '12.500'},
        {'id': '22'},
    ])
    assert items == [
        {'id': '200479', 'qty': '3', 'tier': 'Epic', 'rate': ''},
        {'id': '11', 'qty': '1', 'tier': 'Common', 'rate': '12.5'},
        {'id': '22', 'qty': '1', 'tier': 'Common', 'rate': ''},
    ]


@pytest.mark.parametrize('items', [
    [{'id': 'ID 11'}],
    [{'id': '1', 'qty': ''}],
    [{'id': '1', 'qty': None}],
    [{'id': '1', 'qty': 1.0}],
    [{'id': '1', 'qty': '0'}],
    [{'id': '1'}, {'id': '1'}],
    [{'id': '1', 'rate': '1e3'}],
])
def test_invalid_item_rows_reject_instead_of_being_rewritten_or_dropped(items):
    with pytest.raises(ValueError):
        _clean_items(items)


def test_bundle_item_limit_accepts_200_and_rejects_201_without_truncating():
    assert len(_clean_items([{'id': str(n)} for n in range(1, 201)])) == 200
    with pytest.raises(ValueError):
        _clean_items([{'id': str(n)} for n in range(1, 202)])




def test_run_many_leaves_a_partially_filled_bundle_unsaved():
    """A failed add must not turn the remaining rows into a real Bundle."""
    builder = _builder()
    save_calls = []

    async def partial_fill(*args):
        return 1, 0

    async def save(page):
        save_calls.append(page)
        return True, 'should-not-exist'

    builder._fill_form = partial_fill
    builder._save = save
    results = asyncio.run(_run_many(builder, [], bundles=[{
        'group': 'partial', 'name': 'partial',
        'items': [{'id': '1'}, {'id': '2'}],
        'rewards': [{'type': 'CREDIT', 'value': 'Alz', 'qty': '1'}],
    }]))

    assert save_calls == []
    assert results[0]['saved'] is False
    assert results[0]['bundle_id'] is None
    assert results[0]['error']


async def _async(value):
    return value


async def _run_many(builder, names, bundles=None):
    """Drive run_many with the browser stack stubbed out."""
    if bundles is None:
        bundles = [
            {'group': n, 'name': n, 'items': [{'id': '1'}], 'rewards': []}
            for n in names
        ]

    class FakeNavPage(FakePage):
        async def goto(self, url, **kwargs):
            return None

    page = FakeNavPage(url='https://x/shop/bundles/create')

    class Ctx:
        pages = [page]

        async def new_page(self):
            return page

        async def close(self):
            return None

    class Browser:
        async def new_context(self, **kwargs):
            return Ctx()

        async def close(self):
            return None

    class Chromium:
        async def launch(self, **kwargs):
            return Browser()

    class Driver:
        chromium = Chromium()

        async def stop(self):
            return None

    async def start():
        return Driver()

    real = bundle_runner.async_playwright
    bundle_runner.async_playwright = lambda: type(
        'P', (), {'start': staticmethod(start)})()
    try:
        return await builder.run_many(game='Cabal M', bundles=bundles,
                                      storage_state={})
    finally:
        bundle_runner.async_playwright = real


# --------------------------- kept-open window ---------------------------

class FakeClosable:
    def __init__(self, name, log):
        self._name = name
        self._log = log

    async def close(self):
        self._log.append(self._name)

    # Playwright's driver handle stops rather than closes.
    async def stop(self):
        self._log.append(self._name)


def test_the_next_run_closes_the_window_the_last_preview_left_open():
    """Browser concurrency is meant to stay at one, so the slot must be reclaimed."""
    closed: list[str] = []
    bundle_runner._KEPT['u1'] = tuple(
        FakeClosable(n, closed) for n in ('pw', 'browser', 'context'))
    asyncio.run(bundle_runner.close_kept('u1'))
    assert closed == ['context', 'browser', 'pw']
    assert 'u1' not in bundle_runner._KEPT


def test_closing_a_window_that_the_operator_already_shut_is_harmless():
    asyncio.run(bundle_runner.close_kept('nobody'))  # must not raise


# --------------------------- fake page bits ---------------------------

class FakeLocator:
    def __init__(self, page, name, index=0):
        self._page = page
        self._name = name
        self._index = index

    @property
    def first(self):
        return self

    def nth(self, index):
        return FakeLocator(self._page, self._name, index)

    def locator(self, selector):
        name, index = self._page.child_locators.get(
            (self._name, self._index, selector), (selector, 0))
        return FakeLocator(self._page, name, index)

    async def count(self):
        return self._page.counts.get(self._name, self._page.default_count)

    async def wait_for(self, **kwargs):
        if await self.count() == 0:
            raise LookupError(self._name)
        return None

    async def get_attribute(self, name):
        return self._page.attrs.get(self._name, {}).get(name)

    async def fill(self, value):
        self._page.filled.append((self._name, value))
        self._page.values[self._name] = value

    async def input_value(self):
        return self._page.values.get(self._name, '')

    async def select_option(self, **kwargs):
        self._page.selected.append((self._name, self._index, kwargs))
        self._page.values[self._name] = kwargs.get('label', kwargs.get('value', ''))

    async def is_visible(self):
        return self._page.visible.get((self._name, self._index), True)

    async def click(self, **kwargs):
        self._page.clicked.append(self._name)
        if self._name == SWITCH:
            current = self._page.attrs.setdefault(self._name, {}).get(
                'aria-checked') == 'true'
            self._page.attrs[self._name]['aria-checked'] = (
                'false' if current else 'true')
        handler = self._page.click_handlers.get(
            (self._name, self._index), self._page.click_handlers.get(self._name))
        if handler:
            outcome = handler(self._page)
            if inspect.isawaitable(outcome):
                await outcome


class FakePage:
    """Just enough page surface for the header, rate and save paths."""

    def __init__(self, fields=(), url='https://x/shop/bundles/create',
                 response=None, counts=None, attrs=None, blank_tiers=(),
                 child_locators=None, click_handlers=None, visible=None,
                 default_count=1, values=None):
        self._fields = list(fields)
        self._blank_tiers = list(blank_tiers)
        self.url = url
        self.filled: list[tuple[str, str]] = []
        self.clicked: list[str] = []
        self.selected: list[tuple[str, dict]] = []
        self.counts = counts or {}
        self.default_count = default_count
        self.attrs = attrs or {}
        self.values = values or {}
        self.child_locators = child_locators or {}
        self.click_handlers = click_handlers or {}
        self.visible = visible or {}
        self._response = response

    async def eval_on_selector_all(self, selector, script):
        return self._fields

    async def evaluate(self, script, arg=None):
        return self._blank_tiers

    def locator(self, selector):
        return FakeLocator(self, selector)

    async def wait_for_timeout(self, ms):
        return None

    def expect_response(self, predicate, timeout=None):
        response = self._response
        page = self

        class Ctx:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            @property
            def value(self):
                async def _get():
                    if response is None:
                        raise TimeoutError('no response')
                    return response
                return _get()

        return Ctx()


def _builder():
    return bundle_runner.BundleBuilder(lambda message, level='INFO': None)


# ------------------------------ header --------------------------------

SWITCH = 'button[role="switch"]'


# Header switch/completeness/missing-control tests now exercise the real
# browser runner in test_web_bundle_id_first.py instead of fake CSS probes.


# --------------------------- quantity / tier ---------------------------









# ------------------------------ draw rate ------------------------------

def test_successful_item_rows_keep_their_own_qty_tier_and_rate():
    """After item 1 fails, item 2 becomes row 0 without losing its values."""
    builder = _builder()
    captured = {}
    outcomes = iter([False, True])

    async def add_item(page, item_id):
        return next(outcomes)

    async def capture_qty_tier(page, items):
        captured['qty_tier'] = items

    async def capture_rates(page, items):
        captured['rates'] = items

    builder._fill_header = lambda *args: _async(None)
    builder._add_item = add_item
    builder._fill_qty_tier = capture_qty_tier
    builder._fill_rates = capture_rates
    items = [
        {'id': '100', 'qty': '4', 'tier': 'Epic', 'rate': '10'},
        {'id': '200', 'qty': '51', 'tier': 'Rare', 'rate': '25'},
    ]

    added, rewards_added = asyncio.run(builder._fill_form(
        FakePage(), 'Mixed', 'RANDOM', True, items, []))

    assert (added, rewards_added) == (1, 0)
    assert captured == {'qty_tier': [items[1]], 'rates': [items[1]]}


def test_failed_required_field_fill_keeps_a_complete_add_batch_unsaved():
    """Successful adds do not prove Qty, Tier, and RANDOM rate were written."""
    builder = _builder()
    save_calls = []
    item = {'id': '100', 'qty': '51', 'tier': 'Rare', 'rate': '12.5'}

    builder._fill_header = lambda *args: _async(None)
    builder._add_item = lambda *args: _async(True)
    builder._fill_qty_tier = lambda *args: _async(False)
    builder._fill_rates = lambda *args: _async(False)

    outcome = asyncio.run(builder._fill_form(
        FakePage(), 'RANDOM', 'RANDOM', True, [item], []))

    assert tuple(outcome) == (1, 0)
    assert outcome.fields_complete is False

    async def save(page):
        save_calls.append(page)
        return True, 'must-not-save'

    builder._save = save
    results = asyncio.run(_run_many(builder, [], bundles=[{
        'group': 'required-fields', 'name': 'RANDOM', 'type': 'RANDOM',
        'items': [item], 'rewards': [],
    }]))

    assert save_calls == []
    assert results[0]['saved'] is False
    assert results[0]['fields_complete'] is False
    assert 'field' in results[0]['error'].lower()


def test_failed_header_stays_incomplete_after_successful_item_field_fill():
    """A later successful Qty/Tier fill must not reopen the header save gate."""
    builder = _builder()
    save_calls = []
    item = {'id': '100', 'qty': '2', 'tier': 'Rare', 'rate': ''}
    builder._fill_header = lambda *args: _async(False)
    builder._add_item = lambda *args: _async(True)
    builder._fill_qty_tier = lambda *args: _async(True)

    outcome = asyncio.run(builder._fill_form(
        FakePage(), 'Header failure', 'FIXED', True, [item], []))
    assert tuple(outcome) == (1, 0)
    assert outcome.fields_complete is False

    async def save(page):
        save_calls.append(page)
        return True, 'must-not-save'

    builder._save = save
    results = asyncio.run(_run_many(builder, [], bundles=[{
        'group': 'header-failure', 'name': 'Header failure', 'type': 'FIXED',
        'items': [item], 'rewards': [],
    }]))
    assert save_calls == []
    assert results[0]['saved'] is False
    assert results[0]['fields_complete'] is False






# Save safety is exercised through the real public browser runner and API
# in test_web_bundle_id_first.py and test_bundle_recheck_flow.py.
