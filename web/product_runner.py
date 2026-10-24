# -*- coding: utf-8 -*-
"""Read, fill and submit Aztek v2 Product forms through verified controls."""
from __future__ import annotations

import json
import re
from email.parser import BytesParser
from email.policy import default
from urllib.parse import urlsplit
from uuid import UUID

from playwright.async_api import Error as PlaywrightError, async_playwright, expect

import aztek_core as core
from web import aztek_form, browser_launch
from web.activity_runner import ActivityBuilder
from web.aztek_locator import AztekLocatorError, require_control
from web.search_runner import to_web_url


OPTION_KINDS = frozenset({'currencies', 'categories'})
OPTION_LABELS = {
    'categories': 'Category',
    'currencies': 'Currency',
}

# Independently captured on each owning Product form with all HTTP aborted,
# Oct20. This proves the request route, not a successful response schema.
_VERIFIED_WRITE_PATHS = {
    'CabalM TH': '/cabalm/shop/products',
    'CabalM SEA': '/cabalmsea/shop/products',
    'CabalPC TH': '/cabalpc/shop/products',
    'CabalPC SEA': '/cabalpcsea/shop/products',
}


async def _submitted_product_name(request):
    """Read one scalar th[name] from the observed multipart write, not the DOM."""
    try:
        content_type = await request.header_value('content-type') or ''
        raw = request.post_data_buffer
        if not isinstance(raw, bytes):
            return None
        message = BytesParser(policy=default).parsebytes(
            b'Content-Type: ' + content_type.encode('ascii') + b'\r\n\r\n' + raw)
        if message.get_content_type() != 'multipart/form-data' or not message.is_multipart():
            return None
        if any(part.defects for part in message.walk()):
            return None
        names = []
        for part in message.iter_parts():
            if part.get_param('name', header='content-disposition') != 'th[name]':
                continue
            if part.get_content_disposition() != 'form-data' or part.get_filename() is not None:
                return None
            value = part.get_payload(decode=True)
            if not isinstance(value, bytes):
                return None
            names.append(value.decode('utf-8'))
        return names[0] if len(names) == 1 and names[0].strip() else None
    except (PlaywrightError, ValueError, UnicodeError):
        return None


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


async def _ready_category_trigger(page):
    section = await _product_section(page, 'ข้อมูลทั่วไป')
    return await require_control(
        section, 'Category', selector='button[role="combobox"][data-slot="popover-trigger"]',
        tags=('button',), roles=('combobox',), input_types=('button',))


async def _currency_trigger(row, index):
    return await require_control(
        row, 'Currency แถวที่ %d' % (index + 1),
        selector='button[role="combobox"][data-slot="popover-trigger"]',
        tags=('button',), roles=('combobox',), input_types=('button',))


async def _open_product_options(page, trigger):
    await aztek_form.activate_verified_button(trigger, 'ตัวเลือก Product', 'combobox')
    return await require_control(
        page, 'ตัวเลือก Product',
        selector='[role="dialog"][data-slot="popover-content"]:visible', roles=('dialog',))


async def _product_option_rows(dialog):
    options = dialog.locator('[role="option"]')
    await options.first.wait_for(state='visible', timeout=8000)
    rows = await options.evaluate_all(
        """nodes => nodes.map(node => {
          const parts = (node.getAttribute('data-value') || '').split('\\u0000');
          return {
            value: parts.length === 2 ? parts[1].trim() : '',
            text: (node.textContent || '').trim()
          };
        })""")
    if (any(not row['value'] or not row['text'] for row in rows)
            or len({row['value'] for row in rows}) != len(rows)):
        raise AztekLocatorError('Aztek: ค่าตัวเลือก Product ไม่มี ID หรือซ้ำ/รูปแบบเปลี่ยน')
    return rows


async def _read_popover_options(page, trigger):
    """Read the unique audited no-ID popup without selecting anything."""
    dialog = await _open_product_options(page, trigger)
    try:
        return _clean_option_rows(await _product_option_rows(dialog))
    finally:
        if await dialog.is_visible():
            await dialog.press('Escape')
            await dialog.wait_for(state='hidden', timeout=5000)


