# -*- coding: utf-8 -*-
"""Read and fill the Aztek v2 Product form.

This first slice is deliberately read-only: it harvests the Product page's
current Currency and Category options and never clicks the create button.
"""
from __future__ import annotations

import json
import re

from playwright.async_api import async_playwright

import aztek_core as core
from web import aztek_form, browser_launch
from web.activity_runner import ActivityBuilder
from web.search_runner import to_web_url


OPTION_KINDS = frozenset({'currencies', 'categories'})
OPTION_LABELS = {
    'categories': 'Category',
    'currencies': 'Currency',
}


def product_create_url(game):
    return to_web_url(core.build_url(game, 'shop/products/create'))


def _clean_option_rows(rows):
    """Normalize live ``<option>`` rows without inventing a catalog."""
    output = []
    seen = set()
    for row in rows or ():
        option_id = str((row or {}).get('value') or '').strip()
        text = str((row or {}).get('text') or '').strip()
        if not option_id or not text:
            continue
        slug = ''
        label = text
        if ' - ' in text:
            possible, remainder = text.split(' - ', 1)
            if re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', possible.strip()):
                slug = possible.strip()
                label = remainder.strip()
        key = (option_id, slug, label)
        if key in seen:
            continue
        seen.add(key)
        output.append({'id': option_id, 'slug': slug, 'label': label})
    return output


def _require_product_options(options, wanted):
    missing = [OPTION_LABELS[kind] for kind in wanted
               if not options.get(kind)]
    if missing:
        raise RuntimeError(
            'ไม่พบตัวเลือก %s — หน้า Product อาจยังโหลดไม่ครบ'
            % ', '.join(missing))
    return options


async def _read_options(select):
    rows = await select.locator('option').evaluate_all(
        """nodes => nodes.map(node => ({
          value: node.value || '',
          text: (node.textContent || '').trim()
        }))""")
    return _clean_option_rows(rows)


def _category_trigger(page):
    return page.locator(
        'button[data-slot="popover-trigger"]').filter(
            has_text='เลือก Category').first


async def _ready_category_trigger(page):
    """Wait for the async Category catalog before falling back."""
    trigger = _category_trigger(page)
    try:
        await trigger.wait_for(state='visible', timeout=8000)
    except Exception:
        pass
    return trigger


def _currency_trigger(original_price):
    return original_price.locator(
        'xpath=ancestor::*[.//button[@data-slot="popover-trigger"]][1]'
    ).locator('button[data-slot="popover-trigger"]').first


async def _read_popover_options(page, trigger):
    """Read Radix/cmdk options and keep their server IDs."""
    await trigger.click(timeout=8000)
    options = page.locator('[role="dialog"] [role="option"]')
    await options.first.wait_for(state='attached', timeout=8000)
    rows = await options.evaluate_all(
        """nodes => nodes.map(node => {
          const raw = node.getAttribute('data-value') || '';
          const parts = raw.split('\\u0000');
          return {
            value: parts.length > 1 ? parts[parts.length - 1] : '',
            text: (node.textContent || '').trim()
          };
        })""")
    await page.keyboard.press('Escape')
    return _clean_option_rows(rows)


async def _select_popover_option(page, trigger, option_id):
    """Select one live Radix/cmdk option by its fetched server ID."""
    try:
        await trigger.click(timeout=8000)
        selector = (
            '[role="dialog"] [role="option"][data-value$=%s]'
            % json.dumps(str(option_id)))
        option = page.locator(selector).first
        await option.wait_for(state='attached', timeout=8000)
        await option.click(timeout=8000)
        return True
    except Exception:
        try:
            await page.keyboard.press('Escape')
        except Exception:
            pass
        return False


async def _category_select(page):
    selectors = (
        'xpath=//label[contains(normalize-space(.),"หมวดหมู่")]'
        '/following::select[1]',
        'xpath=//label[contains(normalize-space(.),"Category")]'
        '/following::select[1]',
    )
    for selector in selectors:
        select = page.locator(selector).first
        if await select.count():
            return select
    return None


