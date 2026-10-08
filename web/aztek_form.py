# -*- coding: utf-8 -*-
"""Widget drivers for the Aztek v2 create forms.

Item Code and Event are different forms built from the same handful of v2
widgets, and this module knows how to drive those four:

* a radix **switch**, addressed by the label beside it — the ``<input
  type=checkbox>`` next to one is aria-hidden and covered, so clicking that
  only ever buys a timeout;
* a radix **select**, which still keeps a real ``<select>`` behind it, so it can
  be picked by its options rather than by its position;
* the **date and time** popover — a react-day-picker calendar whose cells carry
  ``data-day="YYYY-MM-DD"``, plus an hour dropdown and minute/second boxes
  labelled in Thai;
* the **bundle** dialog, which searches by name or id and reports each hit as
  ``…ID: <id>``.

Nothing here clicks a save button: writing to the live site stays a decision
the runners make.
"""
import json
import re
from datetime import datetime

from playwright.async_api import Error as PlaywrightError, expect
from web.aztek_locator import AztekLocatorError, require_control

# The calendar caption reads in English regardless of the page's own language.
# Aztek may render it as one label ("July 2026") or split month and year into
# separate labels ("Jul", "2026"), so both month forms are recognised.
MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July',
          'August', 'September', 'October', 'November', 'December')
_MONTH_INDEX = {
    alias.casefold(): index
    for index, month in enumerate(MONTHS)
    for alias in (month, month[:3])
}

# What an unset date button says.
DATE_PLACEHOLDER = 'เลือกวันและเวลา'

_DATETIME = re.compile(r'^\s*(\d{4})-(\d{2})-(\d{2})'
                       r'[ T](\d{1,2}):(\d{2})(?::(\d{2}))?\s*$')

# A label names its switch; the switch itself is a button somewhere near it.
# Walking up from the label finds the smallest box holding both, which is what
# keeps the four switches of a status section apart.
_SWITCH = """
(args) => {
  const want = document.querySelectorAll('label');
  const labels = [...want].filter(l =>
    l.textContent.replace(/\\s+/g, ' ').trim().replace(/\\s*\\*$/, '') === args.text);
  const label = labels[args.occurrence];
  if (!label) return 'no-label';
  let node = label;
  for (let depth = 0; depth < 5 && node; depth++) {
    const button = node.querySelector && node.querySelector('button[role="switch"]');
    if (button) {
      if ((button.getAttribute('aria-checked') === 'true') === args.want)
        return 'already';
      button.click();
      return 'clicked';
    }
    node = node.parentElement;
  }
  return 'no-switch';
}
"""


def parse_datetime(text):
    """``'2026-07-20 09:30:00'`` -> ``('2026-07-20', '09', '30', '00')``.

    Also takes what an ``<input type="datetime-local">`` produces
    (``2026-07-20T09:30``), because that is what the web form sends. Returns
    ``None`` for anything else rather than guessing at a date.
    """
    match = _DATETIME.match(str(text or ''))
    if not match:
        return None
    year, month, day, hour, minute, second = match.groups()
    return ('%s-%s-%s' % (year, month, day), '%02d' % int(hour), minute,
            second or '00')


async def fill(page, selector, value, log=None, label='', scope=None):
    """Put ``value`` in the first match, or say why it could not."""
    if value is None:
        return True
    target = (scope or page).locator(selector).first
    try:
        await target.wait_for(state='visible', timeout=6000)
        await target.fill(str(value))
        return True
    except Exception as exc:
        if log:
            log('กรอก "%s" ไม่สำเร็จ: %s' % (label or selector, exc), 'WARNING')
        return False


async def fill_by_id(scope, element_id, value, label, *, tags=('input',),
                     input_types=('text',)):
    """Fill one verified field and report whether its value reads back."""
    target = await require_control(
        scope, label, element_id=element_id, tags=tags, input_types=input_types)
    text = str(value)
    await target.fill(text)
    return await target.input_value() == text