async def _select_popover_option(page, trigger, option_id):
    """Map the exact fetched business ID, never a suffix or display label."""
    dialog = await _open_product_options(page, trigger)
    try:
        rows = await _product_option_rows(dialog)
        wanted = str(option_id)
        index = next((n for n, row in enumerate(rows) if row['value'] == wanted), None)
        if index is None:
            raise AztekLocatorError('Aztek: ตัวเลือก Product ไม่พบ ID %s ที่ขอ' % wanted)
        # Position is derived from the current, unique business-ID mapping;
        # validate it again atomically after actionability, not a cached index.
        option = dialog.locator('[role="option"]').nth(index)
        await option.click(trial=True, timeout=5000)
        activated = await option.evaluate('''(node,wanted)=>{
          const identity=e=>{const p=(e.getAttribute('data-value')||'').split('\\u0000');
            return p.length===2?p[1].trim():null;};
          const owner=node.closest('[role="dialog"][data-slot="popover-content"]');
          if(!owner || !node.isConnected || node.getAttribute('role')!=='option' ||
             !node.getClientRects().length ||
             ['hidden','collapse'].includes(getComputedStyle(node).visibility) ||
             node.getAttribute('aria-disabled')==='true' || node.disabled || identity(node)!==wanted ||
             [...owner.querySelectorAll('[role="option"]')].filter(e=>identity(e)===wanted).length!==1) return false;
          node.click();return true;
        }''', wanted)
        if not activated:
            raise AztekLocatorError('Aztek: ค่าตัวเลือก Product เปลี่ยนระหว่างรอ')
        await dialog.wait_for(state='hidden', timeout=5000)
        await expect(trigger).to_have_text(rows[index]['text'], timeout=5000)
        return True
    except AztekLocatorError:
        raise
    except (PlaywrightError, AssertionError) as exc:
        raise AztekLocatorError('Aztek: ตัวเลือก Product ไม่พร้อมหรืออ่านกลับไม่ตรงกับ ID %s' % option_id) from exc
    finally:
        if await dialog.is_visible():
            await dialog.press('Escape')
            await dialog.wait_for(state='hidden', timeout=5000)


async def _harvest_product_options(page, wanted):
    options = {}
    if 'categories' in wanted:
        trigger = await _ready_category_trigger(page)
        options['categories'] = await _read_popover_options(page, trigger)
    if 'currencies' in wanted:
        row = await _product_price_row(page, 0)
        trigger = await _currency_trigger(row, 0)
        options['currencies'] = await _read_popover_options(page, trigger)
    return options


async def _product_section(page, title):
    form = await require_control(page, 'ฟอร์ม Product', selector='main form', tags=('form',))
    # No stable section IDs in the independently audited four forms.
    return await require_control(
        form, 'ส่วน %s' % title,
        selector='section:has(h2:text-is(%s))' % json.dumps(title, ensure_ascii=False),
        tags=('section',))


async def _product_language_panel(page, title, language):
    """Follow the audited section's current tab relationship, not runtime IDs."""
    section = await _product_section(page, title)
    caption = 'ไทย' if language == 'th' else 'English'
    label = '%s (%s)' % (title, caption)
    tab = await require_control(
        section, label, selector='[role="tab"]:text-is(%s)' % json.dumps(caption, ensure_ascii=False),
        tags=('button',), roles=('tab',), input_types=('button',))
    await aztek_form.activate_verified_button(tab, label, 'tab')
    try:
        await expect(tab).to_have_attribute('aria-selected', 'true', timeout=5000)
        relation = await tab.get_attribute('aria-controls')
        tab_id = await tab.get_attribute('id')
        if not relation or not re.fullmatch(r'\S+', relation) or not tab_id:
            raise AztekLocatorError('Aztek: %s ความสัมพันธ์แท็บไม่ชัดเจน' % label)
        panel = await require_control(
            section, label, selector='[id=%s]' % json.dumps(relation),
            tags=('div',), roles=('tabpanel',))
        await expect(panel).to_have_attribute('data-state', 'active', timeout=5000)
        await expect(panel).to_have_attribute('aria-labelledby', tab_id, timeout=5000)
        if await section.locator('[role="tabpanel"][data-state="active"]').count() != 1:
            raise AztekLocatorError('Aztek: %s พบหลายพื้นที่ภาษาที่เปิดอยู่' % label)
        return panel
    except (PlaywrightError, AssertionError) as exc:
        raise AztekLocatorError('Aztek: %s แท็บภาษาไม่พร้อมหรืออ่านกลับไม่ตรง' % label) from exc


