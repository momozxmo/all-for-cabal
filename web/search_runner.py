# -*- coding: utf-8 -*-
"""Callback-driven host for the existing Item Finder Playwright engine."""
from urllib.parse import urlsplit

from playwright.async_api import async_playwright

import item_finder
from web import browser_launch, item_service

# The desktop tool targets the v1 host (its own logged-in Chrome profile). The
# web app's users log in to the v2 host, so web searches must run against v2.
# We only rewrite the host for the web path; item_finder.GAMES (v1) is untouched.
_DESKTOP_HOST = 'aztek-tools.combo-interactive.com'
_WEB_HOST = 'aztek-tools-v2.combo-interactive.com'


def to_web_url(url):
    """Rewrite a desktop (v1) Aztek URL to the web (v2) host."""
    return url.replace('//' + _DESKTOP_HOST, '//' + _WEB_HOST, 1)


class AztekSessionExpired(Exception):
    """The stored Aztek session no longer authenticates against the site."""


async def is_login_page(page):
    """Heuristic: is this the Aztek login screen rather than the app shell?

    A login route in the URL path is a reliable signal (e.g. the shared SSO
    redirect). A password field only counts when it is actually *visible* — the
    full app shell may keep a hidden re-login modal in the DOM, and that must
    not be mistaken for a login page (the desktop engine never checks this and
    works on the same page). An empty result table is never a signal: it is a
    legitimate search outcome, not an expired session.
    """
    url = (getattr(page, 'url', '') or '').lower()
    path = (urlsplit(url).path or '').lower()
    if any(part in path for part in ('/login', '/signin', '/sign-in')):
        return True
    try:
        visible_password = await page.evaluate(
            "() => Array.from(document.querySelectorAll("
            "'input[type=\"password\"], input[name=\"password\"]')).some("
            "function(el){ var r = el.getBoundingClientRect();"
            "var st = getComputedStyle(el);"
            "return r.width > 0 && r.height > 0 && el.offsetParent !== null &&"
            "st.display !== 'none' && st.visibility !== 'hidden'; })")
    except Exception:
        visible_password = False
    return bool(visible_password)


class _StubNotebook:
    def select(self, *args, **kwargs):
        return None


class _ImmediateRoot:
    """Execute Tk-style after callbacks immediately on the asyncio thread."""
    def after(self, delay, callback=None, *args):
        if callback:
            return callback(*args)
        return None


class HeadlessFinder:
    def __init__(self, on_log, on_result, on_progress, *, occurrences=None,
                 on_reset=None):
        self._on_log = on_log
        self._on_result = on_result
        self._on_progress = on_progress
        self._on_reset = on_reset or (lambda: None)
        self._cancel = False
        self._results = []
        self._occurrences = [dict(row) for row in (occurrences or [])]
        self._not_found = []
        self._pager_dumped = False
        self.nb = _StubNotebook()
        self.root = _ImmediateRoot()

    def log(self, message, level='INFO'):
        self._on_log(str(message), level)

    def add_result_row(self, item):
        self._on_result(item)

    def set_progress(self, current, total, name):
        self._on_progress(current, total, name)

    def _update_count(self):
        return None

    def _regroup_results(self):
        if not self._occurrences or not self._results:
            return None
        rows = item_service.regroup_results(self._results, self._occurrences)
        if rows == self._results:
            return None
        self._results = rows
        self._on_reset()
        for row in rows:
            self._on_result(row)
        self.log('เรียงผลลัพธ์ตามชุด (เอกสาร) — %d แถว' % len(rows), 'SUCCESS')
        return None

    async def run(self, data, storage_state):
        """Run one search in a fresh, non-persistent context for this user.

        Unlike the desktop ``_auto`` (which reuses a shared persistent Chrome
        profile), the web path launches a throwaway browser seeded only with the
        caller's decrypted Aztek storage state, so users never share a session.

        ``data['headless']`` decides whether the run is watchable; the caller is
        responsible for only allowing a headed run where the server has a
        display (see ``SearchCoordinator``).
        """
        headed = not data.get('headless', True)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                **browser_launch.launch_kwargs(headed))
            context = await browser.new_context(
                **browser_launch.context_kwargs(
                    headed, storage_state=storage_state))
            page = await context.new_page()
            try:
                await page.goto(data['url'], wait_until='domcontentloaded',
                                timeout=30000)
                await page.wait_for_timeout(2000)  # let the SPA settle
                if await is_login_page(page):
                    # Include the URL so the log reveals whether we landed on a
                    # real SSO login (session not authenticating) or the app page.
                    raise AztekSessionExpired(
                        'Aztek session หมดอายุ/ยังไม่ได้ล็อกอิน (หน้า: %s)'
                        % page.url)
                await self._search_all(page, data)
            finally:
                await context.close()
                await browser.close()