async def set_switch(page, label_text, want, log=None, occurrence=0):
    """Turn the switch named by ``label_text`` on or off."""
    try:
        result = await page.evaluate(
            _SWITCH, {'text': label_text, 'want': bool(want),
                      'occurrence': occurrence})
    except Exception as exc:
        if log:
            log('ตั้งสวิตช์ "%s" ไม่สำเร็จ: %s' % (label_text, exc), 'WARNING')
        return False
    if result in ('no-label', 'no-switch'):
        if log:
            log('ไม่เจอสวิตช์ "%s" (%s)' % (label_text, result), 'WARNING')
        return False
    if result == 'clicked':
        # The fields a switch reveals arrive with an animation.
        await page.wait_for_timeout(1200)
    return True


async def set_switch_by_id(scope, element_id, want, label):
    """Set a verified switch, stopping when its ID or state contract breaks."""
    target = await require_control(
        scope, label, element_id=element_id, tags=('button',),
        roles=('switch',), input_types=('button',))
    state = await target.get_attribute('aria-checked')
    if state not in ('true', 'false'):
        raise AztekLocatorError('Aztek: %s อ่านสถานะสวิตช์ไม่ได้' % label)
    expected = 'true' if want else 'false'
    if state != expected:
        try:
            # Wait without clicking, then atomically validate and activate.
            # A locator shape filter alone does not protect an element that
            # mutates while Playwright is waiting for it to become enabled.
            await target.click(trial=True, timeout=5000)
            activated = await target.evaluate('''(button, expected) => {
                const state = button.getAttribute('aria-checked');
                if (button.tagName !== 'BUTTON' || button.type !== 'button' ||
                    button.getAttribute('role') !== 'switch' || button.disabled ||
                    !button.isConnected || !['true','false'].includes(state)) return false;
                if (state !== expected) button.click();
                return true;
            }''', expected)
            if not activated:
                raise AztekLocatorError('Aztek: %s ชนิด control เปลี่ยนระหว่างรอ' % label)
            await expect(target).to_have_attribute('aria-checked', expected, timeout=5000)
        except Exception as exc:
            raise AztekLocatorError('Aztek: %s สถานะสวิตช์ไม่ตรงที่ขอ' % label) from exc
    return True


async def select_by_id(scope, element_id, wanted, label):
    """Use the ID-bearing trigger's unique native sibling (no stable ID)."""
    trigger = await require_control(
        scope, label, element_id=element_id, tags=('button',),
        roles=('combobox',), input_types=('button',))
    native = trigger.locator('xpath=../select')
    try:
        # Verified Radix selects are aria-hidden and clipped to 1px, not
        # display:none. Retain Playwright's normal actionability checks.
        await native.wait_for(state='attached', timeout=5000)
        if await native.count() != 1 or await native.evaluate('e => e.multiple'):
            raise AztekLocatorError('Aztek: %s ตัวเลือกไม่ชัดเจน' % label)
        value = str(wanted)
        option = native.locator('option[value=%s]' % json.dumps(value))
        await option.wait_for(state='attached', timeout=5000)
        if await option.count() != 1:
            raise AztekLocatorError('Aztek: %s ไม่พบค่าที่ขอหรือพบหลายตัว' % label)
        option_label = await option.text_content()
        await native.select_option(value=value, timeout=5000)
        if await native.input_value() != value:
            raise AztekLocatorError('Aztek: %s ค่าที่เลือกไม่ตรงที่ขอ' % label)
        await expect(trigger).to_have_text(option_label, timeout=5000)
    except AztekLocatorError:
        raise
    except Exception as exc:
        raise AztekLocatorError('Aztek: %s เลือกค่าไม่ได้หรือยังไม่พร้อม' % label) from exc
    return True


async def select_by_options(page, wanted, options, log=None, index=0):
    """Choose ``wanted`` in the select recognised by the options it carries.

    v2 draws these as radix comboboxes over a real ``<select>``; telling them
    apart by their options survives a reorder of the page, which counting from
    the top would not.
    """
    xpath = 'xpath=//select[%s]' % ' and '.join(
        'option[contains(normalize-space(.),"%s")]' % text for text in options)
    target = page.locator(xpath).nth(index)
    for how in ('value', 'label'):
        try:
            await target.select_option(**{how: wanted})
            return True
        except Exception:
            continue
    if log:
        log('เลือก "%s" ไม่สำเร็จ' % wanted, 'WARNING')
    return False


