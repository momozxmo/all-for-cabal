# -*- coding: utf-8 -*-
"""ยืนยัน web/search_runner: HeadlessFinder bind engine เดิมได้ + build_search_data + result_view
(ทดสอบได้โดยไม่ต้องต่อ aztek จริง — ใช้ fake page)"""
import os
import sys
import asyncio

from playwright.sync_api import sync_playwright

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from web import search_runner as sr  # noqa: E402
import item_finder  # noqa: E402

FAIL = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else '*** FAIL *** ') + name + (('  ' + extra) if extra else ''))
    if not cond:
        FAIL.append(name)
    assert cond, name + ((' — ' + extra) if extra else '')


class FakePage:
    async def evaluate(self, js, *a):
        return []

    async def wait_for_timeout(self, ms):
        pass


def test_detail_reader_uses_the_live_game_tradeable_checkbox():
    """The current Aztek item form exposes tradeability as #game-tradeable."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content('''
          <section>
            <h2>พารามิเตอร์สำหรับส่งเข้าเกมส์</h2>
            <input id="game-tradeable" type="checkbox" checked>
            <label for="game-tradeable">
              แลกเปลี่ยนได้ (ไม่เลือก = "ผูกมัดไอดี")
            </label>
          </section>
        ''')

        detail = page.evaluate(item_finder._READ_ITEM_DETAIL)

        assert detail['tradeable'] is True
        browser.close()


def test_binding_and_callbacks():
    logs, results, progs = [], [], []
    hf = sr.HeadlessFinder(
        lambda m, level='INFO': logs.append((m, level)),
        lambda it: results.append(it),
        lambda c, t, n: progs.append((c, t, n)))
    for m in ('_auto', '_search_all', '_check_item_detail', '_read_all_pages',
              '_read_table_page', '_go_next_page', '_go_back', '_wait_table_ready',
              '_wait_detail_ready', '_apply_filters', '_dump_pager', '_run_deep_check'):
        check('bound engine method %s' % m, callable(getattr(hf, m, None)))
    hf.log('hello', 'STEP'); hf.add_result_row({'x': 1}); hf.set_progress(1, 5, 'z')
    check('log -> callback', logs == [('hello', 'STEP')])
    check('add_result_row -> callback', results == [{'x': 1}])
    check('set_progress -> callback', progs == [(1, 5, 'z')])
    check('_update_count/_regroup_results no-op', hf._update_count() is None and hf._regroup_results() is None)


def test_regroup_callback_replaces_streamed_rows_in_document_order():
    results, resets = [], []
    occurrences = [
        {'kind': '1', 'opt': '', 'dur': '', 'name': 'A', 'sources': ['G1']},
        {'kind': '2', 'opt': '', 'dur': '', 'name': 'B', 'sources': ['G1']},
        {'kind': '1', 'opt': '', 'dur': '', 'name': 'A', 'sources': ['G2']},
    ]
    hf = sr.HeadlessFinder(
        lambda *a, **k: None, lambda row: results.append(row), lambda *a: None,
        occurrences=occurrences, on_reset=lambda: resets.append(True))
    hf._results = [
        {'aztek_id': '10', 'item_kind': '1', 'item_option': '',
         'duration_index': '', 'item_name': 'A web'},
        {'aztek_id': '20', 'item_kind': '2', 'item_option': '',
         'duration_index': '', 'item_name': 'B web'},
    ]
    hf._regroup_results()
    check('regroup resets streamed table once', resets == [True])
    check('regroup follows occurrence order',
          [r['aztek_id'] for r in hf._results] == ['10', '20', '10'])
    check('regroup re-emits final rows', results == hf._results)


def test_engine_method_runs_on_fake_page():
    hf = sr.HeadlessFinder(lambda *a, **k: None, lambda *a: None, lambda *a: None)
    fp = FakePage()
    rows = asyncio.run(hf._read_table_page(fp))
    check('_read_table_page returns evaluate() result', rows == [])
    hf._cancel = True
    r = asyncio.run(hf._wait_table_ready(fp))
    check('_wait_table_ready respects _cancel (returns falsy fast)', not r)


def test_build_search_data():
    game = item_finder.GAME_NAMES[0]
    crit = [{'kind': '1', 'opt': '', 'dur': '', 'name': 'x',
             'web': 'yes', 'img': 'any', 'qty_val': '', 'trade': 'any',
             'drill': 'any', 'crit_val': ''}]
    d = sr.build_search_data(game, crit, 'no')
    # The web path rewrites the desktop v1 host to the v2 host users log in to.
    check('data game/url set (v2 host)',
          d['game'] == game and d['url'] == sr.to_web_url(item_finder.GAMES[game]))
    check('url uses v2 host', 'aztek-tools-v2.combo-interactive.com' in d['url'])
    check('url keeps the game path',
          item_finder.GAMES[game].split('combo-interactive.com', 1)[1] in d['url'])
    check('web_mode=no overrides row web', d['multi'][0]['web'] == 'no', str(d['multi'][0].get('web')))
    check('deep auto True (row has web)', d['deep'] is True)
    check('headless True', d['headless'] is True)
    # The caller can ask for a watchable window; headless is the default.
    headed = sr.build_search_data(game, crit, 'no', headed=True)
    check('headed=True -> headless False', headed['headless'] is False)

    d2 = sr.build_search_data(game, crit, 'yes')
    check('web_mode=yes -> web yes + _show_web_vals', d2['multi'][0]['web'] == 'yes'
          and d2['multi'][0].get('_show_web_vals') is True)

    try:
        sr.build_search_data('NOPE_GAME', crit, 'any')
        check('unknown game raises', False)
    except ValueError:
        check('unknown game raises', True)

    blank = [{'kind': '1', 'opt': '', 'dur': '', 'name': 'x',
              'web': 'any', 'img': 'any', 'qty_val': '', 'trade': 'any',
              'drill': 'any', 'crit_val': ''}]
    shop = sr.build_search_data(game, blank, 'any', mode='shop')
    check('shop defaults web=no and reads description',
          shop['read_desc'] is True and shop['deep'] is True)
    itemcode = sr.build_search_data(game, crit, 'yes', mode='itemcode')
    check('itemcode locks web=no even if caller asks yes',
          itemcode['multi'][0]['web'] == 'no' and itemcode['read_desc'] is False)


def test_browser_launch_kwargs():
    from web import browser_launch as bl
    # Headed must fill the real window; headless keeps Playwright's wide
    # default viewport (no_viewport there would drop to 800x600).
    launch_headed, launch_hidden = bl.launch_kwargs(True), bl.launch_kwargs(False)
    check('headed launches visible + maximized',
          launch_headed['headless'] is False
          and '--start-maximized' in launch_headed['args'])
    check('headless launches hidden without window args',
          launch_hidden['headless'] is True and 'args' not in launch_hidden)

    ctx_headed = bl.context_kwargs(True, storage_state={'cookies': []})
    ctx_hidden = bl.context_kwargs(False, storage_state={'cookies': []})
    check('headed context uses the window size',
          ctx_headed.get('no_viewport') is True
          and ctx_headed['storage_state'] == {'cookies': []})
    check('headless context keeps the default viewport',
          'no_viewport' not in ctx_hidden
          and ctx_hidden['storage_state'] == {'cookies': []})


def test_result_view():
    item = {'aztek_id': '221070', 'item_name': 'Force Wing',
            'sources': ['Cash Shop'], 'group_keys': ['group-shop'],
            '_desc': 'แฟชั่น', 'web': 'yes', 'img': 'yes'}
    v = sr.result_view(item)
    check('result_view id/name', v['aztek_id'] == '221070' and v['item_name'] == 'Force Wing')
    check('result_view groups joins sources', v['groups'] == 'Cash Shop')
    check('result_view preserves internal group keys',
          v['group_keys'] == ['group-shop'])
    check('result_view desc', v['desc'] == 'แฟชั่น')
    check('result_view params is string', isinstance(v['params'], str) and v['params'])
    check('result_view no file_name -> not flagged', v['name_mismatch'] is False)

    # file name is a contiguous prefix of the web name -> matches, no flag
    ok = sr.result_view({'aztek_id': '1', 'item_name': 'Force Wing (30 Days)',
                         'file_name': 'Force Wing'})
    check('result_view name contained -> not flagged', ok['name_mismatch'] is False)

    # file name NOT contiguous in web name -> flagged for manual review
    # (matches the desktop rule: "Heroic Holy Water (15 min.) x10" vs the web's
    # "...(15 min.) (7 Days) x10" — the "x10" is split off, so it is flagged).
    bad = sr.result_view({'aztek_id': '2', 'item_name': 'Heroic Holy Water (15 min.) (7 Days) x10',
                          'file_name': 'Heroic Holy Water (15 min.) x10'})
    check('result_view name mismatch -> flagged', bad['name_mismatch'] is True)


class _FakeRunPage:
    def __init__(self, url='https://aztek-tools.combo-interactive.com/items'):
        self.url = url

    async def goto(self, *a, **k):
        return None

    async def wait_for_timeout(self, ms):
        return None

    async def evaluate(self, js, *a):
        return False  # no password field -> not the login page


class _FakeContext:
    def __init__(self, page):
        self.page = page
        self.closed = False

    async def new_page(self):
        return self.page

    async def close(self):
        self.closed = True


class _FakeBrowser:
    def __init__(self, page):
        self.context = _FakeContext(page)
        self.new_context_calls = []
        self.closed = False

    async def new_context(self, **kw):
        self.new_context_calls.append(kw)
        return self.context

    async def close(self):
        self.closed = True


class _FakeChromium:
    def __init__(self, page):
        self.browser = _FakeBrowser(page)
        self.launch_calls = []
        self.persistent_calls = []

    async def launch(self, **kw):
        self.launch_calls.append(kw)
        return self.browser

    async def launch_persistent_context(self, **kw):
        self.persistent_calls.append(kw)
        return self.browser


class _FakePlaywright:
    def __init__(self, page=None):
        self.chromium = _FakeChromium(page or _FakeRunPage())

    @property
    def browser(self):
        return self.chromium.browser

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


def _run_data():
    game = item_finder.GAME_NAMES[0]
    return {'game': game, 'url': item_finder.GAMES[game], 'multi': [],
            'deep': False, 'headless': True, 'read_desc': False}


def test_web_runner_uses_non_persistent_context(monkeypatch):
    storage_state = {'cookies': [{'name': 'a', 'value': 'b'}], 'origins': []}
    fake = _FakePlaywright()
    monkeypatch.setattr(sr, 'async_playwright', lambda: fake)
    finder = sr.HeadlessFinder(lambda *a, **k: None, lambda *a: None, lambda *a: None)

    asyncio.run(finder.run(_run_data(), storage_state))

    check('web runner launches non-persistent headless chromium',
          fake.chromium.launch_calls == [{'headless': True}])
    check('web runner seeds a context with storage_state only',
          fake.browser.new_context_calls == [{'storage_state': storage_state}])
    check('web runner never launches a persistent profile',
          fake.chromium.persistent_calls == [])
    check('web runner closes context and browser',
          fake.browser.closed and fake.browser.context.closed)


def test_web_runner_raises_on_login_page(monkeypatch):
    page = _FakeRunPage(url='https://aztek-tools.combo-interactive.com/login')
    fake = _FakePlaywright(page)
    monkeypatch.setattr(sr, 'async_playwright', lambda: fake)
    finder = sr.HeadlessFinder(lambda *a, **k: None, lambda *a: None, lambda *a: None)

    raised = False
    try:
        asyncio.run(finder.run(_run_data(), {'cookies': [], 'origins': []}))
    except sr.AztekSessionExpired:
        raised = True

    check('login page raises AztekSessionExpired', raised)
    check('runner still closes browser after expiry',
          fake.browser.closed and fake.browser.context.closed)


class _RunPageWithVisiblePassword(_FakeRunPage):
    async def evaluate(self, js, *a):
        return True  # the visibility filter in the JS found a visible field


def test_is_login_page_ignores_app_paths_containing_auth(monkeypatch):
    # The old heuristic matched the loose substring '/auth', so an app route like
    # '/authorization/...' was mistaken for a login screen. The path check now
    # only honours real login routes, and there is no visible password field.
    page = _FakeRunPage(
        url='https://aztek-tools.combo-interactive.com/authorization/settings')
    fake = _FakePlaywright(page)
    monkeypatch.setattr(sr, 'async_playwright', lambda: fake)
    finder = sr.HeadlessFinder(lambda *a, **k: None, lambda *a: None, lambda *a: None)

    raised = False
    try:
        asyncio.run(finder.run(_run_data(), {'cookies': [], 'origins': []}))
    except sr.AztekSessionExpired:
        raised = True
    check('app path with "auth" substring is not treated as login', not raised)


def test_is_login_page_flags_visible_password_on_app_page(monkeypatch):
    # A visible password field (e.g. an in-app re-login overlay) still means the
    # session is not authenticated, even on an app URL with no login route.
    page = _RunPageWithVisiblePassword(
        url='https://aztek-tools.combo-interactive.com/combo/cabalm/shop/items')
    fake = _FakePlaywright(page)
    monkeypatch.setattr(sr, 'async_playwright', lambda: fake)
    finder = sr.HeadlessFinder(lambda *a, **k: None, lambda *a: None, lambda *a: None)

    raised = False
    try:
        asyncio.run(finder.run(_run_data(), {'cookies': [], 'origins': []}))
    except sr.AztekSessionExpired:
        raised = True
    check('visible password field on app page is treated as login', raised)


if __name__ == '__main__':
    test_binding_and_callbacks()
    test_regroup_callback_replaces_streamed_rows_in_document_order()
    test_engine_method_runs_on_fake_page()
    test_build_search_data()
    test_browser_launch_kwargs()
    test_result_view()
    print('\n' + ('ALL PASS' if not FAIL else 'FAIL: ' + ', '.join(FAIL)))
    sys.exit(1 if FAIL else 0)
