"""Read saved Aztek data without submitting or changing any form values."""
from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from web.aztek_locator import AztekLocatorError, require_control


class SessionExpiredError(RuntimeError):
    """Aztek redirected a read-only verification to its login page."""


def _reward_display(value) -> str:
    """Aztek's saved card displays a name, while its picker includes a slug."""
    text = str(value or '')
    match = re.fullmatch(r'[a-z0-9_-]+ - (.+)', text)
    return match.group(1) if match else text


async def _read_saved_item(detail, item_url: str, item_id: str) -> dict:
    """Read only the verified Item form after its numeric values settle."""
    await detail.goto(item_url, wait_until='domcontentloaded', timeout=30000)
    if any(part in urlsplit(detail.url).path.lower() for part in ('/login', '/signin')):
        raise SessionExpiredError('เซสชัน Aztek หมดอายุ กรุณาเชื่อมใหม่ก่อนตรวจซ้ำ')
    main = await require_control(detail, 'หน้ารายละเอียด Item', selector='main', tags=('main',))
    await main.get_by_role('heading', name='แก้ไข Item', exact=True).wait_for(timeout=5000)
    identity = main.get_by_text(re.compile(r'^ID:\s*[0-9]+$'))
    expected_identity = re.compile(r'^ID:\s*' + re.escape(item_id) + r'$')
    if urlsplit(detail.url).path != urlsplit(item_url).path or await identity.count() > 1:
        raise ValueError('Item ID ของหน้ารายละเอียดไม่ตรงกับ Bundle')
    try:
        await identity.wait_for(state='visible', timeout=5000)
    except PlaywrightTimeoutError as error:
        raise ValueError('Item ID ของหน้ารายละเอียดไม่ตรงกับ Bundle') from error
    if await identity.count() != 1 or not expected_identity.fullmatch(await identity.inner_text()):
        raise ValueError('Item ID ของหน้ารายละเอียดไม่ตรงกับ Bundle')
    form = await require_control(main, 'ฟอร์มรายละเอียด Item',
                                 selector='form:has([id="item-name"])', tags=('form',))
    await require_control(form, 'ชื่อ Item ที่บันทึกแล้ว', element_id='item-name',
                          tags=('input',), input_types=('text',))
    previous = None
    for _ in range(18):
        values = {}
        for key, identifier in [('kind', 'item-game-item-id'),
                                ('option', 'item-option'), ('duration', 'duration-index')]:
            field = await require_control(form, '%s ของ Item %s' % (key, item_id),
                                          element_id=identifier, tags=('input',),
                                          input_types=('text', 'number'))
            values[key] = await field.input_value()
        if all(re.fullmatch(r'[0-9]+', value) for value in values.values()):
            if values == previous:
                if (urlsplit(detail.url).path != urlsplit(item_url).path
                        or await identity.count() != 1 or not await identity.is_visible()
                        or not expected_identity.fullmatch(await identity.inner_text())):
                    raise ValueError('Item ID ของหน้ารายละเอียดไม่ตรงกับ Bundle')
                return values
            previous = values
        else:
            previous = None
        await detail.wait_for_timeout(300)
    raise AztekLocatorError('Aztek: ค่ารายละเอียด Item %s ยังไม่พร้อมอ่านครบ' % item_id)


_CARD_BUTTONS = 'button[aria-label="ขยาย"][aria-expanded], button[aria-label="ย่อ"][aria-expanded]'
_SAVED_EXPANDER_SHAPE = '''button => {
    const form = button.closest('form'), card = button.parentElement?.parentElement;
    return button.type === 'button' && !button.getAttribute('role') && button.form === form &&
      button.getClientRects().length > 0 && getComputedStyle(button).visibility !== 'hidden' &&
      ['true','false'].includes(button.getAttribute('aria-expanded')) &&
      card && card !== form && card.closest('form') === form &&
      card.querySelectorAll('button[aria-label="ขยาย"][aria-expanded], button[aria-label="ย่อ"][aria-expanded]').length === 1;
}'''