async def select_after_label(page, label, value, log=None):
    """Select an exact live option value from the hidden select after ``label``.

    Product Category and limit widgets are searchable comboboxes visually, but
    keep a real select in the DOM. Selecting the fetched server ID on that
    select is both more stable and safer than clicking a text match.
    """
    target = page.locator(
        'xpath=//label[contains(normalize-space(.),"%s")]'
        '/following::select[1]' % label).first
    try:
        await target.select_option(value=str(value))
        return True
    except Exception as exc:
        if log:
            log('เลือก "%s" ไม่สำเร็จ: %s' % (label, exc), 'WARNING')
        return False


async def _show_month(page, day, log=None):
    """Page the calendar until the month holding ``day`` is on screen."""
    want = int(day[:4]) * 12 + int(day[5:7]) - 1
    captions = page.locator('.rdp-caption_label')
    arrows = page.locator('.rdp-months nav button')
    for _ in range(36):
        caption_texts = []
        for index in range(await captions.count()):
            caption_texts.append(
                (await captions.nth(index).inner_text()).strip())
        text = ' '.join(caption_texts).strip()
        name, _sep, year = text.rpartition(' ')
        month_index = _MONTH_INDEX.get(name.casefold())
        if month_index is None or not year.isdigit():
            if log:
                log('อ่านเดือนในปฏิทินไม่ออก: %r' % text, 'WARNING')
            return False
        shown = int(year) * 12 + month_index
        if shown == want:
            return True
        await arrows.nth(0 if shown > want else 1).click()
        await page.wait_for_timeout(400)
    if log:
        log('เลื่อนปฏิทินไปเดือนของ %s ไม่ถึง' % day, 'WARNING')
    return False


async def _click(locator, timeout=6000):
    """Click through the DOM.

    The popover can render below the fold of a long form, and Playwright will
    not click what it cannot scroll into view — it has no scrollable ancestor
    to work with. The page's own handler does not care where the element sits.
    """
    try:
        await locator.click(timeout=timeout)
    except Exception:
        await locator.evaluate('element => element.click()')


async def _set_time(page, hour, minute, second, log=None, label=''):
    """Fill the hour dropdown and the minute/second boxes of an open picker."""
    ok = True
    try:
        await _click(page.locator(
            'button[role="combobox"][aria-label="ชั่วโมง"]').first)
        await page.wait_for_timeout(600)
        await _click(page.locator('[role="option"]').filter(
            has_text=re.compile(r'^\s*%s\s*$' % hour)).first)
        await page.wait_for_timeout(400)
    except Exception as exc:
        if log:
            log('ตั้งชั่วโมง %s (%s) ไม่สำเร็จ: %s' % (hour, label, exc), 'WARNING')
        ok = False
    # Seconds first: the component rewrites the boxes below whichever one was
    # just committed, so setting minutes last is what makes both stick.
    for box, text in (('วินาที', second), ('นาที', minute)):
        try:
            field = page.locator('input[aria-label="%s"]' % box).first
            await field.fill(text)
            await field.press('Tab')
            await page.wait_for_timeout(250)
        except Exception as exc:
            if log:
                log('ตั้ง%s %s (%s) ไม่สำเร็จ: %s' % (box, text, label, exc),
                    'WARNING')
            ok = False
    return ok


