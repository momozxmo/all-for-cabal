"""Read saved Aztek data without submitting or changing any form values."""
from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urlsplit


async def read_saved_bundle(page, url: str) -> dict:
    """Read every saved occurrence; item attributes come from fresh detail pages.

    Unknown reward cards are explicitly incomplete, never silently discarded as
    evidence of a passing check. This function only navigates and expands cards.
    """
    parsed = urlsplit(url)
    if not re.fullmatch(r'/combo/[^/]+/shop/bundles/[0-9]+', parsed.path):
        raise ValueError('invalid saved Bundle URL')
    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
    await page.get_by_role('heading', name='แก้ไข Bundle', exact=True).wait_for()
    bundle_id = parsed.path.rsplit('/', 1)[-1]
    if (urlsplit(page.url).path != parsed.path or not await page.get_by_text(
            re.compile(r'^ID:\s*' + re.escape(bundle_id) + r'$')).count()):
        raise ValueError('Bundle ID ของหน้าที่เปิดไม่ตรงกับรายการที่สร้าง')
    await page.get_by_role('button', name='ขยายทั้งหมด', exact=True).click()
    cards = page.locator('button[aria-label="ขยาย"][aria-expanded], '
                         'button[aria-label="ย่อ"][aria-expanded]')
    await cards.first.wait_for()
    rows = await cards.evaluate_all('''buttons => buttons.map(button => {
        const card = button.parentElement.parentElement;
        const label = [...card.querySelectorAll('label')].find(e => e.textContent.trim() === 'Item ID');
        const id = label?.parentElement.querySelector('p')?.textContent.trim();
        const qty = card.querySelector('input[name$=".quantity"]')?.value;
        return {id: id || null, qty: qty ?? null};
    })''')
    count_text = await page.get_by_text(
        re.compile(r'^รายการไอเท็ม\s*\(\s*\d+\s*\)$')).inner_text()
    expected_count = int(re.search(r'\d+', count_text).group())
    if len(rows) != expected_count:
        raise ValueError('จำนวนแถวที่อ่านไม่ครบ: %d/%d' % (len(rows), expected_count))
    items, unsupported = [], []
    detail = await page.context.new_page()
    try:
        for index, row in enumerate(rows):
            if not row['id'] or not re.fullmatch(r'[0-9]+', row['id']):
                unsupported.append(index + 1)
                continue
            if row['qty'] is None or not re.fullmatch(r'[0-9]+', row['qty']):
                raise ValueError('อ่านจำนวนรายการที่ %d ไม่สำเร็จ' % (index + 1))
            item_url = url.rsplit('/bundles/', 1)[0] + '/items/' + row['id']
            await detail.goto(item_url, wait_until='domcontentloaded', timeout=30000)
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
            items.append(row)
    finally:
        await detail.close()
    return {'items': items, 'complete': not unsupported, 'unsupported': unsupported}


async def recheck_saved_bundle(page, url: str, reference: dict | None,
                               submitted: dict) -> dict:
    """Compare independent original properties and submitted IDs, as row bags."""
    actual = await read_saved_bundle(page, url)
    reference = reference or {}
    expected = reference.get('items') or []
    fields = ('kind', 'option', 'duration', 'qty')
    missing = not expected or any(
        row.get(field) in (None, '') for row in expected for field in fields)
    # Unsupported checks must not be advertised as a complete pass.
    incomplete = (missing or not reference.get('game') or not submitted.get('game')
                  or not actual['complete']
                  or bool(reference.get('rewards') or submitted.get('rewards'))
                  or submitted.get('type') == 'RANDOM'
                  or any(row.get('tier') not in (None, '') or
                         row.get('rate') not in (None, '') for row in expected))

    def bag(rows, keys):
        return Counter(tuple(str(row.get(key, '')) for key in keys) for row in rows)

    differences = []
    if reference.get('game') and reference['game'] != submitted.get('game'):
        differences.append('game')
    if bag(submitted.get('items') or [], ('id', 'qty')) != bag(actual['items'], ('id', 'qty')):
        differences.append('submitted_items')
    if expected and len(expected) != len(actual['items']):
        differences.append('document_count')
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
                    str(source[key]) != str(row.get(key, '')) for key in fields
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
        different = (['missing_item'] if saved is None else [
            key for key in fields if original.get(key) not in (None, '')
            and str(original[key]) != str(saved.get(key, ''))])
        if saved is not None and sent is not None and str(sent.get('id')) != saved['id']:
            different.append('id')
        if saved is not None and sent is not None and str(sent.get('qty')) != saved['qty']:
            different.append('submitted_qty')
        rows.append({'source_row': original.get('source_row'), 'original': original,
                     'submitted': sent, 'actual': saved, 'different': different})
    for actual_index in unmatched_actual:
        rows.append({'source_row': None, 'original': None,
                     'submitted': submitted_for_actual.get(actual_index),
                     'actual': actual['items'][actual_index],
                     'different': ['extra_item']})
    present_properties = sum(row.get(key) not in (None, '')
                             for row in expected for key in fields)
    return {'outcome': 'mismatch' if differences else 'partial' if incomplete else 'passed',
            'incomplete': bool(incomplete), 'differences': differences,
            'rows': rows,
            'coverage': {'properties': f'{present_properties}/{len(expected) * len(fields)}',
                         'saved_rows': f'{len(actual["items"])}/{len(expected)}'},
            'document_reference': reference, 'submitted_values': submitted,
            'actual': actual}
