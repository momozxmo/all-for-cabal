"""New Item orchestration for evidence-backed four-game forms and write contracts."""
from email import policy
from email.parser import BytesParser
from hashlib import sha256
import re

from playwright.async_api import async_playwright

from web import browser_launch
from web.new_item_domain import compare_new_item
from web.new_item_reader import _item_type, _snapshot, read_saved_new_item
from web.aztek_locator import AztekLocatorError, require_control
from web.search_runner import HeadlessFinder, is_login_page, to_web_url
import item_finder


# Frontend casing plus each game's own manual receipt and saved-page readback:
# docs/tickets/new-item/frontend-contract-20261026.md and live-three-probe-20261027.md.
_CREATE_CONTRACTS = {
    'CabalM TH': ('cabalm', '6eaad7c6-bfc8-48ce-a616-061a2cef8f41', 'itemOption', 'durationIndex'),
    'CabalPC TH': ('cabalpc', '97ac0f24-541a-486c-9d15-e9e1397b46ae', 'item_option', 'duration_index'),
    'CabalPC SEA': ('cabalpcsea', '88a51177-8468-4bbc-8117-a717de2458a2', 'item_option', 'duration_index'),
    'CabalM SEA': ('cabalmsea', '5f0740de-8045-42d4-8460-b03f340f01a6', 'item_option', 'duration_index'),
}


def validate_create_scope(frozen):
    """Unknown games/types remain closed, even if their draft schema allows them."""
    values = frozen.get('submitted_values') or {}
    allowed_types = ('GENERAL', 'CABALPC_PREMIUM') if frozen.get('game') in (
        'CabalPC TH', 'CabalPC SEA') else ('GENERAL',)
    if (frozen.get('game') not in _CREATE_CONTRACTS or values.get('item_type') not in allowed_types or
            not isinstance(values.get('name'), str) or not values['name'].strip() or
            any(not isinstance(values.get(key), str) or not re.fullmatch(r'[0-9]+', values[key])
                for key in ('kind', 'option', 'duration')) or
            type(values.get('tradeable')) is not bool):
        raise ValueError('ร่างอยู่นอกสัญญาสร้าง Item ที่ยืนยันแล้ว')


def saved_detail_url(game, item_id):
    """Only an ID proven by the matched response may use this saved-page schema."""
    if game not in _CREATE_CONTRACTS or not isinstance(item_id, str) or not re.fullmatch(r'[1-9][0-9]*', item_id):
        raise ValueError('เกมหรือ Item ID ไม่ตรงสัญญาบันทึก')
    return to_web_url(item_finder.GAMES[game]) + '/' + item_id


def _matching_formdata(body, content_type, values, image, game):
    """Exact observed multipart contract; reject extra/duplicate/defaulted fields."""
    if not content_type or not content_type.lower().startswith('multipart/form-data;') or not body:
        return False
    message = BytesParser(policy=policy.default).parsebytes(
        ('Content-Type: ' + content_type + '\r\nMIME-Version: 1.0\r\n\r\n').encode() + body)
    if message.defects or not message.is_multipart():
        return False
    fields, files = {}, {}
    try:
        for part in message.iter_parts():
            name = part.get_param('name', header='content-disposition')
            if part.get_content_disposition() != 'form-data' or not name or name in fields or name in files:
                return False
            raw = part.get_payload(decode=True)
            if part.get_filename() is not None:
                files[name] = (raw, part.get_content_type())
            else:
                fields[name] = raw.decode('utf-8', errors='strict')
    except (ValueError, UnicodeError, TypeError):
        return False
    _, _, option_key, duration_key = _CREATE_CONTRACTS[game]
    expected = {
        'data[th][name]': values['name'], 'data[en][name]': values['name'],
        'data[th][detail]': values.get('description') or '',
        'data[en][detail]': values.get('description') or '',
        'data[game_item_type]': values['item_type'], 'data[game_item_id]': values['kind'],
        'data[is_game_stackable]': 'false',
        f'data[game_options_1][{option_key}]': values['option'],
        f'data[game_options_1][{duration_key}]': values['duration'],
        'data[game_options_1][tradeable]': str(values['tradeable']).lower(),
        'data[display_options][is_tradable]': str(values['tradeable']).lower()}
    if fields != expected:
        return False
    if image is None:
        return not files and not values.get('image_key')
    content, media_type = image
    return (set(files) == {'files[th][thumbnail]', 'files[en][thumbnail]'} and
            all(raw == content and kind == media_type for raw, kind in files.values()) and
            values.get('image_key') == 'sha256:' + sha256(content).hexdigest())


