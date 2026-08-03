# -*- coding: utf-8 -*-
"""Turn what the plan file said about a group into a draft Item Code.

Item Finder already reads the conditions block above each prize table — when
the code expires, how many codes per set, how many sets, whether a player may
use one twice — and keeps it per group. This module is the step that reads
those conditions the way an operator would and fills the form in advance.

Nothing here is final: every field it produces is editable on the page. The
point is that the operator checks numbers rather than copies them.

The rules are the desktop tool's (``itemcode_tool.prefill_from_event`` and
``prefill_from_pride``), which is where they were worked out against real
plans; only the shape of the answer is different, because the v2 form is.
"""
import re
from datetime import datetime

import config as cfg

#: The desktop caps a "once per set" plan here rather than drawing 10,000 sets.
MAX_SETS = 300


def _text(value):
    return str(value or '').strip()


def _int(value, default=0):
    text = _text(value)
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return default


def _stamp(moment):
    """A datetime the page's <input type="datetime-local"> will accept."""
    return moment.strftime('%Y-%m-%dT%H:%M:%S')


def code_name(meta):
    """``'<กิจกรรม> - <ชื่อกลุ่ม/ตาราง>'`` — what this code is called.

    The activity is the banner in the sheet's top-left corner and the group is
    the prize table's own heading; a sheet holds several tables and each is its
    own Item Code, so the name has to carry both.
    """
    if meta.get('is_pride'):
        block = meta.get('pride') or {}
        parts = [_text(block.get('event_name')), _text(block.get('title'))]
    else:
        parts = [_text(meta.get('activity')), _text(meta.get('reward'))]
    return ' - '.join(part for part in parts if part)


def _slug(name, game, notes):
    """``'storm-chaser-winner-rewards-msea'``.

    Aztek takes a-z, digits and hyphens only, so a name written in Thai leaves
    nothing behind — say so rather than hand over an empty required field.
    """
    made = re.sub(r'-+', '-', re.sub(r'[^a-z0-9-]', '',
                                     re.sub(r'\s+', '-', name.strip().lower()))).strip('-')
    if not made:
        notes.append('ชื่อเป็นภาษาไทยล้วน — สร้าง slug ให้ไม่ได้ พิมพ์เอง')
        return ''
    server = cfg.server_code(game)
    return '%s-%s' % (made, server) if server else made


def _window(meta, game, now, notes):
    """Start today, end on the date the file gave — or say why it could not."""
    from itemcode_tool import parse_expire

    raw = meta.get('pride', {}).get('expire') if meta.get('is_pride') \
        else meta.get('expire')
    end = parse_expire(raw, now)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if end is None:
        if _text(raw):
            notes.append('อ่านวันหมดอายุไม่ได้: %r — กรุณากรอกวันสิ้นสุดเอง'
                         % _text(raw))
        else:
            notes.append(
                'ไม่พบวันหมดอายุในเอกสาร — กรุณากรอกวันสิ้นสุดเอง')
        return _stamp(start), ''
    end = cfg.region_end_of_day(game, end)
    if end <= start:
        # Old plan files are re-used for the next run of the same activity, so
        # a date that has already been and gone is normal — and would make an
        # Item Code that is dead the moment it exists.
        notes.append('วันหมดอายุในไฟล์คือ %s ซึ่งผ่านมาแล้ว — แก้เวลาสิ้นสุดก่อนสร้าง'
                     % end.strftime('%Y-%m-%d'))
    return _stamp(start), _stamp(end)


def _how_many_sets(meta):
    """How the plan's counts turn into reward sets, and how many codes each.

    One set generated together, or one per "set" the plan names — the file says
    which through its conditions, and the desktop's reading of them is kept:
    not-across-sets or repeatable means one combined batch; once-per-set or
    can-cross means a set each.
    """
    per_set = _int(meta.get('codes_per_set'))
    sets = _int(meta.get('set_count'), 1) or 1
    total = _int(meta.get('total')) or (per_set * sets if per_set else 0)
    if sets <= 1:
        combined = True
    elif meta.get('once_per_set') or meta.get('cross_can'):
        combined = False
    elif meta.get('cross_cannot') or meta.get('can_repeat'):
        combined = True
    else:
        # More than one set and nothing decisive: keep them apart, which is the
        # answer that can be merged by hand. The other way round cannot.
        combined = False
    if combined:
        return 1, total, sets
    return max(1, min(sets, MAX_SETS)), per_set, sets


