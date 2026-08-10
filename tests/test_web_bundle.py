# -*- coding: utf-8 -*-
"""Bundle creation: reward validation, draw-rate discovery, and save safety.

These cover the parts that can write to the live Aztek site, so they run
against fake pages rather than a real browser.
"""
from __future__ import annotations

import asyncio
import inspect

import pytest
from playwright.async_api import async_playwright

from web import bundle_runner
from web.app import BundleRunRequest, _clean_items, _clean_rewards


# ------------------------------ rewards ------------------------------

def test_clean_rewards_keeps_only_well_formed_entries():
    cleaned = _clean_rewards([
        {'type': 'credit', 'value': 'Alz', 'qty': '100'},   # lowercase kind
        {'type': 'PLAYER_EXP', 'value': 'Rank 5', 'qty': 1},
        {'type': 'BITCOIN', 'value': 'nope', 'qty': '1'},   # unknown kind
        {'type': 'DEBIT', 'value': '', 'qty': '1'},         # no value
        {'type': 'MILEAGE', 'value': 'M', 'qty': '0'},      # not a real amount
        {'type': 'MILEAGE', 'value': 'M', 'qty': 'ten'},    # not a number
    ])
    assert cleaned == [
        {'type': 'CREDIT', 'value': 'Alz', 'qty': '100'},
        {'type': 'PLAYER_EXP', 'value': 'Rank 5', 'qty': '1'},
    ]


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


def test_items_are_taken_as_typed_in_the_order_given():
    """The page builds bundles from typed or pasted ids, not from a search, so
    an id only has to look like one. Order is the operator's."""
    items = _clean_items([
        {'id': ' 200479 ', 'qty': '3', 'tier': 'Epic'},
        {'id': 'ID 11', 'rate': '12.5'},          # digits dug out of free text
        {'id': '200479', 'qty': '9'},             # already in — Aztek refuses it
        {'id': 'no digits here'},
        {'id': '22', 'qty': 'ten'},               # unreadable count -> 1
    ])
    assert items == [
        {'id': '200479', 'qty': '3', 'tier': 'Epic', 'rate': ''},
        {'id': '11', 'qty': '1', 'tier': 'Common', 'rate': '12.5'},
        {'id': '22', 'qty': '1', 'tier': 'Common', 'rate': ''},
    ]


def test_a_pasted_column_cannot_grow_without_bound():
    items = _clean_items([{'id': str(n)} for n in range(1, 500)])
    assert len(items) == 200


def test_one_failing_bundle_does_not_stop_the_rest():
    """A batch that dies halfway must still report what it did create."""
    builder = _builder()

    async def fake_fill(page, name, *args):
        if name == 'bad':
            raise RuntimeError('เพิ่มไอเทมไม่ได้')
        return 1, 0

    saves = iter([(True, '111'), (True, '333')])
    builder._fill_form = fake_fill
    builder._save = lambda page: _async(next(saves))
    results = asyncio.run(_run_many(builder, ['good', 'bad', 'later']))
    assert [(r['name'], r['saved'], r['bundle_id']) for r in results] == [
        ('good', True, '111'), ('bad', False, None), ('later', True, '333')]
    assert 'เพิ่มไอเทมไม่ได้' in results[1]['error']


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


class FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status = status
        self.ok = 200 <= status < 300
        self.url = 'https://x/api/bundles'
        self._payload = payload

    async def json(self):
        if self._payload is None:
            raise ValueError('not json')
        return self._payload


def _builder():
    return bundle_runner.BundleBuilder(lambda message, level='INFO': None)


# ------------------------------ header --------------------------------

SWITCH = 'button[role="switch"]'


def test_immediate_send_toggles_the_switch_not_the_hidden_checkbox():
    """The <input type=checkbox> is aria-hidden and covered on v2.

    Clicking it bought a 30s timeout per run and left the toggle on when the
    operator had asked for it off — which delivers a bundle they meant to hold.
    """
    page = FakePage(attrs={SWITCH: {'aria-checked': 'true'}})
    asyncio.run(_builder()._fill_header(page, 'B', 'FIXED', False))
    assert SWITCH in page.clicked
    assert not any('checkbox' in name for name in page.clicked)


def test_immediate_send_is_left_alone_when_it_already_matches():
    page = FakePage(attrs={SWITCH: {'aria-checked': 'true'}})
    asyncio.run(_builder()._fill_header(page, 'B', 'FIXED', True))
    assert page.clicked == []


def test_header_completeness_accepts_delivery_already_matching_or_corrected():
    already = FakePage(attrs={SWITCH: {'aria-checked': 'true'}})
    corrected = FakePage(attrs={SWITCH: {'aria-checked': 'false'}})

    assert asyncio.run(
        _builder()._fill_header(already, 'B', 'FIXED', True)) is True
    assert asyncio.run(
        _builder()._fill_header(corrected, 'B', 'FIXED', True)) is True
    assert already.clicked == []
    assert corrected.clicked == [SWITCH]


