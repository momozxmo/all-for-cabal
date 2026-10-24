# -*- coding: utf-8 -*-
"""Fill the Aztek v2 "สร้าง Event" form.

An Event is the same shape as an Item Code minus the codes: reward sets that
each hand out one bundle, over two time windows — when the activity runs and
when the prize can be claimed.

The bundle ids are already in the monthly plan, so nothing here searches for
items; the operator brings the numbers with them.
"""
from urllib.parse import urlsplit
from uuid import UUID
from playwright.async_api import Error as PlaywrightError, expect

from web import aztek_form
from web.activity_runner import ActivityBuilder
from web.aztek_locator import AztekLocatorError, require_control

#: label, spec key and verified Event trigger ID (all PC/M TH/SEA forms).
DATE_FIELDS = (
    ('วันเริ่มกิจกรรม', 'start_event', 'start_at'),
    ('วันสิ้นสุดกิจกรรม', 'end_event', 'end_at'),
    ('วันเริ่มรับรางวัล', 'start_claim', 'redeem_start_at'),
    ('วันสิ้นสุดการรับรางวัล', 'end_claim', 'redeem_end_at'),
)

# Each POST was independently captured on its owning form with all HTTP
# aborted, Oct 16. These are not paths inferred between games.
_VERIFIED_WRITE_PATHS = {
    'CabalM TH': '/cabalm/event/events',
    'CabalM SEA': '/cabalmsea/event/events',
    'CabalPC TH': '/cabalpc/event/events',
    'CabalPC SEA': '/cabalpcsea/event/events',
}