async def _saved_cards_snapshot(form):
    """Read all occurrence identities and values in one synchronous DOM snapshot."""
    try:
        return await form.evaluate('''(form, buttonsSelector) => {
      const validExpander = ''' + _SAVED_EXPANDER_SHAPE + ''';
      const visible = el => el && el.getClientRects().length > 0 &&
        getComputedStyle(el).visibility !== 'hidden';
      const fail = (control, pending=false) => {throw {control, pending}};
      const one = (scope, selector, control) => {
        const found = scope.querySelectorAll(selector);
        if (found.length > 1) fail(control + ' พบหลายตัว');
        if (!found.length) fail(control + ' หาไม่พบ', true);
        return found[0];
      };
      const field = (scope, name) => {
        const labels = [...scope.querySelectorAll('label')].filter(e =>
          e.textContent.trim().replace(/\\s*\\*$/, '') === name);
        if (labels.length > 1) fail(name + ' กำกวม');
        if (!labels.length || !visible(labels[0])) fail(name + ' ยังไม่พร้อมอ่าน', true);
        return labels[0].parentElement;
      };
      const selection = (scope, name) => {
        const block = field(scope, name);
        const trigger = one(block, '[role="combobox"]', name);
        if (trigger.tagName !== 'BUTTON' || trigger.type !== 'button') fail(name + ' ผิดชนิด');
        if (!visible(trigger)) fail(name + ' ยังไม่พร้อมอ่าน', true);
        const select = one(block, 'select', name);
        if (select.type !== 'select-one') fail(name + ' ผิดชนิด');
        if (select.selectedOptions.length !== 1) fail(name + ' ยังไม่พร้อมอ่าน', true);
        return {value:select.value, text:select.selectedOptions[0].textContent.trim()};
      };
      try {
        const marker = one(form, '[id="bundle-name"]', 'ชื่อ Bundle');
        if (marker.tagName !== 'INPUT' || marker.type !== 'text') fail('ชื่อ Bundle ผิดชนิด');
        if (!visible(marker)) fail('ชื่อ Bundle ยังไม่พร้อมอ่าน', true);
        const type = selection(form, 'ประเภท Bundle').value;
        if (!['CHOICE','FIXED','GACHAPON','GACHAPON_LIMIT','RANDOM'].includes(type))
          fail('ประเภท Bundle ยังไม่พร้อมอ่าน', true);
        const indexes = new Set();
        const buttons = [...form.querySelectorAll(buttonsSelector)];
        const countCandidates = [...form.querySelectorAll('*')].filter(e =>
          /^รายการไอเท็ม\\s*\\(\\s*[0-9]+\\s*\\)$/.test(e.textContent.trim()));
        const counts = countCandidates.filter(e => !countCandidates.some(other => other !== e && e.contains(other)));
        if (counts.length > 1) fail('จำนวนแถวกำกวม');
        if (!counts.length || !visible(counts[0])) fail('จำนวนแถวยังไม่พร้อมอ่าน', true);
        const expected = Number(counts[0].textContent.match(/[0-9]+/)[0]);
        if (buttons.length !== expected) fail('จำนวนแถวที่อ่านไม่ครบ', true);
        const rows = buttons.map((button, position) => {
          if (!validExpander(button)) fail('ปุ่มขยายการ์ดรายการที่ ' + (position + 1) + ' ผิดชนิดหรือไม่พร้อมอ่าน');
          if (button.getAttribute('aria-expanded') !== 'true') fail('การ์ดยังไม่พร้อมอ่าน', true);
          const card = button.parentElement.parentElement;
          const badges = [...button.querySelectorAll('span')].filter(e =>
            ['ITEM','CREDIT','DEBIT','MILEAGE','PLAYER_EXP','PLAYER_EXPERIENCE',
             'WALLET_CREDIT','WALLET','WALLET_MILEAGE'].includes(e.textContent.trim()));
          if (badges.length > 1) fail('ประเภทการ์ดกำกวม');
          if (badges.length && !visible(badges[0])) fail('ประเภทการ์ดยังไม่พร้อมอ่าน', true);
          const badge = badges[0]?.textContent.trim();
          const quantity = one(card, 'input[name^="items."][name$=".quantity"]', 'Quantity');
          if (quantity.type !== 'number') fail('Quantity ผิดชนิด');
          const index = quantity.name.match(/^items\\.([0-9]+)\\.quantity$/)?.[1];
          if (!index || indexes.has(index)) fail('เลขแถว Quantity กำกวมหรือไม่ตรงกับการ์ด');
          indexes.add(index);
          if (!visible(quantity) || !/^[0-9]+$/.test(quantity.value)) fail('Quantity ยังไม่พร้อมอ่าน', true);
          const tier = selection(card, 'Tier').text;
          if (!['Common','Rare','Epic','Mystic','Legend'].includes(tier)) fail('Tier ยังไม่พร้อมอ่าน', true);
          let value = null;
          if (badge) {
            const label = badge === 'ITEM' ? 'Item ID' :
              ['PLAYER_EXP','PLAYER_EXPERIENCE'].includes(badge) ? 'ชื่อ Monarchy' : 'ชื่อ';
            const identity = one(field(card, label), 'p', label);
            value = identity.textContent.trim();
            if (!visible(identity) || !value || (badge === 'ITEM' && !/^[0-9]+$/.test(value)))
              fail(label + ' ยังไม่พร้อมอ่าน', true);
          }
          let rate = null;
          if (type === 'RANDOM') {
            const draw = one(card, '[id=' + JSON.stringify('items.' + index + '.secret_chance') + ']', 'เรทสุ่ม');
            if (draw.tagName !== 'INPUT' || draw.type !== 'number') fail('เรทสุ่มผิดชนิด');
            if (!visible(draw) || !/^[0-9]+(?:\\.[0-9]+)?$/.test(draw.value)) fail('เรทสุ่มยังไม่พร้อมอ่าน', true);
            rate = draw.value;
          }
          const types = {PLAYER_EXPERIENCE:'PLAYER_EXP',WALLET_CREDIT:'CREDIT',
                         WALLET:'DEBIT',WALLET_MILEAGE:'MILEAGE'};
          return {type:types[badge] || badge || null, id:badge === 'ITEM' ? value : null,
                  value:badge === 'ITEM' ? null : value, qty:quantity.value, tier, rate, index};
        });
        return {rows, type};
      } catch (error) {
        if (error.control) return {error:error.control, pending:error.pending};
        throw error;
      }
    }''', _CARD_BUTTONS, timeout=5000)
    except PlaywrightTimeoutError as error:
        raise AztekLocatorError('Aztek: ฟอร์มรายละเอียด Bundle ยังไม่พร้อมอ่าน') from error


