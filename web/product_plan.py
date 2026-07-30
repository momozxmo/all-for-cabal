"""Pure Product drafts built from persisted Shop workspace metadata."""
from __future__ import annotations

import datetime as dt
import math
import re
import unicodedata
from zoneinfo import ZoneInfo


BANGKOK = ZoneInfo('Asia/Bangkok')
TAG_ORDER = ('EVENT', 'HOT', 'LIMITED', 'NEW', 'SALE')
_WEEKDAYS = {
    'monday': 0, 'mon': 0, 'จันทร์': 0,
    'tuesday': 1, 'tue': 1, 'อังคาร': 1,
    'wednesday': 2, 'wed': 2, 'พุธ': 2,
    'thursday': 3, 'thu': 3, 'พฤหัสบดี': 3, 'พฤหัส': 3,
    'friday': 4, 'fri': 4, 'ศุกร์': 4,
    'saturday': 5, 'sat': 5, 'เสาร์': 5,
    'sunday': 6, 'sun': 6, 'อาทิตย์': 6,
}


def _text(value) -> str:
    return str(value or '').strip()


def _norm(value) -> str:
    text = unicodedata.normalize('NFKC', _text(value)).casefold()
    return re.sub(r'[\s_\-/]+', ' ', text).strip()


def _digits(value) -> str:
    match = re.search(r'\d+', _text(value).replace(',', ''))
    return match.group(0) if match else ''


def _bangkok_now(now=None) -> dt.datetime:
    if now is None:
        return dt.datetime.now(BANGKOK)
    if now.tzinfo is None:
        return now.replace(tzinfo=BANGKOK)
    return now.astimezone(BANGKOK)


def _parse_time(value) -> dt.time | None:
    text = _text(value)
    for fmt in ('%H:%M:%S', '%H:%M'):
        try:
            return dt.datetime.strptime(text, fmt).time()
        except ValueError:
            pass
    return None


def _reset_at(reset_day, reset_time, now) -> str:
    day = _norm(reset_day)
    clock = _parse_time(reset_time)
    if not day or day in ('no reset', 'none', 'ไม่ reset', 'ไม่รีเซ็ต'):
        return ''
    if clock is None:
        return ''

    current = _bangkok_now(now)
    if day in ('everyday', 'every day', 'daily', 'ทุกวัน'):
        candidate = dt.datetime.combine(
            current.date(), clock, tzinfo=BANGKOK)
        if candidate <= current:
            candidate += dt.timedelta(days=1)
        return candidate.strftime('%Y-%m-%d %H:%M:%S')

    weekday = _WEEKDAYS.get(day)
    if weekday is None:
        return ''
    days = (weekday - current.weekday()) % 7
    candidate = dt.datetime.combine(
        current.date() + dt.timedelta(days=days),
        clock,
        tzinfo=BANGKOK,
    )
    if candidate <= current:
        candidate += dt.timedelta(days=7)
    return candidate.strftime('%Y-%m-%d %H:%M:%S')


def _limit_fields(meta: dict, now=None) -> dict:
    raw = _text(meta.get('limit_text'))
    normalized = _norm(raw)
    quantity = _digits(raw)
    warnings = []

    if not raw or any(token in normalized for token in (
            'no limit', 'unlimited', 'ไม่จำกัด')):
        limit_type = 'UNLIMITED'
        quantity = ''
    elif any(token in normalized for token in (
            'character', 'char', 'ตัวละคร')):
        limit_type = 'CHARACTER'
    elif any(token in normalized for token in (
            'account', 'player', 'ไอดี', 'บัญชี', ' id')):
        limit_type = 'PLAYER'
    else:
        limit_type = ''
        warnings.append('ตรวจสอบ Limit และเลือกประเภทผู้ซื้อด้วยตนเอง')

    reset_day = _text(meta.get('reset_day'))
    reset_norm = _norm(reset_day)
    if not reset_day or reset_norm in (
            'no reset', 'none', 'ไม่ reset', 'ไม่รีเซ็ต'):
        interval = ''
        reset_at = ''
    elif reset_norm in ('everyday', 'every day', 'daily', 'ทุกวัน'):
        interval = '1'
        reset_at = _reset_at(reset_day, meta.get('reset_time'), now)
    elif reset_norm in _WEEKDAYS:
        interval = '7'
        reset_at = _reset_at(reset_day, meta.get('reset_time'), now)
    else:
        interval = ''
        reset_at = ''
        warnings.append('ตรวจสอบ Reset Day ด้วยตนเอง: %s' % reset_day)
    if interval and not reset_at:
        warnings.append('ตรวจสอบ Reset Time ด้วยตนเอง')

    return {
        'limit_type': limit_type,
        'limit_quantity': quantity,
        'limit_reset_interval_days': interval,
        'limit_reset_at': reset_at,
        'warnings': warnings,
    }