async def set_datetime(page, trigger, value, log=None, label=''):
    """Set one date-and-time button to ``value``.

    The day is clicked by its ``data-day``, so no cell is ever counted and the
    greyed-out days of the neighbouring months cannot be hit by mistake. The
    button's own text is then read back: this picker is fiddly enough that
    "filled it" and "it took" are worth telling apart.
    """
    parts = parse_datetime(value)
    if parts is None:
        if log and str(value or '').strip():
            log('รูปแบบวันเวลาไม่ถูกต้อง (%s): %r' % (label, value), 'WARNING')
        return False
    day, hour, minute, second = parts
    try:
        await _click(trigger, timeout=8000)
        await page.wait_for_selector('.rdp-root', timeout=8000)
    except Exception as exc:
        if log:
            log('เปิดปฏิทิน "%s" ไม่ได้: %s' % (label, exc), 'WARNING')
        return False
    ok = True
    try:
        if not await _show_month(page, day, log):
            ok = False
        else:
            await _click(page.locator(
                'td.rdp-day:not(.rdp-outside)[data-day="%s"] button' % day).first)
            await page.wait_for_timeout(400)
    except Exception as exc:
        if log:
            log('เลือกวันที่ %s (%s) ไม่สำเร็จ: %s' % (day, label, exc), 'WARNING')
        ok = False

    wanted = '%s %s %s %s:%s:%s' % (day[8:], MONTHS[int(day[5:7]) - 1][:3],
                                    day[:4], hour, minute, second)
    shown = ''
    for attempt in range(2):
        if not await _set_time(page, hour, minute, second, log, label):
            ok = False
        try:
            shown = (await trigger.inner_text()).strip()
        except Exception:
            shown = ''
        if shown == wanted:
            break
        if attempt == 0 and log:
            log('ตั้ง %s ได้ %r (ขอ %r) — ลองใหม่' % (label, shown, wanted),
                'WARNING')
    await page.keyboard.press('Escape')
    await page.wait_for_timeout(400)
    if shown != wanted:
        if log:
            log('ตั้ง "%s" ไม่ตรง: ได้ %r ขอ %r' % (label, shown, wanted),
                'WARNING')
        return False
    if log:
        log('ตั้ง %s = %s' % (label, shown), 'INFO')
    return ok


async def activate_verified_button(target, label, role=None):
    """Activate an actionable non-submit button after its scoped lookup."""
    try:
        await target.click(trial=True, timeout=5000)
        activated = await target.evaluate('''(button, role) => {
            if (button.tagName !== 'BUTTON' || button.type !== 'button' ||
                button.disabled || !button.isConnected ||
                (role && button.getAttribute('role') !== role)) return false;
            button.click();return true;
        }''', role)
    except PlaywrightError as exc:
        raise AztekLocatorError('Aztek: %s ปุ่มยังไม่พร้อมหรือคลิกไม่ได้' % label) from exc
    if not activated:
        raise AztekLocatorError('Aztek: %s ชนิดปุ่มเปลี่ยนระหว่างรอ' % label)


async def _related_popup(page, trigger, role, label):
    # Runtime IDs are used only as the trigger's current ARIA relationship.
    await expect(trigger).to_have_attribute('aria-controls', re.compile(r'\S+'), timeout=5000)
    relation = await trigger.get_attribute('aria-controls')
    if len(relation.split()) != 1:
        raise AztekLocatorError('Aztek: %s ความสัมพันธ์ popup ไม่ชัดเจน' % label)
    popup = await require_control(
        page, label, selector='[id=%s]' % json.dumps(relation), roles=(role,))
    await expect(popup).to_have_attribute('data-state', 'open', timeout=5000)
    return popup


async def set_datetime_by_id(page, scope, element_id, value, log=None, label=''):
    """Set a verified date trigger through its own calendar/time popovers."""
    parts = parse_datetime(value)
    if parts is None:
        return False
    day, hour, minute, second = parts
    try:
        datetime.fromisoformat('%sT%s:%s:%s' % parts)
    except ValueError:
        return False
    dialog = None
    try:
        trigger = await require_control(
            scope, label, element_id=element_id, tags=('button',), input_types=('button',))
        await activate_verified_button(trigger, label)
        dialog = await _related_popup(page, trigger, 'dialog', label)
        # These controls have no stable IDs in audited PC/M TH/SEA calendars.
        for caption, value in (('Year', day[:4]), ('Month', str(int(day[5:7]) - 1))):
            select = await require_control(
                dialog, '%s: %s' % (label, caption),
                selector='select[aria-label="Choose the %s"]' % caption,
                tags=('select',), input_types=('select-one',))
            await select.select_option(value=value, timeout=5000)
            if await select.input_value() != value:
                raise AztekLocatorError('Aztek: %s เดือน/ปีไม่ตรงที่ขอ' % label)
        date_button = await require_control(
            dialog, '%s: วันที่' % label,
            selector='td[role="gridcell"][data-day=%s] button' % json.dumps(day),
            tags=('button',), input_types=('button',))
        await activate_verified_button(date_button, label)
        wanted = '%s %s %s %s:%s:%s' % (
            day[8:], MONTHS[int(day[5:7])-1][:3], day[:4], hour, minute, second)
        for attempt in range(2):
            hours = await require_control(
                dialog, '%s: ชั่วโมง' % label,
                selector='button[aria-label="ชั่วโมง"]', tags=('button',),
                roles=('combobox',), input_types=('button',))
            await activate_verified_button(hours, label, 'combobox')
            choices = await _related_popup(page, hours, 'listbox', label)
            option = await require_control(
                choices, '%s: ชั่วโมง %s' % (label, hour),
                selector='[role="option"]:text-is(%s)' % json.dumps(hour),
                tags=('div',), roles=('option',))
            await option.and_(choices.locator('div[role="option"]')).click(timeout=5000)
            await expect(hours).to_have_text(hour, timeout=5000)
            # Commit seconds before minutes, preserving the widget's order.
            for caption, text in (('วินาที', second), ('นาที', minute)):
                field = await require_control(
                    dialog, '%s: %s' % (label, caption),
                    selector='input[aria-label=%s]' % json.dumps(caption, ensure_ascii=False),
                    tags=('input',), input_types=('text',))
                await field.fill(text, timeout=5000)
                await field.press('Tab', timeout=5000)
            try:
                await expect(trigger).to_have_text(wanted, timeout=1000)
                return True
            except AssertionError:
                if attempt == 1:
                    if log:
                        log('ตั้ง "%s" ไม่ตรง: ขอ %s' % (label, wanted), 'WARNING')
                    return False
    except AztekLocatorError:
        raise
    except Exception as exc:
        raise AztekLocatorError('Aztek: %s ปฏิทิน/เวลายังไม่พร้อมหรือ contract เปลี่ยน' % label) from exc
    finally:
        if dialog is not None and await dialog.is_visible():
            await dialog.press('Escape', timeout=5000)