@pytest.mark.parametrize('missing_selector', [
    '#bundle-name, input[name="name"]', 'select', SWITCH,
])
def test_each_missing_required_header_control_keeps_bundle_unsaved(
        missing_selector):
    builder = _builder()
    save_calls = []

    async def save(page):
        save_calls.append(page)
        return True, 'must-not-save'

    builder._save = save

    class HeaderPage(FakePage):
        def __init__(self, *args, **kwargs):
            kwargs['counts'] = {missing_selector: 0}
            super().__init__(*args, **kwargs)

    async def run():
        original = globals()['FakePage']
        globals()['FakePage'] = HeaderPage
        try:
            return await _run_many(builder, [], bundles=[{
                'group': 'header', 'name': 'Required header',
                'type': 'FIXED', 'deliver': True,
                'items': [], 'rewards': [],
            }])
        finally:
            globals()['FakePage'] = original

    results = asyncio.run(run())
    assert save_calls == []
    assert results[0]['fields_complete'] is False
    assert 'field' in results[0]['error'].lower()


# --------------------------- quantity / tier ---------------------------

QTY = 'input[name^="items."][name$=".quantity"]'


def test_quantity_stops_at_the_last_item_so_rewards_keep_their_amount():
    """A reward becomes items.1 on the same form; overwriting it with 1 would
    silently turn "Ark Gem x500" into "Ark Gem x1"."""
    page = FakePage(counts={QTY: 2})
    asyncio.run(_builder()._fill_qty_tier(
        page, [{'id': '1', 'qty': '7', 'tier': 'Rare'}]))
    assert page.filled == [(QTY, '7')]


def test_qty_tier_expands_a_lazy_player_experience_card_before_filling():
    """Its Qty and Tier mount only after the collapsed card is expanded."""
    expand_all = 'button:text-is("Expand All")'
    collapsed = bundle_runner._COLLAPSED_CARD_CHEVRONS
    page = FakePage(
        counts={expand_all: 1, collapsed: 1, QTY: 0, 'select': 1},
        child_locators={
            (QTY, 0, 'xpath=ancestor::*[.//select][1]'): ('player-card', 0),
            ('player-card', 0, 'select'): ('select', 0),
        },
        click_handlers={
            expand_all: lambda fake_page: fake_page.counts.update(
                {collapsed: 0, QTY: 1}),
        },
        default_count=0,
    )
    player_experience = {
        'id': 'PLAYER_EXPERIENCE', 'name': 'Player Experience - SEA',
        'qty': '51', 'tier': 'Common',
    }

    asyncio.run(_builder()._fill_qty_tier(page, [player_experience]))

    assert page.clicked == [expand_all]
    assert page.filled == [(QTY, '51')]
    assert page.selected == [('select', 0, {'label': 'Common'})]


def test_qty_tier_selects_the_tier_inside_its_item_card_not_bundle_type():
    """Select 0 is Bundle Type; the first card owns select 1."""
    page = FakePage(
        counts={QTY: 1, 'select': 2, 'button:text-is("Expand All")': 0},
        child_locators={
            (QTY, 0, 'xpath=ancestor::*[.//select][1]'): ('item-card', 0),
            ('item-card', 0, 'select'): ('select', 1),
        },
        default_count=0,
    )

    asyncio.run(_builder()._fill_qty_tier(
        page, [{'id': '100', 'qty': '51', 'tier': 'Rare'}]))

    assert page.filled == [(QTY, '51')]
    assert page.selected == [('select', 1, {'label': 'Rare'})]


def test_reward_rows_are_given_a_tier_rather_than_asked_for_one():
    """v2 files rewards into the item list, so each one demands a Tier.

    A currency has no rank, and a blank required field blocks the create
    button — so the blanks are filled in for the operator.
    """
    page = FakePage(blank_tiers=[1, 2])
    done = asyncio.run(_builder()._fill_blank_tiers(page))
    assert done == 2
    assert [(name, idx, kw.get('label')) for name, idx, kw in page.selected] == [
        ('select', 1, 'Common'), ('select', 2, 'Common')]


def test_a_tier_the_operator_already_chose_is_left_alone():
    page = FakePage(blank_tiers=[])
    assert asyncio.run(_builder()._fill_blank_tiers(page)) == 0
    assert page.selected == []


def test_blank_tier_search_skips_the_bundle_type_select():
    """It shares the page with the tier pickers and has no Common option.

    Selecting Common there fails outright, so the filter must be on the
    options rather than on position.
    """
    assert "o.textContent.trim() === tier" in bundle_runner._BLANK_TIERS
    assert bundle_runner.TIER_DEFAULT == 'Common'


