"""Read a direct-ID Bundle template without searching or writing to Aztek."""
from __future__ import annotations

import csv
from decimal import Decimal
from io import StringIO
from itertools import chain
from zipfile import ZipFile

from openpyxl import load_workbook

from web.validation import optional_text, positive_int_text, plain_decimal_text

HEADERS = ('Bundle Name', 'Item ID', 'Qty', 'Tier', 'Item Name')
TIERS = ('Common', 'Rare', 'Epic', 'Mystic', 'Legend')
MAX_ROWS = 10000
MAX_SHEETS = 50
MAX_ITEMS = 200
TYPES = ('FIXED', 'CHOICE', 'RANDOM')
REWARDS = ('CREDIT', 'DEBIT', 'MILEAGE', 'PLAYER_EXP')


def _blocks(rows, name):
    result = {'name': name, 'bundles': [], 'errors': []}
    bundles, current, seen = [], None, set()
    for number, values, formula in rows:
        if number > MAX_ROWS:
            raise ValueError('ข้อมูลเกิน 10,000 แถว กรุณาแบ่งชุด')
        if all(_blank(v) for v in values):
            continue
        try:
            if formula or any(isinstance(v, str) and v.startswith('=') for v in values):
                raise ValueError('ไม่รองรับสูตร กรุณาวางเป็นค่า (Values)')
            values = list(values)
            while values and _blank(values[-1]):
                values.pop()
            if len(values) == 2 and str(values[1]).strip().upper() in TYPES:
                title = optional_text(values[0] or '', 'Bundle Name', max_length=200)
                if not title:
                    raise ValueError('กรุณาระบุชื่อบันเดิล')
                current = {'name': title, 'type': str(values[1]).strip().upper(),
                           'deliver': True, 'items': [], 'rewards': [], 'source_row': number}
                bundles.append(current)
                seen = set()
                continue
            if current is None:
                raise ValueError('เริ่มด้วยชื่อบันเดิลและประเภท FIXED / CHOICE / RANDOM ใน 2 คอลัมน์')
            if len(values) > 4:
                raise ValueError('แถวรายการต้องมีไม่เกิน 4 คอลัมน์: ID / จำนวน / Tier / เรท')
            values += [None] * (4 - len(values))
            identity, qty, tier, rate = values
            qty = positive_int_text(1 if _blank(qty) else qty, 'Qty')
            tier = 'Common' if _blank(tier) else str(tier).strip().capitalize()
            if tier not in TIERS:
                raise ValueError('Tier ต้องเป็น Common, Rare, Epic, Mystic หรือ Legend')
            if current['type'] == 'RANDOM':
                if _blank(rate):
                    raise ValueError('RANDOM ต้องระบุเรทสุ่มในคอลัมน์ 4 ทุกแถว')
                rate = plain_decimal_text(str(rate).strip(), 'เรทสุ่ม',
                                          minimum=Decimal('0.001'), maximum=Decimal('100'), places=3)
            elif not _blank(rate):
                raise ValueError('เรทสุ่มใช้เฉพาะประเภท RANDOM กรุณาล้างคอลัมน์ 4')
            else:
                rate = ''
            if len(current['items']) + len(current['rewards']) >= MAX_ITEMS:
                raise ValueError('หนึ่งบันเดิลมีรายการได้ไม่เกิน 200 แถว')
            identity = str(identity).strip() if isinstance(identity, str) else identity
            prefix, separator, value = str(identity).partition(':')
            if separator and prefix.upper() in REWARDS:
                value = optional_text(value, 'Currency', max_length=500)
                if not value or value == '[ชื่อ Currency]':
                    raise ValueError('กรุณาระบุชื่อ Currency จริงหลังเครื่องหมาย :')
                current['rewards'].append({'type': prefix.upper(), 'value': value,
                    'qty': qty, 'tier': tier, 'rate': rate, 'source_row': number})
            else:
                item_id = positive_int_text(identity, 'Item ID (Currency ใช้ CREDIT: ชื่อ หรือชนิด Reward อื่น)')
                if item_id in seen:
                    raise ValueError('Item ID ซ้ำในบันเดิลเดียวกัน กรุณารวมจำนวนเป็นแถวเดียว')
                seen.add(item_id)
                current['items'].append({'id': item_id, 'qty': qty, 'tier': tier,
                    'rate': rate, 'name': '', 'shared': False, 'source_row': number})
        except ValueError as error:
            result['errors'].append({'row': number, 'message': str(error)})
            if len(result['errors']) >= 100:
                break
    if not result['errors']:
        for bundle in bundles:
            entries = bundle['items'] + bundle['rewards']
            if not entries:
                result['errors'].append({'row': bundle['source_row'], 'message': 'บันเดิลนี้ไม่มีรายการ'})
            elif bundle['type'] == 'RANDOM' and sum(Decimal(e['rate']) for e in entries) != 100:
                result['errors'].append({'row': bundle['source_row'], 'message': 'เรท RANDOM รวมต้องเท่ากับ 100%'})
    if not result['errors']:
        result['bundles'] = bundles
    return result


