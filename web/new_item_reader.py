"""Read existing Item forms only; contracts: docs/tickets/new-item/readonly-observations-20261025.md."""
from __future__ import annotations

import re
import time
from urllib.parse import urlsplit

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

import item_finder
from web.aztek_locator import AztekLocatorError, require_control
from web.new_item_domain import ActualItem, GAMES
from web.search_runner import to_web_url


async def _identity(main, item_id):
    # Observed p/span outside the form, without a stable ID. Never borrow an
    # Item/Bundle ID from a picker or another nested section.
    marker = main.locator('p:not(form p)').filter(has_text=re.compile(r'^ID:\s*[0-9]+\s*$'))
    if await marker.count() > 1:
        raise AztekLocatorError('Aztek: Item ID header พบหลายตัว')
    try:
        await marker.wait_for(state='visible', timeout=5000)
    except PlaywrightTimeoutError as error:
        raise AztekLocatorError('Aztek: ไม่พบ Item ID header ที่ยืนยันได้') from error
    if (await marker.count() != 1 or
            not re.fullmatch(r'ID:\s*' + re.escape(item_id) + r'\s*', await marker.inner_text())):
        raise AztekLocatorError('Aztek: Item ID ของหน้ารายละเอียดไม่ตรงกับ checkpoint')


async def _item_type(form, game):
    # No-ID exception: exact semantic label's immediate parent owns this field.
    label = await require_control(form, 'game_item_type label',
                                  selector='label:has-text("game_item_type")', tags=('label',))
    if not re.fullmatch(r'game_item_type\s*\*\s*', await label.inner_text()):
        raise AztekLocatorError('Aztek: game_item_type label ไม่ตรง contract')
    section = label.locator('..')
    selects = section.locator('select')
    triggers = section.locator('button[role="combobox"]')
    if game.startswith('CabalM '):
        if await selects.count() or await triggers.count():
            raise AztekLocatorError('Aztek: Type ของ M ไม่ใช่ GENERAL แบบคงที่')
        if not re.fullmatch(r'game_item_type\s*\*\s*GENERAL\s*', await section.inner_text()):
            raise AztekLocatorError('Aztek: อ่าน GENERAL ของ M ไม่ได้')
        return 'GENERAL'
    await require_control(section, 'PC Type combobox',
                          selector='button[role="combobox"]', tags=('button',), roles=('combobox',))
    if await selects.count() > 1:
        raise AztekLocatorError('Aztek: PC Type select พบหลายตัว')
    try:
        await selects.wait_for(state='attached', timeout=5000)
        await selects.locator('option[value="GENERAL"]').wait_for(state='attached', timeout=5000)
    except PlaywrightTimeoutError:
        return None  # Never infer GENERAL from missing/lazy options.
    if await selects.count() != 1:
        raise AztekLocatorError('Aztek: PC Type select ไม่ชัดเจน')
    options = await selects.evaluate('el => Array.from(el.options, option => option.value)')
    if set(options) - {'', 'GENERAL', 'CABALPC_PREMIUM'}:
        raise AztekLocatorError('Aztek: PC Type options ไม่ตรง contract')
    value = await selects.input_value()
    return value if value in ('GENERAL', 'CABALPC_PREMIUM') else None


async def _snapshot(form, game):
    values, readable = {}, []
    for key, identifier in [('name', 'item-name'), ('kind', 'item-game-item-id'),
                            ('option', 'item-option'), ('duration', 'duration-index'),
                            ('description', 'item-detail')]:
        description = key == 'description'
        control = await require_control(
            form, key, element_id=identifier, tags=('textarea',) if description else ('input',),
            input_types=() if description else ('text', 'number'))
        value = await control.input_value()
        values[key] = value
        if description or (value.strip() and (key == 'name' or re.fullmatch(r'[0-9]+', value))):
            readable.append(key)
    trade = await require_control(form, 'Tradeable', element_id='game-tradeable',
                                  tags=('button',), roles=('checkbox',))
    checked = await trade.get_attribute('aria-checked')
    values['tradeable'] = checked == 'true' if checked in ('true', 'false') else None
    if values['tradeable'] is not None:
        readable.append('tradeable')
    values['item_type'] = await _item_type(form, game)
    if values['item_type'] is not None:
        readable.append('item_type')
    images = form.locator('img[alt="Preview"]')
    count = await images.count()
    if count > 1:
        raise AztekLocatorError('Aztek: รูป Item Preview พบหลายตัว')
    present = bool(await images.get_attribute('src')) if count == 1 else False
    return values, readable, present


async def read_saved_new_item(page, *, game: str, item_id: str,
                              detail_url: str) -> ActualItem:
    """Read a caller-observed link for one exact game/ID, without any mutation."""
    if game not in GAMES or not isinstance(item_id, str) or not re.fullmatch(r'[1-9][0-9]*', item_id):
        raise ValueError('เกมหรือ Item ID ไม่ถูกต้อง')
    base = urlsplit(to_web_url(item_finder.GAMES[game]))
    target = urlsplit(detail_url)
    expected_path = base.path.rstrip('/') + '/' + item_id
    if (target.scheme != 'https' or target.hostname != base.hostname or target.username or
            target.password or target.port not in (None, 443) or target.query or target.fragment or
            target.path != expected_path):
        raise ValueError('ลิงก์ Item ไม่ตรงเกมหรือ checkpoint')
    await page.goto(detail_url, wait_until='domcontentloaded', timeout=30000)
    main = await require_control(page, 'หน้ารายละเอียด Item', selector='main', tags=('main',))
    await require_control(main, 'หัวข้อแก้ไข Item',
                          selector='h1:text-is("แก้ไข Item")', tags=('h1',))
    await _identity(main, item_id)
    form = await require_control(main, 'ฟอร์ม Item',
                                 selector='form:has([id="item-name"])', tags=('form',))
    previous = None
    deadline = time.monotonic() + 5
    while True:
        snapshot = await _snapshot(form, game)
        current = urlsplit(page.url)
        if (current.hostname != target.hostname or current.path != target.path or
                current.query or current.fragment):
            raise AztekLocatorError('Aztek: หน้า Item เปลี่ยนระหว่างอ่าน')
        await _identity(main, item_id)
        complete = len(snapshot[1]) == 7
        if (complete and snapshot == previous) or time.monotonic() >= deadline:
            values, readable, image_present = snapshot
            return {'game': game, 'item_id': item_id, 'values': values,
                    'readable_fields': readable, 'image_present': image_present,
                    'evidence': {'source': 'fresh_saved_item_dom', 'detail_url': detail_url,
                                 'identity_verified': True, 'image_check': 'presence_only'}}
        previous = snapshot
        await page.wait_for_timeout(200)
