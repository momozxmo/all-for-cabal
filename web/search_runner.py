# -*- coding: utf-8 -*-
"""Callback-driven host for the existing Item Finder Playwright engine."""
from urllib.parse import urlsplit

from playwright.async_api import async_playwright

import item_finder
from web import browser_launch, item_service
from web.aztek_locator import AztekLocatorError, require_control

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
    _locator_errors = (AztekLocatorError,)

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


async def _apply_id_first_filters(self, page, criteria):
    if not criteria.get('kind'):
        return
    # Live PC/M list: search has no stable ID; only this main/form exception
    # is allowed. Option/Duration remain Python filters to retain pagination.
    main = await require_control(page, 'Item Finder main', selector='main', tags=('main',))
    form = await require_control(
        main, 'ฟอร์มค้นหา Item',
        selector='form:has(input[placeholder="ค้นหา Item..."])', tags=('form',))
    box = await require_control(
        form, 'ช่องค้นหา Item', selector='input[placeholder="ค้นหา Item..."]',
        tags=('input',), input_types=('text',))
    submit = await require_control(
        form, 'ปุ่มค้นหา Item', selector='button[type="submit"]', tags=('button',))
    await box.fill(criteria['kind'])
    self.log('  Top search: %s' % criteria['kind'], 'INFO')
    await submit.click()
    await page.wait_for_timeout(1500)
    await self._wait_table_ready(page)


HeadlessFinder._apply_filters = _apply_id_first_filters


async def _read_id_first_detail(self, page, item):
    main = await require_control(page, 'Item detail main', selector='main', tags=('main',))
    form = await require_control(
        main, 'ฟอร์มรายละเอียด Item', selector='form:has([id="item-name"])', tags=('form',))
    await require_control(form, 'ชื่อ Item', element_id='item-name', tags=('input',), input_types=('text',))
    for key, element_id, label in (
            ('item_kind', 'item-game-item-id', 'ItemKind'),
            ('item_option', 'item-option', 'ItemOption'),
            ('duration_index', 'duration-index', 'DurationIndex')):
        field = await require_control(form, label, element_id=element_id, tags=('input',),
                                      input_types=('text', 'number'))
        if (await field.input_value()).strip() != str(item.get(key, '')).strip():
            raise AztekLocatorError('Aztek: %s ในรายละเอียดไม่ตรงกับแถว Item ที่ค้นหา' % label)
    description = await require_control(
        form, 'คำอธิบาย Item', element_id='item-detail', tags=('textarea',))
    enabled = await require_control(
        form, 'แสดงผลบนเว็บ', element_id='display-option-enable', tags=('button',), roles=('switch',))
    trade = await require_control(
        form, 'แลกเปลี่ยนได้', element_id='game-tradeable', tags=('button',), roles=('checkbox',))
    web_state = await enabled.get_attribute('aria-checked')
    trade_state = await trade.get_attribute('aria-checked')
    if web_state not in ('true', 'false'):
        raise AztekLocatorError('Aztek: แสดงผลบนเว็บ อ่านสถานะไม่ได้')
    if trade_state not in ('true', 'false'):
        raise AztekLocatorError('Aztek: แลกเปลี่ยนได้ อ่านสถานะไม่ได้')
    web_enabled = web_state == 'true'
    detail = {'webEnabled': web_enabled, 'tradeable': trade_state == 'true',
              'qty': '', 'critVal': '', 'drillable': None,
              'desc': (await description.input_value()).strip(), 'hasImage': False}
    if web_enabled:
        for key, element_id, label in (
                ('qty', 'displayOptions-quantity', 'จำนวน'),
                ('critVal', 'displayOptions-critical', 'คริติคอล')):
            target = await require_control(form, label, element_id=element_id, tags=('input',),
                                           input_types=('text', 'number'))
            detail[key] = (await target.input_value()).strip()
        drill = await require_control(
            form, 'เจาะรูได้', element_id='displayOptions-is_slotable', tags=('button',), roles=('checkbox',))
        drill_state = await drill.get_attribute('aria-checked')
        if drill_state not in ('true', 'false'):
            raise AztekLocatorError('Aztek: เจาะรูได้ อ่านสถานะไม่ได้')
        detail['drillable'] = drill_state == 'true'
    # The saved image has no stable ID. Scope the observed Preview exception
    # to this form so unrelated branding images cannot satisfy image criteria.
    previews = form.locator('img[alt="Preview"]')
    if await previews.count() > 1:
        raise AztekLocatorError('Aztek: รูป Preview พบหลายเป้าหมายในฟอร์ม Item')
    if await previews.count() == 1:
        preview = await require_control(form, 'รูป Preview', selector='img[alt="Preview"]', tags=('img',))
        try:
            await preview.evaluate('''img => new Promise((resolve, reject) => {
                if (img.complete) return resolve();
                const timer = setTimeout(() => reject(new Error('Preview timeout')), 5000);
                img.addEventListener('load', () => {clearTimeout(timer); resolve();}, {once:true});
                img.addEventListener('error', () => {clearTimeout(timer); resolve();}, {once:true});
            })''')
        except Exception as error:
            raise AztekLocatorError('Aztek: รูป Preview ยังโหลดไม่เสร็จ') from error
        detail['hasImage'] = await preview.evaluate(
            'img => img.naturalWidth > 0 && img.naturalHeight > 0 '
            '&& !!img.src && !img.src.startsWith("data:") && img.getBoundingClientRect().width > 30')
    return detail


HeadlessFinder._read_item_detail = _read_id_first_detail


