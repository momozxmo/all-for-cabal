# -*- coding: utf-8 -*-
"""Bundle filler for the Aztek v2 site.

Two phases share one filler:

* **preview** (``do_save=False``) opens ``/shop/bundles/create``, fills the
  header, items, rewards, quantities/tiers and random rates, then STOPS — the
  bundle is never created. It also reads the reward dropdown options off the
  live page so the UI can offer them without a second browser trip.
* **create** (``do_save=True``) does the same and then clicks the confirm
  button, waits for the write request, and reports the new bundle id.

The v2 bundle UI is a full page with stable ids, so this is a small
purpose-built filler rather than the desktop modal engine. Field labels and
the id-extraction rule are imported from ``new_tool`` so both tools stay in
step when the site's wording changes.
"""
import re

from playwright.async_api import async_playwright

import new_tool
from web import browser_launch
from web.create_flow import click_create_and_wait_for_write
from web.search_runner import to_web_url


REWARD_KINDS = tuple(new_tool.REWARD_KINDS)

# v2 puts rewards behind tabs in the "เพิ่มของเข้า Bundle" panel, each holding a
# radix popover picker — not the v1 accordion + <select> that
# ``new_tool.REWARD_LABELS`` describes. The tab wording differs too
# ("Player Exp." here vs "Player Experience" on v1), so v2 keeps its own map.
REWARD_TABS = {
    'CREDIT': 'Credit',
    'DEBIT': 'Debit',
    'MILEAGE': 'Mileage',
    'PLAYER_EXP': 'Player Exp.',
}
# Nearest ancestor of the Qty box that also holds the picker: the reward tab's
# own panel, so the Qty box and เพิ่ม button of the item list can't be hit.
_PANEL_XPATH = ('xpath=//input[@placeholder="Qty"]'
                '/ancestor::div[.//button[@role="combobox"]][1]')
# The popover renders in a portal at body level, outside that panel.
_POPOVER = '[data-radix-popper-content-wrapper]'

# Every row of the item list carries a required Tier — reward rows included,
# because v2 files rewards into that same list. A currency has no tier worth
# choosing, so the operator is never asked and blank rows take the first rank.
TIER_DEFAULT = 'Common'

# The page also holds the bundle-type <select>, which is not a tier picker.
# Telling them apart by their options survives a reorder; counting from the top
# would not.
_BLANK_TIERS = """
tier => [...document.querySelectorAll('select')]
  .map((s, i) => [i, [...s.options].some(o => o.textContent.trim() === tier), s.value])
  .filter(([, isTier, value]) => isTier && !value)
  .map(([i]) => i)
"""

_COLLAPSED_CARD_CHEVRONS = (
    '[data-rfd-draggable-id] button[aria-expanded="false"], '
    '[data-rbd-draggable-id] button[aria-expanded="false"], '
    '[draggable="true"] button[aria-expanded="false"], '
    'button[aria-expanded="false"][aria-label="ขยาย"], '
    'button[aria-expanded="false"][aria-label*="Expand"], '
    'button[aria-expanded="false"][title*="Expand"]')


class FillOutcome(tuple):
    """Two-count fill result with an internal required-field completion flag.

    It remains a two-item tuple for callers that already unpack
    ``(items_added, rewards_added)``. Batch runners additionally use
    :attr:`fields_complete` to fail closed.
    """

    def __new__(cls, added, rewards_added, fields_complete):
        result = super().__new__(cls, (added, rewards_added))
        result.fields_complete = fields_complete
        return result


def bundle_create_url(game):
    """v2 'create bundle' page URL for a game (desktop targets the v1 host)."""
    return to_web_url(new_tool.game_url(game, 'bundles')) + '/create'