async def pick_reward_bundle(page, form, index, bundle_id, label, log=None):
    """Use the audited no-ID Bundle widget in the active reward's form.

    The trigger, search and rows have no stable IDs. Runtime popup IDs are
    followed only through the trigger's ARIA relationship, never cached.
    """
    wanted = str(bundle_id or '').strip()
    if not re.fullmatch(r'[0-9]+', wanted):
        return False
    try:
        anchor_id = 'rewards.%d.name_th' % index
        anchor = await require_control(
            form, label, element_id=anchor_id, tags=('input',), input_types=('text',))
        code_id = 'rewards.%d.is_generate_code' % index
        await require_control(
            form, label, element_id=code_id, tags=('button',), roles=('combobox',),
            input_types=('button',))
        card = await require_control(
            anchor, label,
            selector='xpath=ancestor::div[.//*[@id="%s"]][1]' % code_id, tags=('div',))
        owning_form = await form.element_handle(timeout=5000)
        if owning_form is None or not await card.evaluate(
                '(owner, form) => owner.closest("form") === form', owning_form):
            raise AztekLocatorError('Aztek: %s ขอบเขตชุดรางวัลอยู่นอกฟอร์ม' % label)
        section = await require_control(
            card, label, selector='xpath=.//label[normalize-space(.)="Bundle *"]/parent::div',
            tags=('div',))
        change_selector = 'xpath=.//button[normalize-space(.)="เปลี่ยน"]'
        badge_selector = 'xpath=.//div[button[normalize-space(.)="เปลี่ยน"]]/span'
        if await section.locator(change_selector).count():
            change = await require_control(
                section, label + ': เปลี่ยน', selector=change_selector,
                tags=('button',), input_types=('button',))
            if await section.locator('xpath=.//button[normalize-space(.)="เลือก bundle"]').count():
                raise AztekLocatorError('Aztek: %s สถานะตัวเลือกไม่ชัดเจน' % label)
            badge = await require_control(
                section, label + ': ค่าที่เลือก', selector=badge_selector, tags=('span',))
            await expect(badge).to_have_text(re.compile(r'^\s*#[0-9]+\s+—\s+\S'), timeout=5000)
            current = re.match(r'^\s*#([0-9]+)\s+—', await badge.inner_text()).group(1)
            if current == wanted:
                if log:
                    log('Bundle %s ถูกเลือกอยู่แล้ว' % wanted, 'INFO')
                return True
            await activate_verified_button(change, label + ': เปลี่ยน')
            await expect(change).to_have_count(0, timeout=5000)
        trigger = await require_control(
            section, label, selector='xpath=.//button[normalize-space(.)="เลือก bundle"]',
            tags=('button',), input_types=('button',))
        await expect(trigger).to_have_attribute('aria-haspopup', 'dialog', timeout=5000)
        await activate_verified_button(trigger, label)
        dialog = await _related_popup(page, trigger, 'dialog', label)
        if await dialog.evaluate('el => el.tagName') != 'DIV':
            raise AztekLocatorError('Aztek: %s ชนิด dialog ไม่ตรงกับที่ตรวจไว้' % label)
        search = await require_control(
            dialog, label + ': ค้นหา', selector='input[placeholder="ค้นหาด้วยชื่อหรือ id"]',
            tags=('input',), input_types=('text',))
        await search.fill(wanted)
        if await search.input_value() != wanted:
            raise AztekLocatorError('Aztek: %s คำค้นไม่ตรงที่ขอ' % label)
        hit = await require_control(
            dialog, label + ': รายการ',
            selector='xpath=.//button[span[normalize-space(.)="ID: %s"]]' % wanted,
            tags=('button',), input_types=('button',))
        await require_control(
            card, label, element_id=anchor_id, tags=('input',), input_types=('text',))
        await activate_verified_button(hit, label)
        await expect(dialog).to_be_hidden(timeout=5000)
        badge = await require_control(
            section, label + ': ค่าที่เลือก',
            selector=badge_selector, tags=('span',))
        await expect(badge).to_have_text(
            re.compile(r'^\s*#%s\s+—\s+\S' % re.escape(wanted)), timeout=5000)
        await require_control(
            card, label, element_id=anchor_id, tags=('input',), input_types=('text',))
    except AztekLocatorError:
        raise
    except (AssertionError, PlaywrightError) as exc:
        raise AztekLocatorError('Aztek: %s ตัวเลือกยังไม่พร้อมหรือค่าที่เลือกไม่ตรง' % label) from exc
    if log:
        log('ผูก bundle %s แล้ว' % wanted, 'SUCCESS')
    return True


