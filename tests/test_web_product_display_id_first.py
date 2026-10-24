"""Product display, calendar and limit contracts through public form/runner seams."""
import asyncio
import re

import pytest

from web.aztek_locator import AztekLocatorError
from web.product_runner import ProductBuilder
from test_web_itemcode_id_first import calendar_html, routed_runner_browser
from test_web_product_id_first import BASIC_DISPLAY, HEADER_HTML, SPEC, CREATE_URLS, exercise_form


DISPLAY_CONTROLS = '''
  <div><button id="is_hidden" type="button" role="switch" aria-checked="false"
    onclick="this.setAttribute('aria-checked',this.getAttribute('aria-checked')==='true'?'false':'true')">เปลี่ยนข้อความแล้ว</button></div>
  <section><button id="is_enabled" type="button" role="switch" aria-checked="true"
    onclick="this.setAttribute('aria-checked',this.getAttribute('aria-checked')==='true'?'false':'true')">สถานะใหม่</button></section>
  <button id="is_test_mode" type="button" role="switch" aria-checked="true"
    onclick="this.setAttribute('aria-checked',this.getAttribute('aria-checked')==='true'?'false':'true')">ทดสอบใหม่</button>
  <div><input id="position" name="changed-position" type="number" value="0"></div>
'''


def display_html():
    outside = ''.join('<button id="%s" type="button" role="switch" aria-checked="false" data-display-decoy></button>'
                      % field for field in ('is_enabled', 'is_test_mode', 'is_hidden'))
    decoys = ''.join('''<div><label>%s</label><button type="button" role="switch"
        aria-checked="false" data-display-decoy
        onclick="this.setAttribute('aria-checked','true')"></button></div>''' % label
                    for label in ('เปิดใช้งาน', 'โหมดทดสอบ', 'ซ่อนสินค้า'))
    return (HEADER_HTML.replace('</aside>', outside + '</aside>')
            .replace(BASIC_DISPLAY,
                     '<input name="position" type="number" value="91" data-display-decoy>' + decoys + DISPLAY_CONTROLS))


@pytest.mark.parametrize('url', CREATE_URLS)
def test_product_display_uses_form_ids_not_old_labels_or_named_position(url):
    # A regression to label/name or page-wide ID lookup changes these decoys.
    missing, error, values = exercise_form(display_html(), url=url, spec={
        **SPEC, 'is_enabled': False, 'is_test_mode': False, 'is_hidden': True, 'position': '3'})
    assert error is None
    assert values['display'] == ['false', 'false', 'true', '3']
    assert values['displayDecoys'] == ['false', 'false', 'false', '91', 'false', 'false', 'false']
    assert values['submits'] == ['0']


def date_html(base=None):
    widget = calendar_html()
    widget = widget[widget.index('<div role="dialog" id="other-calendar"'):]
    widget = widget.replace('for(const number of [8,27,28])', 'for(const number of [17,27,28])')
    buttons = ''
    outside = ''
    for field, label in [('hide_at', 'เวลาหยุดขาย (GMT+7)'),
                         ('limit_reset_at', 'วันล่าสุดที่ทำการรีเซ็ทรอบการขาย (GMT+7)'),
                         ('show_at', 'เวลาเริ่มขาย (GMT+7)')]:
        buttons += '''<label>%s</label><button type="button"
          onclick="document.body.dataset.dateDecoyClicks='1'">old-label decoy</button>
          <section><label>Changed date label</label><button id="%s" type="button"
          aria-haspopup="dialog" onclick="openCalendar(this)">เลือกวันและเวลา</button></section>''' % (label, field)
        outside += '<button id="%s" type="button" onclick="document.body.dataset.dateDecoyClicks=1">outside calendar</button>' % field
    return ((display_html() if base is None else base).replace('</aside>', outside + '</aside>')
            .replace('</form>', buttons + '</form>') + widget)


@pytest.mark.parametrize('url', CREATE_URLS)
def test_product_sale_window_uses_own_date_ids_and_preserves_last_second(url):
    # Old labels and a different open calendar must not steal either window.
    missing, error, values = exercise_form(date_html(), url=url, spec={
        **SPEC, 'start_at': '2026-10-17 00:00:00', 'end_at': '2027-09-28 23:59:59'})
    assert error is None
    assert values['dates'] == ['17 Oct 2026 00:00:00', '28 Sep 2027 23:59:59', 'เลือกวันและเวลา']
    assert values['dateDecoyClicks'] == '0'
    assert values['calendarDecoys'] == ['17', '16']
    assert 'วันเริ่มขาย' not in missing and 'วันสิ้นสุด' not in missing
    assert values['submits'] == ['0']


