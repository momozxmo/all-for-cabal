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
import asyncio
import json
import re
from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError, async_playwright, expect

import new_tool
from web import browser_launch
from web.create_flow import click_create_and_wait_for_write
from web.search_runner import to_web_url
from web.bundle_recheck import SessionExpiredError, recheck_saved_bundle
from web.aztek_locator import AztekLocatorError, require_control


async def retry_saved_recheck(page, url, reference, submitted, *, attempts=3):
    """Reread an existing ID, never save. A decisive mismatch is not transient."""
    for attempt in range(1, attempts + 1):
        try:
            result = await recheck_saved_bundle(page, url, reference, submitted)
            return dict(result, read_attempts=attempt)
        except SessionExpiredError as exc:
            return {'outcome': 'failed', 'incomplete': True,
                    'session_expired': True, 'error': str(exc),
                    'read_attempts': attempt}
        except ValueError as exc:
            # A wrong ID/game cannot become correct merely by polling again.
            message = str(exc)
            if not any(part in message for part in ('จำนวนแถว', 'อ่านจำนวน')):
                return {'outcome': 'failed', 'incomplete': True,
                        'error': message[:200], 'read_attempts': attempt}
            if attempt == attempts:
                return {'outcome': 'failed', 'incomplete': True,
                        'error': message[:200], 'read_attempts': attempt}
        except (TimeoutError, PlaywrightError) as exc:
            if attempt == attempts:
                return {'outcome': 'failed', 'incomplete': True,
                        'error': str(exc)[:200], 'read_attempts': attempt}
        except Exception as exc:
            return {'outcome': 'failed', 'incomplete': True,
                    'error': str(exc)[:200], 'read_attempts': attempt}
        await asyncio.sleep(0.5)


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
# The popover renders in a portal at body level, outside that panel.
_POPOVER = '[data-radix-popper-content-wrapper]'

# Every row of the item list carries a required Tier — reward rows included,
# because v2 files rewards into that same list. A currency has no tier worth
# choosing, so the operator is never asked and blank rows take the first rank.
TIER_DEFAULT = 'Common'


def _reward_name(value):
    """The verified card shows the fetched option's name, not its slug."""
    text = str(value or '').strip()
    named = re.fullmatch(r'[a-z0-9_-]+ - (.+)', text)
    return named.group(1) if named else text


_CARD_EXPANDERS = 'button[aria-label="ขยาย"],button[aria-label="ย่อ"]'
_COLLAPSED_CARD_CHEVRONS = 'main form button[aria-expanded="false"][aria-label="ขยาย"]'

_CARD_EXPANDER_SHAPE = '''el => {
    const card = el.parentElement?.parentElement;
    const form = el.closest('form');
    const kinds = ['ITEM','WALLET','WALLET_CREDIT','WALLET_MILEAGE','PLAYER_EXPERIENCE'];
    return el.type === 'button' && [null,'button'].includes(el.getAttribute('role'))
      && ['true','false'].includes(el.getAttribute('aria-expanded'))
      && card && form && card !== form
      && card.closest('form') === form
      && card.querySelectorAll('button[aria-label="ขยาย"],button[aria-label="ย่อ"]').length === 1
      && [...card.querySelectorAll('span')].filter(s=>kinds.includes(s.textContent.trim())).length === 1;
}'''


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


async def read_existing_bundle(game, bundle_id, reference, submitted,
                               storage_state, *, headed=False):
    """Open a saved Bundle by ID and verify it without a create/save action."""
    url = bundle_create_url(game).rsplit('/create', 1)[0] + '/' + str(bundle_id)
    pw = await async_playwright().start()
    browser = context = None
    try:
        browser = await pw.chromium.launch(**browser_launch.launch_kwargs(headed))
        context = await browser.new_context(
            **browser_launch.context_kwargs(headed, storage_state=storage_state))
        page = await context.new_page()
        return await retry_saved_recheck(page, url, reference, submitted)
    finally:
        await _shutdown(pw, browser, context)