async def _fill_create_form(page, url, values, image, game):
    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
    if page.url != url or await is_login_page(page):
        raise AztekLocatorError('Aztek: ไม่อยู่หน้าสร้าง Item ของเกมที่ยืนยัน')
    main = await require_control(page, 'หน้าสร้าง Item', selector='main', tags=('main',))
    await require_control(main, 'หัวข้อสร้าง Item', selector='h1:text-is("สร้าง Item")', tags=('h1',))
    form = await require_control(main, 'ฟอร์มสร้าง Item',
                                 selector='form:has([id="item-name"])', tags=('form',))
    current_type = await _item_type(form, game)
    if game.startswith('CabalPC ') and current_type != values['item_type']:
        # Observed no-ID exception: label-owned PC trigger, one active listbox.
        label = await require_control(form, 'PC Type label',
            selector='label:has-text("game_item_type")', tags=('label',))
        trigger = await require_control(label.locator('..'), 'PC Type combobox',
            selector='button[role="combobox"]', tags=('button',), roles=('combobox',))
        await trigger.click()
        popup = await require_control(page, 'PC Type options',
            selector='[role="listbox"]', roles=('listbox',))
        option = await require_control(popup, 'PC Type option',
            selector=f'[role="option"]:text-is("{values["item_type"]}")', roles=('option',))
        await option.click()
    if await _item_type(form, game) != values['item_type']:
        raise AztekLocatorError('Aztek: Type ไม่ตรงร่างที่ยืนยัน')
    for key, identifier in [('name', 'item-name'), ('kind', 'item-game-item-id'),
                            ('option', 'item-option'), ('duration', 'duration-index'),
                            ('description', 'item-detail')]:
        description = key == 'description'
        control = await require_control(form, key, element_id=identifier,
            tags=('textarea',) if description else ('input',),
            input_types=() if description else ('text', 'number'))
        await control.fill(values.get(key) or '')
    for label, identifier, role, expected in [
        ('Tradeable', 'game-tradeable', 'checkbox', values['tradeable']),
        ('Web display', 'display-option-enable', 'switch', False)]:
        control = await require_control(form, label, element_id=identifier, tags=('button',), roles=(role,))
        state = await control.get_attribute('aria-checked')
        if state not in ('true', 'false'):
            raise AztekLocatorError('Aztek: อ่านสถานะ ' + label + ' ไม่ได้')
        if (state == 'true') != expected:
            await control.click()
        if await control.get_attribute('aria-checked') != str(expected).lower():
            raise AztekLocatorError('Aztek: ตั้งค่า ' + label + ' ไม่ตรง')
    file_input = form.locator('input[type="file"]')
    if await file_input.count() != 1:
        raise AztekLocatorError('Aztek: ช่องรูป Item ไม่ชัดเจน')
    if image:
        content, media_type = image
        await file_input.set_input_files({'name': 'item.' + {'image/png': 'png', 'image/jpeg': 'jpg',
            'image/webp': 'webp'}[media_type], 'mimeType': media_type, 'buffer': content})
    snapshot, readable, image_present = await _snapshot(form, game)
    if (len(readable) != 7 or any(snapshot.get(key) != (values.get(key) or '' if key == 'description'
            else values[key]) for key in snapshot) or (not image and image_present)):
        raise AztekLocatorError('Aztek: ค่าที่กรอกอ่านกลับไม่ตรงร่าง')
    create = await require_control(form, 'สร้าง Item', selector='button[type="submit"]:text-is("สร้าง Item")',
                                   tags=('button',), input_types=('submit',))
    await create.click()
    dialog = await require_control(page, 'ยืนยันสร้าง Item', selector='[role="alertdialog"]', roles=('alertdialog',))
    if (await dialog.get_by_text('ยืนยันการสร้าง', exact=True).count() != 1 or
            await dialog.get_by_text('ต้องการสร้าง Item ใช่หรือไม่?', exact=True).count() != 1):
        raise AztekLocatorError('Aztek: ข้อความยืนยันสร้าง Item ไม่ตรง')
    return await require_control(dialog, 'ยืนยัน', selector='button:text-is("ยืนยัน")', tags=('button',))


