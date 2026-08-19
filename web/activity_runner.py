# -*- coding: utf-8 -*-
"""Shared machinery for the two v2 "activity" forms: Item Code and Event.

Both are the same job around a different form — open the create page with the
operator's own Aztek session, fill it, and either stop there for them to read
or press the button and report the new id. That job lives here; what goes in
which field lives in :mod:`web.itemcode_runner` and :mod:`web.event_runner`.

A preview never saves. ``run`` fills and stops; only ``run_many`` writes, and
only because the caller asked it to.
"""
import re

from playwright.async_api import async_playwright

import aztek_core as core
import new_tool
from web import browser_launch
from web.create_flow import click_create_and_wait_for_write
from web.search_runner import to_web_url


def create_url(game, path):
    """The v2 create page for a game — ``itemcodes`` and ``events`` sit at the
    game root, not under ``/shop/`` where the bundle pages live."""
    return to_web_url(core.build_url(game, path + '/create'))


class ActivityBuilder:
    """Drive one v2 create form. Subclasses supply the form knowledge."""

    #: URL segment of the list page ('itemcodes' / 'events').
    PATH = ''
    #: What the confirm button says.
    SAVE_LABEL = ''
    #: Word used in the operator's log ("Item Code" / "Event").
    KIND = ''
    #: Substring that marks the write request among the page's traffic.
    WRITE_MARK = ''
    #: A visible field proving this subclass's client-rendered form is ready.
    READY_SELECTOR = 'input[name="name_th"]'

    def __init__(self, on_log):
        self._log = on_log
        self._cancel = False

    def log(self, message, level='INFO'):
        self._log(message, level)

    def create_url(self, game):
        """Return this builder's create page.

        Product lives under ``/shop/`` while Item Code and Event live at the
        game root, so subclasses may override this without changing the safe
        preview/create lifecycle.
        """
        return create_url(game, self.PATH)

    def cancel(self):
        """Stop before the next item — a run in flight finishes its page."""
        self._cancel = True

    async def fill_form(self, page, spec):
        """Fill the open create page. Returns a list of unfilled required fields."""
        raise NotImplementedError

    async def add_reward_set(self, page, index):
        """Open reward set ``index`` by adding it, and wait for its fields.

        Reward sets are tabs on v2: only the selected one is rendered, and
        adding a set selects it. Waiting for that set's own name box is what
        tells "the tab switched" apart from "the click did nothing" — filling
        blind would write set 2's values over set 1.
        """
        try:
            await page.locator(
                'button:has-text("เพิ่มของรางวัล")').first.click(timeout=8000)
            await page.locator(
                'input[name="rewards.%d.name_th"]' % index).wait_for(
                    state='visible', timeout=8000)
            await page.wait_for_timeout(600)
            return True
        except Exception as exc:
            self.log('เปิดชุดรางวัลที่ %d ไม่ได้: %s' % (index + 1, exc), 'WARNING')
            return False

    # ------------------------------------------------------------------ save

    async def _save(self, page):
        """Press confirm and report the new id.

        The id is only read from a 2xx body or the resulting URL: an error body
        can carry numbers of its own, and reporting one as an id would send the
        operator looking for something that was never created.
        """
        button = page.locator("button:has-text('%s')" % self.SAVE_LABEL).first
        if await button.count() == 0:
            self.log('หาปุ่ม "%s" ไม่เจอ — ไม่ได้สร้าง' % self.SAVE_LABEL, 'ERROR')
            return False, None
        response, confirmed = await click_create_and_wait_for_write(
            page, button,
            lambda r: (r.request.method in ('POST', 'PUT', 'PATCH')
                       and self.WRITE_MARK in r.url.lower()),
        )
        if confirmed:
            self.log('กด "ยืนยัน" ในหน้าต่างยืนยันการสร้างแล้ว', 'INFO')
        await page.wait_for_timeout(1500)

        if response is not None and not response.ok:
            self.log('เว็บตอบกลับ HTTP %d — %s อาจไม่ถูกสร้าง'
                     % (response.status, self.KIND), 'ERROR')
            return False, None
        made_id = None
        if response is not None:
            self.log('เว็บตอบกลับ HTTP %d' % response.status, 'INFO')
            try:
                made_id = new_tool.extract_bundle_id(await response.json())
            except Exception:
                made_id = None
        if not made_id:
            match = re.search(r'/%s/(\d+)' % self.PATH, page.url)
            if match:
                made_id = match.group(1)
        if response is None and not made_id:
            self.log('ยืนยันการสร้าง%sไม่ได้ — ไม่พบคำตอบที่สำเร็จหรือเลขใน URL'
                     % self.KIND, 'ERROR')
            return False, None
        self.log('กดยืนยันการสร้าง%sแล้ว' % self.KIND, 'SUCCESS')
        if made_id:
            self.log('สร้าง%sสำเร็จ — เลข: %s' % (self.KIND, made_id), 'SUCCESS')
        else:
            self.log('สร้างแล้วแต่อ่านเลขไม่ได้ — ตรวจบนเว็บอีกที', 'WARNING')
        return True, made_id

    # ------------------------------------------------------------------- run

    async def _open(self, page, url):
        await page.goto(url, wait_until='domcontentloaded', timeout=40000)
        if any(part in page.url.lower() for part in ('/login', '/signin')):
            raise RuntimeError('session หมดอายุ (โดนเด้งไปหน้า login)')
        try:
            await page.locator(self.READY_SELECTOR).wait_for(
                state='visible', timeout=20000)
        except Exception:
            if not any(part in page.url.lower() for part in ('/login', '/signin')):
                raise
            raise RuntimeError('session หมดอายุ (โดนเด้งไปหน้า login)')
        if any(part in page.url.lower() for part in ('/login', '/signin')):
            raise RuntimeError('session หมดอายุ (โดนเด้งไปหน้า login)')

    async def run(self, game, spec, storage_state, *, headed=False,
                  keep_open_key=None):
        """Fill one form and stop. Nothing is created here, ever.

        A headed preview leaves the window standing so the operator can read
        the real form rather than a screenshot of it.
        """
        url = self.create_url(game)
        self.log('เปิดหน้าสร้าง%s: %s' % (self.KIND, url), 'STEP')
        if keep_open_key:
            await close_kept(keep_open_key)
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(**browser_launch.launch_kwargs(headed))
        context = await browser.new_context(
            **browser_launch.context_kwargs(headed, storage_state=storage_state))
        page = await context.new_page()
        shot = None
        missing = []
        keep = False
        try:
            await self._open(page, url)
            missing = await self.fill_form(page, spec)
            keep = bool(keep_open_key) and headed
            if not keep:
                try:
                    shot = await page.screenshot(full_page=True)
                except Exception:
                    shot = None
            if missing:
                self.log('กรอกฟอร์มแล้ว แต่ยังไม่ครบ: %s' % ', '.join(missing),
                         'WARNING')
            else:
                self.log('กรอกฟอร์มเสร็จ (ยังไม่กดสร้าง)', 'SUCCESS')
        finally:
            if keep:
                _KEPT[keep_open_key] = (pw, browser, context)
                self.log('เปิดหน้าต่างค้างไว้ให้ตรวจ — ปิดเองได้ '
                         'หรือจะปิดให้เองตอนเปิดครั้งถัดไป', 'INFO')
            else:
                await _shutdown(pw, browser, context)
        return {'url': url, 'screenshot': shot, 'missing': missing,
                'kept_open': keep}

    async def run_many(self, game, specs, storage_state, *, headed=False):
        """Create every one of them in a single browser session.

        A form that came back with required fields unfilled is *not* saved: an
        Item Code or Event on the live site missing half its data is worse than
        one that was never made, and the operator can see exactly which field
        stopped it.
        """
        url = self.create_url(game)
        self.log('==== สร้าง%s %d รายการ ====' % (self.KIND, len(specs)), 'STEP')
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(**browser_launch.launch_kwargs(headed))
        context = await browser.new_context(
            **browser_launch.context_kwargs(headed, storage_state=storage_state))
        page = await context.new_page()
        results = []
        try:
            for number, spec in enumerate(specs, 1):
                if self._cancel:
                    self.log('หยุดกลางคัน (ทำไป %d/%d)'
                             % (number - 1, len(specs)), 'WARNING')
                    break
                name = spec.get('name_th') or spec.get('slug') or '#%d' % number
                self.log('----- [%d/%d] %s -----' % (number, len(specs), name),
                         'STEP')
                entry = {'name': name, 'slug': spec.get('slug', ''),
                         'group': spec.get('group', ''), 'saved': False,
                         'made_id': None, 'missing': [], 'error': None}
                try:
                    # A fresh page each time: the last one still holds the last
                    # form's answers.
                    await self._open(page, url)
                    entry['missing'] = await self.fill_form(page, spec)
                    if entry['missing']:
                        raise RuntimeError('กรอกไม่ครบ: %s'
                                           % ', '.join(entry['missing']))
                    if self._cancel:
                        raise RuntimeError('ถูกยกเลิกก่อนกดสร้าง')
                    entry['saved'], entry['made_id'] = await self._save(page)
                except Exception as exc:
                    entry['error'] = str(exc)[:200]
                    self.log('%s "%s" ไม่สำเร็จ: %s' % (self.KIND, name, exc),
                             'ERROR')
                results.append(entry)
                await page.wait_for_timeout(1000)
        finally:
            await _shutdown(pw, browser, context)
        ok = sum(1 for r in results if r['saved'])
        self.log('==== เสร็จ: สร้างสำเร็จ %d/%d ====' % (ok, len(specs)),
                 'SUCCESS' if ok == len(specs) else 'WARNING')
        return results


# Windows a headed preview left standing, one per operator per tool.
_KEPT: dict[str, tuple] = {}


async def _shutdown(pw, browser, context):
    """Close a browser and its driver, tolerating a window the user already shut."""
    for closeable in (context, browser):
        try:
            await closeable.close()
        except Exception:
            pass
    try:
        await pw.stop()
    except Exception:
        pass


async def close_kept(key):
    """Close the window a previous headed preview left open, if any."""
    kept = _KEPT.pop(key, None)
    if kept:
        await _shutdown(*kept)