async def _currency_select(page):
    price = page.locator(
        'input[name="prices.0.original_price"]').first
    if not await price.count():
        add = page.locator(
            'button:has-text("เพิ่มสกุลเงิน"),'
            'button:has-text("เพิ่มราคา"),'
            'button:has-text("Add Currency")').first
        if await add.count():
            await add.click()
            await price.wait_for(state='attached', timeout=8000)
    if not await price.count():
        return None
    wrapper = price.locator(
        'xpath=ancestor::*[.//select][1]').first
    select = wrapper.locator('select').first
    return select if await select.count() else None


async def _harvest_product_options(page, wanted):
    options = {}
    if 'categories' in wanted:
        trigger = await _ready_category_trigger(page)
        if await trigger.count():
            options['categories'] = await _read_popover_options(
                page, trigger)
        else:
            select = await _category_select(page)
            options['categories'] = (
                await _read_options(select) if select is not None else [])
    if 'currencies' in wanted:
        select = await _currency_select(page)
        original = page.locator(
            'input[name="prices.0.original_price"]').first
        trigger = _currency_trigger(original)
        if await original.count() and await trigger.count():
            options['currencies'] = await _read_popover_options(
                page, trigger)
        else:
            options['currencies'] = (
                await _read_options(select) if select is not None else [])
    return options


async def fetch_options(game, storage_state, kinds):
    """Read requested live Product options and leave without submitting."""
    wanted = set(kinds or ()) & OPTION_KINDS
    url = product_create_url(game)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            **browser_launch.launch_kwargs(False))
        context = await browser.new_context(
            **browser_launch.context_kwargs(
                False, storage_state=storage_state))
        page = await context.new_page()
        try:
            await page.goto(
                url, wait_until='domcontentloaded', timeout=30000)
            await page.locator('input[name="th_name"]').wait_for(
                state='visible', timeout=20000)
            await page.wait_for_timeout(2500)
            if any(part in page.url.lower()
                   for part in ('/login', '/signin')):
                raise RuntimeError('Aztek session expired')
            return _require_product_options(
                await _harvest_product_options(page, wanted), wanted)
        finally:
            await context.close()
            await browser.close()


def _date_trigger(page, label):
    """The Product date-time button immediately following a visible label."""
    return page.locator(
        'xpath=//label[contains(normalize-space(.),"%s")]'
        '/following::button[1]' % label).first