_ENGINE_METHODS = (
    '_auto', '_search_all', '_wait_table_ready', '_wait_detail_ready',
    '_apply_filters', '_read_all_pages', '_dump_pager', '_read_table_page',
    '_go_next_page', '_run_deep_check', '_check_item_detail', '_go_back',
)
for _method_name in _ENGINE_METHODS:
    setattr(HeadlessFinder, _method_name, getattr(item_finder.App, _method_name))
del _method_name


def build_search_data(game, criteria, web_mode=None, *, mode='event',
                      headed=False):
    """Build the same multi-search data as desktop, including mode policy."""
    if game not in item_finder.GAMES:
        raise ValueError('ไม่รู้จักเกม: %s' % game)
    policy = item_service.mode_policy(mode)
    if policy['web_locked']:
        web_mode = policy['web_mode']
    elif web_mode is None:
        web_mode = policy['web_mode']
    if web_mode not in ('any', 'yes', 'no'):
        raise ValueError('ค่าแสดงผลบนเว็บไม่ถูกต้อง: %s' % web_mode)

    multi = [dict(row) for row in criteria]
    if web_mode in ('yes', 'no'):
        def needs_web(row):
            return (row.get('trade', 'any') != 'any'
                    or row.get('drill', 'any') != 'any'
                    or str(row.get('qty_val', '') or '').strip()
                    or str(row.get('crit_val', '') or '').strip())

        for row in multi:
            row['web'] = 'yes' if web_mode == 'no' and needs_web(row) else web_mode
            if web_mode == 'yes':
                row['_show_web_vals'] = True

    def has_deep(row):
        return (row.get('web', 'any') != 'any'
                or row.get('img', 'any') != 'any'
                or row.get('qty_val', '') != ''
                or row.get('trade', 'any') != 'any'
                or row.get('drill', 'any') != 'any'
                or row.get('crit_val', '') != '')

    return {
        'game': game,
        'url': to_web_url(item_finder.GAMES[game]),
        'multi': multi,
        # Shop must visit every detail page to read textarea[name="detail"],
        # even when every filter in a generic template is Any.
        'deep': policy['read_desc'] or any(has_deep(row) for row in multi),
        'web': 'any', 'img': 'any', 'qty_val': '', 'trade': 'any',
        'drill': 'any', 'crit_val': '', 'batch': 10,
        'headless': not headed,
        'read_desc': policy['read_desc'],
    }


def result_view(item):
    params = item_finder.deep_summary(item)
    web_values = item.get('_web_vals')
    if web_values:
        params = ((params + ' | ' + web_values)
                  if params and params != '-' else web_values)
    file_name = item.get('file_name', '') or ''
    web_name = item.get('item_name', '') or ''
    # Same rule as the desktop table: the name from the file is only used to eye-
    # check the web result (search matches by kind/opt/dur, not name). Flag rows
    # whose file name is not contained in the web name so the UI can highlight
    # them for manual review — it does NOT mean the row is wrong.
    name_mismatch = bool(
        file_name
        and item_finder._norm_name(file_name) not in item_finder._norm_name(web_name)
    )
    sources = [str(s) for s in (item.get('sources') or [])]
    group_keys = [str(key) for key in (
        item.get('group_keys') or item.get('sources') or [])]
    return {
        'aztek_id': item.get('aztek_id', ''),
        'item_name': web_name,
        'file_name': file_name,
        'item_kind': item.get('item_kind', '') or '',
        'item_option': item.get('item_option', '') or '',
        'duration_index': item.get('duration_index', '') or '',
        'game': item.get('game', '') or '',
        'notes': item.get('notes', '') or '',
        'criteria_no': item.get('_ci', '') or '',
        'params': params,
        'groups': ' , '.join(sources),
        # Keep the raw group list too: build_bundles groups by 'sources', and the
        # persisted results must carry it so bundling works after a reload.
        'sources': sources,
        # Stable worksheet/reward identity travels beside the readable label.
        'group_keys': group_keys,
        # Quantity from the imported 'Amt' column (carried by regroup_results);
        # build_bundles uses it to pre-fill the bundle qty.
        'amt': str(item.get('amt', '') or '').strip(),
        # Draw rate from a random box's plan table, already a percentage.
        'rate': str(item.get('rate', '') or '').strip(),
        # Live search rows carry the private collection key, while rows loaded
        # back from a workspace are already in this public shape.
        'desc': item.get('_desc') or item.get('desc', '') or '',
        'name_mismatch': name_mismatch,
    }
