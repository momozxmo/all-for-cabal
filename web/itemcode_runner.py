# -*- coding: utf-8 -*-
"""Fill the Aztek v2 "สร้าง Item Code" form.

One Item Code holds one or more reward sets. Each set carries its own codes —
either a list the operator supplies (Fix) or a count for the server to generate
— and exactly one bundle: v2 replaces a chosen bundle rather than adding to it,
so a plan that names several bundles for one prize needs several reward sets.

The desktop tool drives the v1 page, whose fields are laid out differently;
this is the v2 form and keeps its own selectors.
"""
from web import aztek_form
from web.activity_runner import ActivityBuilder

#: value of the "ประเภทของ Code" select
CODE_FIX, CODE_SERVER = '1', '2'


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

    async def _fill_header(self, page, spec, missing):
        # Descriptions stay on the page defaults. Names, slug, use limit,
        # availability window and the optional code-wide count belong here.
        for field, value, label in (
            ('name_th', spec.get('name_th'), 'ชื่อ Item Code (ไทย)'),
            ('name_en', spec.get('name_en'), 'ชื่อ Item Code (อังกฤษ)'),
            ('slug', spec.get('slug'), 'Slug'),
        ):
            text = str(value or '')
            ok = await aztek_form.fill(page, 'input[name="%s"]' % field, text,
                                       self.log, label)
            if not ok or not text:
                missing.append(label)
        # Always ALL: an Item Code is a code anyone holding it may redeem, and
        # WINNER is the Event's idea, not this one's.
        await aztek_form.select_by_options(page, 'ALL', ('WINNER', 'ALL'), self.log)
        await aztek_form.fill(page, 'input[name="per_player_limit"]',
                              spec.get('uses_per_user') or '1', self.log,
                              'จำนวนการใช้งานต่อ 1 User')
        for key, label in (('start_time', 'เวลาเริ่มใช้งาน'),
                           ('end_time', 'เวลาสิ้นสุด')):
            if not await aztek_form.set_datetime(
                    page, _date_trigger(page, label), spec.get(key),
                    self.log, label):
                missing.append(label)
        limited = bool(spec.get('limited'))
        await aztek_form.set_switch(page, 'จำกัดจำนวน', limited, self.log)
        if limited:
            await aztek_form.fill(
                page, 'input[name="quantity"]', spec.get('quantity') or '',
                self.log, 'จำนวนครั้งที่สามารถใช้งานได้')
            await aztek_form.fill(
                page, 'input[name="remaining"]', spec.get('remaining') or '',
                self.log, 'จำนวนคงเหลือ')

    async def _fill_reward(self, page, index, reward, missing):
        where = 'ชุดรางวัลที่ %d' % (index + 1)
        self.log('  %s: %s' % (where, reward.get('name_th') or '-'), 'STEP')
        for field, value, label, required in (
            ('name_th', reward.get('name_th'), 'ชื่อรางวัล (ไทย)', True),
            ('name_en', reward.get('name_en'), 'ชื่อรางวัล (อังกฤษ)', True),
        ):
            text = str(value or '')
            ok = await aztek_form.fill(
                page, 'input[name="rewards.%d.%s"]' % (index, field), text,
                self.log, label)
            if required and (not ok or not text):
                missing.append('%s: %s' % (where, label))
        await aztek_form.fill(
            page, 'input[name="rewards.%d.per_player_limit"]' % index,
            reward.get('uses_per_user') or '1', self.log,
            'จำนวนการใช้งานต่อ 1 User')

        limited = bool(reward.get('limited'))
        # Reward sets are tabs: only the open one is on the page, so its switch
        # and its code-type select are always the first of their kind.
        await aztek_form.set_switch(page, 'จำกัดจำนวน Code', limited, self.log)
        if limited:
            await aztek_form.fill(
                page, 'input[name="rewards.%d.quantity"]' % index,
                reward.get('quantity') or '', self.log, 'จำนวนครั้ง')
            await aztek_form.fill(
                page, 'input[name="rewards.%d.remaining"]' % index,
                reward.get('remaining') or '', self.log, 'คงเหลือ')

        wanted = code_type_value(reward.get('code_type'))
        await aztek_form.select_by_options(page, wanted, ('Fix Codes',), self.log)
        await page.wait_for_timeout(1200)
        if wanted == CODE_SERVER:
            await aztek_form.fill(
                page, 'input[name="rewards.%d.prefix"]' % index,
                reward.get('prefix') or '', self.log, 'prefix')
            amount = str(reward.get('num_codes') or '').strip()
            ok = await aztek_form.fill(
                page, 'input[name="rewards.%d.amount"]' % index, amount,
                self.log, 'จำนวนโค้ดที่ต้องการ')
            if not amount or not ok:
                missing.append('%s: จำนวนโค้ดที่ต้องการ' % where)
        else:
            codes = str(reward.get('code_list') or '').strip()
            ok = await aztek_form.fill(
                page, 'textarea[name="rewards.%d.serial"]' % index, codes,
                self.log, 'รายการ Code')
            if not codes or not ok:
                missing.append('%s: รายการ Code' % where)

        bundle_id = str(reward.get('bundle_id') or '').strip()
        if not bundle_id:
            missing.append('%s: Bundle' % where)
        elif not await aztek_form.pick_bundle(
                page, aztek_form.reward_card(page, index), bundle_id, self.log):
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