class ProductBuilder(ActivityBuilder):
    """Fill Aztek v2's Product form without inventing live option values."""

    PATH = 'products'
    SAVE_LABEL = 'สร้าง Product'
    KIND = 'Product'
    WRITE_MARK = 'product'
    READY_SELECTOR = 'input[name="th_name"]'

    def create_url(self, game):
        return product_create_url(game)

    async def _fill_general(self, page, spec, missing):
        for field, selector, label in (
            ('name_th', 'input[name="th_name"]', 'ชื่อ Product (ไทย)'),
            ('name_en', 'input[name="en_name"]', 'ชื่อ Product (อังกฤษ)'),
        ):
            value = str(spec.get(field) or '').strip()
            ok = await aztek_form.fill(
                page, selector, value, self.log, label)
            if not value or not ok:
                missing.append(label)
        category_id = str(spec.get('category_id') or '').strip()
        if not category_id:
            missing.append('หมวดหมู่')
        else:
            trigger = await _ready_category_trigger(page)
            if await trigger.count():
                selected = await _select_popover_option(
                    page, trigger, category_id)
            else:
                selected = await aztek_form.select_after_label(
                    page, 'หมวดหมู่', category_id, self.log)
            if not selected:
                missing.append('หมวดหมู่')

    async def _fill_rich_text(self, page, language, value):
        """Fill the visible TinyMCE after selecting its language tab."""
        if not str(value or ''):
            return True
        label = 'ไทย' if language == 'th' else 'English'
        try:
            tab = page.get_by_role('tab', name=label, exact=True).first
            if await tab.count():
                await tab.click(timeout=6000)
                await page.wait_for_timeout(500)
            frame = page.locator(
                'iframe.tox-edit-area__iframe:visible').first
            await frame.wait_for(state='visible', timeout=6000)
            await frame.content_frame.locator('body').fill(str(value))
            return True
        except Exception as exc:
            self.log('กรอกรายละเอียด %s ไม่สำเร็จ: %s'
                     % (label, exc), 'WARNING')
            return False

    async def _fill_details(self, page, spec):
        for language, field in (
            ('th', 'details_th'), ('en', 'details_en'),
        ):
            value = spec.get(field)
            if str(value or ''):
                await self._fill_rich_text(page, language, value)

    async def _fill_images(self, page, spec, missing):
        images = spec.get('images') or {}
        for index, slot in enumerate((
            'thumbnail_th', 'banner_th', 'thumbnail_en', 'banner_en',
        )):
            image = images.get(slot)
            if not image:
                continue
            try:
                await page.locator('input[type="file"]').nth(
                    index).set_input_files({
                        'name': image['name'],
                        'mimeType': image['content_type'],
                        'buffer': image['bytes'],
                    })
            except Exception as exc:
                missing.append('รูป %s' % slot)
                self.log('ใส่รูป %s ไม่สำเร็จ: %s' % (slot, exc), 'WARNING')

    async def _add_price_row(self, page, index):
        original = page.locator(
            'input[name="prices.%d.original_price"]' % index).first
        if await original.count():
            return original
        add = page.locator(
            'button:has-text("เพิ่มสกุลเงิน"),'
            'button:has-text("เพิ่มราคา"),'
            'button:has-text("Add Currency")').first
        try:
            await add.click(timeout=8000)
            await original.wait_for(state='attached', timeout=8000)
            await page.wait_for_timeout(500)
            return original
        except Exception as exc:
            self.log('เพิ่มแถวสกุลเงินที่ %d ไม่สำเร็จ: %s'
                     % (index + 1, exc), 'WARNING')
            return None

    async def _fill_prices(self, page, spec, missing):
        prices = spec.get('prices') or []
        if not prices:
            missing.append('สกุลเงิน')
            return
        for index, price in enumerate(prices):
            currency_id = str(price.get('currency_id') or '').strip()
            where = 'สกุลเงินที่ %d' % (index + 1)
            original = await self._add_price_row(page, index)
            if original is None:
                missing.append(where)
                continue
            if not currency_id:
                missing.append(where)
            else:
                trigger = _currency_trigger(original)
                if await trigger.count():
                    selected = await _select_popover_option(
                        page, trigger, currency_id)
                else:
                    select = original.locator(
                        'xpath=ancestor::*[.//select][1]').first.locator(
                            'select').first
                    try:
                        await select.select_option(value=currency_id)
                        selected = True
                    except Exception as exc:
                        selected = False
                        self.log('เลือก %s ไม่สำเร็จ: %s'
                                 % (where, exc), 'WARNING')
                if not selected:
                    missing.append(where)
            for field, label in (
                ('original_price', 'ราคาปกติ'),
                ('price', 'ราคาขาย'),
            ):
                value = price.get(field)
                ok = await aztek_form.fill(
                    page, 'input[name="prices.%d.%s"]' % (index, field),
                    value, self.log, '%s %s' % (where, label))
                if value in (None, '') or not ok:
                    missing.append('%s: %s' % (where, label))

    async def _fill_display(self, page, spec, missing):
        for label, field, default in (
            ('เปิดใช้งาน', 'is_enabled', False),
            ('โหมดทดสอบ', 'is_test_mode', True),
            ('ซ่อนสินค้า', 'is_hidden', False),
        ):
            await aztek_form.set_switch(
                page, label, bool(spec.get(field, default)), self.log)
        await aztek_form.fill(
            page, 'input[name="position"]',
            spec.get('position', '0'), self.log, 'ตำแหน่ง')
        for label, field, missing_label in (
            ('เวลาเริ่มขาย (GMT+7)', 'start_at', 'วันเริ่มขาย'),
            ('เวลาหยุดขาย (GMT+7)', 'end_at', 'วันสิ้นสุด'),
        ):
            value = str(spec.get(field) or '').strip()
            if not value:
                missing.append(missing_label)
                continue
            if not await aztek_form.set_datetime(
                    page, _date_trigger(page, label), value,
                    self.log, label=label):
                missing.append(missing_label)

    async def _fill_limit(self, page, spec, missing):
        limit_type = str(spec.get('limit_type') or '').strip()
        if not limit_type:
            missing.append('ประเภทการจำกัด')
            return
        aztek_limit_type = (
            'NONE' if limit_type == 'UNLIMITED' else limit_type)
        if not await aztek_form.select_after_label(
                page, 'รูปแบบการจำกัดการซื้อ', aztek_limit_type, self.log):
            missing.append('ประเภทการจำกัด')
        if limit_type == 'UNLIMITED':
            return
        quantity = str(spec.get('limit_quantity') or '').strip()
        ok = await aztek_form.fill(
            page, 'input[name="limit_per"]', quantity,
            self.log, 'จำนวนที่ซื้อได้')
        if not quantity or not ok:
            missing.append('จำนวนที่ซื้อได้')
        interval = str(
            spec.get('limit_reset_interval_days') or '').strip()
        if interval:
            await aztek_form.fill(
                page, 'input[name="limit_reset_interval_days"]',
                interval, self.log, 'รีเซ็ตทุกกี่วัน')
        reset_at = str(spec.get('limit_reset_at') or '').strip()
        if reset_at and not await aztek_form.set_datetime(
                page, _date_trigger(
                    page,
                    'วันล่าสุดที่ทำการรีเซ็ทรอบการขาย (GMT+7)'),
                reset_at, self.log,
                label='วันล่าสุดที่ทำการรีเซ็ทรอบการขาย (GMT+7)'):
            missing.append('รีเซ็ตล่าสุด')

    async def _fill_tags(self, page, spec, missing):
        # Kept as a compatibility no-op for old queue payloads.  The current
        # Aztek Product form has no Tag controls, so tags must never block a run.
        return None

    async def _fill_bundles(self, page, spec, missing):
        raw_ids = spec.get('bundle_ids') or [spec.get('bundle_id')]
        bundle_ids = [str(value or '').strip() for value in raw_ids
                      if str(value or '').strip()]
        if not bundle_ids:
            missing.append('Bundle')
            return
        heading = page.get_by_role('heading', name='Bundle', exact=True)
        section = page.locator('section').filter(has=heading).first
        for bundle_id in bundle_ids:
            if not await aztek_form.pick_bundle(
                    page, section, bundle_id, self.log):
                missing.append('Bundle %s' % bundle_id)
                return
            text = await section.inner_text()
            if not re.search(r'#%s\b' % re.escape(bundle_id), text):
                missing.append('Bundle %s' % bundle_id)
                return

        primary_id = str(
            spec.get('primary_bundle_id') or bundle_ids[0]).strip()
        if primary_id not in bundle_ids:
            missing.append('Primary Bundle %s' % primary_id)
            return
        primary_text = section.get_by_text(
            '#%s' % primary_id, exact=True).first
        primary_card = primary_text.locator(
            'xpath=ancestor::*[.//button[@role="checkbox"]][1]').first
        primary = primary_card.locator('button[role="checkbox"]').first
        try:
            if await primary.count() == 0:
                raise RuntimeError('Primary control not found')
            if await primary.get_attribute('aria-checked') != 'true':
                await primary.click(timeout=6000)
            if await primary.get_attribute('aria-checked') != 'true':
                raise RuntimeError('Primary control did not stay checked')
        except Exception as exc:
            self.log('เลือก Primary Bundle %s ไม่สำเร็จ: %s' % (
                primary_id, exc), 'WARNING')
            missing.append('Primary Bundle %s' % primary_id)
            return

        text = await section.inner_text()
        selected_ids = re.findall(r'#(\d+)\b', text)
        expected_count = len(bundle_ids)
        count_ok = re.search(
            r'\b%s\s*/\s*20\s*Bundles\b' % expected_count,
            text, re.I)
        if selected_ids != bundle_ids or not count_ok:
            missing.append('Bundle list/count')

    async def _fill_bundle(self, page, spec, missing):
        await self._fill_bundles(page, spec, missing)

    async def fill_form(self, page, spec):
        missing = []
        await self._fill_general(page, spec, missing)
        await self._fill_details(page, spec)
        await self._fill_images(page, spec, missing)
        await self._fill_prices(page, spec, missing)
        await self._fill_display(page, spec, missing)
        await self._fill_limit(page, spec, missing)
        await self._fill_bundles(page, spec, missing)
        return missing