async def create_new_item(frozen, *, storage_state, image, on_submit, on_saved):
    """One exact POST at most. Callbacks durably checkpoint before write/readback."""
    validate_create_scope(frozen)
    game = frozen['game']
    slug, game_uuid, _, _ = _CREATE_CONTRACTS[game]
    create_post = f'https://admin-api-v2.combo-interactive.com/{slug}/game/items'
    values = frozen['submitted_values']
    list_url = to_web_url(item_finder.GAMES[frozen['game']])
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**browser_launch.launch_kwargs(False))
        try:
            context = await browser.new_context(**browser_launch.context_kwargs(
                False, storage_state=storage_state, service_workers='block'))
            page = await context.new_page()
            armed, forwarded = False, None

            async def guarded_request(route):
                nonlocal forwarded
                request = route.request
                if request.method in ('GET', 'HEAD'):
                    await route.fallback()
                    return
                content_type = await request.header_value('content-type')
                # Recheck the one-shot latch AFTER the last await. Two POSTs can
                # otherwise both observe forwarded=None before header retrieval.
                allowed = (armed and forwarded is None and request.method == 'POST' and
                    request.url == create_post and request.frame == page.main_frame and
                    page.url == list_url + '/create' and _matching_formdata(
                        request.post_data_buffer, content_type, values, image, game))
                if not allowed:
                    await route.abort()
                    return
                try:
                    on_submit()  # Atomic durable claim MUST precede any forwarding.
                except Exception:
                    await route.abort()
                    return
                forwarded = request
                await route.fallback()

            await context.route('**/*', guarded_request)
            confirm = await _fill_create_form(page, list_url + '/create', values, image, game)
            armed = True
            async with page.expect_response(lambda response: forwarded is not None and
                                            response.request == forwarded, timeout=8000) as pending:
                await confirm.click(timeout=5000)
            response = await pending.value
            body = await response.json()
            resource = body.get('data', {}).get('data') if isinstance(body, dict) and isinstance(body.get('data'), dict) else None
            if (response.status != 200 or body.get('success') is not True or
                    not isinstance(resource, dict) or type(resource.get('id')) is not int or
                    resource['id'] <= 0 or resource.get('game_id') != game_uuid or
                    resource.get('game_item_type') != values['item_type']):
                raise ValueError('คำตอบสร้าง Item ไม่ตรงสัญญาที่พิสูจน์แล้ว')
            item_id = str(resource['id'])
            detail_url = saved_detail_url(game, item_id)
            on_saved(item_id, detail_url)  # Commit ID before any further navigation can fail.
            actual = await read_saved_new_item(page, game=frozen['game'], item_id=item_id, detail_url=detail_url)
            return compare_new_item(frozen, actual, expected_item_id=item_id)
        finally:
            await browser.close()


class _CandidateFinder(HeadlessFinder):
    """Reuse verified Finder controls; retain actual row-owned links only."""
    async def _read_table_page(self, page):
        rows = await super()._read_table_page(page)
        if not rows:
            return rows
        main = await require_control(page, 'Item Finder main', selector='main', tags=('main',))
        table = await require_control(main, 'ตาราง Item', selector='table', tags=('table',))
        links = await table.evaluate('''table => {
            const headers = [...table.querySelectorAll('thead th')].map(e => e.innerText.trim());
            const index = headers.indexOf('Aztek Item Id');
            return [...table.querySelectorAll('tbody tr')].map(tr => ({
                id: (tr.querySelectorAll('td')[index]?.innerText || '').trim(),
                links: [...tr.querySelectorAll('a[href]')].map(a => a.href)
            }));
        }''')
        for row in rows:
            matches = [entry for entry in links if entry['id'] == row['aztek_id']]
            expected = self.list_url + '/' + row['aztek_id']
            if (len(matches) != 1 or matches[0]['links'].count(expected) != 1):
                raise AztekLocatorError('Aztek: ไม่พบลิงก์รายละเอียด Item ที่ยืนยันได้ในแถวเดียวกัน')
            row['detail_url'] = next(link for link in matches[0]['links'] if link == expected)
        return rows


async def search_existing_new_items(frozen, *, storage_state):
    """Search the confirmed triple; names are display evidence, not identity."""
    url = to_web_url(item_finder.GAMES[frozen['game']])
    values = frozen['submitted_values']
    criteria = {'kind': values['kind'], 'opt': values['option'], 'dur': values['duration']}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**browser_launch.launch_kwargs(False))
        try:
            context = await browser.new_context(**browser_launch.context_kwargs(
                False, storage_state=storage_state, service_workers='block'))
            async def readonly_request(route):
                if route.request.method in ('GET', 'HEAD'):
                    await route.fallback()
                else:
                    await route.abort()
            await context.route('**/*', readonly_request)
            page = await context.new_page()
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            if await is_login_page(page):
                raise ValueError('เซสชัน Aztek หมดอายุ')
            finder = _CandidateFinder(lambda *_: None, lambda *_: None, lambda *_: None)
            finder.list_url = url
            await finder._apply_filters(page, criteria)
            rows = await finder._read_all_pages(page, criteria)
            if page.url.split('?', 1)[0] != url:
                raise AztekLocatorError('Aztek: หน้าเกมเปลี่ยนระหว่างค้นหา Item')
            return [{'item_id': row['aztek_id'], 'name': row['item_name'],
                     'kind': row['item_kind'], 'option': row['item_option'],
                     'duration': row['duration_index'], 'detail_url': row['detail_url']}
                    for row in rows if row['item_kind'] == criteria['kind']]
        finally:
            await browser.close()


async def read_existing_new_item(frozen, *, item_id, detail_url, storage_state):
    """Use an isolated browser and the caller's retained saved-record identity."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**browser_launch.launch_kwargs(False))
        try:
            context = await browser.new_context(**browser_launch.context_kwargs(
                False, storage_state=storage_state, service_workers='block'))

            async def readonly_request(route):
                if route.request.method in ('GET', 'HEAD'):
                    await route.fallback()
                else:
                    await route.abort()

            await context.route('**/*', readonly_request)
            page = await context.new_page()
            actual = await read_saved_new_item(page, game=frozen['game'], item_id=item_id,
                                               detail_url=detail_url)
            return compare_new_item(frozen, actual, expected_item_id=item_id)
        finally:
            await browser.close()