def read_bundle_text(text):
    delimiter = '\t' if '\t' in text else '|'
    try:
        rows = csv.reader(StringIO(text), delimiter=delimiter)
        sheet = _blocks(((i, values, False) for i, values in enumerate(rows, 1)), 'ข้อความที่วาง')
    except csv.Error:
        raise ValueError('ข้อความไม่ถูกต้อง กรุณาคัดลอกเซลล์ Excel ไม่เกิน 10,000 แถว') from None
    return {'sheets': [sheet]}


def _blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _sheet(sheet):
    result = {'name': sheet.title, 'bundles': [], 'errors': []}
    # Some Excel exporters leave a stale used-range hint. Read the actual rows.
    sheet.reset_dimensions()
    # A:D are block data; E:F are reserved empty columns. G contains the
    # downloadable template's instructions, not import data.
    rows = sheet.iter_rows(max_col=6)
    header = next(rows, ())
    if tuple(str(c.value or '').strip() for c in header[:5]) != HEADERS:
        return _blocks(((number, [c.value for c in cells], any(c.data_type in ('f', 'e') for c in cells))
                        for number, cells in enumerate(chain([header], rows), 1)), sheet.title)
    groups = {}
    seen = {}
    for number, cells in enumerate(rows, 2):
        if number > MAX_ROWS + 1:
            raise ValueError('Excel มีข้อมูลเกิน 10,000 แถวต่อ Sheet')
        values = [c.value for c in cells]
        if all(_blank(v) for v in values):
            continue
        try:
            if any(c.data_type in ('f', 'e') for c in cells):
                raise ValueError('ไม่รองรับสูตรหรือค่า Error กรุณาวางเป็นค่า (Values)')
            if any(not _blank(v) for v in values[5:]):
                raise ValueError('มีข้อมูลเกินคอลัมน์ของ Template กรุณาตรวจแถวนี้')
            name, item_id, qty, tier, item_name = values[:5]
            name = optional_text(name or '', 'Bundle Name', max_length=200)
            if not name:
                raise ValueError('กรุณาระบุ Bundle Name ทุกแถว')
            item_id = positive_int_text(item_id, 'Item ID')
            qty = positive_int_text(1 if _blank(qty) else qty, 'Qty')
            tier = 'Common' if _blank(tier) else tier
            if tier not in TIERS:
                raise ValueError('Tier ต้องเป็น Common, Rare, Epic, Mystic หรือ Legend')
            item_name = optional_text(item_name or '', 'Item Name', max_length=500)
            bundle = groups.setdefault(name, {
                'name': name, 'type': 'FIXED', 'deliver': True, 'items': [], 'rewards': []})
            ids = seen.setdefault(name, set())
            if item_id in ids:
                raise ValueError('Item ID ซ้ำในบันเดิลเดียวกัน กรุณารวมจำนวนเป็นแถวเดียว')
            if len(bundle['items']) >= MAX_ITEMS:
                raise ValueError('หนึ่งบันเดิลมีไอเทมได้ไม่เกิน 200 แถว')
            ids.add(item_id)
            bundle['items'].append({
                'id': item_id, 'qty': qty, 'tier': tier, 'name': item_name,
                'rate': '', 'shared': False, 'source_row': number})
        except ValueError as error:
            result['errors'].append({'row': number, 'message': str(error)})
            if len(result['errors']) >= 100:
                break
    # Never make a partially imported bundle look complete.
    if not result['errors']:
        result['bundles'] = list(groups.values())
    return result


def read_bundle_template(path):
    """Keep visible sheets separate and reject excessive decompressed content."""
    with ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 2000 or sum(e.file_size for e in entries) > 64 * 1024 * 1024:
            raise ValueError('ข้อมูลภายใน Excel ใหญ่เกินกำหนด กรุณาแบ่งไฟล์')
    book = load_workbook(path, read_only=True, data_only=False, keep_links=False)
    try:
        sheets = [s for s in book.worksheets if s.sheet_state == 'visible']
        if len(sheets) > MAX_SHEETS:
            raise ValueError('Excel มี Sheet มากกว่า 50 แท็บ กรุณาแบ่งไฟล์')
        return {'sheets': [_sheet(s) for s in sheets]}
    finally:
        book.close()