class BundleBuilder:
    """Fill one bundle form on Aztek v2, and create it only when asked."""

    def __init__(self, on_log):
        self._log = on_log
        self._cancel = False

    def log(self, message, level='INFO'):
        self._log(message, level)

    async def _native_option(self, page, scope, control, requested, *, preserve_existing=False, bound=None):
        """A visible trigger is checked by the caller; Radix's select is hidden."""
        select = scope.locator('select') if bound is None else None
        if bound is None:
            if await select.count() > 1:
                raise AztekLocatorError('Aztek: %s ช่อง native select ซ้ำ' % control)
            try:
                await select.wait_for(state='attached', timeout=5000)
            except PlaywrightError as exc:
                raise AztekLocatorError('Aztek: %s ช่อง native select ยังไม่พร้อม' % control) from exc
        deadline = asyncio.get_running_loop().time() + 5
        while True:
            if bound is not None:
                if not await bound.evaluate('card => card.isConnected'):
                    raise AztekLocatorError('Aztek: %s การ์ดถูกแทนที่ระหว่างรอ' % control)
                native = await bound.query_selector_all('select')
                if len(native) > 1:
                    raise AztekLocatorError('Aztek: %s ช่อง native select ซ้ำ' % control)
                if not native:
                    if asyncio.get_running_loop().time() >= deadline:
                        raise AztekLocatorError('Aztek: %s ช่อง native select ยังไม่พร้อม' % control)
                    await page.wait_for_timeout(100)
                    continue
                select = native[0]
                if await select.evaluate('s => s.type') != 'select-one':
                    raise AztekLocatorError('Aztek: %s ชนิด native select ไม่ตรง' % control)
            elif await select.count() != 1:
                raise AztekLocatorError('Aztek: %s ช่อง native select หายหรือซ้ำ' % control)
            options = await select.evaluate('s => [...s.options].map(o=>({text:o.textContent.trim(),value:o.value}))')
            current = await select.input_value() if preserve_existing else ''
            matches = ([o for o in options if o['value'] == current] if current
                       else [o for o in options if requested in (o['text'], o['value'])])
            if len(matches) == 1:
                return select, matches[0]['value']
            if len(matches) > 1 or asyncio.get_running_loop().time() >= deadline:
                raise AztekLocatorError('Aztek: %s ตัวเลือกที่กำหนดหายหรือซ้ำ' % control)
            await page.wait_for_timeout(100)

    async def _fill_header(self, page, name, btype, deliver):
        form = await require_control(page, 'ฟอร์ม Bundle', selector='main form', tags=('form',))
        box = await require_control(form, 'ชื่อ Bundle', element_id='bundle-name',
                                    tags=('input',), input_types=('text',))
        # No stable ID on the type widget in the four live game forms. Its
        # visible trigger establishes readiness before using its native select.
        type_block = await require_control(
            form, 'ประเภท Bundle',
            selector='xpath=.//label[contains(normalize-space(.),"ประเภท Bundle")]/..',
            tags=('div',))
        await require_control(type_block, 'ประเภท Bundle',
                              selector='button[role="combobox"]',
                              tags=('button',), roles=('combobox',))
        sel, selected_value = await self._native_option(page, type_block, 'ประเภท Bundle', btype)
        switch = await require_control(form, 'ส่งทันที', element_id='immediately-send',
                                       tags=('button',), roles=('switch',))
        state = await switch.get_attribute('aria-checked')
        if state not in ('true', 'false'):
            raise AztekLocatorError('ส่งทันที: อ่านสถานะสวิตช์ไม่ได้')
        # Validate the complete header contract before writing any header value.
        await box.fill(name)
        await sel.select_option(value=selected_value)
        if (state == 'true') != deliver:
            await switch.click(timeout=6000)
        complete = ((await box.input_value()) == name
                    and (await sel.input_value()) == selected_value
                    and (await switch.get_attribute('aria-checked')) == str(deliver).lower())
        self.log('ตั้งชื่อ/ประเภท/ส่งทันที Bundle แล้ว', 'INFO' if complete else 'WARNING')
        return complete

    async def _add_item(self, page, item_id):
        """Search the item id in the 'เพิ่มของเข้า Bundle' panel and click เพิ่ม."""
        try:
            form = await require_control(page, 'ฟอร์ม Bundle', selector='main form', tags=('form',))
            tab = await require_control(form, 'แท็บ Item',
                                        selector='button[role="tab"]:text-is("Item")',
                                        tags=('button',), roles=('tab',))
            await tab.click(timeout=5000)
            panel = await require_control(form, 'แผงเพิ่ม Item',
                                          selector='[role="tabpanel"][data-state="active"]',
                                          tags=('div',), roles=('tabpanel',))
            if await tab.get_attribute('aria-selected') != 'true':
                raise AztekLocatorError('แท็บ Item: ไม่ได้อยู่ในสถานะที่เลือก')
            box = await require_control(panel, 'ค้นหา Item ใน Bundle',
                                        selector='input[placeholder="ค้นหาชื่อ Item..."]',
                                        tags=('input',), input_types=('text',))
            await box.fill(str(item_id))
            # Result controls have no stable IDs. The verified result is a div
            # with its own direct Add button and one exact Item ID span. Search
            # only descendants: an ancestor walk can escape to a sibling's Add.
            if not str(item_id).isdigit():
                raise AztekLocatorError('Item ID ใน Bundle ไม่ถูกต้อง')
            row = panel.locator(
                'xpath=.//div[./button[normalize-space(.)="เพิ่ม"]]'
                '[.//span[normalize-space(.)="ID: %s"]]' % item_id)
            deadline = asyncio.get_running_loop().time() + 5
            while await row.count() == 0 and asyncio.get_running_loop().time() < deadline:
                await page.wait_for_timeout(100)
            if await row.count() == 0:
                identity = panel.locator('span').filter(
                    has_text=re.compile(r'^\s*ID:\s*%s\s*$' % re.escape(str(item_id))))
                if await identity.count():
                    raise AztekLocatorError('Item %s: หาแถวและปุ่มเพิ่มของรายการนี้ไม่ได้' % item_id)
                self.log('หาไอเทม %s ไม่เจอในผลค้นหา — ไม่กดเพิ่มรายการอื่น' % item_id, 'WARNING')
                return False
            if await row.count() != 1:
                raise AztekLocatorError('Item %s: ผลค้นหาใน Bundle ซ้ำ' % item_id)
            identities = row.locator('span').filter(has_text=re.compile(r'^\s*ID:\s*[0-9]+\s*$'))
            if await identities.count() != 1:
                raise AztekLocatorError('Item %s: ขอบเขตแถวมีหลาย Item ID' % item_id)
            add = await require_control(row, 'เพิ่ม Item %s' % item_id,
                                        selector='button:text-is("เพิ่ม")', tags=('button',))
            await add.click(timeout=5000)
            self.log('เพิ่มไอเทม %s' % item_id, 'INFO')
            await page.wait_for_timeout(600)
            return True
        except AztekLocatorError:
            raise
        except Exception as exc:
            self.log('เพิ่มไอเทม %s ไม่สำเร็จ: %s' % (item_id, exc), 'WARNING')
            return False

    # ---------------------------- rewards ----------------------------

    async def _open_reward_tab(self, page, kind):
        """Use the selected tab's runtime association, never a cached Radix ID."""
        name = REWARD_TABS.get(kind)
        if name is None:
            raise AztekLocatorError('Aztek: ไม่รู้จักชนิด reward %s' % kind)
        form = await require_control(page, 'ฟอร์ม Bundle', selector='main form', tags=('form',))
        tab = await require_control(form, 'แท็บ reward %s' % name,
                                    selector='button[role="tab"]:text-is(%s)' % json.dumps(name),
                                    tags=('button',), roles=('tab',), input_types=('button',))
        await tab.click(timeout=5000)
        deadline = asyncio.get_running_loop().time() + 5
        while (not await tab.get_attribute('aria-controls')
               or await tab.get_attribute('aria-selected') != 'true') and asyncio.get_running_loop().time() < deadline:
            await page.wait_for_timeout(100)
        panel_id = await tab.get_attribute('aria-controls')
        if not panel_id or await tab.get_attribute('aria-selected') != 'true':
            raise AztekLocatorError('Aztek: แท็บ reward %s ไม่พร้อมหรือไม่ชี้แผง' % name)
        panel = await require_control(form, 'แผง reward %s' % name,
                                      selector='[id=%s]' % json.dumps(panel_id),
                                      tags=('div',), roles=('tabpanel',))
        tab_id = await tab.get_attribute('id')
        deadline = asyncio.get_running_loop().time() + 5
        while tab_id and (await panel.get_attribute('data-state') != 'active'
                         or await panel.get_attribute('aria-labelledby') != tab_id) and asyncio.get_running_loop().time() < deadline:
            await page.wait_for_timeout(100)
        if (not tab_id or await panel.get_attribute('data-state') != 'active'
                or await panel.get_attribute('aria-labelledby') != tab_id):
            raise AztekLocatorError('Aztek: แผง reward %s ไม่ตรงกับแท็บที่เลือก' % name)
        return panel

    async def _open_picker(self, page, panel):
        """Follow live aria-controls through portal dialog/search/listbox."""
        picker = await require_control(panel, 'ตัวเลือก reward',
                                       selector='button[role="combobox"]', tags=('button',),
                                       roles=('combobox',), input_types=('button',))
        if await picker.get_attribute('aria-expanded') != 'false':
            raise AztekLocatorError('Aztek: ตัวเลือก reward ไม่อยู่ในสถานะปิดที่ตรวจไว้')
        await picker.click(timeout=5000)
        deadline = asyncio.get_running_loop().time() + 5
        while (not await picker.get_attribute('aria-controls')
               or await picker.get_attribute('aria-expanded') != 'true') and asyncio.get_running_loop().time() < deadline:
            await page.wait_for_timeout(100)
        dialog_id = await picker.get_attribute('aria-controls')
        if not dialog_id or await picker.get_attribute('aria-expanded') != 'true':
            raise AztekLocatorError('Aztek: ตัวเลือก reward ไม่ชี้ dialog ที่เปิด')
        dialog = await require_control(page.locator(_POPOVER), 'dialog reward',
                                       selector='[id=%s]' % json.dumps(dialog_id),
                                       tags=('div',), roles=('dialog',))
        search = await require_control(dialog, 'ค้นหา reward', selector='input[role="combobox"]',
                                       tags=('input',), roles=('combobox',), input_types=('text',))
        deadline = asyncio.get_running_loop().time() + 5
        while not await search.get_attribute('aria-controls') and asyncio.get_running_loop().time() < deadline:
            await page.wait_for_timeout(100)
        list_id = await search.get_attribute('aria-controls')
        if not list_id:
            raise AztekLocatorError('Aztek: ช่องค้นหา reward ไม่ชี้รายการตัวเลือก')
        choices = await require_control(dialog, 'รายการตัวเลือก reward',
                                        selector='[id=%s]' % json.dumps(list_id),
                                        tags=('div',), roles=('listbox',))
        return picker, dialog, search, choices

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
                    _, _, _, choices = await self._open_picker(page, panel)
                    opts = choices.locator('[role="option"]')
                    try:
                        # Enumeration may use the first option for readiness,
                        # but selecting a requested reward requires uniqueness.
                        await opts.first.wait_for(state='visible', timeout=5000)
                    except PlaywrightError as exc:
                        raise AztekLocatorError('Aztek: ตัวเลือก reward %s ยังไม่พร้อม' % kind) from exc
                    names = [text.strip()
                             for text in await opts.all_inner_texts()
                             if text.strip()]
                    # Duplicates are real on this site (two "Pull Free" entries);
                    # keep first-seen order but offer each name once.
                    names = list(dict.fromkeys(names))
                    await page.keyboard.press('Escape')
                    await page.wait_for_timeout(400)
            except AztekLocatorError:
                raise
            except Exception as exc:
                self.log('อ่านตัวเลือก %s ไม่สำเร็จ: %s'
                         % (REWARD_TABS.get(kind, kind), exc), 'WARNING')
            self.log('  %s: %d รายการ' % (kind, len(names)),
                     'INFO' if names else 'WARNING')
            options[kind] = names
        # Leave the panel back on the item list — that is what the operator
        # expects to see on a preview.
        try:
            form = await require_control(page, 'ฟอร์ม Bundle', selector='main form', tags=('form',))
            tab = await require_control(form, 'แท็บ Item', selector='button[role="tab"]:text-is("Item")',
                                        tags=('button',), roles=('tab',), input_types=('button',))
            await tab.click(timeout=3000)
        except AztekLocatorError:
            raise
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
            picker, _, search, choices = await self._open_picker(page, panel)
            await search.fill(value)
            hit = await require_control(choices, 'reward %s: %s' % (kind, value),
                                        selector='[role="option"]:text-is(%s)' % json.dumps(value, ensure_ascii=False),
                                        tags=('div',), roles=('option',))
            await hit.click(timeout=5000)
            deadline = asyncio.get_running_loop().time() + 5
            while (await picker.get_attribute('aria-expanded') != 'false'
                   or (await picker.inner_text()).strip() != value) and asyncio.get_running_loop().time() < deadline:
                await page.wait_for_timeout(100)
            if await picker.get_attribute('aria-expanded') != 'false':
                raise AztekLocatorError('Aztek: เลือก reward แล้ว picker ยังไม่ปิด')
            if (await picker.inner_text()).strip() != value:
                raise AztekLocatorError('Aztek: ตัวเลือก reward อ่านกลับไม่ตรงกับชื่อที่ขอ')
        except AztekLocatorError:
            raise
        except Exception as exc:
            self.log('reward %s เลือกไม่สำเร็จ: %s' % (kind, exc), 'WARNING')
            return False
        try:
            amount = await require_control(panel, 'จำนวน reward', selector='input[placeholder="Qty"]',
                                           tags=('input',), input_types=('number',))
            await amount.fill(str(qty))
            if await amount.input_value() != str(qty):
                raise AztekLocatorError('Aztek: จำนวน reward อ่านกลับไม่ตรง')
        except AztekLocatorError:
            raise
        except Exception as exc:
            self.log('reward %s ใส่จำนวนไม่สำเร็จ: %s' % (kind, exc), 'WARNING')
            return False
        try:
            # v2 labels this button plain "เพิ่ม" — the v1 wording in
            # new_tool.SEL['add_to_bundle'] does not appear on this page.
            add = await require_control(panel, 'เพิ่ม reward', selector='button:text-is("เพิ่ม")',
                                        tags=('button',), roles=(None, 'button'), input_types=('button',))
            await add.click(timeout=5000)
            self.log('เพิ่ม reward %s = %s x%s' % (kind, value, qty), 'SUCCESS')
            await page.wait_for_timeout(700)
            return True
        except AztekLocatorError:
            raise
        except Exception as exc:
            self.log('reward %s กดเพิ่มไม่ได้: %s' % (kind, exc), 'WARNING')
            return False

    # ------------------------ per-item fields ------------------------

    async def _expand_item_cards(self, page):
        """Reveal lazy item cards before addressing their controls.

        The site can mount Qty/Tier only after a card opens. Validate each
        expander's actual card scope before clicking; opening cards is not a
        reason to press another form action. Already-open cards stay open.
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
            attempts = 0
            limit = max(collapsed * 2, 4)
            while await chevrons.count():
                if attempts >= limit:
                    self.log('เปิดการ์ดไม่ครบภายในจำนวนครั้งที่ปลอดภัย', 'WARNING')
                    return False
                before = await chevrons.count()
                chevron = chevrons.first
                valid_card = await chevron.evaluate(_CARD_EXPANDER_SHAPE)
                if not valid_card:
                    raise AztekLocatorError('Aztek: ปุ่มกางการ์ดไม่ได้อยู่ในการ์ดรางวัลที่ตรวจไว้')
                if not await chevron.is_visible():
                    self.log('พบการ์ดที่ยังปิดแต่กดเปิดไม่ได้', 'WARNING')
                    return False
                await chevron.click(timeout=5000)
                after = await chevrons.count()
                deadline = asyncio.get_running_loop().time() + 5
                while after >= before and asyncio.get_running_loop().time() < deadline:
                    await page.wait_for_timeout(100)
                    after = await chevrons.count()
                if after >= before:
                    self.log('การ์ดไม่เปลี่ยนเป็นสถานะเปิด', 'WARNING')
                    return False
                attempts += 1
            return True
        except AztekLocatorError:
            raise
        except Exception as exc:
            self.log('เปิดการ์ดไอเท็มเพื่อกรอก Tier ไม่สำเร็จ: %s' % exc,
                     'WARNING')
            return False

    async def _fill_qty_tier(self, page, items):
        """Match Item/reward identity before touching its Quantity/Tier."""
        seen_ids = set()
        seen_rewards = set()
        for entry in items:
            item_id = entry.get('id') or entry.get('aztek_id')
            if item_id is not None:
                identity = str(item_id)
                if identity in seen_ids and entry.get('_aztek_card') is None:
                    raise AztekLocatorError('Aztek: Item %s ซ้ำ ไม่สามารถจับคู่การ์ดได้อย่างแน่นอน' % identity)
                seen_ids.add(identity)
            elif entry.get('type') in REWARD_TABS:
                identity = (entry['type'], _reward_name(entry.get('value')))
                if identity in seen_rewards and entry.get('_aztek_card') is None:
                    raise AztekLocatorError('Aztek: reward %s ซ้ำ ไม่สามารถจับคู่การ์ดได้อย่างแน่นอน' % identity[1])
                seen_rewards.add(identity)
        expansion_complete = await self._expand_item_cards(page)
        complete = expansion_complete
        for it in items:
            item_id = it.get('id') or it.get('aztek_id')
            if item_id is not None or it.get('type') in REWARD_TABS:
                card, quantity, control = await self._entry_card(page, it)
                bound = it.get('_aztek_card')
                quantity = await self._owned_control(quantity, bound, control)
                qty = str(it.get('qty') or it.get('quantity') or '1')
                tier = it.get('tier') or TIER_DEFAULT
                await require_control(card, 'Tier ของ %s' % control,
                                      selector='button[role="combobox"]',
                                      tags=('button',), roles=('combobox',), input_types=('button',))
                await quantity.fill(qty)
                if bound is not None:
                    # Quantity input may reorder/renumber the same live card.
                    card, _, _ = await self._entry_card(page, it)
                    await require_control(card, 'Tier ของ %s' % control,
                                          selector='button[role="combobox"]',
                                          tags=('button',), roles=('combobox',), input_types=('button',))
                selects, selected_value = await self._native_option(
                    page, card, 'Tier ของ %s' % control, tier,
                    preserve_existing=item_id is None and not it.get('tier'), bound=bound)
                await selects.select_option(value=selected_value)
                if (await quantity.input_value() != qty
                        or await selects.input_value() != selected_value):
                    raise AztekLocatorError('Aztek: จำนวน/Tier ของ %s อ่านกลับไม่ตรง' % control)
                if it.get('_aztek_card') is not None:
                    it['_aztek_tier_value'] = selected_value
                continue
            raise AztekLocatorError('Aztek: รายการไม่มี Item/reward identity ที่รองรับ')
        if items:
            self.log('ตั้งจำนวน/Tier ให้ %d รายการ' % len(items), 'INFO')

        return complete

    async def _bound_card(self, candidates, handle, control):
        """Resolve a fill-local node identity; never reuse its previous index.

        This is not a stable Aztek ID. Replaced/deleted duplicate nodes cannot
        be recovered by guessing an occurrence from the new DOM order.
        """
        matches = []
        for index in range(await candidates.count()):
            candidate = candidates.nth(index)
            if await candidate.evaluate('(node, original) => node === original && node.isConnected', handle):
                matches.append(candidate)
        if len(matches) != 1:
            raise AztekLocatorError('Aztek: การ์ด %s ซ้ำ/เปลี่ยนไป จับคู่รายการเดิมไม่ได้' % control)
        return matches[0]

    async def _owned_control(self, locator, bound, control):
        if bound is None:
            return locator
        node = await locator.element_handle()
        if node is None or not await bound.evaluate(
                '(card, node) => card.isConnected && node.isConnected && card.contains(node)', node):
            raise AztekLocatorError('Aztek: %s เปลี่ยนการ์ดระหว่างกรอก' % control)
        # A node-specific handle cannot silently retarget after a DOM reorder.
        return node

    async def _entry_card(self, page, entry):
        item_id = entry.get('id') or entry.get('aztek_id')
        if item_id is not None:
            card, quantity = await self._item_card(page, item_id, entry.get('_aztek_card'))
            return card, quantity, 'Item %s' % item_id
        card, quantity = await self._reward_card(page, entry, entry.get('_aztek_card'))
        return card, quantity, 'reward %s' % entry.get('value')

    async def _draw_control(self, card, quantity, control, bound=None):
        current = re.fullmatch(r'items\.([0-9]+)\.quantity', await quantity.get_attribute('name') or '')
        if current is None:
            raise AztekLocatorError('Aztek: index การ์ด %s ไม่ถูกต้อง' % control)
        form = card.locator('xpath=ancestor::form[1]')
        box = await require_control(form, 'เรทสุ่มของ %s' % control,
                                    element_id='items.%s.secret_chance' % current.group(1),
                                    tags=('input',), input_types=('number',))
        if not await box.evaluate('(node, card) => card.contains(node)', await card.element_handle()):
            raise AztekLocatorError('Aztek: เรทสุ่มของ %s อยู่ผิดการ์ด' % control)
        return await self._owned_control(box, bound, 'เรทสุ่มของ %s' % control)

    async def _card_handles(self, page):
        form = await require_control(page, 'ฟอร์ม Bundle', selector='main form', tags=('form',))
        return await form.locator(_CARD_EXPANDERS).locator('xpath=../..').element_handles()

    async def _new_card(self, page, before, entry):
        control = ('Item %s' % (entry.get('id') or entry.get('aztek_id'))
                   if entry.get('id') or entry.get('aztek_id') else 'reward %s' % entry.get('value'))
        deadline = asyncio.get_running_loop().time() + 5
        while True:
            after = await self._card_handles(page)
            if len(after) > len(before):
                break
            if asyncio.get_running_loop().time() >= deadline:
                raise AztekLocatorError('Aztek: การ์ด %s ซ้ำหรือถูกรวม ไม่มีรายการใหม่ให้จับคู่' % control)
            await page.wait_for_timeout(100)
        if len(after) != len(before) + 1:
            raise AztekLocatorError('Aztek: การ์ด %s เพิ่มหลายรายการ จับคู่ไม่ชัดเจน' % control)
        new = []
        retained = set()
        for card in after:
            old_matches = [index for index, old in enumerate(before)
                           if await card.evaluate('(node, old) => node === old && node.isConnected', old)]
            if old_matches:
                retained.update(old_matches)
            else:
                new.append(card)
        if len(new) != 1 or len(retained) != len(before):
            raise AztekLocatorError('Aztek: การ์ด %s ซ้ำ/ถูกแทนที่ จับคู่รายการเดิมไม่ได้' % control)
        return dict(entry, _aztek_card=new[0])

    async def _verify_occurrences(self, page, entries, btype):
        """Later inputs must not silently change a previously filled row."""
        seen_indexes = set()
        for entry in entries:
            card, quantity, control = await self._entry_card(page, entry)
            quantity = await self._owned_control(quantity, entry['_aztek_card'], control)
            current = re.fullmatch(r'items\.([0-9]+)\.quantity', await quantity.get_attribute('name') or '')
            if current is None or int(current.group(1)) in seen_indexes:
                raise AztekLocatorError('Aztek: index ของ %s หายหรือซ้ำกับการ์ดอื่น' % control)
            seen_indexes.add(int(current.group(1)))
            qty = str(entry.get('qty') or entry.get('quantity') or '1')
            select, expected = await self._native_option(
                page, card, 'Tier ของ %s' % control, entry['_aztek_tier_value'], bound=entry['_aztek_card'])
            if await quantity.input_value() != qty or await select.input_value() != expected:
                raise AztekLocatorError('Aztek: จำนวน/Tier ของ %s เปลี่ยนหลังกรอกรายการอื่น' % control)
            raw_rate = entry.get('rate')
            rate = '' if raw_rate is None else str(raw_rate).strip()
            if btype == 'RANDOM' and rate:
                box = await self._draw_control(card, quantity, control, entry['_aztek_card'])
                if await box.input_value() != rate:
                    raise AztekLocatorError('Aztek: เรทสุ่มของ %s เปลี่ยนหลังกรอกรายการอื่น' % control)

    async def _item_card(self, page, item_id, bound=None):
        """Resolve an Item's current card, never its submitted list position.

        Saved M SEA Item cards expose no permanent card/Quantity/Tier IDs.
        Their expander and exact Item ID label are the scoped exception; the
        quantity name gives the *current* indexed row for stable rate IDs.
        """
        form = await require_control(page, 'ฟอร์ม Bundle', selector='main form', tags=('form',))
        if not re.fullmatch(r'[0-9]+', str(item_id)):
            raise AztekLocatorError('Aztek: Item ID ของการ์ดไม่ถูกต้อง')
        identity = 'xpath=.//label[normalize-space(.)="Item ID"]/following-sibling::p[normalize-space(.)="%s"]' % item_id
        card = form.locator(_CARD_EXPANDERS).locator('xpath=../..').filter(has=page.locator(identity))
        deadline = asyncio.get_running_loop().time() + 5
        while not await card.count() and asyncio.get_running_loop().time() < deadline:
            if not await self._expand_item_cards(page):
                raise AztekLocatorError('Aztek: เปิดการ์ด Item %s ไม่สำเร็จ' % item_id)
            await page.wait_for_timeout(100)
        if bound is not None:
            card = await self._bound_card(card, bound, 'Item %s' % item_id)
        if await card.count() != 1:
            raise AztekLocatorError('Aztek: การ์ด Item %s หาไม่ได้หรือพบหลายรายการ' % item_id)
        expander = card.locator(_CARD_EXPANDERS)
        if await expander.count() != 1 or not await expander.evaluate(_CARD_EXPANDER_SHAPE):
            raise AztekLocatorError('Aztek: การ์ด Item %s โครงสร้างไม่ตรงกับที่ตรวจไว้' % item_id)
        if await card.locator('span:text-is("ITEM")').count() != 1:
            raise AztekLocatorError('Aztek: การ์ด Item %s ชนิดรางวัลไม่ใช่ ITEM' % item_id)
        if not await self._expand_item_cards(page):
            raise AztekLocatorError('Aztek: เปิดการ์ด Item %s ไม่สำเร็จ' % item_id)
        if await card.locator('xpath=.//label[normalize-space(.)="Item ID"]/following-sibling::p').count() != 1:
            raise AztekLocatorError('Aztek: การ์ด Item %s มี identity ที่ไม่ชัดเจน' % item_id)
        quantity = await require_control(card, 'จำนวนของ Item %s' % item_id,
                                         selector='input[name^="items."][name$=".quantity"]',
                                         tags=('input',), input_types=('number',))
        return card, quantity

    async def _reward_card(self, page, reward, bound=None):
        """No-ID exception: one kind/name card, validated against its header."""
        kinds = {'CREDIT': 'WALLET_CREDIT', 'DEBIT': 'WALLET',
                 'MILEAGE': 'WALLET_MILEAGE', 'PLAYER_EXP': 'PLAYER_EXPERIENCE'}
        kind = reward.get('type')
        if kind not in kinds:
            raise AztekLocatorError('Aztek: ชนิด reward ของการ์ดไม่ถูกต้อง')
        name = _reward_name(reward.get('value'))
        if not name:
            raise AztekLocatorError('Aztek: ชื่อ reward ของการ์ดว่าง')
        label = 'ชื่อ Monarchy' if kind == 'PLAYER_EXP' else 'ชื่อ'
        form = await require_control(page, 'ฟอร์ม Bundle', selector='main form', tags=('form',))
        identity = 'label:text-is(%s) + p:text-is(%s)' % (json.dumps(label, ensure_ascii=False), json.dumps(name, ensure_ascii=False))
        card = form.locator(_CARD_EXPANDERS).locator('xpath=../..').filter(
            has=page.locator(identity)).filter(has=page.locator('span:text-is(%s)' % json.dumps(kinds[kind])))
        deadline = asyncio.get_running_loop().time() + 5
        while not await card.count() and asyncio.get_running_loop().time() < deadline:
            if not await self._expand_item_cards(page):
                raise AztekLocatorError('Aztek: เปิดการ์ด reward %s ไม่สำเร็จ' % name)
            await page.wait_for_timeout(100)
        if bound is not None:
            card = await self._bound_card(card, bound, 'reward %s' % name)
        if await card.count() != 1:
            raise AztekLocatorError('Aztek: การ์ด reward %s หาไม่ได้หรือพบหลายรายการ' % name)
        expander = card.locator(_CARD_EXPANDERS)
        if await expander.count() != 1 or not await expander.evaluate(_CARD_EXPANDER_SHAPE):
            raise AztekLocatorError('Aztek: การ์ด reward %s โครงสร้างไม่ตรงกับที่ตรวจไว้' % name)
        if (await card.locator('label:text-is(%s) + p' % json.dumps(label, ensure_ascii=False)).count() != 1
                or await expander.locator('p:text-is(%s)' % json.dumps(name, ensure_ascii=False)).count() != 1):
            raise AztekLocatorError('Aztek: ชื่อการ์ด reward %s อ่านกลับไม่ตรงหรือกำกวม' % name)
        if not await self._expand_item_cards(page):
            raise AztekLocatorError('Aztek: เปิดการ์ด reward %s ไม่สำเร็จ' % name)
        quantity = await require_control(card, 'จำนวนของ reward %s' % name,
                                         selector='input[name^="items."][name$=".quantity"]',
                                         tags=('input',), input_types=('number',))
        return card, quantity


    async def _fill_rates(self, page, items):
        """Set the random rate on each item card (RANDOM bundles only).

        Item/reward identities resolve their current card/index before literal
        stable-ID lookup. The adjacent ``chance`` is display-only.
        """
        done = 0
        for it in items:
            raw_rate = it.get('rate')
            rate = '' if raw_rate is None else str(raw_rate).strip()
            if not rate:
                continue
            item_id = it.get('id') or it.get('aztek_id')
            if item_id is not None or it.get('type') in REWARD_TABS:
                card, quantity, control = await self._entry_card(page, it)
                quantity = await self._owned_control(quantity, it.get('_aztek_card'), control)
                box = await self._draw_control(card, quantity, control, it.get('_aztek_card'))
                await box.fill(rate)
                if await box.input_value() != rate:
                    raise AztekLocatorError('Aztek: เรทสุ่มของ %s อ่านกลับไม่ตรง' % control)
                done += 1
                continue
            raise AztekLocatorError('Aztek: รายการเรทไม่มี Item/reward identity ที่รองรับ')
        if done:
            self.log('ตั้งเรทสุ่มให้ %d ไอเทม' % done, 'INFO')

        return done == len(items)

    # ------------------------------ save ------------------------------

    async def _create_button(self, page):
        # Observed no-ID exception: one exact submit action in the main form.
        form = await require_control(page, 'Bundle form', selector='main form', tags=('form',))
        contract = dict(selector='button:text-is("สร้าง Bundle")',
                        tags=('button',), roles=(None, 'button'), input_types=('submit',))
        button = await require_control(form, 'สร้าง Bundle', **contract)
        try:
            await expect(button).to_be_enabled(timeout=5000)
        except AssertionError as exc:
            raise AztekLocatorError('Aztek: สร้าง Bundle ยังไม่พร้อมใช้งาน') from exc
        # Waiting can mount a replacement or change type/form ownership.
        form = await require_control(page, 'Bundle form', selector='main form', tags=('form',))
        button = await require_control(form, 'สร้าง Bundle', **contract)
        if not await button.evaluate('el => el.form === el.closest("form")'):
            raise AztekLocatorError('Aztek: สร้าง Bundle ผูกกับฟอร์มอื่น')
        return button

    async def _confirmation_button(self, page, create_url):
        # M TH observed no-ID exception. Runtime Radix IDs only link live ARIA
        # title/description; they are never cached as developer-maintained IDs.
        selector = ('[role="alertdialog"][data-state="open"]'
                    ':has(h2:text-is("ยืนยันการสร้าง"))'
                    ':has(p:text-is("ต้องการสร้าง Bundle ใช่หรือไม่?"))')
        contract = dict(selector='button:text-is("ยืนยัน")', tags=('button',),
                        roles=(None, 'button'), input_types=('button',))
        if page.url != create_url:
            raise AztekLocatorError('Aztek: หน้า Bundle เปลี่ยนก่อนยืนยัน ต้องตรวจผลบนเว็บ')
        try:
            dialog = await require_control(page, 'กล่องยืนยัน Bundle', selector=selector,
                                           tags=('div',), roles=('alertdialog',))
        except AztekLocatorError:
            # Legacy direct-write pages have no popup. Absence is not the same
            # as a present but broken/ambiguous confirmation contract.
            if (page.url == create_url
                    and await page.locator('[role="dialog"],[role="alertdialog"]').count() == 0
                    and await page.locator('h2:text-is("ยืนยันการสร้าง"), '
                                           'p:text-is("ต้องการสร้าง Bundle ใช่หรือไม่?")').count() == 0):
                return None
            raise
        button = await require_control(dialog, 'ยืนยัน Bundle', **contract)
        try:
            await expect(button).to_be_enabled(timeout=5000)
        except AssertionError as exc:
            raise AztekLocatorError('Aztek: ยืนยัน Bundle ยังไม่พร้อมใช้งาน') from exc
        dialog = await require_control(page, 'กล่องยืนยัน Bundle', selector=selector,
                                       tags=('div',), roles=('alertdialog',))
        button = await require_control(dialog, 'ยืนยัน Bundle', **contract)
        valid = await dialog.evaluate('''d => {
            const titleId=d.getAttribute('aria-labelledby');
            const descriptionId=d.getAttribute('aria-describedby');
            const linked=(id,tag,text) => {
                const nodes=[...document.querySelectorAll('[id]')].filter(e=>e.id===id);
                return !!id && nodes.length===1 && nodes[0].tagName===tag
                    && nodes[0].textContent.trim()===text && d.contains(nodes[0])
                    && nodes[0].closest('[role="dialog"],[role="alertdialog"]')===d;
            };
            return linked(titleId,'H2','ยืนยันการสร้าง')
                && linked(descriptionId,'P','ต้องการสร้าง Bundle ใช่หรือไม่?')
                && !d.querySelector('[role="dialog"],[role="alertdialog"]');
        }''')
        if (page.url != create_url or not valid
                or not await button.evaluate('el => el.form === null')):
            raise AztekLocatorError('Aztek: กล่องยืนยัน Bundle มี scope หรือ ARIA ไม่ตรง')
        return button

    async def _save(self, page):
        """Click confirm and report the created bundle id.

        The id is only read from a 2xx response body or the redirect URL — an
        error body can carry unrelated numbers.
        """
        button = await self._create_button(page)
        create_url = page.url
        confirmation_error = None

        def matches_write(response):
            # Only M TH has a captured create-operation contract. Other games
            # retain compatibility until their actual endpoints are verified.
            if create_url == bundle_create_url('CabalM TH'):
                parsed = urlsplit(response.url)
                try:
                    return (response.request.method == 'POST'
                            and (parsed.scheme, parsed.netloc, parsed.path) == (
                                'https', 'admin-api-v2.combo-interactive.com',
                                '/cabalm/warehouse/bundles')
                            and response.request.frame == page.main_frame)
                except PlaywrightError:
                    # A worker-owned request has no verified form/frame owner.
                    return False
            return (response.request.method in ('POST', 'PUT', 'PATCH')
                    and 'bundle' in response.url.lower())

        try:
            response, confirmed = await click_create_and_wait_for_write(
                page, button, matches_write,
                confirm_resolver=lambda: self._confirmation_button(page, create_url),
            )
        except (AztekLocatorError, PlaywrightError) as exc:
            # The first click may already have written and navigated. Reconcile
            # existing URL proof before losing its ID to a confirmation error.
            confirmation_error = exc
            response, confirmed = None, False
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
            match = re.fullmatch(re.escape(create_url.rsplit('/create', 1)[0])
                                 + r'/(\d+)(?:[/?#].*)?', page.url)
            if match:
                bundle_id = match.group(1)
        if response is None and not bundle_id:
            if confirmation_error is not None:
                raise confirmation_error
            self.log('ยังยืนยันผลสร้างไม่ได้: ไม่พบคำตอบการบันทึกหรือเลข Bundle '
                     'ใน URL — ตรวจบนเว็บก่อน ห้ามสร้างซ้ำ',
                     'ERROR')
            return False, None
        if confirmation_error is not None:
            self.log('กล่องยืนยันอ่านไม่ได้ แต่พบเลข Bundle จากหน้าผลสร้าง '
                     'ของเกมเดิม — เก็บผลไว้และห้ามสร้างซ้ำ', 'WARNING')
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
        successful_rewards = []
        header_complete = await self._fill_header(page, name, btype, deliver)
        # Older tests/integrations monkeypatch this method with a coroutine that
        # returns None; only an explicit False from the real completion-aware
        # header path closes the save gate.
        fields_complete = header_complete is not False
        identities = [('ITEM', str(it.get('id') or it.get('aztek_id'))) for it in items]
        identities += [(r.get('type'), _reward_name(r.get('value'))) for r in rewards]
        track_occurrences = len(identities) != len(set(identities))
        for it in items:
            if self._cancel:
                break
            before = await self._card_handles(page) if track_occurrences else None
            if await self._add_item(page, it.get('id') or it.get('aztek_id')):
                added += 1
                successful_items.append(await self._new_card(page, before, it) if track_occurrences else it)
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
            before = await self._card_handles(page) if track_occurrences else None
            if await self._add_reward(page, reward.get('type'),
                                      reward.get('value'),
                                      reward.get('qty') or '1'):
                rewards_added += 1
                successful_rewards.append(await self._new_card(page, before, reward) if track_occurrences else reward)
        # Each reward's name/kind resolves its current card, including default
        # Common and numeric zero rates; truthiness must not skip that row.
        if successful_rewards:
            entries = successful_items + successful_rewards
            fields_complete = ((await self._fill_qty_tier(page, entries)) is not False) and fields_complete
            if btype == 'RANDOM' and any('tier' in reward or reward.get('rate') not in (None, '')
                                         for reward in successful_rewards):
                fields_complete = ((await self._fill_rates(page, entries)) is not False) and fields_complete
        # Defaults were filled on the matched cards above, never by sweeping
        # unrelated native selects or unrequested cards on the page.
        if track_occurrences and fields_complete:
            await self._verify_occurrences(page, successful_items + successful_rewards, btype)
        return FillOutcome(added, rewards_added, fields_complete)

    async def run_many(self, game, bundles, storage_state, *, headed=False,
                       checkpoint=None):
        """Create every bundle in one browser session, and report each id.

        One window for the whole run rather than one per bundle: opening Chrome
        and restoring the session costs more than the filling does, and the
        operator watching a headed run sees one window work through the list.

        Every bundle here is created for real — this is the equivalent of the
        desktop "สร้างทุก bundle อัตโนมัติ" button, which has no preview phase.
        Only a full recheck pass permits the next creation.
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
                        # A known pre-click locator failure is not an uncertain
                        # write and must not lock an otherwise retryable draft.
                        await self._create_button(page)
                        # The write may succeed even when Chromium loses its
                        # response. Reserve this key durably before clicking.
                        entry['creation_uncertain'] = True
                        entry['recheck'] = {'outcome': 'pending', 'incomplete': True}
                        if checkpoint is not None:
                            checkpoint(bundle, entry)
                        entry['saved'], entry['bundle_id'] = await self._save(page)
                        if entry['saved']:
                            entry['creation_uncertain'] = False
                            entry['recheck'] = {'outcome': 'pending', 'incomplete': True}
                            # Persist the existence/ID before any read can fail.
                            if checkpoint is not None:
                                checkpoint(bundle, entry)
                            try:
                                if not entry['bundle_id']:
                                    raise ValueError('สร้างแล้วแต่อ่าน Bundle ID ไม่ได้ ห้ามสร้างซ้ำ')
                                entry['recheck'] = await retry_saved_recheck(
                                    page, url.rsplit('/create', 1)[0] + '/' + str(entry['bundle_id']),
                                    bundle.get('document_reference'), dict(bundle, game=game))
                            except Exception as exc:
                                entry['recheck'] = {'outcome': 'failed', 'incomplete': True,
                                                    'error': str(exc)[:200]}
                            if checkpoint is not None:
                                checkpoint(bundle, entry)
                except Exception as exc:
                    if isinstance(exc, AztekLocatorError):
                        entry['fields_complete'] = False
                    entry['error'] = str(exc)[:200]
                    self.log('บันเดิล "%s" ไม่สำเร็จ: %s' % (name, exc), 'ERROR')
                results.append(entry)
                if entry.get('recheck', {}).get('outcome') != 'passed':
                    self.log('หยุดคิว: ต้องตรวจผลและยืนยันก่อนทำรายการถัดไป', 'WARNING')
                    break
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


def kept_count():
    return len(_KEPT)


async def close_all_kept():
    for key, (pw, browser, context) in list(_KEPT.items()):
        if browser.is_connected():
            await context.close()
            await browser.close()
        await pw.stop()
        _KEPT.pop(key, None)


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