async def _product_price_row(page, index):
    section = await _product_section(page, 'สกุลเงิน')
    original_name = 'prices.%d.original_price' % index
    price_name = 'prices.%d.price' % index
    original_selector = 'input[name=%s]' % json.dumps(original_name)
    if await section.locator(original_selector).count() == 0:
        add = await require_control(
            section, 'เพิ่มสกุลเงิน', selector='button:text-is("เพิ่มสกุลเงิน")',
            tags=('button',), input_types=('button',))
        await aztek_form.activate_verified_button(add, 'เพิ่มสกุลเงิน')
    original = await require_control(
        section, 'ราคาปกติ แถวที่ %d' % (index + 1), selector=original_selector,
        tags=('input',), input_types=('number',))
    # The no-ID row must contain both indexed price inputs and its Currency
    # trigger, without climbing to the whole section or a neighbouring row.
    row = original.locator(
        'xpath=ancestor::*[.//input[@name="%s"] and .//button[@role="combobox"]][1]' % price_name)
    if (await row.count() != 1
            or await row.locator('input[name$=".original_price"]').count() != 1
            or await row.locator('input[name$=".price"]').count() != 1
            or await row.locator('h2').count()):
        raise AztekLocatorError('Aztek: แถวสกุลเงินที่ %d ไม่ชัดเจน' % (index + 1))
    await require_control(
        row, 'ราคาขาย แถวที่ %d' % (index + 1), selector='input[name=%s]' % json.dumps(price_name),
        tags=('input',), input_types=('number',))
    return row


async def _pick_product_bundle(page, section, bundle_id):
    """Product's audited no-ID picker follows its own current popup relation."""
    label = 'Bundle %s' % bundle_id
    trigger = await require_control(
        section, label, selector='button[aria-haspopup="dialog"]',
        tags=('button',), input_types=('button',))
    popup = None
    try:
        await aztek_form.activate_verified_button(trigger, label)
        await expect(trigger).to_have_attribute('aria-expanded', 'true', timeout=5000)
        await expect(trigger).to_have_attribute('aria-controls', re.compile(r'\S+'), timeout=5000)
        relation = await trigger.get_attribute('aria-controls')
        if len(relation.split()) != 1:
            raise AztekLocatorError('Aztek: %s popup ไม่ชัดเจน' % label)
        popup = await require_control(
            page, label, selector='[id=%s]' % json.dumps(relation), tags=('div',), roles=('dialog',))
        await expect(popup).to_have_attribute('data-state', 'open', timeout=5000)
        box = await require_control(
            popup, 'ค้นหา %s' % label, selector='input[placeholder="ค้นหาด้วยชื่อหรือ id"]',
            tags=('input',), input_types=('text',))
        await box.fill(bundle_id)
        if await box.input_value() != bundle_id:
            raise AztekLocatorError('Aztek: ค้นหา %s อ่านกลับไม่ตรง' % label)
        row = await require_control(
            popup, label, selector='button:has(span:text-is(%s))' % json.dumps('ID: ' + bundle_id),
            tags=('button',), input_types=('button',))
        await row.click(trial=True, timeout=5000)
        activated = await row.evaluate(r'''(b,args)=>{
          const owner=b.closest('[role="dialog"]');
          const match=e=>[...e.querySelectorAll('span')].filter(s=>s.textContent.trim()==='ID: '+args.id).length===1;
          if(!owner || owner.id!==args.popup || owner.getAttribute('data-state')!=='open' ||
             !args.trigger.isConnected || args.trigger.closest('section')!==args.section ||
             args.trigger.getAttribute('aria-controls')!==owner.id || args.trigger.type!=='button' ||
             !b.isConnected || b.disabled || !b.getClientRects().length ||
             ['hidden','collapse'].includes(getComputedStyle(b).visibility) ||
             b.tagName!=='BUTTON' || b.type!=='button' || !match(b) ||
             [...owner.querySelectorAll('button')].filter(match).length!==1) return false;
          b.click();return true;
        }''', {'id':bundle_id, 'popup':relation, 'trigger':await trigger.element_handle(),
               'section':await section.element_handle()})
        if not activated:
            raise AztekLocatorError('Aztek: %s ตัวเลือกเปลี่ยนระหว่างรอ' % label)
        await popup.wait_for(state='hidden', timeout=5000)
        await require_control(
            section, label, selector='span:text-is(%s)' % json.dumps('#' + bundle_id), tags=('span',))
        return True
    except (PlaywrightError, AssertionError) as exc:
        raise AztekLocatorError('Aztek: %s เลือกหรืออ่านกลับไม่ได้' % label) from exc
    finally:
        if popup is not None and await popup.is_visible():
            await popup.press('Escape', timeout=5000)