def _tag_values(shop_label) -> list[str]:
    text = _norm(shop_label)
    compact = text.replace(' ', '')
    hits = set()
    if any(token in text for token in ('event', 'กิจกรรม')):
        hits.add('EVENT')
    if any(token in text for token in (
            'popular', 'must have', 'musthave', 'ยอดนิยม')):
        hits.add('HOT')
    if any(token in text for token in ('limited', 'จำกัด')):
        hits.add('LIMITED')
    if re.search(r'(^|\s)new($|\s)', text) or 'ใหม่' in text:
        hits.add('NEW')
    if ('%' in _text(shop_label)
            or any(token in text for token in (
                'sale', 'discount', 'off', 'ลด'))):
        hits.add('SALE')
    # Keep this local variable used: it makes "MustHave" match without adding a
    # hardcoded Product catalog.
    if 'musthave' in compact:
        hits.add('HOT')
    return [tag for tag in TAG_ORDER if tag in hits]


def _clean_prices(raw) -> list[dict]:
    output = []
    seen = set()
    for entry in raw or ():
        label = _text((entry or {}).get('source_label'))
        if not label:
            continue
        try:
            sale = float((entry or {}).get('sale_price'))
            original = float((entry or {}).get('original_price', sale))
        except (TypeError, ValueError):
            continue
        if (not math.isfinite(sale) or not math.isfinite(original)
                or sale < 0 or original < 0):
            continue
        key = _norm(label)
        if key in seen:
            continue
        seen.add(key)
        output.append({
            'source_label': label,
            'original_price': (
                int(original) if original.is_integer() else original),
            'sale_price': int(sale) if sale.is_integer() else sale,
        })
    return output


def _unique_warnings(values) -> list[str]:
    output = []
    seen = set()
    for value in values:
        text = _text(value)
        if text and text not in seen:
            seen.add(text)
            output.append(text)
    return output


def _draft_from_meta(group_key, meta, product, game, now=None) -> dict:
    current = _bangkok_now(now)
    name = _text(product.get('name') or meta.get('product') or group_key)
    start_at = _text(product.get('start_at'))
    if not start_at:
        start_at = current.strftime('%Y-%m-%d 00:00:00')
    end_at = _text(product.get('end_at'))
    bundle_id = _digits(product.get('bundle_id'))
    limit = _limit_fields(product, now=current)
    warnings = list(product.get('warnings') or ())
    warnings.extend(limit.pop('warnings'))
    if not end_at:
        warnings.append('ไม่พบ End Date/End Time ของ Product')

    draft = {
        'source_group_key': str(group_key),
        'source_sheet': _text(product.get('source_sheet')),
        'game': _text(game),
        'name_th': name,
        'name_en': name,
        'category_source': _text(product.get('category_label')),
        'category_id': '',
        'category_label': '',
        'details_th': '',
        'details_en': '',
        'start_at': start_at,
        'end_at': end_at,
        'bundle_id': bundle_id,
        'bundle_source': 'workbook' if bundle_id else '',
        'price_candidates': _clean_prices(product.get('price_candidates')),
        'prices': [],
        'tags': _tag_values(product.get('shop_label')),
        'is_enabled': False,
        'is_test_mode': True,
        'is_hidden': False,
        'position': '0',
        'warnings': _unique_warnings(warnings),
    }
    draft.update(limit)
    return draft


def build_products(group_meta: dict, game: str, now=None) -> list[dict]:
    drafts = []
    for group_key, meta in (group_meta or {}).items():
        product = (meta or {}).get('product_meta') or {}
        if not product:
            continue
        drafts.append(_draft_from_meta(
            str(group_key), meta or {}, product, game, now=now))
    return drafts


def count_products(rows: list[dict]) -> int:
    keys = set()
    for row in rows or ():
        meta = row.get('group_meta') or {}
        product = meta.get('product_meta') or {}
        sources = row.get('group_keys') or row.get('sources') or ()
        key = (meta.get('group_key') or product.get('source_group_key')
               or (sources[0] if sources else ''))
        if product and key:
            keys.add(str(key))
    return len(keys)