def _reward(name, uses_per_user, *, limited=False, quantity='', remaining='',
            code_type='1', code_list='', prefix='', num_codes=''):
    return {'name_th': name, 'name_en': name,
            'uses_per_user': uses_per_user, 'limited': limited,
            'quantity': quantity, 'remaining': remaining,
            'code_type': code_type, 'code_list': code_list,
            'prefix': prefix, 'num_codes': num_codes, 'bundle_id': ''}


def _from_event(meta, game, name, now, notes):
    blocks, per_base, asked_sets = _how_many_sets(meta)
    buffer = cfg.code_buffer(game)
    # The buffer covers codes that fail to deliver, and only the first two sets
    # get it — that is the operator's rule, not a rounding.
    item_total = (per_base * blocks + buffer * min(blocks, 2)) if per_base else 0
    if blocks < asked_sets:
        notes.append('ไฟล์สั่ง %d ชุด — สร้างให้ %d ชุด (เกินขีดจำกัด เพิ่มเองได้)'
                     % (asked_sets, blocks))
    if meta.get('cannot_repeat'):
        uses = '1'
    elif meta.get('can_repeat') and item_total:
        uses = str(item_total)
    else:
        uses = '1'
    server = bool(meta.get('unique_code'))
    rewards = []
    for index in range(blocks):
        each = str(per_base + (buffer if index < 2 else 0)) if per_base else ''
        reward_uses = each if meta.get('can_repeat') and each else '1'
        rewards.append(_reward(
            '%s %d' % (name, index + 1) if blocks > 1 else name, reward_uses,
            limited=bool(each) and server,
            quantity=each if server else '', remaining=each if server else '',
            code_type='2' if server else '1',
            num_codes=each if server else ''))
    start, end = _window(meta, game, now, notes)
    item_limit = str(item_total) if item_total > 0 else ''
    return {'name_th': name, 'name_en': name, 'slug': _slug(name, game, notes),
            'uses_per_user': uses,
            'limited': bool(item_limit),
            'quantity': item_limit, 'remaining': item_limit,
            'start_time': start, 'end_time': end, 'rewards': rewards}


def _from_pride(meta, game, name, now, notes):
    block = meta.get('pride') or {}
    server = bool(block.get('unique_code'))
    # A generated code is capped by how many were asked for; a fixed one by how
    # many times that single code may be redeemed.
    limit = _text(block.get('code_count') if server else block.get('refill_limit'))
    if block.get('note'):
        notes.append('หมายเหตุจากไฟล์: %s' % block['note'])
    fixed = _text(block.get('fix_code'))
    if not server and not fixed:
        notes.append('ไฟล์ไม่มีตัวโค้ด — ใส่รายการ Code เองก่อนสร้าง')
    start, end = _window(meta, game, now, notes)
    item_limit = limit if limit.isdigit() and int(limit) > 0 else ''
    return {'name_th': name, 'name_en': name, 'slug': _slug(name, game, notes),
            'uses_per_user': '1',
            'limited': bool(item_limit),
            'quantity': item_limit, 'remaining': item_limit,
            'start_time': start, 'end_time': end,
            'rewards': [_reward(
                name, '1', limited=bool(limit), quantity=limit, remaining=limit,
                code_type='2' if server else '1',
                code_list='' if server else fixed,
                num_codes=limit if server else '')]}


def build_itemcodes(group_meta, game, groups=None, now=None):
    """One draft Item Code per group, in the order the operator sees them.

    ``groups`` is the order the results table uses; groups the plan knows
    nothing about are skipped rather than turned into an empty form.
    """
    now = now or datetime.now()
    order = list(groups) if groups else list(group_meta)
    drafts = []
    for group in order:
        meta = group_meta.get(group)
        if not meta:
            continue
        name = code_name(meta) or group
        notes = []
        build = _from_pride if meta.get('is_pride') else _from_event
        draft = build(meta, game, name, now, notes)
        draft['group'] = group
        draft['notes'] = notes
        drafts.append(draft)
    return drafts