class BundleBuilder:
    """Fill one bundle form on Aztek v2, and create it only when asked."""

    def __init__(self, on_log):
        self._log = on_log
        self._cancel = False
        self._blank_tiers_complete = True

    def log(self, message, level='INFO'):
        self._log(message, level)

    async def _fill_header(self, page, name, btype, deliver):
        name_complete = False
        type_complete = False
        delivery_complete = False
        # Name — stable id on v2.
        try:
            box = page.locator('#bundle-name, input[name="name"]').first
            await box.wait_for(state='visible', timeout=8000)
            await box.fill(name)
            name_complete = (await box.input_value()) == name
            if name_complete:
                self.log('ใส่ชื่อ Bundle: %s' % name, 'INFO')
            else:
                self.log('กรอกชื่อ Bundle แล้วแต่ค่าในฟอร์มไม่ตรง', 'WARNING')
        except Exception as exc:
            self.log('กรอกชื่อ Bundle ไม่สำเร็จ: %s' % exc, 'WARNING')
        # Type — the only <select> in the header.
        try:
            sel = page.locator('select').first
            if await sel.count() > 0:
                for how in ('label', 'value'):
                    try:
                        if how == 'label':
                            await sel.select_option(label=btype)
                        else:
                            await sel.select_option(value=btype)
                        type_complete = True
                        self.log('เลือกประเภท Bundle: %s' % btype, 'INFO')
                        break
                    except Exception:
                        continue
            if not type_complete:
                self.log('ไม่เจอตัวเลือกประเภท Bundle ที่กำหนด', 'WARNING')
        except Exception as exc:
            self.log('เลือกประเภท Bundle ไม่สำเร็จ: %s' % exc, 'WARNING')
        # Immediate-send toggle. v2 draws it as a radix switch; the
        # <input type="checkbox"> beside it is aria-hidden and covered, so
        # clicking that one only ever bought a 30s timeout — and left the toggle
        # on when the operator had asked for it off.
        try:
            switch = page.locator('button[role="switch"]').first
            if await switch.count() > 0:
                on = (await switch.get_attribute('aria-checked')) == 'true'
                if on != deliver:
                    await switch.click(timeout=6000)
                delivery_complete = (
                    (await switch.get_attribute('aria-checked')) == 'true'
                ) == deliver
                if delivery_complete:
                    self.log('ตั้งส่งทันที: %s' % ('เปิด' if deliver else 'ปิด'), 'INFO')
                else:
                    self.log('ตั้งส่งทันทีแล้วแต่สถานะในฟอร์มไม่ตรง', 'WARNING')
            else:
                self.log('ไม่เจอสวิตช์ "ส่งทันที"', 'WARNING')
        except Exception as exc:
            self.log('ตั้งส่งทันทีไม่สำเร็จ: %s' % exc, 'WARNING')
        return name_complete and type_complete and delivery_complete

    async def _add_item(self, page, item_id):
        """Search the item id in the 'เพิ่มของเข้า Bundle' panel and click เพิ่ม."""
        try:
            box = page.locator('input[placeholder*="ค้นหาชื่อ Item"], '
                               'input[placeholder*="ค้นหา Item"]').first
            await box.wait_for(state='visible', timeout=8000)
            await box.fill(str(item_id))
            await page.wait_for_timeout(1500)
            # The matching result row exposes an "เพิ่ม" button; pick the row that
            # shows this id.
            row = page.locator(
                'xpath=//*[contains(normalize-space(.),"ID: %s")]'
                '[.//button[contains(normalize-space(.),"เพิ่ม")]]' % item_id).first
            if await row.count() == 0:
                # Fallback: any visible เพิ่ม button after the search.
                add = page.locator('button:has-text("เพิ่ม")').first
            else:
                add = row.locator('button:has-text("เพิ่ม")').first
            if await add.count() > 0 and await add.is_visible():
                await add.click()
                self.log('เพิ่มไอเทม %s' % item_id, 'INFO')
                await page.wait_for_timeout(600)
                return True
            self.log('หาไอเทม %s ไม่เจอในผลค้นหา' % item_id, 'WARNING')
            return False
        except Exception as exc:
            self.log('เพิ่มไอเทม %s ไม่สำเร็จ: %s' % (item_id, exc), 'WARNING')
            return False

    # ---------------------------- rewards ----------------------------

    async def _open_reward_tab(self, page, kind):
        """Switch the add panel to a reward tab and return that panel.

        Returns ``None`` when the tab or its picker never appears, so callers
        report a miss instead of typing into whatever else is on screen.
        """
        tab = REWARD_TABS.get(kind, kind)
        try:
            await page.locator("button:text-is('%s')" % tab).first.click(timeout=6000)
        except Exception as exc:
            self.log('reward %s: กดแท็บ "%s" ไม่ได้: %s' % (kind, tab, exc), 'WARNING')
            return None
        await page.wait_for_timeout(900)
        panel = page.locator(_PANEL_XPATH).first
        try:
            await panel.wait_for(state='visible', timeout=6000)
        except Exception:
            self.log('reward %s: ไม่เจอแผงของแท็บ "%s"' % (kind, tab), 'WARNING')
            return None
        return panel

    async def _open_picker(self, page, panel):
        """Open the reward popover and return its option locator."""
        await panel.locator('button[role="combobox"]').first.click(timeout=6000)
        await page.wait_for_timeout(1200)
        return page.locator('%s [role="option"]' % _POPOVER)

    async def read_reward_options(self, page):
        """Read each reward picker's choices so the UI can offer them.

        Visits all four tabs, so it belongs only to the explicit
        :func:`fetch_reward_options` trip — a preview that adds one reward must
        not tour the whole panel to fill a cache nobody asked for.
        """
        options = {}
        for kind in REWARD_KINDS:
            names = []
            try:
                panel = await self._open_reward_tab(page, kind)
                if panel is not None:
                    opts = await self._open_picker(page, panel)
                    names = [text.strip()
                             for text in await opts.all_inner_texts()
                             if text.strip()]
                    # Duplicates are real on this site (two "Pull Free" entries);
                    # keep first-seen order but offer each name once.
                    names = list(dict.fromkeys(names))
                    await page.keyboard.press('Escape')
                    await page.wait_for_timeout(400)
            except Exception as exc:
                self.log('อ่านตัวเลือก %s ไม่สำเร็จ: %s'
                         % (REWARD_TABS.get(kind, kind), exc), 'WARNING')
            self.log('  %s: %d รายการ' % (kind, len(names)),
                     'INFO' if names else 'WARNING')
            options[kind] = names
        # Leave the panel back on the item list — that is what the operator
        # expects to see on a preview.
        try:
            await page.locator("button:text-is('Item')").first.click(timeout=3000)
        except Exception:
            pass
        found = sum(len(v) for v in options.values())
        self.log('อ่านตัวเลือก reward ได้ %d รายการ' % found,
                 'SUCCESS' if found else 'WARNING')
        return options

    async def _add_reward(self, page, kind, value, qty):
        panel = await self._open_reward_tab(page, kind)
        if panel is None:
            return False
        try:
            opts = await self._open_picker(page, panel)
            # The picker has its own search box; narrowing first keeps this
            # working when a game has a long currency list.
            try:
                await page.locator('%s input' % _POPOVER).first.fill(value)
                await page.wait_for_timeout(900)
            except Exception:
                pass
            hit = opts.filter(has_text=re.compile(r'^\s*%s\s*$' % re.escape(value)))
            if await hit.count() == 0:
                self.log('reward %s: ไม่มีตัวเลือกชื่อ "%s"' % (kind, value), 'WARNING')
                await page.keyboard.press('Escape')
                return False
            await hit.first.click()
            await page.wait_for_timeout(700)
        except Exception as exc:
            self.log('reward %s เลือกไม่สำเร็จ: %s' % (kind, exc), 'WARNING')
            return False
        try:
            await panel.locator('input[placeholder="Qty"]').first.fill(str(qty))
        except Exception as exc:
            self.log('reward %s ใส่จำนวนไม่สำเร็จ: %s' % (kind, exc), 'WARNING')
            return False
        try:
            # v2 labels this button plain "เพิ่ม" — the v1 wording in
            # new_tool.SEL['add_to_bundle'] does not appear on this page.
            await panel.locator("button:text-is('เพิ่ม')").first.click()
            self.log('เพิ่ม reward %s = %s x%s' % (kind, value, qty), 'SUCCESS')
            await page.wait_for_timeout(700)
            return True
        except Exception as exc:
            self.log('reward %s กดเพิ่มไม่ได้: %s' % (kind, exc), 'WARNING')
            return False

    # ------------------------ per-item fields ------------------------

    async def _expand_item_cards(self, page):
        """Reveal lazy item cards before addressing their controls.

        The site can mount Qty/Tier only after a card opens.  Prefer its
        one-shot control; otherwise use the expanded-state chevrons on the
        draggable cards.  This remains safe for pages that already show every
        card because neither locator is required.
        """
        chevrons = page.locator(_COLLAPSED_CARD_CHEVRONS)
        try:
            collapsed = await chevrons.count()
        except Exception as exc:
            self.log('ตรวจการ์ดที่ยังปิดไม่สำเร็จ: %s' % exc, 'WARNING')
            return False
        if not collapsed:
            return True
        try:
            expand_all = page.locator('button:text-is("Expand All")').first
            if collapsed and await expand_all.count() and await expand_all.is_visible():
                await expand_all.click(timeout=5000)
                await page.wait_for_timeout(300)
                if not await chevrons.count():
                    return True
        except Exception:
            pass
        try:
            attempts = 0
            limit = max(collapsed * 2, 4)
            while await chevrons.count():
                if attempts >= limit:
                    self.log('เปิดการ์ดไม่ครบภายในจำนวนครั้งที่ปลอดภัย', 'WARNING')
                    return False
                before = await chevrons.count()
                chevron = chevrons.first
                if not await chevron.is_visible():
                    self.log('พบการ์ดที่ยังปิดแต่กดเปิดไม่ได้', 'WARNING')
                    return False
                await chevron.click(timeout=5000)
                await page.wait_for_timeout(300)
                after = await chevrons.count()
                if after >= before:
                    self.log('การ์ดไม่เปลี่ยนเป็นสถานะเปิด', 'WARNING')
                    return False
                attempts += 1
            return True
        except Exception as exc:
            self.log('เปิดการ์ดไอเท็มเพื่อกรอก Tier ไม่สำเร็จ: %s' % exc,
                     'WARNING')
            return False

    async def _fill_qty_tier(self, page, items):
        """Set quantity and tier on each item card. v2 exposes a stable
        ``items.<n>.quantity`` number input and a hidden <select> for the tier.
        """
        expansion_complete = await self._expand_item_cards(page)
        cards = page.locator('input[name^="items."][name$=".quantity"]')
        # Rewards join the same items.<n> numbering, so any row past the item
        # list is a reward — filling it would overwrite the amount the operator
        # asked for with a 1.
        card_count = await cards.count()
        count = min(card_count, len(items))
        complete = expansion_complete and card_count >= len(items)
        for idx in range(count):
            it = items[idx] if idx < len(items) else {}
            qty = str(it.get('qty') or it.get('quantity') or '1')
            tier = it.get('tier') or 'Common'
            qty_filled = False
            try:
                await cards.nth(idx).fill(qty)
                qty_filled = True
            except Exception as exc:
                self.log('ตั้งจำนวนไอเทม #%d ไม่สำเร็จ: %s' % (idx + 1, exc), 'WARNING')
            # Bundle Type is also a page-level <select>, so choose only inside
            # this quantity field's own card instead of counting page selects.
            tier_selected = False
            try:
                card = cards.nth(idx).locator(
                    'xpath=ancestor::*[.//select][1]').first
                selects = card.locator('select')
                if await selects.count():
                    for how in ('label', 'value'):
                        try:
                            if how == 'label':
                                await selects.first.select_option(label=tier)
                            else:
                                await selects.first.select_option(value=tier)
                            tier_selected = True
                            break
                        except Exception:
                            continue
            except Exception as exc:
                self.log('ตั้ง Tier ไอเทม #%d ไม่สำเร็จ: %s' % (idx + 1, exc), 'WARNING')
            complete = complete and qty_filled and tier_selected
        if count:
            self.log('ตั้งจำนวน/Tier ให้ %d ไอเทม' % count, 'INFO')

        return complete

    async def _fill_blank_tiers(self, page):
        """Give every Tier still showing its placeholder the default rank.

        A reward row is required to carry a tier it has no meaning for, and
        leaving it blank blocks the create button. Rather than ask the operator
        for a rank on a currency, fill whatever is still empty with Common.
        """
        self._blank_tiers_complete = await self._expand_item_cards(page)
        try:
            blanks = await page.evaluate(_BLANK_TIERS, TIER_DEFAULT)
        except Exception as exc:
            self.log('หาช่อง Tier ที่ยังว่างไม่สำเร็จ: %s' % exc, 'WARNING')
            self._blank_tiers_complete = False
            return 0
        done = 0
        for idx in blanks:
            try:
                await page.locator('select').nth(idx).select_option(
                    label=TIER_DEFAULT, timeout=5000)
                done += 1
            except Exception as exc:
                self._blank_tiers_complete = False
                self.log('ตั้ง Tier ช่องที่ %d ไม่สำเร็จ: %s' % (idx + 1, exc),
                         'WARNING')
        if done:
            self.log('ตั้ง Tier = %s ให้ %d แถวที่ยังว่าง (reward ไม่ต้องเลือกเอง)'
                     % (TIER_DEFAULT, done), 'INFO')
        return done

    async def _fill_rates(self, page, items):
        """Set the random rate on each item card (RANDOM bundles only).

        The rate field name is discovered from the DOM rather than hardcoded: a
        card can carry both a draw rate and a display rate, and only the draw
        rate is required. Reading the real names keeps this working if the site
        renames the field.
        """
        try:
            fields = await page.eval_on_selector_all(
                'input[name^="items."]',
                'els => els.map(e => ({name: e.name, required: e.required}))')
        except Exception as exc:
            self.log('หาช่องเรทสุ่มไม่สำเร็จ: %s' % exc, 'WARNING')
            return False
        done = 0
        for idx, it in enumerate(items):
            rate = str(it.get('rate') or '').strip()
            if not rate:
                continue
            prefix = 'items.%d.' % idx
            candidates = [f for f in fields
                          if f['name'].startswith(prefix)
                          and 'rate' in f['name'].rsplit('.', 1)[-1].lower()]
            # Prefer the required field (the draw rate) over the display rate;
            # DOM order breaks the tie.
            chosen = next((f for f in candidates if f['required']), None) \
                or (candidates[0] if candidates else None)
            if chosen is None:
                self.log('ไอเทม #%d: หาช่องเรทสุ่มไม่เจอ' % (idx + 1), 'WARNING')
                continue
            try:
                box = page.locator('input[name="%s"]' % chosen['name']).first
                await box.fill('')
                await box.fill(rate)
                done += 1
            except Exception as exc:
                self.log('ตั้งเรทสุ่มไอเทม #%d ไม่สำเร็จ: %s'
                         % (idx + 1, exc), 'WARNING')
        if done:
            self.log('ตั้งเรทสุ่มให้ %d ไอเทม' % done, 'INFO')

        return done == len(items)

    # ------------------------------ save ------------------------------

    async def _save(self, page):
        """Click confirm and report the created bundle id.

        The id is only read from a 2xx response body or the redirect URL — an
        error body can carry unrelated numbers.
        """
        labels = ('สร้าง Bundle', new_tool.SEL['save_btn'])
        button = None
        for label in labels:
            candidate = page.locator("button:has-text('%s')" % label).first
            if await candidate.count():
                button = candidate
                break
        if button is None:
            self.log('หาปุ่มสร้าง Bundle ไม่เจอ — ไม่ได้สร้าง', 'ERROR')
            return False, None
        response, confirmed = await click_create_and_wait_for_write(
            page, button,
            lambda r: (r.request.method in ('POST', 'PUT', 'PATCH')
                       and 'bundle' in r.url.lower()),
        )
        if confirmed:
            self.log('กด "ยืนยัน" ในหน้าต่างยืนยันการสร้าง Bundle แล้ว', 'INFO')
        self.log('กดสร้าง Bundle แล้ว กำลังตรวจผล', 'INFO')
        await page.wait_for_timeout(1500)

        if response is not None and not response.ok:
            self.log('เว็บตอบกลับ HTTP %d — บันเดิลอาจไม่ถูกสร้าง'
                     % response.status, 'ERROR')
            return False, None

        bundle_id = None
        if response is not None:
            self.log('เว็บตอบกลับ HTTP %d' % response.status, 'INFO')
            try:
                bundle_id = new_tool.extract_bundle_id(await response.json())
            except Exception:
                bundle_id = None
        if not bundle_id:
            match = re.search(r'/bundles?/(\d+)', page.url)
            if match:
                bundle_id = match.group(1)
        if response is None and not bundle_id:
            self.log('ไม่พบคำตอบการบันทึกหรือเลข Bundle ใน URL — ถือว่ายังไม่สร้าง',
                     'ERROR')
            return False, None
        if bundle_id:
            self.log('สร้างบันเดิลสำเร็จ — เลข Bundle: %s' % bundle_id, 'SUCCESS')
        else:
            self.log('เว็บตอบรับการสร้างแล้ว แต่อ่านเลข Bundle ไม่ได้ — ตรวจบนเว็บอีกที',
                     'WARNING')
        return True, bundle_id

    # ------------------------------ run ------------------------------

    async def _fill_form(self, page, name, btype, deliver, items, rewards):
        """Fill an already-open create page. Returns (items added, rewards added).

        Shared by the one-bundle preview and the create-them-all run so both put
        the same values in the same order.
        """
        added = 0
        successful_items = []
        rewards_added = 0
        header_complete = await self._fill_header(page, name, btype, deliver)
        # Older tests/integrations monkeypatch this method with a coroutine that
        # returns None; only an explicit False from the real completion-aware
        # header path closes the save gate.
        fields_complete = header_complete is not False
        for it in items:
            if self._cancel:
                break
            if await self._add_item(page, it.get('id') or it.get('aztek_id')):
                added += 1
                successful_items.append(it)
        if successful_items:
            await page.wait_for_timeout(500)
            fields_complete = ((await self._fill_qty_tier(
                page, successful_items)) is not False) and fields_complete
            if btype == 'RANDOM':
                fields_complete = ((await self._fill_rates(page, successful_items))
                                   is not False) and fields_complete
        # Rewards land last: they share the items.<n> numbering, so adding
        # them earlier would shift the quantity and rate fields above.
        for reward in rewards:
            if self._cancel:
                break
            if await self._add_reward(page, reward.get('type'),
                                      reward.get('value'),
                                      reward.get('qty') or '1'):
                rewards_added += 1
        # Last of all, because a reward row only exists once it is added and
        # arrives with its required Tier unset.
        if added or rewards_added:
            await self._fill_blank_tiers(page)
            fields_complete = self._blank_tiers_complete and fields_complete
        return FillOutcome(added, rewards_added, fields_complete)

    async def run_many(self, game, bundles, storage_state, *, headed=False):
        """Create every bundle in one browser session, and report each id.

        One window for the whole run rather than one per bundle: opening Chrome
        and restoring the session costs more than the filling does, and the
        operator watching a headed run sees one window work through the list.

        Every bundle here is created for real — this is the equivalent of the
        desktop "สร้างทุก bundle อัตโนมัติ" button, which has no preview phase.
        Failures do not stop the run; each bundle reports its own outcome.
        """
        url = bundle_create_url(game)
        self.log('==== สร้างทุกบันเดิลอัตโนมัติ %d อัน ====' % len(bundles), 'STEP')
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(**browser_launch.launch_kwargs(headed))
        context = await browser.new_context(
            **browser_launch.context_kwargs(headed, storage_state=storage_state))
        page = await context.new_page()
        results = []
        try:
            for number, bundle in enumerate(bundles, 1):
                if self._cancel:
                    self.log('หยุดกลางคัน (ทำไป %d/%d)'
                             % (number - 1, len(bundles)), 'WARNING')
                    break
                name = bundle['name']
                self.log('----- [%d/%d] %s -----' % (number, len(bundles), name),
                         'STEP')
                entry = {'group': bundle.get('group', ''), 'name': name,
                         'saved': False, 'bundle_id': None, 'added': 0,
                         'total': len(bundle['items']), 'rewards_added': 0,
                         'rewards_total': len(bundle.get('rewards') or ()),
                         'fields_complete': True, 'error': None}
                try:
                    # A fresh create page per bundle: the previous one still
                    # holds the last bundle's items.
                    await page.goto(url, wait_until='domcontentloaded',
                                    timeout=30000)
                    await page.wait_for_timeout(3000)
                    if any(p in page.url.lower() for p in ('/login', '/signin')):
                        raise RuntimeError('session หมดอายุ (โดนเด้งไปหน้า login)')
                    fill_outcome = await self._fill_form(
                        page, name, bundle.get('type', 'FIXED'),
                        bundle.get('deliver', True), bundle['items'],
                        bundle.get('rewards') or ())
                    entry['added'], entry['rewards_added'] = fill_outcome
                    fields_complete = getattr(fill_outcome, 'fields_complete', True)
                    entry['fields_complete'] = fields_complete
                    if self._cancel:
                        raise RuntimeError('ถูกยกเลิกก่อนกดสร้าง')
                    if (entry['added'] != entry['total']
                            or entry['rewards_added'] != entry['rewards_total']
                            or not fields_complete):
                        entry['error'] = (
                            'form incomplete: items %d/%d, rewards %d/%d' % (
                                entry['added'], entry['total'],
                                entry['rewards_added'], entry['rewards_total']))
                        if not fields_complete:
                            entry['error'] += ', required field fill failed'
                        self.log('ไม่กดสร้าง "%s" เพราะกรอกฟอร์มไม่ครบ (%s)'
                                 % (name, entry['error']), 'ERROR')
                    else:
                        entry['saved'], entry['bundle_id'] = await self._save(page)
                except Exception as exc:
                    entry['error'] = str(exc)[:200]
                    self.log('บันเดิล "%s" ไม่สำเร็จ: %s' % (name, exc), 'ERROR')
                results.append(entry)
                await page.wait_for_timeout(1000)
        finally:
            await _shutdown(pw, browser, context)
        ok = sum(1 for r in results if r['saved'])
        self.log('==== เสร็จ: สร้างสำเร็จ %d/%d อัน ====' % (ok, len(bundles)),
                 'SUCCESS' if ok == len(bundles) else 'WARNING')
        return results

    async def run(self, game, name, btype, deliver, items, storage_state,
                  *, headed=False, rewards=(), do_save=False, keep_open_key=None):
        """Open the create page with the user's session and fill it.

        Nothing is created unless ``do_save`` is true. A headed preview leaves
        the window standing (see :func:`close_kept`) so the operator can read the
        real form instead of a screenshot of it.
        """
        url = bundle_create_url(game)
        self.log('เปิดหน้าสร้าง Bundle: %s' % url, 'STEP')
        if keep_open_key:
            await close_kept(keep_open_key)
        # Started by hand rather than via ``async with``: the window may outlive
        # this call, so the driver must not be torn down on the way out.
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(**browser_launch.launch_kwargs(headed))
        context = await browser.new_context(
            **browser_launch.context_kwargs(headed, storage_state=storage_state))
        page = await context.new_page()
        shot = None
        final_url = None
        added = 0
        rewards_added = 0
        fields_complete = True
        saved = False
        bundle_id = None
        keep = False
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(3000)
            low = page.url.lower()
            if any(p in low for p in ('/login', '/signin')):
                raise RuntimeError('session หมดอายุ (โดนเด้งไปหน้า login)')
            fill_outcome = await self._fill_form(
                page, name, btype, deliver, items, rewards)
            added, rewards_added = fill_outcome
            fields_complete = getattr(fill_outcome, 'fields_complete', True)
            final_url = page.url
            # A window that stays open needs no screenshot — the operator is
            # looking at the page itself.
            keep = bool(keep_open_key) and headed and not do_save
            if not keep:
                try:
                    shot = await page.screenshot(full_page=True)
                except Exception:
                    shot = None
            if do_save and not self._cancel:
                if (added != len(items) or rewards_added != len(rewards)
                        or not fields_complete):
                    self.log('ไม่กดสร้าง เพราะกรอกฟอร์มไม่ครบ: items %d/%d, rewards %d/%d'
                             % (added, len(items), rewards_added, len(rewards)),
                             'ERROR')
                else:
                    saved, bundle_id = await self._save(page)
                final_url = page.url
                await page.wait_for_timeout(2000 if headed else 0)
            else:
                self.log('กรอกฟอร์มเสร็จ (ยังไม่กดสร้าง) — เพิ่มไอเทม %d/%d'
                         % (added, len(items)), 'SUCCESS')
        finally:
            if keep:
                _KEPT[keep_open_key] = (pw, browser, context)
                self.log('เปิดหน้าต่างค้างไว้ให้ตรวจ — ปิดเองได้ '
                         'หรือจะปิดให้เองตอนเปิดครั้งถัดไป', 'INFO')
            else:
                await _shutdown(pw, browser, context)
        return {'url': final_url, 'screenshot': shot, 'added': added,
                'total': len(items), 'rewards_added': rewards_added,
                'rewards_total': len(rewards), 'fields_complete': fields_complete,
                'kept_open': keep,
                'saved': saved, 'bundle_id': bundle_id}


# Windows a headed preview left standing, one per operator. Browser concurrency
# is meant to stay at one, so the next run closes the last one first.
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


async def fetch_reward_options(game, storage_state, on_log):
    """Open the create page read-only and return ``{KIND: [names]}``.

    Split out from :meth:`BundleBuilder.run` so the operator can populate the
    reward dropdowns before building anything. It fills no field and clicks no
    confirm button, so it can never write to the live site — and it always runs
    headless, since there is nothing here worth watching.
    """
    url = bundle_create_url(game)
    on_log('อ่านตัวเลือก reward จาก: %s' % url, 'STEP')
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**browser_launch.launch_kwargs(False))
        context = await browser.new_context(
            **browser_launch.context_kwargs(False, storage_state=storage_state))
        page = await context.new_page()
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(2500)
            if any(p in page.url.lower() for p in ('/login', '/signin')):
                raise RuntimeError('session หมดอายุ (โดนเด้งไปหน้า login)')
            return await BundleBuilder(on_log).read_reward_options(page)
        finally:
            await context.close()
            await browser.close()


# The class was preview-only when it was introduced; keep the old name working
# for anything still importing it.
BundlePreview = BundleBuilder