class EventBuilder(ActivityBuilder):
    PATH = 'events'
    SAVE_LABEL = 'สร้าง Event'
    KIND = 'Event'
    WRITE_MARK = 'event'
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
                return False

        return matches

    def _confirmation_resolver(self, page, create_url):
        # Dialog and write endpoint were independently read in all four games.
        if self._verified_write_path(create_url) is None:
            return None
        return lambda: aztek_form.require_confirmation_button(page, create_url, self.KIND)

    def _confirmation_activator(self, page, create_url):
        if self._verified_write_path(create_url) is None:
            return None
        return lambda button, write_pending: aztek_form.activate_confirmation_button(
            button, create_url, self.KIND, write_pending)

    async def _read_created_id(self, page, response, create_url):
        if self._verified_write_path(create_url) is not None and response is not None:
            # M TH envelope observed Oct17; independent M SEA/PC TH/PC SEA
            # captures Oct21 retained data.data.id UUID and matching slug.
            # Accept only that exact shape/own request identity, not nested
            # Reward/Bundle IDs or an inferred result URL.
            try:
                payload = await response.json()
                if isinstance(payload, dict) and payload.get('success') is False:
                    raise RuntimeError('Aztek ตอบ success=false — ยังยืนยันผลสร้าง Event ไม่ได้ '
                                       'โปรดตรวจบนเว็บก่อนลองใหม่')
                if not isinstance(payload, dict) or payload.get('success') is not True:
                    return None
                request = response.request.post_data_json
                envelope = payload.get('data')
                record = envelope.get('data') if isinstance(envelope, dict) else None
                if not isinstance(record, dict) or not isinstance(request, dict):
                    return None
                slug = request.get('slug')
                if not isinstance(slug, str) or not slug or record.get('slug') != slug:
                    return None
                value = record.get('id')
                if isinstance(value, str):
                    parsed = UUID(value)
                    if parsed.int and str(parsed) == value.lower():
                        return value
            except (PlaywrightError, ValueError):
                pass
            return None
        if self._verified_write_path(create_url) is not None:
            # No verified response: never borrow numeric Bundle IDs or assume
            # numeric result URLs for any audited game. Keep unknown-ID warning.
            return None
        return await super()._read_created_id(page, response, create_url)

    async def _create_button(self, page):
        return await aztek_form.require_create_button(page, self.KIND)

    async def _activate_create(self, button):
        await aztek_form.activate_create_button(button, self.KIND)

    async def _reward_section(self, page):
        form = await require_control(
            page, 'ฟอร์ม Event', selector='main form', tags=('form',))
        # All four Event forms: this no-ID section owns both add/tabs and
        # indexed controls. Other sections have unrelated language tablists.
        return await require_control(
            form, 'ส่วนของรางวัล Event',
            selector='section:has(> header > div > h2:text-is("ของรางวัล"))',
            tags=('section',))

    async def _open_reward_tab(self, page, index):
        section = await self._reward_section(page)
        label = 'ชุดรางวัลที่ %d' % (index + 1)
        # A second set always has tabs, but its fields may mount first.
        # Keep the verified one-set/no-tabs exception only for index zero.
        if index or await section.locator('[role="tab"]').count():
            tablist = await require_control(
                section, label, selector='[role="tablist"]',
                tags=('div',), roles=('tablist',))
            # Independently observed ordinal/name direct SPANs, no tab ID
            # or ARIA panel relation. Names may change as the user fills.
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
        await require_control(
            section, '%s: ชื่อรางวัล (ไทย)' % label,
            element_id='rewards.%d.name_th' % index,
            tags=('input',), input_types=('text',))
        return section

    async def add_reward_set(self, page, index):
        section = await self._reward_section(page)
        label = 'เพิ่มชุดรางวัลที่ %d' % (index + 1)
        button = await require_control(
            section, label, selector='button:text-is("+ เพิ่มของรางวัล")',
            tags=('button',), roles=(None, 'button'), input_types=('button',))
        await aztek_form.activate_verified_button(button, label)
        # Adding selects the newly mounted set; do not borrow the prior set.
        await require_control(
            section, 'ชุดรางวัลที่ %d: ชื่อรางวัล (ไทย)' % (index + 1),
            element_id='rewards.%d.name_th' % index,
            tags=('input',), input_types=('text',))
        await self._open_reward_tab(page, index)
        return True

    async def _fill_header(self, page, spec, missing):
        # Independently observed on all four Event create forms: no form ID,
        # one main form, and typed inputs with these developer-maintained IDs.
        form = await require_control(
            page, 'ฟอร์ม Event', selector='main form', tags=('form',))
        # The page arrives with a generated slug (event-<timestamp>), so this
        # is an overwrite rather than a fill — an empty value would leave that
        # placeholder behind on the live site.
        for field, label in (('slug', 'Slug'), ('name_th', 'ชื่อ Event (ไทย)'),
                             ('name_en', 'ชื่อ Event (อังกฤษ)')):
            text = str(spec.get(field) or '')
            ok = await aztek_form.fill_by_id(form, field, text, label)
            if not ok or not text:
                missing.append(label)
        # All four Event forms lack IDs on this trigger/native sibling.
        # The verified section + direct label owner disambiguates Reward sets.
        await aztek_form.select_without_id(
            form, 'section:has(> header > div > h2:text-is("การรับรางวัล")) '
            '> div > div:has(> label:text-is("ผู้มีสิทธิ์รับรางวัล")) > button[role="combobox"]',
            spec.get('type') or 'WINNER', 'ผู้มีสิทธิ์รับรางวัล')
        for field, value, label in (
            ('per_player_limit', spec.get('uses_per_user') or '1',
             'จำกัดต่อผู้เล่น'),
            ('quantity', spec.get('quantity') or '0', 'จำนวนรางวัลทั้งหมด'),
            ('remaining', spec.get('remaining') or '0', 'คงเหลือ'),
        ):
            if not await aztek_form.fill_by_id(
                    form, field, value, label, input_types=('number',)):
                missing.append(label)
        for label, key, element_id in DATE_FIELDS:
            if not await aztek_form.set_datetime_by_id(
                    page, form, element_id, spec.get(key), self.log, label):
                missing.append(label)

    async def _fill_reward(self, page, index, reward, missing):
        where = 'ชุดรางวัลที่ %d' % (index + 1)
        section = await self._open_reward_tab(page, index)
        self.log('  %s: %s (bundle %s)'
                 % (where, reward.get('name_th') or '-',
                    reward.get('bundle_id') or '-'), 'STEP')
        for field, label in (('name_th', 'ชื่อรางวัล (ไทย)'),
                             ('name_en', 'ชื่อรางวัล (อังกฤษ)')):
            text = str(reward.get(field) or '')
            ok = await aztek_form.fill_by_id(
                section, 'rewards.%d.%s' % (index, field), text,
                '%s: %s' % (where, label))
            if not ok or not text:
                missing.append('%s: %s' % (where, label))
        for field in ('desc_th', 'desc_en'):
            if str(reward.get(field) or ''):
                label = '%s: %s' % (where, field)
                if not await aztek_form.fill_by_id(
                        section, 'rewards.%d.%s' % (index, field),
                        reward.get(field), label, tags=('textarea',),
                        input_types=('textarea',)):
                    missing.append(label)
        limited = bool(reward.get('limited'))
        await aztek_form.set_switch_by_id(
            section, 'rewards.%d.is_limited' % index,
            limited, '%s: จำกัดจำนวน' % where)
        if not await aztek_form.fill_by_id(
                section, 'rewards.%d.per_player_limit' % index,
                reward.get('uses_per_user') or '1', '%s: จำกัดต่อผู้เล่น' % where,
                input_types=('number',)):
            missing.append('%s: จำกัดต่อผู้เล่น' % where)
        if limited:
            for field, label in (('quantity', 'จำนวนทั้งหมด'), ('remaining', 'คงเหลือ')):
                value = reward.get(field)
                text = '' if value is None else str(value)
                ok = await aztek_form.fill_by_id(
                    section, 'rewards.%d.%s' % (index, field), text,
                    '%s: %s' % (where, label), input_types=('number',))
                if not ok or not text:
                    missing.append('%s: %s' % (where, label))
        bundle_id = str(reward.get('bundle_id') or '').strip()
        if not bundle_id:
            missing.append('%s: Bundle' % where)
        else:
            form = await require_control(
                page, 'ฟอร์ม Event', selector='main form', tags=('form',))
            if not await aztek_form.pick_reward_bundle(
                    page, form, index, bundle_id, '%s: Bundle %s' % (where, bundle_id),
                    self.log, event_reward=True):
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
            # Unlike Item Code, an Event page loads with no reward set at all.
            if not await self.add_reward_set(page, index):
                missing.append('ชุดรางวัลที่ %d' % (index + 1))
                continue
            await self._fill_reward(page, index, reward, missing)
        return missing
