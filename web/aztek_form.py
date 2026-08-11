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
import re

# The calendar caption reads in English regardless of the page's own language
# ("July 2026"), so the month is matched against this list rather than parsed.
MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July',
          'August', 'September', 'October', 'November', 'December')

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
    caption = page.locator('.rdp-caption_label').first
    arrows = page.locator('.rdp-months nav button')
    for _ in range(36):
        text = (await caption.inner_text()).strip()
        name, _sep, year = text.rpartition(' ')
        if name not in MONTHS or not year.isdigit():
            if log:
                log('อ่านเดือนในปฏิทินไม่ออก: %r' % text, 'WARNING')
            return False
        shown = int(year) * 12 + MONTHS.index(name)
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