async def pick_bundle(page, scope, bundle_id, log=None):
    """Attach one bundle to a reward set through the picker dialog.

    v2 holds a single bundle per reward set: once one is chosen the button
    reads "เปลี่ยน" rather than offering to add another.
    """
    wanted = str(bundle_id or '').strip()
    if not wanted:
        return False
    trigger = scope.locator(
        'button:has-text("เลือก bundle"), button:has-text("เปลี่ยน")').first
    try:
        await trigger.click(timeout=8000)
        dialog = page.locator('[role="dialog"]').last
        await dialog.wait_for(state='visible', timeout=8000)
        box = dialog.locator(
            'input[placeholder="ค้นหาด้วยชื่อหรือ id"],'
            'input[placeholder*="ค้นหา"],input[type="search"]').first
        await box.wait_for(state='visible', timeout=8000)
        await box.fill(wanted)
        await page.wait_for_timeout(2000)
    except Exception as exc:
        if log:
            log('เปิดตัวเลือก bundle ไม่ได้: %s' % exc, 'WARNING')
        return False
    # Anchored at the end of the row: "…ID: 2081" must not match id 20810.
    hit = dialog.locator('button').filter(
        has_text=re.compile(r'ID:\s*%s\s*$' % re.escape(wanted)))
    try:
        if await hit.count() == 0:
            if log:
                log('ไม่เจอ bundle เลข %s ในรายการ' % wanted, 'WARNING')
            await page.keyboard.press('Escape')
            return False
        await hit.first.click(timeout=6000)
        await page.wait_for_timeout(1000)
    except Exception as exc:
        if log:
            log('เลือก bundle %s ไม่สำเร็จ: %s' % (wanted, exc), 'WARNING')
        return False
    if log:
        log('ผูก bundle %s แล้ว' % wanted, 'SUCCESS')
    return True


def reward_card(page, index):
    """The block of the form holding reward set ``index`` (0-based).

    Found from a field only that reward set can have, then up to the smallest
    box that also holds its bundle button — so a second reward set can never be
    filled through the first one's controls.
    """
    return page.locator(
        'xpath=//input[@name="rewards.%d.name_th"]'
        '/ancestor::*[.//button[contains(.,"เลือก bundle")'
        ' or contains(.,"เปลี่ยน")]][1]' % index)