async def _ready_saved_cards(page, form):
    previous = None
    snapshot = {}
    for _ in range(18):
        snapshot = await _saved_cards_snapshot(form)
        if snapshot.get('error'):
            if not snapshot.get('pending'):
                raise AztekLocatorError('Aztek: ' + snapshot['error'])
            previous = None
        elif snapshot == previous:
            return snapshot
        else:
            previous = snapshot
        await page.wait_for_timeout(300)
    raise AztekLocatorError('Aztek: ' + snapshot.get('error', 'ข้อมูลการ์ดเปลี่ยนระหว่างอ่าน'))


async def read_saved_bundle(page, url: str) -> dict:
    """Read every saved occurrence; item attributes come from fresh detail pages.

    Unknown reward cards are explicitly incomplete, never silently discarded as
    evidence of a passing check. This function only navigates and expands cards.
    """
    parsed = urlsplit(url)
    if not re.fullmatch(r'/combo/[^/]+/shop/bundles/[0-9]+', parsed.path):
        raise ValueError('invalid saved Bundle URL')
    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
    if any(part in urlsplit(page.url).path.lower() for part in ('/login', '/signin')):
        raise SessionExpiredError('เซสชัน Aztek หมดอายุ กรุณาเชื่อมใหม่ก่อนตรวจซ้ำ')
    main = await require_control(page, 'หน้ารายละเอียด Bundle', selector='main', tags=('main',))
    await main.get_by_role('heading', name='แก้ไข Bundle', exact=True).wait_for(timeout=5000)
    bundle_id = parsed.path.rsplit('/', 1)[-1]
    # No stable header ID: the saved record marker is outside forms. Item-picker
    # results inside the form also render "ID:" and may mount during detail reads.
    identity = main.get_by_text(re.compile(r'^ID:\s*[0-9]+$')).and_(
        main.locator(':not(form *)'))
    expected_identity = re.compile(r'^ID:\s*' + re.escape(bundle_id) + r'$')
    if urlsplit(page.url).path != parsed.path or await identity.count() > 1:
        raise ValueError('Bundle ID ของหน้าที่เปิดไม่ตรงกับรายการที่สร้าง')
    try:
        await identity.wait_for(state='visible', timeout=5000)
    except PlaywrightTimeoutError as error:
        raise ValueError('Bundle ID ของหน้าที่เปิดไม่ตรงกับรายการที่สร้าง') from error
    if await identity.count() != 1 or not expected_identity.fullmatch(await identity.inner_text()):
        raise ValueError('Bundle ID ของหน้าที่เปิดไม่ตรงกับรายการที่สร้าง')
    form = await require_control(main, 'ฟอร์มรายละเอียด Bundle',
                                 selector='form:has([id="bundle-name"])', tags=('form',))
    await require_control(form, 'ชื่อ Bundle ที่บันทึกแล้ว', element_id='bundle-name',
                          tags=('input',), input_types=('text',))
    cards = form.locator(_CARD_BUTTONS)
    try:
        await cards.first.wait_for(timeout=5000)
    except PlaywrightTimeoutError as error:
        raise AztekLocatorError('Aztek: การ์ด Bundle หาไม่พบหรือยังไม่พร้อมอ่าน') from error
    count_label = form.get_by_text(re.compile(r'^รายการไอเท็ม\s*\(\s*\d+\s*\)$'))
    if await count_label.count() > 1:
        raise AztekLocatorError('Aztek: จำนวนแถวกำกวม')
    try:
        await count_label.wait_for(state='visible', timeout=5000)
    except PlaywrightTimeoutError as error:
        raise AztekLocatorError('Aztek: จำนวนแถวยังไม่พร้อมอ่าน') from error
    count_text = await count_label.inner_text(timeout=5000)
    expected_count = int(re.search(r'\d+', count_text).group())
    for _ in range(18):
        count = await cards.count()
        if count == expected_count or count > expected_count:
            break
        await page.wait_for_timeout(300)
    if count != expected_count:
        raise ValueError('จำนวนแถวที่อ่านไม่ครบ: %d/%d' % (await cards.count(), expected_count))
    for index in range(expected_count):
        expander = cards.nth(index)
        for _ in range(18):
            if await expander.is_visible() and await expander.is_enabled():
                break
            await page.wait_for_timeout(300)
        if not await expander.evaluate(_SAVED_EXPANDER_SHAPE):
            raise AztekLocatorError('Aztek: ปุ่มขยายการ์ดรายการที่ %d ไม่ตรงกับที่ตรวจไว้' % (index + 1))
        if await expander.get_attribute('aria-expanded') == 'false':
            # The final click locator retains the type contract during actionability waits.
            safe_expander = expander.and_(form.locator('button[type="button"]:not([role])'))
            try:
                await safe_expander.click(timeout=5000)
            except PlaywrightTimeoutError as error:
                raise AztekLocatorError('Aztek: ปุ่มขยายการ์ดไม่พร้อมอ่านหรือเปลี่ยนชนิด') from error
        for _ in range(18):
            if await expander.get_attribute('aria-expanded') == 'true':
                break
            await page.wait_for_timeout(300)
        else:
            raise AztekLocatorError('Aztek: การ์ดรายการที่ %d ยังไม่พร้อมอ่าน' % (index + 1))
    snapshot = await _ready_saved_cards(page, form)
    rows = snapshot['rows']
    items, rewards, unsupported = [], [], []
    detail = await page.context.new_page()
    try:
        for index, row in enumerate(rows):
            if row['type'] not in ('ITEM', 'CREDIT', 'DEBIT', 'MILEAGE',
                                   'PLAYER_EXP', 'PLAYER_EXPERIENCE'):
                unsupported.append(index + 1)
                continue
            if row['qty'] is None or not re.fullmatch(r'[0-9]+', row['qty']):
                raise ValueError('อ่านจำนวนรายการที่ %d ไม่สำเร็จ' % (index + 1))
            if row['type'] != 'ITEM':
                if not row['value']:
                    unsupported.append(index + 1)
                    continue
                rewards.append({key: value for key, value in row.items()
                                if key in ('type', 'value', 'qty', 'tier', 'rate')
                                and value is not None})
                continue
            if not row['id'] or not re.fullmatch(r'[0-9]+', row['id']):
                unsupported.append(index + 1)
                continue
            item_url = url.rsplit('/bundles/', 1)[0] + '/items/' + row['id']
            saved_item = dict(row, **await _read_saved_item(detail, item_url, row['id']))
            items.append({key: value for key, value in saved_item.items()
                          if key in ('id', 'qty', 'kind', 'option', 'duration', 'tier', 'rate')
                          and value is not None})
    finally:
        await detail.close()
    if (urlsplit(page.url).path != parsed.path or await identity.count() != 1
            or not await identity.is_visible()
            or not expected_identity.fullmatch(await identity.inner_text())):
        raise ValueError('Bundle ID เปลี่ยนระหว่างอ่านรายละเอียด')
    if await _saved_cards_snapshot(form) != snapshot:
        raise AztekLocatorError('Aztek: ข้อมูลการ์ดเปลี่ยนระหว่างอ่าน กรุณาตรวจซ้ำ')
    return {'items': items, 'rewards': rewards,
            'complete': not unsupported, 'unsupported': unsupported}