async def _product_bundle_cards(section):
    """Map current business markers to their verified indexed Primary IDs."""
    markers = section.locator('span:text-matches("^#[0-9]+$")')
    ids = [text.strip()[1:] for text in await markers.all_text_contents()]
    if len(set(ids)) != len(ids):
        raise AztekLocatorError('Aztek: รายการ Bundle ซ้ำหรือขอบเขตการ์ดไม่ชัดเจน')
    cards = []
    owner = await section.element_handle()
    for index, bundle_id in enumerate(ids):
        label = 'Primary Bundle %s' % bundle_id
        marker = await require_control(
            section, label, selector='span:text-is(%s)' % json.dumps('#' + bundle_id), tags=('span',))
        card = marker.locator('xpath=ancestor::div[.//button[@role="checkbox"]][1]')
        if (await card.count() != 1
                or await card.locator('button[role="checkbox"]').count() != 1
                or await card.locator('span:text-matches("^#[0-9]+$")').count() != 1
                or not await card.evaluate('(e,s)=>e.closest("section")===s', owner)):
            raise AztekLocatorError('Aztek: %s ขอบเขตการ์ดไม่ตรง' % label)
        element_id = 'bundle-primary-%d' % index
        primary = await require_control(
            section, label, element_id=element_id, tags=('button',),
            roles=('checkbox',), input_types=('button',))
        if await card.locator('[id=%s]' % json.dumps(element_id)).count() != 1:
            raise AztekLocatorError('Aztek: %s ID ไม่ตรงกับการ์ด' % label)
        state = await primary.get_attribute('aria-checked')
        if state not in ('true', 'false'):
            raise AztekLocatorError('Aztek: %s อ่านสถานะไม่ได้' % label)
        cards.append((bundle_id, primary, state))
    if await section.locator('[id^="bundle-primary-"]').count() != len(cards):
        raise AztekLocatorError('Aztek: Primary Bundle มี ID เกินหรือขาดจากรายการ')
    return cards


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
            if any(part in page.url.lower()
                   for part in ('/login', '/signin')):
                raise RuntimeError('Aztek session expired')
            form = await require_control(page, 'ฟอร์ม Product', selector='main form', tags=('form',))
            await require_control(
                form, 'ชื่อ Product (ไทย)', element_id='th_name', tags=('input',),
                input_types=('text',), timeout=20000)
            return _require_product_options(
                await _harvest_product_options(page, wanted), wanted)
        finally:
            await context.close()
            await browser.close()