# ------------------------------ draw rate ------------------------------

def test_rate_targets_the_required_field_not_the_display_rate():
    """A card carries a draw rate and a display rate; only the first is required."""
    page = FakePage(fields=[
        {'name': 'items.0.quantity', 'required': True},
        {'name': 'items.0.randomRate', 'required': True},
        {'name': 'items.0.displayRate', 'required': False},
    ])
    asyncio.run(_builder()._fill_rates(page, [{'id': '1', 'rate': '12.5'}]))
    assert page.filled == [('input[name="items.0.randomRate"]', ''),
                           ('input[name="items.0.randomRate"]', '12.5')]


def test_rate_is_skipped_for_items_without_one():
    page = FakePage(fields=[{'name': 'items.0.rate', 'required': True},
                            {'name': 'items.1.rate', 'required': True}])
    asyncio.run(_builder()._fill_rates(
        page, [{'id': '1', 'rate': ''}, {'id': '2', 'rate': '5'}]))
    assert [name for name, _ in page.filled] == [
        'input[name="items.1.rate"]', 'input[name="items.1.rate"]']


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
    builder._fill_blank_tiers = lambda *args: _async(0)
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
    builder._fill_blank_tiers = lambda *args: _async(0)

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
    builder._fill_blank_tiers = lambda *args: _async(0)

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


def test_collapsed_rfd_player_experience_card_expands_once_across_two_passes():
    """The fallback must open the real card shape without re-collapsing it."""
    async def exercise():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content('''
              <div data-rfd-draggable-id="player-exp-card">
                <span>Player Experience - SEA</span>
                <span class="badge">PLAYER_EXPERIENCE</span>
                <span>x51</span>
                <button id="chevron" aria-expanded="false">v</button>
              </div>
              <script>
                window.chevronClicks = 0;
                const card = document.querySelector('[data-rfd-draggable-id]');
                document.getElementById('chevron').addEventListener('click', () => {
                  window.chevronClicks += 1;
                  const closed = card.querySelector('#chevron').getAttribute('aria-expanded') === 'false';
                  card.querySelector('#chevron').setAttribute('aria-expanded', closed ? 'true' : 'false');
                  if (closed) card.insertAdjacentHTML('beforeend',
                    '<input name="items.0.quantity" value="1"><select><option>Common</option><option>Rare</option></select>');
                  else card.querySelectorAll('input,select').forEach(node => node.remove());
                });
              </script>
            ''')
            card = page.locator('[data-rfd-draggable-id]')
            assert 'Player Experience - SEA' in await card.inner_text()
            assert 'PLAYER_EXPERIENCE' in await card.inner_text()
            assert 'x51' in await card.inner_text()
            builder = _builder()
            await builder._fill_qty_tier(
                page, [{'id': 'PLAYER_EXP', 'qty': '51', 'tier': 'Rare'}])
            await builder._fill_blank_tiers(page)
            result = {
                'clicks': await page.evaluate('window.chevronClicks'),
                'expanded': await page.locator('#chevron').get_attribute('aria-expanded'),
                'qty': await page.locator('input[name="items.0.quantity"]').input_value(),
                'tier': await page.locator('select').input_value(),
            }
            await browser.close()
            return result

    assert asyncio.run(exercise()) == {
        'clicks': 1, 'expanded': 'true', 'qty': '51', 'tier': 'Rare',
    }


def test_rfd_fallback_expands_every_live_collapsed_card_without_index_shift():
    """Clicking card 1 removes it from the live matcher; card 2 must still open."""
    async def exercise():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content('''
              <div data-rfd-draggable-id="one"><button aria-expanded="false">v</button></div>
              <div data-rfd-draggable-id="two"><button aria-expanded="false">v</button></div>
              <script>
                window.clicks = 0;
                document.querySelectorAll('[data-rfd-draggable-id] button').forEach((button, index) => {
                  button.addEventListener('click', () => {
                    window.clicks += 1;
                    button.setAttribute('aria-expanded', 'true');
                    button.insertAdjacentHTML('afterend',
                      `<input name="items.${index}.quantity" value="1"><select><option>Common</option></select>`);
                  });
                });
              </script>
            ''')
            complete = await _builder()._expand_item_cards(page)
            result = {
                'complete': complete,
                'clicks': await page.evaluate('window.clicks'),
                'states': await page.locator('[data-rfd-draggable-id] button').evaluate_all(
                    'buttons => buttons.map(button => button.getAttribute("aria-expanded"))'),
                'mounted': await page.locator('input[name^="items."]').count(),
            }
            await browser.close()
            return result

    assert asyncio.run(exercise()) == {
        'complete': True, 'clicks': 2, 'states': ['true', 'true'], 'mounted': 2,
    }


