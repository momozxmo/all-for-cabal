# -*- coding: utf-8 -*-
"""Fill the Aztek v2 "สร้าง Item Code" form.

One Item Code holds one or more reward sets. Each set carries its own codes —
either a list the operator supplies (Fix) or a count for the server to generate
— and exactly one bundle: v2 replaces a chosen bundle rather than adding to it,
so a plan that names several bundles for one prize needs several reward sets.

The desktop tool drives the v1 page, whose fields are laid out differently;
this is the v2 form and keeps its own selectors.
"""
from urllib.parse import urlsplit
from playwright.async_api import Error as PlaywrightError, expect
from web import aztek_form
from web.activity_runner import ActivityBuilder
from web.aztek_locator import AztekLocatorError, require_control

#: value of the "ประเภทของ Code" select
CODE_FIX, CODE_SERVER = '1', '2'

# Independently captured POST operations, not paths inferred between games.
_VERIFIED_WRITE_PATHS = {
    'CabalM TH': '/cabalm/itemcode/events',
    'CabalM SEA': '/cabalmsea/itemcode/events',
    'CabalPC TH': '/cabalpc/itemcode/events',
    'CabalPC SEA': '/cabalpcsea/itemcode/events',
}


def code_type_value(text):
    """'SERVER' / 'Server Generate Codes' / '2' -> the select's value."""
    lowered = str(text or '').strip().lower()
    return CODE_SERVER if ('server' in lowered or lowered == '2') else CODE_FIX


def _date_trigger(page, label):
    """The date-and-time button belonging to a label."""
    return page.locator('xpath=//label[contains(normalize-space(.),"%s")]'
                        '/following::button[1]' % label).first