async def recheck_saved_bundle(page, url: str, reference: dict | None,
                               submitted: dict) -> dict:
    """Compare independent original properties and submitted IDs, as row bags."""
    actual = await read_saved_bundle(page, url)
    reference = reference or {}
    expected = reference.get('items') or []
    expected_rewards = reference.get('rewards') or []
    actual_rewards = actual.get('rewards') or []
    fields = ('kind', 'option', 'duration', 'qty')
    missing = not (expected or expected_rewards) or any(
        row.get(field) in (None, '') for row in expected for field in fields)
    if expected_rewards:
        missing |= any(row.get(field) in (None, '') for row in expected_rewards
                       for field in ('type', 'value', 'qty'))
    if submitted.get('type') == 'RANDOM':
        missing |= any(row.get('rate') in (None, '') for row in
                       expected + expected_rewards)
    missing |= any(row.get('tier') in (None, '') for row in
                   expected + expected_rewards if any('tier' in s for s in
                   (submitted.get('items') or []) + (submitted.get('rewards') or [])))
    missing |= bool(submitted.get('rewards')) and 'rewards' not in reference
    missing |= bool(submitted.get('items')) and 'items' not in reference
    display_only_rewards = [row for row in expected_rewards
                            if _reward_display(row.get('value')) != str(row.get('value') or '')]
    missing |= bool(display_only_rewards)
    # Unsupported checks must not be advertised as a complete pass.
    incomplete = (missing or not reference.get('game') or not submitted.get('game')
                  or not actual['complete'])

    def same(key, left, right):
        if key == 'value':
            return _reward_display(left) == _reward_display(right)
        if key == 'rate':
            try:
                return Decimal(str(left)) == Decimal(str(right))
            except (InvalidOperation, ValueError):
                return False
        return str(left) == str(right)

    def bag(rows, keys):
        return Counter(tuple(str(row.get(key, '')) for key in keys) for row in rows)

    def reward_bag(rows):
        return Counter((str(row.get('type', '')), _reward_display(row.get('value')),
                        str(row.get('qty', ''))) for row in rows)

    differences = []
    if reference.get('game') and reference['game'] != submitted.get('game'):
        differences.append('game')
    if actual['complete'] and bag(submitted.get('items') or [], ('id', 'qty')) != bag(actual['items'], ('id', 'qty')):
        differences.append('submitted_items')
    if actual['complete'] and reward_bag(submitted.get('rewards') or []) != reward_bag(actual_rewards):
        differences.append('submitted_rewards')
    if actual['complete'] and 'items' in reference and len(expected) != len(actual['items']):
        differences.append('document_count')
    if actual['complete'] and 'rewards' in reference and len(expected_rewards) != len(actual_rewards):
        differences.append('document_reward_count')
    matches = {}
    if expected:
        # Maximum one-to-one matching: missing source cells are unknown, not
        # zero. A broad partial row must not steal the only match of a more
        # specific row. Each actual occurrence can satisfy at most one row.
        def match(source_index, seen):
            source = expected[source_index]
            for actual_index, row in enumerate(actual['items']):
                if actual_index in seen or any(
                    source.get(key) not in (None, '') and
                    not same(key, source[key], row.get(key, '')) for key in fields
                ):
                    continue
                seen.add(actual_index)
                if actual_index not in matches or match(matches[actual_index], seen):
                    matches[actual_index] = source_index
                    return True
            return False

        if sum(bool(match(index, set())) for index in range(len(expected))) != len(expected):
            differences.append('document_items')
    matched_sources = {source_index: actual_index
                       for actual_index, source_index in matches.items()} if expected else {}
    unmatched_actual = [index for index in range(len(actual['items']))
                        if index not in matches]
    submitted_rows = submitted.get('items') or []
    remaining_submitted = list(range(len(submitted_rows)))
    submitted_for_actual = {}
    for actual_index, item in enumerate(actual['items']):
        chosen = next((index for index in remaining_submitted
                       if str(submitted_rows[index].get('id', '')) == item['id']
                       and str(submitted_rows[index].get('qty', '')) == item['qty']), None)
        if chosen is None and remaining_submitted:
            chosen = remaining_submitted[0]
        if chosen is not None:
            remaining_submitted.remove(chosen)
            submitted_for_actual[actual_index] = submitted_rows[chosen]
    rows = []
    for source_index, original in enumerate(expected):
        actual_index = matched_sources.get(source_index)
        if actual_index is None and unmatched_actual:
            actual_index = unmatched_actual.pop(0)
        saved = actual['items'][actual_index] if actual_index is not None else None
        sent = submitted_for_actual.get(actual_index) if actual_index is not None else None
        different = (['missing_item' if actual['complete'] else 'unreadable_item'] if saved is None else [
            key for key in fields if original.get(key) not in (None, '')
            and saved.get(key) not in (None, '')
            and not same(key, original[key], saved.get(key, ''))])
        if saved is not None:
            different += [key for key in ('tier', 'rate')
                          if original.get(key) not in (None, '')
                          and saved.get(key) not in (None, '')
                          and not same(key, original[key], saved.get(key, ''))]
        if saved is not None and sent is not None and str(sent.get('id')) != saved['id']:
            different.append('id')
        if saved is not None and sent is not None and str(sent.get('qty')) != saved['qty']:
            different.append('submitted_qty')
        rows.append({'source_row': original.get('source_row'), 'original': original,
                     'submitted': sent, 'actual': saved, 'different': different})
        if saved is not None and any(original.get(key) not in (None, '')
                                     and saved.get(key) in (None, '')
                                     for key in ('tier', 'rate')):
            incomplete = True
        if any(key != 'unreadable_item' for key in different) and 'document_items' not in differences:
            differences.append('document_items')
    for actual_index in unmatched_actual:
        rows.append({'source_row': None, 'original': None,
                     'submitted': submitted_for_actual.get(actual_index),
                     'actual': actual['items'][actual_index],
                     'different': ['extra_item']})
    identity = ('type', 'value')
    reward_matches = {}

    def match_reward(source_index, seen):
        original = expected_rewards[source_index]
        for actual_index, saved in enumerate(actual_rewards):
            if (actual_index in seen
                    or not all(same(key, original.get(key), saved.get(key)) for key in identity)
                    or any(original.get(key) not in (None, '') and saved.get(key) not in (None, '')
                           and not same(key, original[key], saved[key]) for key in ('qty', 'tier', 'rate'))):
                continue
            seen.add(actual_index)
            if actual_index not in reward_matches or match_reward(reward_matches[actual_index], seen):
                reward_matches[actual_index] = source_index
                return True
        return False

    for source_index in range(len(expected_rewards)):
        match_reward(source_index, set())
    reward_sources = {source: actual_index for actual_index, source in reward_matches.items()}
    remaining_rewards = [index for index in range(len(actual_rewards)) if index not in reward_matches]
    remaining_sent_rewards = list(submitted.get('rewards') or [])
    for source_index, original in enumerate(expected_rewards):
        actual_index = reward_sources.get(source_index)
        if actual_index is None:
            actual_index = next((index for index in remaining_rewards
                                 if all(same(key, original.get(key), actual_rewards[index].get(key))
                                        for key in identity)), None)
            if actual_index is not None:
                remaining_rewards.remove(actual_index)
        saved = actual_rewards[actual_index] if actual_index is not None else None
        sent_index = next((index for index, entry in enumerate(remaining_sent_rewards)
                           if all(same(key, original.get(key), entry.get(key)) for key in identity)
                           and all(original.get(key) in (None, '') or entry.get(key) in (None, '')
                                   or same(key, original[key], entry[key]) for key in ('qty', 'tier', 'rate'))), None)
        if sent_index is None:
            sent_index = next((index for index, entry in enumerate(remaining_sent_rewards)
                               if all(same(key, original.get(key), entry.get(key)) for key in identity)), None)
        sent = remaining_sent_rewards.pop(sent_index) if sent_index is not None else None
        different = ['missing_reward' if actual['complete'] else 'unreadable_reward'] if saved is None else [
            key for key in ('qty', 'tier', 'rate')
            if original.get(key) not in (None, '')
            and saved.get(key) not in (None, '')
            and not same(key, original[key], saved.get(key, ''))]
        if any(key != 'unreadable_reward' for key in different) and 'document_rewards' not in differences:
            differences.append('document_rewards')
        if saved is not None and any(original.get(key) not in (None, '')
                                     and saved.get(key) in (None, '')
                                     for key in ('tier', 'rate')):
            incomplete = True
        rows.append({'source_row': original.get('source_row'), 'original': original,
                     'submitted': sent, 'actual': saved, 'different': different})
    if 'rewards' in reference:
        for actual_index in remaining_rewards:
            saved = actual_rewards[actual_index]
            rows.append({'source_row': None, 'original': None, 'submitted': None,
                         'actual': saved, 'different': ['extra_reward']})
            if 'document_rewards' not in differences:
                differences.append('document_rewards')
    present_properties = sum(row.get(key) not in (None, '')
                             for row in expected for key in fields)
    return {'outcome': 'mismatch' if differences else 'failed' if not actual['complete']
            else 'partial' if incomplete else 'passed',
            'incomplete': bool(incomplete), 'differences': differences,
            'rows': rows,
            'coverage': {'properties': f'{present_properties}/{len(expected) * len(fields)}',
                         'saved_rows': f'{len(actual["items"]) + len(actual_rewards)}/{len(expected) + len(expected_rewards)}'},
            'limitations': ['saved_currency_code_not_visible'] if display_only_rewards else [],
            'document_reference': reference, 'submitted_values': submitted,
            'actual': actual}