async def _read_scoped_table_state(self, page):
    main = await require_control(page, 'Item Finder main', selector='main', tags=('main',))
    tables = main.locator('table')
    empty = main.locator('p:text-is("ไม่พบ Item ที่ตรงกับเงื่อนไข")')
    if await empty.count() > 1 or (await empty.count() and await tables.count()):
        raise AztekLocatorError('Aztek: สถานะตาราง Item พบหลายเป้าหมาย')
    if not await tables.count():
        # Observed completed-empty state removes the table entirely. Absence
        # alone is not evidence of zero results while the SPA is loading.
        return {'rows': [], 'ready': await empty.count() == 1 and await empty.is_visible()}
    table = await require_control(main, 'ตาราง Item', selector='table', tags=('table',))
    data = await table.evaluate('''table => {
        const headers = [...table.querySelectorAll('thead th')].map(
            th => (th.innerText || '').replace(/\\s+/g, ' ').trim());
        const fields = {aztek_id:'Aztek Item Id', item_name:'ชื่อ', item_kind:'ItemKind',
                        item_option:'ItemOption', duration_index:'DurationIndex'};
        const indexes = {};
        for (const [field, label] of Object.entries(fields)) {
            if (headers.filter(text => text === label).length !== 1)
                return {error:label};
            indexes[field] = headers.indexOf(label);
        }
        const rows = [];
        let loading = false;
        for (const tr of table.querySelectorAll('tbody tr')) {
            const cells = [...tr.querySelectorAll('td')];
            // Empty/loading state uses one colspan cell, not an Item record.
            if (cells.length === 1 && cells[0].hasAttribute('colspan')) { loading = true; continue; }
            if (!cells.length) continue;
            if (cells.length < headers.length) return {error:'จำนวนคอลัมน์'};
            const row = {};
            for (const [field, index] of Object.entries(indexes))
                row[field] = (cells[index].innerText || '').trim();
            if (!/^\\d+$/.test(row.aztek_id)) return {error:'Aztek Item Id'};
            rows.push(row);
        }
        return {rows, ready:rows.length > 0 && !loading};
    }''')
    if data.get('error'):
        raise AztekLocatorError('Aztek: ตาราง Item อ่านคอลัมน์ %s ไม่ได้แน่นอน' % data['error'])
    return data


HeadlessFinder._read_table_state = _read_scoped_table_state


async def _read_scoped_table(self, page):
    data = await self._read_table_state(page)
    if not data['ready']:
        raise AztekLocatorError('Aztek: ตาราง Item ยังโหลดไม่เสร็จ หยุดก่อนอ่านผล')
    return data['rows']


HeadlessFinder._read_table_page = _read_scoped_table


async def _wait_scoped_table(self, page, tries=10, interval=250):
    last, stable = None, 0
    for _ in range(tries):
        if self._cancel:
            return
        data = await self._read_table_state(page)
        signature = tuple(tuple(row.values()) for row in data['rows']) if data['ready'] else None
        stable = stable + 1 if signature is not None and signature == last else 0
        if stable >= 2:
            return
        last = signature
        await page.wait_for_timeout(interval)
    raise AztekLocatorError('Aztek: ตาราง Item ยังไม่นิ่ง หยุดก่อนอ่านผล')


async def _go_scoped_next_page(self, page, prev_first_id=None):
    state = await self._read_table_state(page)
    if state['ready'] and not state['rows']:
        return False
    main = await require_control(page, 'Item Finder main', selector='main', tags=('main',))
    next_button = await require_control(
        main, 'หน้าถัดไป Item', selector='button:text-is("Next ›")', tags=('button',))
    if not await next_button.is_enabled():
        return False
    await next_button.click()
    for _ in range(20):
        if self._cancel:
            return False
        state = await self._read_table_state(page)
        rows = state['rows'] if state['ready'] else []
        first_id = rows[0]['aztek_id'] if rows else None
        if rows and first_id != prev_first_id:
            await self._wait_table_ready(page)
            return True
        await page.wait_for_timeout(250)
    raise AztekLocatorError('Aztek: หน้าถัดไป Item ไม่เปลี่ยนผล หยุดก่อนอ่านซ้ำ')


async def _dump_scoped_pager(self, page):
    if self._pager_dumped:
        return
    self._pager_dumped = True
    self.log('  [pager] อ่าน Next ภายใน Item main; กรอง Option/Duration หลังอ่านครบทุกหน้า', 'INFO')


HeadlessFinder._wait_table_ready = _wait_scoped_table
HeadlessFinder._go_next_page = _go_scoped_next_page
HeadlessFinder._dump_pager = _dump_scoped_pager


async def _wait_id_first_detail(self, page, tries=18, interval=300):
    main = await require_control(page, 'Item detail main', selector='main', tags=('main',))
    form = await require_control(
        main, 'ฟอร์มรายละเอียด Item', selector='form:has([id="item-name"])', tags=('form',))
    kind = await require_control(form, 'ItemKind', element_id='item-game-item-id',
                                 tags=('input',), input_types=('text', 'number'))
    last, stable = None, 0
    for _ in range(tries):
        if self._cancel:
            return False
        value = (await kind.input_value()).strip()
        stable = stable + 1 if value.isascii() and value.isdigit() and value == last else 0
        if stable >= 2:
            return True
        last = value
        await page.wait_for_timeout(interval)
    raise AztekLocatorError('Aztek: ItemKind ยังไม่พร้อมในรายละเอียด Item')


HeadlessFinder._wait_detail_ready = _wait_id_first_detail


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
        'document_reference': item.get('document_reference'),
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