class ItemCodeBuilder(ActivityBuilder):
    PATH = 'itemcodes'
    SAVE_LABEL = 'สร้าง Item Code'
    KIND = 'Item Code'
    WRITE_MARK = 'itemcode'
    READY_SELECTOR = 'main form input[id="name_th"]'

    def _verified_write_path(self, create_url):
        return next((path for game, path in _VERIFIED_WRITE_PATHS.items()
                     if create_url == self.create_url(game)), None)

    def _write_matcher(self, page, create_url):
        write_path = self._verified_write_path(create_url)
        if write_path is None:
            return super()._write_matcher(page, create_url)

        def matches(response):
            parsed = urlsplit(response.url)
            try:
                return (response.request.method == 'POST'
                        and (parsed.scheme, parsed.netloc, parsed.path) == (
                            'https', 'admin-api-v2.combo-interactive.com', write_path)
                        and response.request.frame == page.main_frame)
            except PlaywrightError:
                return False  # No verified owning frame (e.g. service worker).

        return matches

    def _confirmation_resolver(self, page, create_url):
        # All four create dialogs were independently observed on Oct 8–9.
        if self._verified_write_path(create_url) is None:
            return None
        return lambda: aztek_form.require_confirmation_button(page, create_url, self.KIND)

    def _confirmation_activator(self, page, create_url):
        if self._verified_write_path(create_url) is None:
            return None
        return lambda button, write_pending: aztek_form.activate_confirmation_button(
            button, create_url, self.KIND, write_pending)

    async def _read_created_id(self, page, response, create_url):
        if self._verified_write_path(create_url) is None:
            return await super()._read_created_id(page, response, create_url)
        if response is not None:
            try:
                payload = await response.json()
            except (PlaywrightError, ValueError):
                payload = None
            # Preserve the existing flat numeric-id compatibility. The shared
            # Bundle reader recursively prefers bundle_id, which can identify
            # a reward's Bundle instead of this Item Code. Unknown envelopes
            # must not borrow those IDs (including Reward Set IDs).
            value = payload.get('id') if isinstance(payload, dict) else None
            if ((isinstance(value, int) and not isinstance(value, bool))
                    or (isinstance(value, str) and value.isdigit())):
                return str(value)
        # Preserve only the existing same-origin/game result-URL behavior;
        # never feed an unknown response to the recursive Bundle extractor.
        return await super()._read_created_id(page, None, create_url)

    async def _create_button(self, page):
        return await aztek_form.require_create_button(page, self.KIND)

    async def _activate_create(self, button):
        await aztek_form.activate_create_button(button, self.KIND)

    async def _open_reward_tab(self, page, index):
        form = await require_control(
            page, 'ฟอร์ม Item Code', selector='main form', tags=('form',))
        label = 'ชุดรางวัลที่ %d' % (index + 1)
        # All four games expose no tab IDs/ARIA panel relation. The first
        # direct span is the ordinal; the second is the editable reward name.
        tabs = form.locator('[role="tab"]')
        if await tabs.count():
            tablist = await require_control(
                form, label, selector='[role="tablist"]', tags=('div',), roles=('tablist',))
            tab = await require_control(
                tablist, label,
                selector='xpath=.//button[@role="tab"][span[1][normalize-space(.)="%d"]]' % (index + 1),
                tags=('button',), roles=('tab',), input_types=('button',))
            selected = await tab.get_attribute('aria-selected')
            if selected not in ('true', 'false'):
                raise AztekLocatorError('Aztek: %s อ่านสถานะแท็บไม่ได้' % label)
            if selected == 'false':
                await aztek_form.activate_verified_button(tab, label, 'tab')
            try:
                await expect(tab).to_have_attribute('aria-selected', 'true', timeout=5000)
            except (AssertionError, PlaywrightError) as exc:
                raise AztekLocatorError('Aztek: %s เปิดแท็บไม่สำเร็จ' % label) from exc
            if await tablist.locator('[role="tab"][aria-selected="true"]').count() != 1:
                raise AztekLocatorError('Aztek: %s มีแท็บ active หลายตัว' % label)
        elif index:
            raise AztekLocatorError('Aztek: %s ไม่พบแท็บรางวัล' % label)
        await require_control(
            form, '%s: ชื่อรางวัล (ไทย)' % label, element_id='rewards.%d.name_th' % index,
            tags=('input',), input_types=('text',))
        return form

    async def add_reward_set(self, page, index):
        """Add within the verified form, then wait for the intended tab's ID."""
        form = await require_control(
            page, 'ฟอร์ม Item Code', selector='main form', tags=('form',))
        label = 'เพิ่มชุดรางวัลที่ %d' % (index + 1)
        button = await require_control(
            form, label,
            selector='xpath=.//button[normalize-space(.)="+ เพิ่มของรางวัล"]',
            tags=('button',), input_types=('button',))
        await aztek_form.activate_verified_button(button, label)
        # Adding lazily mounts the new tab list and active reward controls.
        await require_control(
            form, label, element_id='rewards.%d.name_th' % index,
            tags=('input',), input_types=('text',))
        await self._open_reward_tab(page, index)
        return True

    async def _fill_header(self, page, spec, missing):
        # Descriptions stay on the page defaults. Names, slug, use limit,
        # availability window and the optional code-wide count belong here.
        # Live PC/M TH/SEA forms have no form ID, but exactly one main form.
        form = await require_control(
            page, 'ฟอร์ม Item Code', selector='main form', tags=('form',))
        for field, value, label, input_type in (
            ('name_th', spec.get('name_th'), 'ชื่อ Item Code (ไทย)', 'text'),
            ('name_en', spec.get('name_en'), 'ชื่อ Item Code (อังกฤษ)', 'text'),
            ('slug', spec.get('slug'), 'Slug', 'text'),
            ('per_player_limit', spec.get('uses_per_user') or '1',
             'จำนวนการใช้งานต่อ 1 User', 'number'),
        ):
            text = str(value or '')
            ok = await aztek_form.fill_by_id(
                form, field, text, label,
                input_types=(input_type,))
            if not ok or not text:
                missing.append(label)
        # Always ALL: an Item Code is a code anyone holding it may redeem, and
        # WINNER is the Event's idea, not this one's.
        await aztek_form.select_by_id(form, 'redeem_type', 'ALL', 'ประเภท Item Code')
        for key, element_id, label in (('start_time', 'start_at', 'เวลาเริ่มใช้งาน'),
                                       ('end_time', 'end_at', 'เวลาสิ้นสุด')):
            if not await aztek_form.set_datetime_by_id(
                    page, form, element_id, spec.get(key), self.log, label):
                missing.append(label)
        limited = bool(spec.get('limited'))
        await aztek_form.set_switch_by_id(form, 'is_limited', limited, 'จำกัดจำนวน')
        if limited:
            for field, label in (('quantity', 'จำนวนครั้งที่สามารถใช้งานได้'),
                                 ('remaining', 'จำนวนคงเหลือ')):
                text = str(spec.get(field) or '')
                ok = await aztek_form.fill_by_id(
                    form, field, text, label, input_types=('number',))
                if not ok or not text:
                    missing.append(label)

    async def _fill_reward(self, page, index, reward, missing):
        where = 'ชุดรางวัลที่ %d' % (index + 1)
        self.log('  %s: %s' % (where, reward.get('name_th') or '-'), 'STEP')
        form = await self._open_reward_tab(page, index)
        for field, value, label, input_type in (
            ('name_th', reward.get('name_th'), 'ชื่อรางวัล (ไทย)', 'text'),
            ('name_en', reward.get('name_en'), 'ชื่อรางวัล (อังกฤษ)', 'text'),
            ('per_player_limit', reward.get('uses_per_user') or '1',
             'จำนวนการใช้งานต่อ 1 User', 'number'),
        ):
            text = str(value or '')
            ok = await aztek_form.fill_by_id(
                form, 'rewards.%d.%s' % (index, field), text,
                '%s: %s' % (where, label), input_types=(input_type,))
            if not ok or not text:
                missing.append('%s: %s' % (where, label))

        limited = bool(reward.get('limited'))
        await aztek_form.set_switch_by_id(
            form, 'rewards.%d.is_limited' % index, limited,
            '%s: จำกัดจำนวน Code' % where)
        if limited:
            for field, label in (('quantity', 'จำนวนครั้ง'), ('remaining', 'คงเหลือ')):
                text = str(reward.get(field) or '')
                ok = await aztek_form.fill_by_id(
                    form, 'rewards.%d.%s' % (index, field), text,
                    '%s: %s' % (where, label), input_types=('number',))
                if not ok or not text:
                    missing.append('%s: %s' % (where, label))

        wanted = code_type_value(reward.get('code_type'))
        await aztek_form.select_by_id(
            form, 'rewards.%d.is_generate_code' % index, wanted,
            '%s: ประเภทของ Code' % where)
        if wanted == CODE_SERVER:
            ok = await aztek_form.fill_by_id(
                form, 'rewards.%d.prefix' % index, reward.get('prefix') or '',
                '%s: prefix' % where)
            if not ok:
                missing.append('%s: prefix' % where)
            amount = str(reward.get('num_codes') or '').strip()
            ok = await aztek_form.fill_by_id(
                form, 'rewards.%d.amount' % index, amount,
                '%s: จำนวนโค้ดที่ต้องการ' % where, input_types=('number',))
            if not amount or not ok:
                missing.append('%s: จำนวนโค้ดที่ต้องการ' % where)
        else:
            codes = str(reward.get('code_list') or '').strip()
            ok = await aztek_form.fill_by_id(
                form, 'rewards.%d.serial' % index, codes,
                '%s: รายการ Code' % where, tags=('textarea',), input_types=())
            if not codes or not ok:
                missing.append('%s: รายการ Code' % where)

        bundle_id = str(reward.get('bundle_id') or '').strip()
        if not bundle_id:
            missing.append('%s: Bundle' % where)
        elif not await aztek_form.pick_reward_bundle(
                page, form, index, bundle_id, '%s: Bundle %s' % (where, bundle_id), self.log):
            missing.append('%s: Bundle %s' % (where, bundle_id))

    async def fill_form(self, page, spec):
        """Fill the whole page and report which required fields are still empty."""
        missing = []
        await self._fill_header(page, spec, missing)
        rewards = spec.get('rewards') or []
        if not rewards:
            missing.append('ชุดรางวัล')
        for index, reward in enumerate(rewards):
            if self._cancel:
                break
            # The first set is already on the page when it loads.
            if index and not await self.add_reward_set(page, index):
                missing.append('ชุดรางวัลที่ %d' % (index + 1))
                continue
            await self._fill_reward(page, index, reward, missing)
        return missing