def limit_html(base=None):
    controls = '''<div><label>รูปแบบการจำกัดการซื้อ</label>
      <select data-limit-decoy><option value="NONE">ไม่จำกัด</option><option value="PLAYER">PLAYER</option></select></div>
      <input name="limit_per" type="number" value="91" data-limit-decoy>
      <input name="limit_reset_interval_days" type="number" value="92" data-limit-decoy>
      <section><div><label>Changed purchase limit label</label>
        <button id="purchase_limit_type" type="button" role="combobox">ไม่จำกัด</button>
        <select aria-hidden="true" tabindex="-1"
          style="position:absolute;width:1px;height:1px;clip:rect(0,0,0,0)"
          onchange="this.previousElementSibling.textContent=this.selectedOptions[0].textContent;document.querySelector('[data-limited-fields]').hidden=this.value==='NONE'">
          <option value="NONE">ไม่จำกัด</option><option value="PLAYER">PLAYER</option><option value="CHARACTER">CHARACTER</option>
        </select>
      </div><div data-limited-fields hidden><input id="limit_per" name="changed-limit" type="number" min="0" value="8"></div>
      <div><input id="limit_reset_interval_days" name="changed-interval" type="number" value="9"></div></section>'''
    return date_html(base).replace('</form>', controls + '</form>')


@pytest.mark.parametrize('url', CREATE_URLS)
def test_product_limit_uses_id_association_and_resets_its_own_calendar(url):
    # Selecting the old label's decoy cannot expose/fill the real quantity.
    missing, error, values = exercise_form(limit_html(), url=url, spec={
        **SPEC, 'limit_type': 'PLAYER', 'limit_quantity': '10',
        'limit_reset_interval_days': '7', 'limit_reset_at': '2026-10-17 03:04:05'})
    assert error is None
    assert values['limitMode'] == 'PLAYER'
    assert values['numbers'] == ['10', '7']
    assert values['dates'][2] == '17 Oct 2026 03:04:05'
    assert values['limitDecoys'] == ['NONE', '91', '92']
    assert 'ประเภทการจำกัด' not in missing and 'จำนวนที่ซื้อได้' not in missing
    assert values['submits'] == ['0']


FULL_SPEC = {**SPEC, 'is_enabled': False, 'is_test_mode': False, 'is_hidden': True,
             'position': '3', 'start_at': '2026-10-17 00:00:00', 'end_at': '2027-09-28 23:59:59',
             'limit_type': 'PLAYER', 'limit_quantity': '10', 'limit_reset_interval_days': '7',
             'limit_reset_at': '2026-10-17 03:04:05'}
CONTROLS = (
    ('is_enabled', 'เปิดใช้งาน'), ('is_test_mode', 'โหมดทดสอบ'), ('is_hidden', 'ซ่อนสินค้า'),
    ('position', 'ตำแหน่ง'), ('show_at', 'วันเริ่มขาย'), ('hide_at', 'วันสิ้นสุด'),
    ('purchase_limit_type', 'ประเภทการจำกัด'), ('limit_per', 'จำนวนที่ซื้อได้'),
    ('limit_reset_interval_days', 'รีเซ็ตทุกกี่วัน'), ('limit_reset_at', 'รีเซ็ตล่าสุด'),
)


@pytest.mark.parametrize(('field', 'label'), CONTROLS)
@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'wrong-type'])
def test_product_broken_display_date_or_limit_id_stops_without_fallback(field, label, fault):
    before, form = limit_html().split('<main>', 1)
    if fault == 'missing':
        form = form.replace('id="%s"' % field, 'data-removed-id="%s"' % field)
    elif fault == 'duplicate':
        form = form.replace('</form>', '<input hidden id="%s"></form>' % field)
    else:
        # A button becoming submit is as unsafe as a number becoming text.
        form = re.sub(r'(<(?:button|input) id="%s"[^>]*type=")[^"]*' % field,
                      r'\g<1>' + ('text' if field in ('position', 'limit_per', 'limit_reset_interval_days') else 'submit'), form)
    _missing, error, values = exercise_form(before + '<main>' + form, spec=FULL_SPEC)
    assert isinstance(error, AztekLocatorError)
    assert label in str(error)
    assert values['displayDecoys'] == ['false', 'false', 'false', '91', 'false', 'false', 'false']
    assert values['limitDecoys'] == ['NONE', '91', '92']
    assert values['dateDecoyClicks'] == '0'
    assert values['submits'] == ['0']


