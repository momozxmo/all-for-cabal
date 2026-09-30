"""Read saved Aztek data without submitting or changing any form values."""
from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit


class SessionExpiredError(RuntimeError):
    """Aztek redirected a read-only verification to its login page."""


def _reward_display(value) -> str:
    """Aztek's saved card displays a name, while its picker includes a slug."""
    text = str(value or '')
    match = re.fullmatch(r'[a-z0-9_-]+ - (.+)', text)
    return match.group(1) if match else text


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
    await page.get_by_role('heading', name='แก้ไข Bundle', exact=True).wait_for()
    bundle_id = parsed.path.rsplit('/', 1)[-1]
    if (urlsplit(page.url).path != parsed.path or not await page.get_by_text(
            re.compile(r'^ID:\s*' + re.escape(bundle_id) + r'$')).count()):
        raise ValueError('Bundle ID ของหน้าที่เปิดไม่ตรงกับรายการที่สร้าง')
    expand_all = page.get_by_role('button', name='ขยายทั้งหมด', exact=True)
    if await expand_all.count():
        await expand_all.click()
    cards = page.locator('button[aria-label="ขยาย"][aria-expanded], '
                         'button[aria-label="ย่อ"][aria-expanded]')
    await cards.first.wait_for()
    rows = await cards.evaluate_all('''buttons => buttons.map(button => {
        const card = button.parentElement.parentElement;
        const field = name => [...card.querySelectorAll('label')]
          .find(e => e.textContent.trim().replace(/\\s*\\*$/, '') === name)?.parentElement;
        const id = field('Item ID')?.querySelector('p')?.textContent.trim();
        const qty = card.querySelector('input[name$=".quantity"]')?.value;
        const badge = [...button.querySelectorAll('span')].map(e => e.textContent.trim())
          .find(v => ['ITEM','CREDIT','DEBIT','MILEAGE','PLAYER_EXP','PLAYER_EXPERIENCE',
            'WALLET_CREDIT','WALLET','WALLET_MILEAGE'].includes(v));
        const tier = [...card.querySelectorAll('select')].find(s =>
          [...s.options].some(o => o.textContent.trim() === 'Common'))?.selectedOptions[0]?.textContent.trim();
        const rate = card.querySelector('input[name$=".secret_chance"]')?.value;
        const value = field('ชื่อ')?.querySelector('p')?.textContent.trim()
          || button.querySelector('p')?.textContent.trim();
        const types = {PLAYER_EXPERIENCE:'PLAYER_EXP',WALLET_CREDIT:'CREDIT',
          WALLET:'DEBIT',WALLET_MILEAGE:'MILEAGE'};
        return {type: types[badge] || badge || (id ? 'ITEM' : null), id: id || null,
          value: value || null, qty: qty ?? null, tier: tier ?? null, rate: rate ?? null};
    })''')
    count_text = await page.get_by_text(
        re.compile(r'^รายการไอเท็ม\s*\(\s*\d+\s*\)$')).inner_text()
    expected_count = int(re.search(r'\d+', count_text).group())
    if len(rows) != expected_count:
        raise ValueError('จำนวนแถวที่อ่านไม่ครบ: %d/%d' % (len(rows), expected_count))
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
            await detail.goto(item_url, wait_until='domcontentloaded', timeout=30000)
            if any(part in urlsplit(detail.url).path.lower() for part in ('/login', '/signin')):
                raise SessionExpiredError('เซสชัน Aztek หมดอายุ กรุณาเชื่อมใหม่ก่อนตรวจซ้ำ')
            await detail.get_by_role('heading', name='แก้ไข Item', exact=True).wait_for()
            if (urlsplit(detail.url).path != urlsplit(item_url).path or
                    not await detail.get_by_text(re.compile(
                        r'^ID:\s*' + re.escape(row['id']) + r'$')).count()):
                raise ValueError('Item ID ของหน้ารายละเอียดไม่ตรงกับ Bundle')
            for key, selector in [('kind', '#item-game-item-id'),
                                  ('option', '#item-option'),
                                  ('duration', '#duration-index')]:
                field = detail.locator(selector)
                await field.wait_for(state='visible')
                value = await field.input_value()
                if not re.fullmatch(r'[0-9]+', value):
                    raise ValueError('อ่าน %s ของ Item %s ไม่สำเร็จ' % (key, row['id']))
                row[key] = value
            items.append({key: value for key, value in row.items()
                          if key in ('id', 'qty', 'kind', 'option', 'duration', 'tier', 'rate')
                          and value is not None})
    finally:
        await detail.close()
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
    remaining_rewards = list(actual_rewards)
    for original in expected_rewards:
        identity = ('type', 'value')
        match_index = next((index for index, saved in enumerate(remaining_rewards)
                            if all(same(key, original.get(key), saved.get(key))
                                   for key in identity)), None)
        saved = remaining_rewards.pop(match_index) if match_index is not None else None
        sent = next((entry for entry in submitted.get('rewards') or []
                     if all(same(key, original.get(key), entry.get(key))
                            for key in identity)), None)
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
        for saved in remaining_rewards:
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