class ProductBuilder(ActivityBuilder):
    """Fill Aztek v2's Product form without inventing live option values."""

    PATH = 'products'
    SAVE_LABEL = 'สร้าง Product'
    KIND = 'Product'
    WRITE_MARK = 'product'
    READY_SELECTOR = 'main form input[id="th_name"]'

    def create_url(self, game):
        return product_create_url(game)

    async def _create_button(self, page):
        return await aztek_form.require_create_button(page, self.KIND, name_id='th_name')

    async def _activate_create(self, button):
        await aztek_form.activate_create_button(button, self.KIND, name_id='th_name')

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
        if self._verified_write_path(create_url) is None:
            return None
        return lambda: aztek_form.require_confirmation_button(page, create_url, self.KIND)

    def _confirmation_activator(self, page, create_url):
        if self._verified_write_path(create_url) is None:
            return None
        return lambda button, write_pending: aztek_form.activate_confirmation_button(
            button, create_url, self.KIND, write_pending)

    async def _read_created_id(self, page, response, create_url):
        if self._verified_write_path(create_url) is not None:
            if response is not None:
                try:
                    payload = await response.json()
                except (PlaywrightError, ValueError):
                    payload = None
                if isinstance(payload, dict) and payload.get('success') is False:
                    raise RuntimeError('Aztek ตอบ success=false — ยังยืนยันผลสร้าง Product ไม่ได้ '
                                       'โปรดตรวจบนเว็บก่อนลองใหม่')
                if isinstance(payload, dict) and payload.get('success') is True:
                    # Separately approved creates independently observed this
                    # envelope/UUID in all four games, Oct21; not inferred.
                    envelope = payload.get('data')
                    record = envelope.get('data') if isinstance(envelope, dict) else None
                    value = record.get('id') if isinstance(record, dict) else None
                    if isinstance(value, str):
                        try:
                            parsed = UUID(value)
                            if (parsed.int and str(parsed) == value.lower()
                                    and (name := await _submitted_product_name(response.request))
                                    and record.get('name') == name):
                                return value
                        except ValueError:
                            pass
            # Unknown body shapes and all saved-result URLs stay unverified.
            # Never borrow nested Bundle/Category/Currency IDs or guess a URL.
            return None
        return await super()._read_created_id(page, response, create_url)

    async def _fill_general(self, page, spec, missing):
        # Audited in all four Product forms: one no-ID form within main;
        # names have developer-maintained IDs, unlike option popup internals.
        form = await require_control(
            page, 'ฟอร์ม Product', selector='main form', tags=('form',))
        for field, element_id, label in (
            ('name_th', 'th_name', 'ชื่อ Product (ไทย)'),
            ('name_en', 'en_name', 'ชื่อ Product (อังกฤษ)'),
        ):
            value = str(spec.get(field) or '').strip()
            ok = await aztek_form.fill_by_id(form, element_id, value, label)
            if not value or not ok:
                missing.append(label)
        category_id = str(spec.get('category_id') or '').strip()
        if not category_id:
            missing.append('หมวดหมู่')
        else:
            trigger = await _ready_category_trigger(page)
            selected = await _select_popover_option(page, trigger, category_id)
            if not selected:
                missing.append('หมวดหมู่')

    async def _fill_rich_text(self, page, language, value):
        """Fill the visible TinyMCE after selecting its language tab."""
        if not str(value or ''):
            return True
        label = 'รายละเอียด (%s)' % ('ไทย' if language == 'th' else 'English')
        panel = await _product_language_panel(page, 'รายละเอียด', language)
        frame = await require_control(panel, label, selector='iframe', tags=('iframe',))
        if await frame.get_attribute('title') != 'Rich Text Area':
            raise AztekLocatorError('Aztek: %s editor ไม่ตรงกับที่ตรวจไว้' % label)
        try:
            body = await require_control(frame.content_frame, label, selector='body', tags=('body',))
            await body.fill(str(value), timeout=5000)
            await body.press('Tab', timeout=5000)
            await expect(body).to_have_text(str(value), use_inner_text=True, timeout=5000)
            return True
        except (PlaywrightError, AssertionError) as exc:
            raise AztekLocatorError('Aztek: %s กรอกหรืออ่านกลับไม่ตรงที่ขอ' % label) from exc

    async def _fill_details(self, page, spec):
        for language, field in (
            ('th', 'details_th'), ('en', 'details_en'),
        ):
            value = spec.get(field)
            if str(value or ''):
                await self._fill_rich_text(page, language, value)

    async def _fill_images(self, page, spec, missing):
        images = spec.get('images') or {}
        for slot, language, caption in (
            ('thumbnail_th', 'th', 'Thumbnail'), ('banner_th', 'th', 'Banner'),
            ('thumbnail_en', 'en', 'Thumbnail'), ('banner_en', 'en', 'Banner'),
        ):
            image = images.get(slot)
            if not image:
                continue
            label = 'รูป %s' % slot
            panel = await _product_language_panel(page, 'รูปภาพสินค้า', language)
            field_label = await require_control(
                panel, label, selector='label:text-is(%s)' % json.dumps(caption), tags=('label',))
            # Audited no-ID field wrapper: one label and its own hidden input.
            field = field_label.locator('xpath=..')
            if await field.locator('label').count() != 1:
                raise AztekLocatorError('Aztek: %s ขอบเขตช่องรูปไม่ชัดเจน' % label)
            target = field.locator('input')
            try:
                await target.wait_for(state='attached', timeout=5000)
                if await target.count() != 1 or await target.get_attribute('type') != 'file':
                    raise AztekLocatorError('Aztek: %s ช่องไฟล์ไม่ตรงกับที่ตรวจไว้' % label)
                await expect(target).to_be_enabled(timeout=5000)
                await target.set_input_files({
                    'name': image['name'], 'mimeType': image['content_type'], 'buffer': image['bytes'],
                }, timeout=5000)
                actual = await target.evaluate('e=>[...e.files].map(f=>({name:f.name,type:f.type,size:f.size}))')
                if actual != [{'name':image['name'], 'type':image['content_type'], 'size':len(image['bytes'])}]:
                    raise AztekLocatorError('Aztek: %s อ่านไฟล์กลับไม่ตรงที่ขอ' % label)
            except (PlaywrightError, AssertionError) as exc:
                raise AztekLocatorError('Aztek: %s ช่องไฟล์ไม่พร้อมหรือขอบเขตเปลี่ยน' % label) from exc

    async def _fill_prices(self, page, spec, missing):
        prices = spec.get('prices') or []
        if not prices:
            missing.append('สกุลเงิน')
            return
        for index, price in enumerate(prices):
            currency_id = str(price.get('currency_id') or '').strip()
            where = 'สกุลเงินที่ %d' % (index + 1)
            row = await _product_price_row(page, index)
            if not currency_id:
                missing.append(where)
            else:
                trigger = await _currency_trigger(row, index)
                selected = await _select_popover_option(page, trigger, currency_id)
                if not selected:
                    missing.append(where)
            for field, label in (
                ('original_price', 'ราคาปกติ'),
                ('price', 'ราคาขาย'),
            ):
                value = price.get(field)
                if value in (None, ''):
                    missing.append('%s: %s' % (where, label))
                    continue
                target = await require_control(
                    row, '%s: %s' % (where, label),
                    selector='input[name="prices.%d.%s"]' % (index, field),
                    tags=('input',), input_types=('number',))
                await target.fill(str(value))
                if await target.input_value() != str(value):
                    missing.append('%s: %s' % (where, label))

    async def _fill_display(self, page, spec, missing):
        form = await require_control(
            page, 'ฟอร์ม Product', selector='main form', tags=('form',))
        for label, field, default in (
            ('เปิดใช้งาน', 'is_enabled', False),
            ('โหมดทดสอบ', 'is_test_mode', True),
            ('ซ่อนสินค้า', 'is_hidden', False),
        ):
            await aztek_form.set_switch_by_id(
                form, field, bool(spec.get(field, default)), label)
        if not await aztek_form.fill_by_id(
                form, 'position', spec.get('position', '0'), 'ตำแหน่ง',
                input_types=('number',)):
            missing.append('ตำแหน่ง')
        for element_id, field, missing_label in (
            ('show_at', 'start_at', 'วันเริ่มขาย'),
            ('hide_at', 'end_at', 'วันสิ้นสุด'),
        ):
            value = str(spec.get(field) or '').strip()
            if not value:
                missing.append(missing_label)
                continue
            if not await aztek_form.set_datetime_by_id(
                    page, form, element_id, value,
                    self.log, label=missing_label):
                missing.append(missing_label)

    async def _fill_limit(self, page, spec, missing):
        limit_type = str(spec.get('limit_type') or '').strip()
        if not limit_type:
            missing.append('ประเภทการจำกัด')
            return
        aztek_limit_type = (
            'NONE' if limit_type == 'UNLIMITED' else limit_type)
        form = await require_control(
            page, 'ฟอร์ม Product', selector='main form', tags=('form',))
        if not await aztek_form.select_by_id(
                form, 'purchase_limit_type', aztek_limit_type, 'ประเภทการจำกัด'):
            missing.append('ประเภทการจำกัด')
        if limit_type == 'UNLIMITED':
            return
        quantity = str(spec.get('limit_quantity') or '').strip()
        ok = await aztek_form.fill_by_id(
            form, 'limit_per', quantity, 'จำนวนที่ซื้อได้', input_types=('number',))
        if not quantity or not ok:
            missing.append('จำนวนที่ซื้อได้')
        interval = str(
            spec.get('limit_reset_interval_days') or '').strip()
        if interval:
            if not await aztek_form.fill_by_id(
                    form, 'limit_reset_interval_days', interval, 'รีเซ็ตทุกกี่วัน',
                    input_types=('number',)):
                missing.append('รีเซ็ตทุกกี่วัน')
        reset_at = str(spec.get('limit_reset_at') or '').strip()
        if reset_at and not await aztek_form.set_datetime_by_id(
                page, form, 'limit_reset_at', reset_at, self.log, label='รีเซ็ตล่าสุด'):
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
        section = await _product_section(page, 'Bundle')
        existing = [card[0] for card in await _product_bundle_cards(section)]
        if existing != bundle_ids[:len(existing)]:
            raise AztekLocatorError('Aztek: รายการ Bundle เดิมไม่ตรงกับร่างที่ขอ — ไม่เปลี่ยนหรือลบแทน')
        for bundle_id in bundle_ids[len(existing):]:
            if not await _pick_product_bundle(page, section, bundle_id):
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
        cards = await _product_bundle_cards(section)
        if [card[0] for card in cards] != bundle_ids:
            raise AztekLocatorError('Aztek: Bundle list/count ไม่ตรงกับรายการที่ขอ')
        primary = cards[bundle_ids.index(primary_id)][1]
        try:
            if await primary.get_attribute('aria-checked') != 'true':
                await primary.click(trial=True, timeout=5000)
                activated = await primary.evaluate('''(b,wanted)=>{
                  const section=b.closest('section');let card=b.parentElement;
                  const marks=e=>[...e.querySelectorAll('span')].filter(s=>/^#[0-9]+$/.test(s.textContent.trim()));
                  while(card && card!==section && !marks(card).some(s=>s.textContent.trim()==='#'+wanted))card=card.parentElement;
                  if(!section || !card || card===section || !b.isConnected || b.disabled ||
                     b.tagName!=='BUTTON' || b.type!=='button' || b.getAttribute('role')!=='checkbox' ||
                     !['true','false'].includes(b.getAttribute('aria-checked')) ||
                     marks(card).length!==1 || marks(card)[0].textContent.trim()!=='#'+wanted ||
                     card.querySelectorAll('button[role="checkbox"]').length!==1) return false;
                  b.click();return true;
                }''', primary_id)
                if not activated:
                    raise AztekLocatorError('Aztek: Primary Bundle %s การ์ดเปลี่ยนระหว่างรอ' % primary_id)
            await expect(primary).to_have_attribute('aria-checked', 'true', timeout=5000)
        except (PlaywrightError, AssertionError) as exc:
            raise AztekLocatorError('Aztek: Primary Bundle %s เลือกหรืออ่านกลับไม่ได้' % primary_id) from exc
        cards = await _product_bundle_cards(section)
        if ([card[0] for card in cards] != bundle_ids
                or [card[0] for card in cards if card[2] == 'true'] != [primary_id]):
            raise AztekLocatorError('Aztek: Primary Bundle/list อ่านกลับไม่ตรงที่ขอ')

        text = await section.inner_text()
        expected_count = len(bundle_ids)
        count_ok = re.search(
            r'\b%s\s*/\s*20\s*Bundles\b' % expected_count,
            text, re.I)
        if not count_ok:
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