def test_expand_all_is_not_clicked_again_when_cards_are_already_open():
    """A visible toggle must not close cards during the blank-Tier pass."""
    async def exercise():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content('''
              <button id="expand-all">Expand All</button>
              <div data-rfd-draggable-id="one"><button aria-expanded="false">v</button></div>
              <div data-rfd-draggable-id="two"><button aria-expanded="false">v</button></div>
              <script>
                window.expandClicks = 0;
                const cards = [...document.querySelectorAll('[data-rfd-draggable-id]')];
                const setCards = open => cards.forEach((card, index) => {
                  const button = card.querySelector('button');
                  button.setAttribute('aria-expanded', String(open));
                  card.querySelectorAll('input,select').forEach(node => node.remove());
                  if (open) card.insertAdjacentHTML('beforeend',
                    `<input name="items.${index}.quantity" value="1"><select><option>Common</option><option>Rare</option></select>`);
                });
                document.getElementById('expand-all').addEventListener('click', () => {
                  window.expandClicks += 1;
                  setCards(cards.some(card => card.querySelector('button').getAttribute('aria-expanded') === 'false'));
                });
              </script>
            ''')
            builder = _builder()
            qty_complete = await builder._fill_qty_tier(
                page, [{'id': '1', 'qty': '51', 'tier': 'Rare'}])
            await builder._fill_blank_tiers(page)
            result = {
                'qty_complete': qty_complete,
                'blank_complete': builder._blank_tiers_complete,
                'clicks': await page.evaluate('window.expandClicks'),
                'states': await page.locator('[data-rfd-draggable-id] button').evaluate_all(
                    'buttons => buttons.map(button => button.getAttribute("aria-expanded"))'),
                'mounted': await page.locator('input[name^="items."]').count(),
                'first_qty': await page.locator('input[name="items.0.quantity"]').count(),
            }
            await browser.close()
            return result

    assert asyncio.run(exercise()) == {
        'qty_complete': True, 'blank_complete': True, 'clicks': 1,
        'states': ['true', 'true'], 'mounted': 2, 'first_qty': 1,
    }


def test_blank_tiers_stay_incomplete_when_a_collapsed_card_will_not_open():
    """An unopened reward card has no mounted Tier and must fail closed."""
    collapsed = bundle_runner._COLLAPSED_CARD_CHEVRONS
    page = FakePage(
        counts={collapsed: 1, 'button:text-is("Expand All")': 0},
        default_count=0,
    )

    builder = _builder()
    assert asyncio.run(builder._fill_blank_tiers(page)) == 0
    assert builder._blank_tiers_complete is False


# -------------------------------- save --------------------------------

def test_save_reports_the_new_bundle_id():
    page = FakePage(response=FakeResponse(200, {'data': {'bundleId': 90210}}))
    saved, bundle_id = asyncio.run(_builder()._save(page))
    assert saved is True
    assert bundle_id == '90210'


def test_save_reads_the_id_from_the_redirect_when_the_body_has_none():
    page = FakePage(response=FakeResponse(200, None),
                    url='https://x/shop/bundles/4242')
    saved, bundle_id = asyncio.run(_builder()._save(page))
    assert saved is True
    assert bundle_id == '4242'


def test_save_refuses_an_unverified_confirm_click():
    """A click with no write response and no detail URL creates no proof."""
    page = FakePage()
    saved, bundle_id = asyncio.run(_builder()._save(page))
    assert (saved, bundle_id) == (False, None)


def test_save_refuses_to_claim_success_on_an_error_response():
    """An error body can carry unrelated numbers — never report one as an id."""
    page = FakePage(response=FakeResponse(500, {'id': 13}),
                    url='https://x/shop/bundles/999')
    saved, bundle_id = asyncio.run(_builder()._save(page))
    assert saved is False
    assert bundle_id is None


def test_save_uses_the_current_v2_create_bundle_button():
    old = "button:has-text('ยืนยันการสร้างบันเดิล')"
    current = "button:has-text('สร้าง Bundle')"
    page = FakePage(
        response=FakeResponse(200, {'data': {'bundleId': 90210}}),
        counts={old: 0, current: 1},
    )
    saved, bundle_id = asyncio.run(_builder()._save(page))
    assert saved is True
    assert bundle_id == '90210'
    assert page.clicked == [current]


def test_save_stops_when_the_confirm_button_is_missing():
    page = FakePage(counts={
        "button:has-text('สร้าง Bundle')": 0,
        "button:has-text('ยืนยันการสร้างบันเดิล')": 0,
    })
    saved, bundle_id = asyncio.run(_builder()._save(page))
    assert saved is False
    assert bundle_id is None
    assert page.clicked == []