def test_product_display_keeps_defaults_and_unlimited_ignores_hidden_limit_controls():
    html = limit_html().replace('id="limit_per"', 'data-unused-id="limit_per"')
    html = html.replace('id="limit_reset_interval_days"', 'data-unused-id="limit_reset_interval_days"')
    html = html.replace('id="limit_reset_at"', 'data-unused-id="limit_reset_at"')
    missing, error, values = exercise_form(html, spec={**SPEC, 'limit_type': 'UNLIMITED'})
    assert error is None
    assert values['display'] == ['false', 'true', 'false', '0']
    assert values['limitMode'] == 'ไม่จำกัด'
    assert missing == ['หมวดหมู่', 'สกุลเงิน', 'วันเริ่มขาย', 'วันสิ้นสุด', 'Bundle']
    assert values['limitDecoys'] == ['NONE', '91', '92']
    assert values['submits'] == ['0']


@pytest.mark.parametrize(('field', 'label'), [('position', 'ตำแหน่ง'), ('limit_per', 'จำนวนที่ซื้อได้')])
def test_product_rejected_number_readback_is_incomplete(field, label):
    html = limit_html().replace('id="%s"' % field, 'id="%s" oninput="this.value=8"' % field)
    missing, error, values = exercise_form(html, spec=FULL_SPEC)
    assert error is None
    assert label in missing
    assert values['submits'] == ['0']


@pytest.mark.parametrize('field', ['show_at', 'hide_at', 'limit_reset_at'])
def test_product_invalid_datetime_reports_affected_field_without_opening_it(field):
    key = {'show_at':'start_at', 'hide_at':'end_at', 'limit_reset_at':'limit_reset_at'}[field]
    label = dict(CONTROLS)[field]
    missing, error, values = exercise_form(limit_html(), spec={**FULL_SPEC, key:'2026-02-30 23:59:59'})
    assert error is None
    assert label in missing
    assert values['dates'][['show_at','hide_at','limit_reset_at'].index(field)] == 'เลือกวันและเวลา'
    assert values['dateDecoyClicks'] == '0' and values['submits'] == ['0']


def test_product_waits_for_late_position_without_writing_named_decoy():
    html = display_html() + '''<script>
      const field=document.querySelector('main form [id="position"]'), owner=field.parentElement;
      field.remove();setTimeout(()=>owner.append(field),250);
    </script>'''
    _missing, error, values = exercise_form(html, spec={**SPEC, 'position':'3'})
    assert error is None
    assert values['display'][3] == '3'
    assert values['displayDecoys'][3] == '91'
    assert values['submits'] == ['0']


def test_product_queue_retains_identity_and_never_creates_when_display_contract_breaks(monkeypatch):
    html = limit_html().replace('id="is_hidden" type="button"', 'id="is_hidden" type="submit"')
    traffic, snapshots = routed_runner_browser(monkeypatch, html, preview_urls=(CREATE_URLS[0],))
    entries = asyncio.run(ProductBuilder(lambda *_:None).run_many('CabalM TH', [
        {**FULL_SPEC, 'slug':'keep-product', 'group':'keep-group'}], {}))
    assert len(entries) == 1
    entry = entries[0]
    assert entry['saved'] is False and entry['made_id'] is None
    assert entry['slug'] == 'keep-product' and entry['group'] == 'keep-group'
    assert entry['name'] == 'สินค้าที่ขอ' and 'ซ่อนสินค้า' in entry['error']
    assert traffic == [('GET', CREATE_URLS[0])]
    assert snapshots[-1]['submits'] == ['0']


def test_product_rejected_reset_interval_is_incomplete_not_silently_accepted():
    html = limit_html().replace('id="limit_reset_interval_days"',
                               'id="limit_reset_interval_days" oninput="this.value=9"')
    missing, error, values = exercise_form(html, spec={
        **SPEC, 'limit_type': 'PLAYER', 'limit_quantity': '10', 'limit_reset_interval_days': '7'})
    assert error is None
    assert 'รีเซ็ตทุกกี่วัน' in missing
    assert values['numbers'] == ['10', '9']
    assert values['submits'] == ['0']
