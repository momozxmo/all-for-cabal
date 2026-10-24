"""Public Event filling against network-isolated synthetic Aztek forms."""
import asyncio

import pytest
from playwright.async_api import async_playwright

from web.aztek_locator import AztekLocatorError
from web.event_runner import EventBuilder
from test_web_itemcode_id_first import calendar_html as itemcode_calendar_html
from test_web_itemcode_id_first import routed_runner_browser


CREATE_URLS = (
    'https://aztek-tools-v2.combo-interactive.com/combo/cabalm/events/create',
    'https://aztek-tools-v2.combo-interactive.com/combo/cabalmsea/events/create',
    'https://aztek-tools-v2.combo-interactive.com/combo/cabalpc/events/create',
    'https://aztek-tools-v2.combo-interactive.com/combo/cabalpcsea/events/create',
)
HEADER_HTML = '''<aside>
  <input id="slug" value="outside-slug">
  <input id="name_th" value="outside-th">
  <input id="name_en" value="outside-en">
</aside><main><h1>เปลี่ยนข้อความหัวข้อแล้ว</h1>
<form onsubmit="event.preventDefault(); this.dataset.submits='1'">
  <input name="slug" data-decoy value="keep-slug">
  <input name="name_th" data-decoy value="keep-th">
  <input name="name_en" data-decoy value="keep-en">
  <section><div><input id="name_en" name="renamed-en"></div></section>
  <div><input id="slug" name="renamed-slug" value="event-generated"></div>
  <section><input id="name_th" name="renamed-th"></section>
  <section><header><div><h2>การรับรางวัล</h2></div></header>
    <div><div><label>ผู้มีสิทธิ์รับรางวัล</label>
      <button type="button" role="combobox" aria-expanded="false">WINNER</button>
      <select aria-hidden="true" tabindex="-1" data-event-type
        style="position:absolute;width:1px;height:1px;clip:rect(0,0,0,0)"
        onchange="this.previousElementSibling.textContent=this.selectedOptions[0].textContent">
        <option value="WINNER">WINNER</option><option value="ALL">ALL</option>
      </select>
    </div></div>
  </section>
  <input id="per_player_limit" name="per_player_limit" type="number" value="1">
  <input id="quantity" name="quantity" type="number" value="0">
  <input id="remaining" name="remaining" type="number" value="0">
  <button type="submit">สร้าง Event</button>
</form></main>'''
SPEC = {'slug': 'requested-event', 'name_th': 'กิจกรรมที่ขอ',
        'name_en': 'Requested event', 'rewards': []}
COUNTER_FIELDS = (
    ('per_player_limit', 'uses_per_user', 'จำกัดต่อผู้เล่น'),
    ('quantity', 'quantity', 'จำนวนรางวัลทั้งหมด'),
    ('remaining', 'remaining', 'คงเหลือ'),
)
DATE_CONTROLS = (
    ('start_at', 'start_event', 'วันเริ่มกิจกรรม'),
    ('end_at', 'end_event', 'วันสิ้นสุดกิจกรรม'),
    ('redeem_start_at', 'start_claim', 'วันเริ่มรับรางวัล'),
    ('redeem_end_at', 'end_claim', 'วันสิ้นสุดการรับรางวัล'),
)
COUNTER_HTML = HEADER_HTML.replace('</aside>', '''
  <input id="per_player_limit" type="number" value="901">
  <input id="quantity" type="number" value="902">
  <input id="remaining" type="number" value="903">
</aside>''')
for _field, _key, _label in COUNTER_FIELDS:
    COUNTER_HTML = COUNTER_HTML.replace(
        '<input id="%s" name="%s" type="number"' % (_field, _field),
        '<input data-counter-decoy name="%s" type="number"' % _field)
COUNTER_HTML = COUNTER_HTML.replace('</form>', '''
  <section><input id="remaining" name="changed-remaining" type="number" value="83"></section>
  <div><input id="per_player_limit" name="changed-limit" type="number" value="81"></div>
  <section><div><input id="quantity" name="changed-quantity" type="number" value="82"></div></section>
</form>''')


def exercise_form(html=HEADER_HTML, *, url=CREATE_URLS[0], spec=None):
    async def exercise():
        async with async_playwright() as driver:
            browser = await driver.chromium.launch(headless=True)
            context = await browser.new_context(service_workers='block')
            unexpected = []

            async def route_request(route):
                if route.request.url == url and route.request.method == 'GET':
                    await route.fulfill(status=200, content_type='text/html; charset=utf-8', body=html)
                else:
                    unexpected.append((route.request.method, route.request.url))
                    await route.abort()

            await context.route('**/*', route_request)
            page = await context.new_page()
            await page.goto(url)
            missing, error = None, None
            try:
                missing = await EventBuilder(lambda *_: None).fill_form(
                    page, dict(SPEC if spec is None else spec))
            except Exception as caught:
                error = caught
            values = await page.evaluate('''() => ({
                header: ['slug','name_th','name_en'].map(id =>
                    document.querySelector('main form [id="'+id+'"]')?.value),
                decoys: [...document.querySelectorAll('[data-decoy]')].map(e=>e.value),
                outside: [...document.querySelectorAll('aside input')].map(e=>e.value),
                counters: ['per_player_limit','quantity','remaining'].map(id =>
                    document.querySelector('main form [id="'+id+'"]')?.value),
                counterDecoys: [...document.querySelectorAll('[data-counter-decoy]')].map(e=>e.value),
                dates: ['start_at','end_at','redeem_start_at','redeem_end_at'].map(id =>
                    document.querySelector('main form [id="'+id+'"]')?.textContent),
                calendarDecoys: [...document.querySelectorAll('[data-calendar-decoy]')].map(e=>e.value),
                dateDecoyClicks: document.body.dataset.dateDecoyClicks || '0',
                eventType: document.querySelector('main form [data-event-type]')?.value,
                typeText: document.querySelector('main form [data-event-type]')?.previousElementSibling?.textContent,
                typeDecoys: [...document.querySelectorAll('[data-type-decoy]')].map(e=>e.value),
                rewards: window.eventRewardValues || [],
                rewardDecoys: [...document.querySelectorAll('[data-reward-decoy]')].map(e=>e.value),
                rewardDecoyClicks: document.body.dataset.rewardDecoyClicks || '0',
                languageClicks: document.body.dataset.languageClicks || '0',
                pickerDecoys: [...document.querySelectorAll('[data-picker-decoy]')].map(e=>e.value),
                wrongPickerClicks: document.body.dataset.wrongPickerClicks || '0',
                bundleChanges: document.body.dataset.bundleChanges || '0',
                submits: [...document.querySelectorAll('form')].map(e=>e.dataset.submits || '0')
            })''')
            await browser.close()
            assert unexpected == []
            return missing, error, values
    return asyncio.run(exercise())


def event_reward_html(base=HEADER_HTML):
    # Independent live evidence: Event starts with no reward, one set has no
    # tabs, and two sets expose ordinal SPANs in their own no-ID tablist.
    # Language tabs elsewhere in the same form must not be mistaken for these.
    markup = '''
      <button type="button" onclick="document.body.dataset.rewardDecoyClicks='1'">+ เพิ่มของรางวัล</button>
      <div role="tablist"><button role="tab" type="button" aria-selected="true"
        onclick="document.body.dataset.languageClicks='1'"><span>1</span><span>ไทย</span></button></div>
      <label>จำกัดจำนวน<button role="switch" type="button" aria-checked="false"
        onclick="document.body.dataset.rewardDecoyClicks='1'">สถานะ Event</button></label>
      <input name="rewards.0.name_th" data-reward-decoy value="keep-zero-th">
      <input name="rewards.0.name_en" data-reward-decoy value="keep-zero-en">
      <input name="rewards.1.name_th" data-reward-decoy value="keep-one-th">
      <input name="rewards.1.name_en" data-reward-decoy value="keep-one-en">
      <input name="rewards.0.per_player_limit" data-reward-decoy value="91">
      <input name="rewards.1.per_player_limit" data-reward-decoy value="92">
      <textarea name="rewards.0.desc_th" data-reward-decoy>keep-description</textarea>
      <section data-reward-section><header><div><h2>ของรางวัล</h2></div><div>
        <button type="button" onclick="addEventReward()">+ เพิ่มของรางวัล</button>
      </div></header><div data-reward-tabs></div><div data-reward-fields></div></section>
    '''
    script = '''<script>
    window.eventRewardValues=[];
    function renderEventReward(i) {
      const section=document.querySelector('[data-reward-section]');
      const tabs=section.querySelector('[data-reward-tabs]');
      tabs.innerHTML=eventRewardValues.length>1 ? '<div role="tablist">'+eventRewardValues.map((r,n)=>
        '<button type="button" role="tab" aria-selected="'+(n===i)+'" onclick="renderEventReward('+n+')">'+
        '<span>'+(n+1)+'</span><span>'+r.name_th+'</span></button>').join('')+'</div>' : '';
      const r=eventRewardValues[i];
      section.querySelector('[data-reward-fields]').innerHTML=
        '<div><input id="rewards.'+i+'.name_en" name="changed-en"></div>'+
        '<section><input id="rewards.'+i+'.name_th" name="changed-th"></section>'+
        '<textarea id="rewards.'+i+'.desc_th" name="changed-desc-th"></textarea>'+
        '<textarea id="rewards.'+i+'.desc_en" name="changed-desc-en"></textarea>'+
        '<button id="rewards.'+i+'.is_limited" type="button" role="switch" aria-checked="'+r.limited+'">ใหม่</button>'+
        '<input id="rewards.'+i+'.per_player_limit" type="number" name="changed-limit">'+
        '<div data-reward-counts></div>';
      for(const key of ['name_th','name_en','desc_th','desc_en','per_player_limit']) {
        const el=document.getElementById('rewards.'+i+'.'+key);el.value=r[key];
        el.oninput=()=>{r[key]=el.value};
      }
      const limited=document.getElementById('rewards.'+i+'.is_limited');
      limited.onclick=()=>{r.limited=!r.limited;limited.setAttribute('aria-checked',String(r.limited));renderEventRewardCounts(i)};
      renderEventRewardCounts(i);
    }
    function renderEventRewardCounts(i) {
      const r=eventRewardValues[i];
      const holder=document.querySelector('[data-reward-section] [data-reward-counts]');
      holder.innerHTML=r.limited ?
        '<section><input id="rewards.'+i+'.remaining" type="number" name="changed-remaining"></section>'+
        '<div><input id="rewards.'+i+'.quantity" type="number" name="changed-quantity"></div>' : '';
      if(r.limited) for(const key of ['quantity','remaining']) {
        const el=holder.querySelector('[id="rewards.'+i+'.'+key+'"]');el.value=r[key];
        el.oninput=()=>{r[key]=el.value};
      }
    }
    function addEventReward() {
      eventRewardValues.push({name_th:'ชุดที่ '+(eventRewardValues.length+1),name_en:'',
        desc_th:'',desc_en:'',limited:false,per_player_limit:'1',quantity:'0',remaining:'0'});
      renderEventReward(eventRewardValues.length-1);
    }
    </script>'''
    return base.replace('</form>', markup + '</form>') + script


@pytest.mark.parametrize('url', CREATE_URLS)
def test_event_reward_sets_fill_their_own_ids_without_changing_language_tabs_or_decoys(url):
    # Removing indexed ID selection, using the first add/switch, or treating
    # the language tablist as a reward tablist must leave observable wrong data.
    spec = {**SPEC, 'rewards': [
        {'name_th': 'รางวัลแรก', 'name_en': 'First', 'desc_th': 'อธิบายหนึ่ง',
         'desc_en': 'Description one', 'limited': True, 'uses_per_user': '2',
         'quantity': '200', 'remaining': '179'},
        {'name_th': 'รางวัลสอง', 'name_en': 'Second', 'desc_th': 'อธิบายสอง',
         'desc_en': 'Description two', 'limited': False, 'uses_per_user': '3'},
    ]}
    missing, error, values = exercise_form(event_reward_html(), url=url, spec=spec)
    assert error is None
    assert values['rewards'] == [
        {'name_th': 'รางวัลแรก', 'name_en': 'First', 'desc_th': 'อธิบายหนึ่ง',
         'desc_en': 'Description one', 'limited': True, 'per_player_limit': '2',
         'quantity': '200', 'remaining': '179'},
        {'name_th': 'รางวัลสอง', 'name_en': 'Second', 'desc_th': 'อธิบายสอง',
         'desc_en': 'Description two', 'limited': False, 'per_player_limit': '3',
         'quantity': '0', 'remaining': '0'},
    ]
    assert values['rewardDecoys'] == ['keep-zero-th', 'keep-zero-en', 'keep-one-th',
                                      'keep-one-en', '91', '92', 'keep-description']
    assert values['rewardDecoyClicks'] == '0' and values['languageClicks'] == '0'
    assert missing == ['วันเริ่มกิจกรรม', 'วันสิ้นสุดกิจกรรม',
                       'วันเริ่มรับรางวัล', 'วันสิ้นสุดการรับรางวัล',
                       'ชุดรางวัลที่ 1: Bundle', 'ชุดรางวัลที่ 2: Bundle']
    assert values['submits'] == ['0']


REWARD_REQUEST = {'name_th': 'รางวัลแรก', 'name_en': 'First',
                  'desc_th': 'อธิบายหนึ่ง', 'desc_en': 'Description one',
                  'limited': True, 'uses_per_user': '2',
                  'quantity': '200', 'remaining': '179'}


def event_bundle_html(base=HEADER_HTML):
    # Independent Event audit: Bundle label has no asterisk; the active
    # card owns both indexed name IDs, not Item Code's is_generate_code.
    return event_reward_html(base) + '''<pre id="reward-values"></pre>
    <div role="dialog" id="unrelated-picker" data-state="open">
      <input placeholder="ค้นหาด้วยชื่อหรือ id" data-picker-decoy value="keep-search">
      <button type="button" onclick="document.body.dataset.wrongPickerClicks='1'">
        Wrong bundle ID: 1001</button></div><script>
    const rewardRender=renderEventReward;
    renderEventReward=i=>{
      rewardRender(i);
      const holder=document.querySelector('[data-reward-fields]');
      const card=document.createElement('div');const body=document.createElement('div');
      while(holder.firstChild)body.append(holder.firstChild);
      card.append(body);holder.append(card);renderEventBundle(i,body);
    };
    function renderEventBundle(i,body){
      document.getElementById('reward-values').textContent=JSON.stringify(eventRewardValues);
      const r=eventRewardValues[i];let field=body.querySelector('[data-bundle-field]');
      if(!field){field=document.createElement('div');field.dataset.bundleField='';body.append(field);}
      field.innerHTML='<label>Bundle</label>';
      if(r.bundle_id){
        const row=document.createElement('div');const badge=document.createElement('span');
        badge.textContent='#'+r.bundle_id+' — Bundle selected';row.append(badge);
        const change=document.createElement('button');change.type='button';change.textContent='เปลี่ยน';
        change.onclick=()=>{document.body.dataset.bundleChanges=Number(document.body.dataset.bundleChanges||0)+1;
          r.bundle_id='';renderEventBundle(i,body);};
        row.append(change);field.append(row);
      }else{
        const button=document.createElement('button');button.type='button';button.textContent='เลือก bundle';
        button.setAttribute('aria-haspopup','dialog');button.setAttribute('aria-expanded','false');
        field.append(button);button.onclick=()=>{
          const dialog=document.createElement('div');dialog.id='runtime-event-bundle-'+i;
          dialog.setAttribute('role','dialog');dialog.dataset.state='open';
          button.setAttribute('aria-controls',dialog.id);button.setAttribute('aria-expanded','true');
          const search=document.createElement('input');search.placeholder='ค้นหาด้วยชื่อหรือ id';
          dialog.append(search);const results=document.createElement('div');dialog.append(results);
          function rows(){results.innerHTML='';for(const id of ['10010','1001','2002']){
            if(!id.includes(search.value))continue;
            const hit=document.createElement('button');hit.type='button';
            hit.innerHTML='<span>Bundle result</span><span>ID: '+id+'</span>';
            hit.onclick=()=>{r.bundle_id=id;dialog.remove();renderEventBundle(i,body);};results.append(hit);
          }}
          search.oninput=()=>{results.innerHTML='';setTimeout(rows,150);};
          document.body.insertBefore(dialog,document.getElementById('unrelated-picker'));rows();
        };
      }
    }
    </script>'''


@pytest.mark.parametrize('url', CREATE_URLS)
def test_event_bundle_picker_keeps_exact_ids_in_own_rewards_not_other_portal(url):
    missing, error, values = exercise_form(event_bundle_html(), url=url, spec={
        **SPEC, 'rewards': [{**REWARD_REQUEST, 'bundle_id': '1001'},
                           {**REWARD_REQUEST, 'name_th': 'สอง', 'bundle_id': '2002'}]})
    assert error is None
    assert [r.get('bundle_id') for r in values['rewards']] == ['1001', '2002']
    assert missing == ['วันเริ่มกิจกรรม', 'วันสิ้นสุดกิจกรรม',
                       'วันเริ่มรับรางวัล', 'วันสิ้นสุดการรับรางวัล']
    assert values['pickerDecoys'] == ['keep-search']
    assert values['wrongPickerClicks'] == '0' and values['submits'] == ['0']


@pytest.mark.parametrize('existing,changes', [('1001', '0'), ('10010', '1')])
def test_event_bundle_picker_preserves_matching_selection_or_changes_different_id(existing, changes):
    html = event_bundle_html().replace('function renderEventBundle(i,body){',
        "function renderEventBundle(i,body){if(!('bundle_id' in eventRewardValues[i]))"
        "eventRewardValues[i].bundle_id='%s';" % existing)
    missing, error, values = exercise_form(html, spec={
        **SPEC, 'rewards': [{**REWARD_REQUEST, 'bundle_id': '1001'}]})
    assert error is None
    assert values['rewards'][0]['bundle_id'] == '1001'
    assert values['bundleChanges'] == changes
    assert missing == ['วันเริ่มกิจกรรม', 'วันสิ้นสุดกิจกรรม',
                       'วันเริ่มรับรางวัล', 'วันสิ้นสุดการรับรางวัล']
    assert values['pickerDecoys'] == ['keep-search'] and values['wrongPickerClicks'] == '0'
    assert values['submits'] == ['0']


@pytest.mark.parametrize('before,after', (
    ("field.innerHTML='<label>Bundle</label>';", "field.innerHTML='<label>Unknown</label>';"),
    ('field.append(button);button.onclick=', 'field.append(button);field.append(button.cloneNode(true));button.onclick='),
    ("button.type='button';button.textContent='เลือก bundle';", "button.type='submit';button.textContent='เลือก bundle';"),
    ("button.setAttribute('aria-controls',dialog.id);", "button.setAttribute('aria-controls','missing-popup');"),
    ("dialog.setAttribute('role','dialog');", "dialog.setAttribute('role','region');"),
    ("search.placeholder='ค้นหาด้วยชื่อหรือ id';", "search.placeholder='Unknown';"),
    ('dialog.append(search);const results=', 'dialog.append(search);dialog.append(search.cloneNode(true));const results='),
    ("['10010','1001','2002']", "['10010','2002']"),
    ('results.append(hit);', 'results.append(hit);results.append(hit.cloneNode(true));'),
    ("hit.type='button';", "hit.type='submit';"),
    ('r.bundle_id=id;', "r.bundle_id='10010';"),
    ("search.oninput=()=>{results.innerHTML='';", "search.oninput=()=>{document.getElementById('rewards.0.name_th').remove();results.innerHTML='';"),
))
def test_event_broken_bundle_picker_stops_before_submit_without_guessing(before, after):
    html = event_bundle_html().replace(before, after)
    assert html != event_bundle_html()
    missing, error, values = exercise_form(html, spec={
        **SPEC, 'rewards': [{**REWARD_REQUEST, 'bundle_id': '1001'}]})
    assert isinstance(error, AztekLocatorError)
    assert 'ชุดรางวัลที่ 1: Bundle 1001' in str(error)
    assert missing is None
    assert values['pickerDecoys'] == ['keep-search'] and values['wrongPickerClicks'] == '0'
    assert values['submits'] == ['0']


def test_event_queue_bundle_failure_preserves_first_reward_and_does_not_submit(monkeypatch):
    html = event_bundle_html().replace("const search=document.createElement('input');",
        "const search=document.createElement('input');if(i===1)search.type='number';")
    html = html[html.index('<main>'):]
    traffic, snapshots = routed_runner_browser(monkeypatch, html, preview_urls=CREATE_URLS)
    results = asyncio.run(EventBuilder(lambda *_: None).run_many(
        'CabalM TH', [{**SPEC, 'rewards': [{**REWARD_REQUEST, 'bundle_id': '1001'},
                                        {**REWARD_REQUEST, 'bundle_id': '2002'}]}],
        {'cookies': [], 'origins': []}))
    assert len(results) == 1
    assert results[0]['saved'] is False and results[0]['made_id'] is None
    assert 'ชุดรางวัลที่ 2: Bundle 2002' in results[0]['error']
    assert snapshots[0]['rewards'][0]['bundle_id'] == '1001'
    assert snapshots[0]['rewards'][1].get('bundle_id') is None
    assert snapshots[0]['submits'] == ['0']
    assert traffic == [('GET', CREATE_URLS[0])]


SYNTHETIC_EVENT_WRITE = 'https://afc-synthetic.invalid/event-write'
MTH_EVENT_WRITE = 'https://admin-api-v2.combo-interactive.com/cabalm/event/events'
EVENT_WRITE_URLS = {
    'CabalM TH': MTH_EVENT_WRITE,
    'CabalM SEA': 'https://admin-api-v2.combo-interactive.com/cabalmsea/event/events',
    'CabalPC TH': 'https://admin-api-v2.combo-interactive.com/cabalpc/event/events',
    'CabalPC SEA': 'https://admin-api-v2.combo-interactive.com/cabalpcsea/event/events',
}


def event_create_html(write_url=MTH_EVENT_WRITE):
    html = event_bundle_html(event_calendar_html())
    html = html.replace('''onsubmit="event.preventDefault(); this.dataset.submits='1'"''',
        '''onsubmit="event.preventDefault(); this.dataset.submits=String(Number(this.dataset.submits||0)+1);
        fetch('https://afc-synthetic.invalid/event-write?owner=form',{method:'POST'})"''')
    html = html.replace('<main>', '''<button type="button" onclick="
        document.body.dataset.outsideCreates='1';
        fetch('https://afc-synthetic.invalid/event-write?owner=outside',{method:'POST'})">สร้าง Event</button>
        <main>''') + '<script>document.body.dataset.createAudit="";</script>'
    return html.replace(SYNTHETIC_EVENT_WRITE, write_url)


def event_create_spec():
    return {**SPEC, 'group': 'source-group',
            'start_event': '2026-08-27 00:00:00', 'end_event': '2026-08-27 23:59:59',
            'start_claim': '2026-08-27 00:00:00', 'end_claim': '2026-08-27 23:59:59',
            'rewards': [{**REWARD_REQUEST, 'bundle_id': '1001'}]}


def event_mth_confirmation_html():
    # This M TH fixture's same dialog contract was independently observed in
    # all four games on Oct 16. Runtime IDs model current ARIA links only.
    html = event_create_html().replace(
        "fetch('https://admin-api-v2.combo-interactive.com/cabalm/event/events?owner=form',{method:'POST'})",
        "document.getElementById('runtime-event-dialog').hidden=false")
    return html + '''<div id="runtime-event-dialog" role="alertdialog" data-state="open" hidden
      aria-labelledby="runtime-event-title" aria-describedby="runtime-event-description">
      <h2 id="runtime-event-title">ยืนยันการสร้าง</h2>
      <p id="runtime-event-description">ต้องการสร้าง Event ใช่หรือไม่?</p>
      <button type="button">ยกเลิก</button>
      <button type="button" onclick="document.body.dataset.confirms=String(Number(document.body.dataset.confirms||0)+1);
        fetch('https://admin-api-v2.combo-interactive.com/cabalm/event/events?owner=form',{method:'POST'})">ยืนยัน</button>
    </div><script>document.body.dataset.confirmAudit='1';</script>'''


def test_event_mth_unrelated_response_cannot_supply_result_or_skip_confirmation(monkeypatch):
    html = event_mth_confirmation_html().replace(
        "document.getElementById('runtime-event-dialog').hidden=false",
        "document.getElementById('runtime-event-dialog').hidden=false;"
        "fetch('https://afc-synthetic.invalid/event-write?owner=outside',{method:'POST'})")
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS,
        synthetic_write_url=(MTH_EVENT_WRITE, SYNTHETIC_EVENT_WRITE))
    result = asyncio.run(EventBuilder(lambda *_: None).run_many(
        'CabalM TH', [event_create_spec()], {'cookies': [], 'origins': []}))[0]
    # Unverified numeric JSON IDs must not become M TH Event IDs.
    assert (result['saved'], result['made_id'], result['error']) == (True, None, None)
    assert snapshots[0]['confirms'] == '1' and snapshots[0]['submits'] == ['1']
    assert traffic == [('GET', CREATE_URLS[0]),
                       ('POST', SYNTHETIC_EVENT_WRITE + '?owner=outside'),
                       ('POST', MTH_EVENT_WRITE + '?owner=form')]


def test_event_mth_broken_confirmation_relation_stops_without_write(monkeypatch):
    html = event_mth_confirmation_html().replace('aria-describedby="runtime-event-description"', '')
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=MTH_EVENT_WRITE)
    result = asyncio.run(EventBuilder(lambda *_: None).run_many(
        'CabalM TH', [event_create_spec()], {'cookies': [], 'origins': []}))[0]
    assert (result['saved'], result['made_id']) == (False, None)
    assert 'Event' in (result['error'] or '')
    assert snapshots[0]['submits'] == ['1'] and snapshots[0]['confirms'] == '0'
    assert snapshots[0]['rewards'][0]['bundle_id'] == '1001'
    assert traffic == [('GET', CREATE_URLS[0])]


@pytest.mark.parametrize('game', ('CabalM TH', 'CabalM SEA', 'CabalPC TH', 'CabalPC SEA'))
def test_event_create_action_submits_only_own_form_not_same_named_outside_button(monkeypatch, game):
    write_url = EVENT_WRITE_URLS[game]
    traffic, snapshots = routed_runner_browser(
        monkeypatch, event_create_html(write_url), preview_urls=CREATE_URLS,
        synthetic_write_url=write_url)
    results = asyncio.run(EventBuilder(lambda *_: None).run_many(
        game, [event_create_spec()], {'cookies': [], 'origins': []}))
    assert [(r['slug'], r['group'], r['saved'], r['made_id'], r['error']) for r in results] == [
        ('requested-event', 'source-group', True, None, None)]
    assert snapshots[0]['submits'] == ['1']
    assert snapshots[0]['outsideCreates'] == '0'
    assert snapshots[0]['rewards'][0]['bundle_id'] == '1001'
    assert traffic[-1] == ('POST', write_url + '?owner=form')
    assert [method for method, _ in traffic] == ['GET', 'POST']


@pytest.mark.parametrize('replacement', (
    '',
    '<button type="submit">สร้าง Event เพิ่มเติม</button>',
    '<button type="submit">สร้าง Event</button>' * 2,
    '<button type="submit" hidden>สร้าง Event</button><button type="submit">สร้าง Event</button>',
    '<button type="button">สร้าง Event</button>',
    '<button>สร้าง Event</button>',
    '<button type="submit" role="link">สร้าง Event</button>',
    '<button type="submit" disabled>สร้าง Event</button>',
    '<button type="submit" form="other-form">สร้าง Event</button>',
), ids=('missing', 'partial-label', 'duplicate', 'hidden-duplicate', 'wrong-type',
        'implicit-type', 'wrong-role', 'disabled', 'wrong-form-owner'))
def test_event_create_action_broken_contract_keeps_queue_identity_and_never_submits(monkeypatch, replacement):
    html = event_create_html().replace('<button type="submit">สร้าง Event</button>',
        '''<button type="button" onclick="document.body.dataset.alternativeCreates='1'">
        บันทึกและสร้างต่อ</button>''' + replacement)
    html += '<form id="other-form" onsubmit="event.preventDefault();this.dataset.submits=\'1\'"></form>'
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=MTH_EVENT_WRITE)
    results = asyncio.run(EventBuilder(lambda *_: None).run_many(
        'CabalM TH', [event_create_spec()], {'cookies': [], 'origins': []}))
    assert [(r['slug'], r['group'], r['saved'], r['made_id']) for r in results] == [
        ('requested-event', 'source-group', False, None)]
    assert 'สร้าง Event' in results[0]['error']
    assert snapshots[0]['submits'] == ['0', '0']
    assert snapshots[0]['outsideCreates'] == '0' and snapshots[0]['alternativeCreates'] == '0'
    assert snapshots[0]['rewards'][0]['bundle_id'] == '1001'
    assert traffic == [('GET', CREATE_URLS[0])]


def test_event_create_action_is_never_pressed_in_preview(monkeypatch):
    traffic, snapshots = routed_runner_browser(
        monkeypatch, event_create_html(), preview_urls=CREATE_URLS,
        synthetic_write_url=MTH_EVENT_WRITE)
    result = asyncio.run(EventBuilder(lambda *_: None).run(
        'CabalM TH', event_create_spec(), {'cookies': [], 'origins': []}))
    assert result['missing'] == []
    assert snapshots[0]['submits'] == ['0'] and snapshots[0]['outsideCreates'] == '0'
    assert traffic == [('GET', CREATE_URLS[0])]


def test_event_create_action_without_write_response_is_not_reported_created_or_retried(monkeypatch):
    html = event_create_html().replace(
        "fetch('https://admin-api-v2.combo-interactive.com/cabalm/event/events?owner=form',{method:'POST'})", '')
    assert html != event_create_html()
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=MTH_EVENT_WRITE)
    result = asyncio.run(EventBuilder(lambda *_: None).run_many(
        'CabalM TH', [event_create_spec()], {'cookies': [], 'origins': []}))[0]
    assert (result['slug'], result['group'], result['saved'], result['made_id']) == (
        'requested-event', 'source-group', False, None)
    assert snapshots[0]['submits'] == ['1'] and snapshots[0]['outsideCreates'] == '0'
    assert snapshots[0]['rewards'][0]['bundle_id'] == '1001'
    assert traffic == [('GET', CREATE_URLS[0])]


@pytest.mark.parametrize('mutation,expected', (
    ('b.hidden=false', True), ("b.type='button';b.disabled=false", False),
))
def test_event_create_action_waits_for_lazy_button_but_rejects_changed_type(monkeypatch, mutation, expected):
    html = event_create_html() + '''<script>
      const b=document.querySelector('main form button[type="submit"]');
      b.hidden=MUTATION.startsWith('b.hidden');b.disabled=!b.hidden;
      const mounted=new MutationObserver(()=>{
        const rewards=JSON.parse(document.getElementById('reward-values').textContent);
        if(rewards.length && rewards.every(r=>r.bundle_id)){
          mounted.disconnect();setTimeout(()=>{ACTION},200);
        }
      });mounted.observe(document.getElementById('reward-values'),{childList:true});
    </script>'''.replace('MUTATION', repr(mutation)).replace('ACTION', mutation)
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=MTH_EVENT_WRITE)
    result = asyncio.run(EventBuilder(lambda *_: None).run_many(
        'CabalM TH', [event_create_spec()], {'cookies': [], 'origins': []}))[0]
    assert result['saved'] is expected
    assert result['made_id'] is None
    assert snapshots[0]['submits'] == (['1'] if expected else ['0'])
    assert snapshots[0]['outsideCreates'] == '0'
    if expected:
        assert traffic[-1] == ('POST', MTH_EVENT_WRITE + '?owner=form')
    else:
        assert 'สร้าง Event' in result['error']
        assert traffic == [('GET', CREATE_URLS[0])]


def test_event_create_action_rechecks_owner_after_actionability_wait(monkeypatch):
    html = event_create_html().replace('<button type="submit">สร้าง Event</button>',
        '<button type="submit" style="position:fixed;top:0;right:0;width:180px;height:60px">สร้าง Event</button>')
    html += '''<form id="other-form" onsubmit="event.preventDefault();this.dataset.submits='1';
      fetch('https://afc-synthetic.invalid/event-write?owner=outside',{method:'POST'})"></form>
    <div id="create-obstruction" style="position:fixed;top:0;right:0;width:400px;height:70px;z-index:10000"></div>
    <script>
      const mounted=new MutationObserver(()=>{
        const rewards=JSON.parse(document.getElementById('reward-values').textContent);
        if(rewards.length && rewards.every(r=>r.bundle_id)){
          mounted.disconnect();setTimeout(()=>{
            document.querySelector('main form button[type="submit"]').setAttribute('form','other-form');
            document.getElementById('create-obstruction').remove();
          },700);
        }
      });mounted.observe(document.getElementById('reward-values'),{childList:true});
    </script>'''
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=CREATE_URLS, synthetic_write_url=MTH_EVENT_WRITE)
    result = asyncio.run(EventBuilder(lambda *_: None).run_many(
        'CabalM TH', [event_create_spec()], {'cookies': [], 'origins': []}))[0]
    assert result['saved'] is False and result['made_id'] is None
    assert 'สร้าง Event' in result['error']
    assert snapshots[0]['submits'] == ['0', '0'] and snapshots[0]['outsideCreates'] == '0'
    assert traffic == [('GET', CREATE_URLS[0])]


def mutate_reward_mount(script):
    return event_reward_html() + '''<script>
      const originalRender=renderEventReward;
      renderEventReward=i=>{originalRender(i);%s};
    </script>''' % script


@pytest.mark.parametrize('field,label', (
    ('name_th', 'ชื่อรางวัล (ไทย)'), ('name_en', 'ชื่อรางวัล (อังกฤษ)'),
    ('desc_th', 'desc_th'), ('desc_en', 'desc_en'),
    ('per_player_limit', 'จำกัดต่อผู้เล่น'),
))
@pytest.mark.parametrize('fault', ('missing', 'duplicate', 'wrong-type', 'hidden'))
def test_event_reward_id_contract_failure_names_its_set_without_fallback(field, label, fault):
    mutations = {
        'missing': 'el.remove();',
        'duplicate': 'el.after(el.cloneNode(true));',
        'wrong-type': "const bad=document.createElement('button');bad.type='button';bad.id=el.id;el.replaceWith(bad);",
        'hidden': 'el.hidden=true;',
    }
    html = mutate_reward_mount(
        "const el=document.getElementById('rewards.'+i+'.%s');%s" % (field, mutations[fault]))
    missing, error, values = exercise_form(html, spec={**SPEC, 'rewards': [REWARD_REQUEST]})
    assert isinstance(error, AztekLocatorError)
    assert 'ชุดรางวัลที่ 1' in str(error) and label in str(error)
    assert missing is None
    assert values['rewardDecoys'] == ['keep-zero-th', 'keep-zero-en', 'keep-one-th',
                                      'keep-one-en', '91', '92', 'keep-description']
    assert values['rewardDecoyClicks'] == '0' and values['languageClicks'] == '0'
    assert values['submits'] == ['0']


@pytest.mark.parametrize('fault', ('missing', 'duplicate', 'submit-type', 'wrong-role',
                                  'invalid-state', 'rejected-readback'))
def test_event_reward_limit_contract_failure_does_not_toggle_event_status(fault):
    mutations = {
        'missing': 'el.remove();',
        'duplicate': 'el.after(el.cloneNode(true));',
        'submit-type': "el.type='submit';",
        'wrong-role': "el.setAttribute('role','button');",
        'invalid-state': "el.setAttribute('aria-checked','mixed');",
        'rejected-readback': 'el.onclick=()=>{};',
    }
    html = mutate_reward_mount(
        "const el=document.getElementById('rewards.'+i+'.is_limited');%s" % mutations[fault])
    missing, error, values = exercise_form(html, spec={**SPEC, 'rewards': [REWARD_REQUEST]})
    assert isinstance(error, AztekLocatorError)
    assert 'ชุดรางวัลที่ 1: จำกัดจำนวน' in str(error)
    assert missing is None
    assert values['rewardDecoyClicks'] == '0'
    assert values['submits'] == ['0']


@pytest.mark.parametrize('fault', ('missing-section', 'duplicate-section', 'missing-add',
                                  'duplicate-add', 'submit-add', 'disabled-add'))
def test_event_reward_owner_or_add_failure_cannot_use_the_other_add_button(fault):
    html = event_reward_html()
    if fault == 'missing-section':
        html = html.replace('<h2>ของรางวัล</h2>', '<h2>อีกส่วน</h2>')
    elif fault == 'duplicate-section':
        html = html.replace('</form>', '<section><header><div><h2>ของรางวัล</h2></div></header></section></form>')
    else:
        button = '<button type="button" onclick="addEventReward()">+ เพิ่มของรางวัล</button>'
        replacement = {
            'missing-add': '', 'duplicate-add': button + button,
            'submit-add': button.replace('type="button"', 'type="submit"'),
            'disabled-add': button.replace('<button ', '<button disabled '),
        }[fault]
        html = html.replace(button, replacement)
    missing, error, values = exercise_form(html, spec={**SPEC, 'rewards': [REWARD_REQUEST]})
    assert isinstance(error, AztekLocatorError)
    assert ('ส่วนของรางวัล Event' if 'section' in fault else 'เพิ่มชุดรางวัลที่ 1') in str(error)
    assert missing is None
    assert values['rewards'] == []
    assert values['rewardDecoyClicks'] == '0'
    assert values['submits'] == ['0']


def test_event_reward_waits_for_lazy_mount_instead_of_filling_named_decoys():
    html = event_reward_html().replace(
        'renderEventReward(eventRewardValues.length-1);',
        'setTimeout(()=>renderEventReward(eventRewardValues.length-1),200);')
    missing, error, values = exercise_form(html, spec={**SPEC, 'rewards': [REWARD_REQUEST]})
    assert error is None
    assert values['rewards'] == [{'name_th': 'รางวัลแรก', 'name_en': 'First',
                                 'desc_th': 'อธิบายหนึ่ง', 'desc_en': 'Description one',
                                 'limited': True, 'per_player_limit': '2',
                                 'quantity': '200', 'remaining': '179'}]
    assert missing[-1] == 'ชุดรางวัลที่ 1: Bundle'
    assert values['rewardDecoyClicks'] == '0' and values['submits'] == ['0']


def test_event_reward_waits_when_second_set_fields_mount_before_its_tabs():
    html = mutate_reward_mount('''if(i===1){
      const tabs=document.querySelector('[data-reward-section] [role=tablist]');
      const holder=document.createElement('div');tabs.replaceWith(holder);
      setTimeout(()=>holder.replaceWith(tabs),200);
    }''')
    missing, error, values = exercise_form(html, spec={**SPEC, 'rewards': [
        REWARD_REQUEST, {**REWARD_REQUEST, 'name_th': 'รางวัลสอง', 'name_en': 'Second'}]})
    assert error is None
    assert [r['name_th'] for r in values['rewards']] == ['รางวัลแรก', 'รางวัลสอง']
    assert [r['name_en'] for r in values['rewards']] == ['First', 'Second']
    assert missing[-2:] == ['ชุดรางวัลที่ 1: Bundle', 'ชุดรางวัลที่ 2: Bundle']
    assert values['languageClicks'] == '0' and values['submits'] == ['0']


@pytest.mark.parametrize('source,expected', ((None, '1'), ('0', '0'), (0, '1'), ('4', '4')))
def test_event_reward_preserves_existing_per_player_default_and_zero_semantics(source, expected):
    spec = {**SPEC, 'rewards': [{**REWARD_REQUEST, 'uses_per_user': source}]}
    missing, error, values = exercise_form(event_reward_html(), spec=spec)
    assert error is None
    assert values['rewards'][0]['per_player_limit'] == expected
    assert 'ชุดรางวัลที่ 1: จำกัดต่อผู้เล่น' not in missing
    assert values['submits'] == ['0']


@pytest.mark.parametrize('field,label', (
    ('name_th', 'ชื่อรางวัล (ไทย)'), ('name_en', 'ชื่อรางวัล (อังกฤษ)'),
    ('desc_th', 'desc_th'), ('desc_en', 'desc_en'), ('per_player_limit', 'จำกัดต่อผู้เล่น'),
))
def test_event_reward_rejected_value_is_reported_as_incomplete_not_success(field, label):
    html = mutate_reward_mount("""const rejected=document.getElementById('rewards.'+i+'.%s');
      rejected.addEventListener('input',()=>{rejected.value='';});""" % field)
    missing, error, values = exercise_form(html, spec={**SPEC, 'rewards': [REWARD_REQUEST]})
    assert error is None
    assert 'ชุดรางวัลที่ 1: %s' % label in missing
    assert values['submits'] == ['0']


def test_event_empty_optional_reward_descriptions_do_not_require_unrequested_controls():
    html = mutate_reward_mount("""document.getElementById('rewards.'+i+'.desc_th').remove();
      document.getElementById('rewards.'+i+'.desc_en').remove();""")
    missing, error, values = exercise_form(html, spec={**SPEC, 'rewards': [
        {**REWARD_REQUEST, 'desc_th': '', 'desc_en': None}]})
    assert error is None
    assert missing[-1] == 'ชุดรางวัลที่ 1: Bundle'
    assert not any('desc_' in entry for entry in missing)
    assert values['submits'] == ['0']


@pytest.mark.parametrize('fault', ('duplicate-ordinal', 'wrong-type', 'invalid-state',
                                  'multiple-active', 'no-activation'))
def test_event_reward_tab_contract_failure_stops_before_filling_second_set(fault):
    changes = {
        'duplicate-ordinal': "tab.after(tab.cloneNode(true));",
        'wrong-type': "tab.type='submit';",
        'invalid-state': "tab.setAttribute('aria-selected','maybe');",
        'multiple-active': "section.querySelector('[role=tab]').setAttribute('aria-selected','true');",
        'no-activation': "tab.setAttribute('aria-selected','false');tab.onclick=()=>{};",
    }
    html = mutate_reward_mount('''if(i===1){
        const section=document.querySelector('[data-reward-section]');
        const tab=section.querySelectorAll('[role=tab]')[1];%s
      }''' % changes[fault])
    missing, error, values = exercise_form(
        html, spec={**SPEC, 'rewards': [REWARD_REQUEST, {**REWARD_REQUEST, 'name_th': 'สอง'}]})
    assert isinstance(error, AztekLocatorError)
    assert 'ชุดรางวัลที่ 2' in str(error)
    assert missing is None
    assert values['rewards'][0]['name_th'] == 'รางวัลแรก'
    assert values['rewards'][1]['name_th'] == 'ชุดที่ 2'
    assert values['languageClicks'] == '0' and values['submits'] == ['0']


def test_event_queue_reward_id_failure_reports_error_without_submitting(monkeypatch):
    html = mutate_reward_mount("document.getElementById('rewards.'+i+'.name_en').remove();")
    html = html[html.index('<main>'):]
    traffic, snapshots = routed_runner_browser(monkeypatch, html, preview_urls=CREATE_URLS)
    results = asyncio.run(EventBuilder(lambda *_: None).run_many(
        'CabalM TH', [{**SPEC, 'rewards': [REWARD_REQUEST]}], {'cookies': [], 'origins': []}))
    assert len(results) == 1
    assert results[0]['saved'] is False and results[0]['made_id'] is None
    assert 'ชุดรางวัลที่ 1: ชื่อรางวัล (อังกฤษ)' in results[0]['error']
    assert snapshots[0]['submits'] == ['0']
    assert traffic == [('GET', CREATE_URLS[0])]


def mutate_reward_counts(script):
    return event_reward_html() + '''<script>
      const originalCounts=renderEventRewardCounts;
      renderEventRewardCounts=i=>{originalCounts(i);if(eventRewardValues[i].limited){%s}};
    </script>''' % script


def test_event_reward_counters_keep_two_sets_separate_from_header_and_decoys():
    html = event_reward_html().replace('</form>', '''
      <input id="rewards.0.quantity" type="number" data-counter-decoy value="901">
      <input id="rewards.0.remaining" type="number" data-counter-decoy value="902">
      <input name="rewards.1.quantity" type="number" data-counter-decoy value="903">
      <input name="rewards.1.remaining" type="number" data-counter-decoy value="904">
    </form>''')
    missing, error, values = exercise_form(html, spec={**SPEC, 'quantity': '80', 'remaining': '60',
        'rewards': [REWARD_REQUEST, {**REWARD_REQUEST, 'name_th': 'สอง',
                                   'quantity': '19', 'remaining': '7'}]})
    assert error is None
    assert [(r['quantity'], r['remaining']) for r in values['rewards']] == [('200', '179'), ('19', '7')]
    assert values['counters'] == ['1', '80', '60']
    assert values['counterDecoys'] == ['901', '902', '903', '904']
    assert missing[-2:] == ['ชุดรางวัลที่ 1: Bundle', 'ชุดรางวัลที่ 2: Bundle']
    assert values['submits'] == ['0']


@pytest.mark.parametrize('field,label', (('quantity', 'จำนวนทั้งหมด'), ('remaining', 'คงเหลือ')))
@pytest.mark.parametrize('fault', ('missing', 'duplicate', 'text-type', 'hidden'))
def test_event_reward_counter_contract_failure_names_its_set_and_stops(field, label, fault):
    mutations = {'missing': 'el.remove();', 'duplicate': 'el.after(el.cloneNode(true));',
                 'text-type': "el.type='text';", 'hidden': 'el.hidden=true;'}
    html = mutate_reward_counts("const el=document.getElementById('rewards.'+i+'.%s');%s" %
                                (field, mutations[fault]))
    missing, error, values = exercise_form(html, spec={**SPEC, 'rewards': [REWARD_REQUEST]})
    assert isinstance(error, AztekLocatorError)
    assert 'ชุดรางวัลที่ 1: %s' % label in str(error)
    assert missing is None
    assert values['counters'] == ['1', '0', '0']
    assert values['submits'] == ['0']


@pytest.mark.parametrize('field,label', (('quantity', 'จำนวนทั้งหมด'), ('remaining', 'คงเหลือ')))
def test_event_reward_counter_readback_mismatch_is_incomplete(field, label):
    html = mutate_reward_counts("""const el=document.getElementById('rewards.'+i+'.%s');
      el.addEventListener('input',()=>{el.value='';});""" % field)
    missing, error, values = exercise_form(html, spec={**SPEC, 'rewards': [REWARD_REQUEST]})
    assert error is None
    assert 'ชุดรางวัลที่ 1: %s' % label in missing
    assert values['submits'] == ['0']


@pytest.mark.parametrize('field,label', (('quantity', 'จำนวนทั้งหมด'), ('remaining', 'คงเหลือ')))
@pytest.mark.parametrize('value', (None, ''))
def test_event_limited_reward_requires_an_explicit_counter_value(field, label, value):
    missing, error, values = exercise_form(event_reward_html(), spec={**SPEC, 'rewards': [
        {**REWARD_REQUEST, field: value}]})
    assert error is None
    assert 'ชุดรางวัลที่ 1: %s' % label in missing
    assert values['rewards'][0][field] == ''
    assert values['submits'] == ['0']


@pytest.mark.parametrize('value', (0, '0'))
def test_event_reward_runner_preserves_explicit_zero_without_changing_api_validation(value):
    # The API still rejects non-positive limited counts. At the runner seam,
    # zero is an explicit numeric value, not a missing value or a default.
    missing, error, values = exercise_form(event_reward_html(), spec={**SPEC, 'rewards': [
        {**REWARD_REQUEST, 'quantity': value, 'remaining': value}]})
    assert error is None
    assert values['rewards'][0]['quantity'] == '0' and values['rewards'][0]['remaining'] == '0'
    assert 'ชุดรางวัลที่ 1: จำนวนทั้งหมด' not in missing
    assert 'ชุดรางวัลที่ 1: คงเหลือ' not in missing
    assert values['submits'] == ['0']


def test_event_unlimited_reward_does_not_require_hidden_counter_controls():
    missing, error, values = exercise_form(event_reward_html(), spec={**SPEC, 'rewards': [
        {**REWARD_REQUEST, 'limited': False, 'quantity': '999', 'remaining': '888'}]})
    assert error is None
    assert values['rewards'][0]['quantity'] == '0' and values['rewards'][0]['remaining'] == '0'
    assert missing[-1] == 'ชุดรางวัลที่ 1: Bundle'
    assert 'ชุดรางวัลที่ 1: จำนวนทั้งหมด' not in missing
    assert 'ชุดรางวัลที่ 1: คงเหลือ' not in missing
    assert values['submits'] == ['0']


def test_event_reward_waits_for_counter_fields_after_enabling_limit():
    html = event_reward_html() + '''<script>
      const originalCounts=renderEventRewardCounts;
      renderEventRewardCounts=i=>{if(eventRewardValues[i].limited)
        setTimeout(()=>originalCounts(i),200);else originalCounts(i);};
    </script>'''
    missing, error, values = exercise_form(html, spec={**SPEC, 'rewards': [REWARD_REQUEST]})
    assert error is None
    assert (values['rewards'][0]['quantity'], values['rewards'][0]['remaining']) == ('200', '179')
    assert missing[-1] == 'ชุดรางวัลที่ 1: Bundle'
    assert values['submits'] == ['0']


def test_event_queue_broken_reward_counter_never_submits_or_reports_created(monkeypatch):
    html = mutate_reward_counts("document.getElementById('rewards.'+i+'.quantity').remove();")
    html = html[html.index('<main>'):]
    traffic, snapshots = routed_runner_browser(monkeypatch, html, preview_urls=CREATE_URLS)
    results = asyncio.run(EventBuilder(lambda *_: None).run_many(
        'CabalM TH', [{**SPEC, 'rewards': [REWARD_REQUEST]}], {'cookies': [], 'origins': []}))
    assert len(results) == 1
    assert results[0]['saved'] is False and results[0]['made_id'] is None
    assert 'ชุดรางวัลที่ 1: จำนวนทั้งหมด' in results[0]['error']
    assert snapshots[0]['submits'] == ['0']
    assert traffic == [('GET', CREATE_URLS[0])]


@pytest.mark.parametrize('url', CREATE_URLS)
def test_event_type_uses_own_redemption_section_not_first_select(url):
    decoy = ('<select data-type-decoy><option value="WINNER">WINNER</option>'
             '<option value="ALL">ALL</option></select>')
    html = HEADER_HTML.replace('<main>', decoy + '<main>').replace(
        '  <section><header>', '  <section><h2>ชุดรางวัล</h2>' + decoy + '</section>\n  <section><header>', 1)
    missing, error, values = exercise_form(html, url=url, spec={**SPEC, 'type': 'ALL'})
    assert error is None
    assert values['eventType'] == 'ALL'
    assert values['typeText'] == 'ALL'
    assert values['typeDecoys'] == ['WINNER', 'WINNER']
    assert missing == ['วันเริ่มกิจกรรม', 'วันสิ้นสุดกิจกรรม',
                       'วันเริ่มรับรางวัล', 'วันสิ้นสุดการรับรางวัล', 'ชุดรางวัล']
    assert values['submits'] == ['0']


@pytest.mark.parametrize('game,url', tuple(zip(
    ('CabalM TH', 'CabalM SEA', 'CabalPC TH', 'CabalPC SEA'), CREATE_URLS)))
def test_event_preview_readiness_uses_form_name_id_when_name_attribute_changes(monkeypatch, game, url):
    # Real run/open/fill lifecycle; only browser traffic is replaced.
    html = HEADER_HTML[HEADER_HTML.index('<main>'):].replace(
        'name="name_th" data-decoy', 'name="old-name" data-decoy')
    traffic, snapshots = routed_runner_browser(monkeypatch, html, preview_urls=CREATE_URLS)
    result = asyncio.run(EventBuilder(lambda *_: None).run(
        game, SPEC, {'cookies': [], 'origins': []}))
    assert result['missing'] == ['วันเริ่มกิจกรรม', 'วันสิ้นสุดกิจกรรม',
                                 'วันเริ่มรับรางวัล', 'วันสิ้นสุดการรับรางวัล', 'ชุดรางวัล']
    assert snapshots == [{'names': ['กิจกรรมที่ขอ', 'Requested event', 'requested-event'],
                          'submits': ['0']}]
    assert traffic == [('GET', url)]


@pytest.mark.parametrize('fault', (
    'missing-trigger', 'duplicate-trigger', 'hidden-trigger', 'submit-trigger',
    'disabled-trigger', 'aria-disabled-trigger', 'wrong-role', 'wrong-label',
    'wrong-section', 'duplicate-owner', 'missing-native', 'duplicate-native',
    'disabled-native', 'multiple-native', 'missing-option', 'duplicate-option',
    'stale-trigger-readback', 'rejected-native-readback',
))
def test_event_type_contract_failure_cannot_choose_another_select_or_submit(fault):
    html = HEADER_HTML
    trigger = '<button type="button" role="combobox" aria-expanded="false">WINNER</button>'
    start = html.index('<select aria-hidden="true"')
    end = html.index('</select>', start) + len('</select>')
    native = html[start:end]
    if fault == 'missing-trigger':
        html = html.replace(trigger, '')
    elif fault == 'duplicate-trigger':
        html = html.replace(trigger, trigger + trigger)
    elif fault == 'hidden-trigger':
        html = html.replace(trigger, trigger.replace('<button ', '<button hidden '))
    elif fault == 'submit-trigger':
        html = html.replace(trigger, trigger.replace('type="button"', 'type="submit"'))
    elif fault in ('disabled-trigger', 'aria-disabled-trigger'):
        attribute = 'disabled' if fault == 'disabled-trigger' else 'aria-disabled="true"'
        html = html.replace(trigger, trigger.replace('<button ', '<button %s ' % attribute))
    elif fault == 'wrong-role':
        html = html.replace('role="combobox"', 'role="listbox"')
    elif fault == 'wrong-label':
        html = html.replace('<label>ผู้มีสิทธิ์รับรางวัล</label>', '<label>เปลี่ยน label</label>')
    elif fault == 'wrong-section':
        html = html.replace('<h2>การรับรางวัล</h2>', '<h2>อีกส่วนหนึ่ง</h2>')
    elif fault == 'duplicate-owner':
        start_owner = html.index('<section><header>')
        end_owner = html.index('</section>', start_owner) + len('</section>')
        owner = html[start_owner:end_owner]
        html = html.replace(owner, owner + owner)
    elif fault == 'missing-native':
        html = html.replace(native, '')
    elif fault == 'duplicate-native':
        html = html.replace(native, native + native)
    elif fault in ('disabled-native', 'multiple-native'):
        attribute = 'disabled' if fault == 'disabled-native' else 'multiple'
        html = html.replace(native, native.replace('<select ', '<select %s ' % attribute))
    elif fault == 'missing-option':
        html = html.replace('<option value="ALL">ALL</option>', '')
    elif fault == 'duplicate-option':
        html = html.replace('<option value="ALL">ALL</option>', '<option value="ALL">ALL</option>' * 2)
    elif fault == 'stale-trigger-readback':
        html = html.replace('this.previousElementSibling.textContent=this.selectedOptions[0].textContent', '')
    else:
        html = html.replace('this.previousElementSibling.textContent=this.selectedOptions[0].textContent',
                            "this.value='WINNER';this.previousElementSibling.textContent='ALL'")
    decoy = '<select data-type-decoy><option>WINNER</option><option>ALL</option></select>'
    html = html.replace('</aside>', decoy + '</aside>')
    missing, error, values = exercise_form(html, spec={**SPEC, 'type': 'ALL'})
    assert isinstance(error, AztekLocatorError)
    assert 'ผู้มีสิทธิ์รับรางวัล' in str(error)
    assert missing is None
    assert values['typeDecoys'] == ['WINNER']
    assert values['submits'] == ['0']
    if fault in ('disabled-trigger', 'aria-disabled-trigger'):
        assert values['eventType'] == 'WINNER'


@pytest.mark.parametrize('wanted', ('WINNER', 'ALL', None))
def test_event_type_preserves_default_or_requested_value(wanted):
    html = HEADER_HTML.replace(
        '<option value="ALL">ALL</option>', '<option value="ALL" selected>ALL</option>').replace(
        'aria-expanded="false">WINNER', 'aria-expanded="false">ALL')
    missing, error, values = exercise_form(html, spec={**SPEC, 'type': wanted})
    assert error is None
    assert values['eventType'] == ('ALL' if wanted == 'ALL' else 'WINNER')
    assert values['typeText'] == ('ALL' if wanted == 'ALL' else 'WINNER')
    assert 'ชุดรางวัล' in missing
    assert values['submits'] == ['0']


def test_event_type_waits_for_lazy_owner_mount_without_borrowing_decoy():
    start = HEADER_HTML.index('<section><header>')
    end = HEADER_HTML.index('</section>', start) + len('</section>')
    owner = HEADER_HTML[start:end]
    html = HEADER_HTML.replace(owner, '<div id="lazy-owner"></div>')
    html += '<script>setTimeout(()=>{document.getElementById("lazy-owner").outerHTML=' + repr(owner) + ';},200)</script>'
    missing, error, values = exercise_form(html, spec={**SPEC, 'type': 'ALL'})
    assert error is None
    assert values['eventType'] == 'ALL' and values['typeText'] == 'ALL'
    assert 'ชุดรางวัล' in missing
    assert values['submits'] == ['0']


@pytest.mark.parametrize('placement', ('sibling', 'nested'))
def test_event_type_owner_cannot_escape_into_sibling_or_nested_section(placement):
    start = HEADER_HTML.index('<section><header>')
    end = HEADER_HTML.index('</section>', start) + len('</section>')
    owner = HEADER_HTML[start:end]
    broken_owner = owner.replace(
        '<button type="button" role="combobox" aria-expanded="false">WINNER</button>', '')
    decoy = owner.replace('<h2>การรับรางวัล</h2>', '<h2>รางวัลอีกส่วน</h2>').replace(
        'data-event-type', 'data-type-decoy')
    replacement = ('<section>' + broken_owner + decoy + '</section>' if placement == 'sibling'
                   else broken_owner.replace('</section>', decoy + '</section>'))
    missing, error, values = exercise_form(HEADER_HTML.replace(owner, replacement),
                                          spec={**SPEC, 'type': 'ALL'})
    assert isinstance(error, AztekLocatorError)
    assert 'ผู้มีสิทธิ์รับรางวัล' in str(error)
    assert missing is None
    assert values['eventType'] == 'WINNER' and values['typeDecoys'] == ['WINNER']
    assert values['submits'] == ['0']


@pytest.mark.parametrize('fault', ('transient-disabled', 'disabled-after-option', 'wrong-type-after-option',
                                  'disabled-during-native-readiness'))
def test_event_type_rechecks_trigger_readiness_after_lazy_option_mount(fault):
    html = (HEADER_HTML.replace('<select aria-hidden=', '<select disabled aria-hidden=')
            if fault == 'disabled-during-native-readiness'
            else HEADER_HTML.replace('<option value="ALL">ALL</option>', ''))
    if fault == 'transient-disabled':
        html = html.replace('role="combobox" aria-expanded=', 'disabled role="combobox" aria-expanded=')
    action = {'transient-disabled': 'trigger.disabled=false',
              'disabled-after-option': 'trigger.disabled=true',
              'wrong-type-after-option': "trigger.type='submit'",
              'disabled-during-native-readiness': 'native.disabled=false;trigger.disabled=true'}[fault]
    html += '''<script>setTimeout(()=>{
      const native=document.querySelector('[data-event-type]');const trigger=native.previousElementSibling;
      ACTION;INSERT_OPTION
    },700)</script>'''.replace('ACTION', action).replace('INSERT_OPTION',
        '' if fault == 'disabled-during-native-readiness' else
        '''native.insertAdjacentHTML('beforeend','<option value="ALL">ALL</option>');''')
    missing, error, values = exercise_form(html, spec={**SPEC, 'type': 'ALL'})
    if fault == 'transient-disabled':
        assert error is None
        assert values['eventType'] == 'ALL' and values['typeText'] == 'ALL'
        assert 'ชุดรางวัล' in missing
    else:
        assert isinstance(error, AztekLocatorError)
        assert 'ผู้มีสิทธิ์รับรางวัล' in str(error)
        assert missing is None
        assert values['eventType'] == 'WINNER'
    assert values['submits'] == ['0']


def test_event_type_ignores_an_identical_owner_outside_main_form():
    start = HEADER_HTML.index('<section><header>')
    end = HEADER_HTML.index('</section>', start) + len('</section>')
    decoy = HEADER_HTML[start:end].replace('data-event-type', 'data-type-decoy')
    html = HEADER_HTML.replace('</aside>', decoy + '</aside>')
    missing, error, values = exercise_form(html, spec={**SPEC, 'type': 'ALL'})
    assert error is None
    assert values['eventType'] == 'ALL' and values['typeDecoys'] == ['WINNER']
    assert 'ชุดรางวัล' in missing
    assert values['submits'] == ['0']


def test_event_preview_waits_for_lazy_id_without_legacy_name(monkeypatch):
    html = HEADER_HTML[HEADER_HTML.index('<main>'):].replace(
        'name="name_th" data-decoy', 'name="old-name" data-decoy').replace(
        '<input id="name_th" name="renamed-th">', '<span id="lazy-name"></span>')
    html += '''<script>setTimeout(()=>{document.getElementById('lazy-name').outerHTML=
      '<input id="name_th" name="another-name">';},700)</script>'''
    traffic, snapshots = routed_runner_browser(monkeypatch, html, preview_urls=CREATE_URLS)
    result = asyncio.run(EventBuilder(lambda *_: None).run(
        'CabalM TH', SPEC, {'cookies': [], 'origins': []}))
    assert 'ชุดรางวัล' in result['missing']
    assert snapshots == [{'names': ['กิจกรรมที่ขอ', 'Requested event', 'requested-event'], 'submits': ['0']}]
    assert traffic == [('GET', CREATE_URLS[0])]


def test_event_queue_cannot_submit_after_redemption_contract_breaks(monkeypatch):
    html = HEADER_HTML[HEADER_HTML.index('<main>'):].replace(
        'type="button" role="combobox"', 'type="submit" role="combobox"')
    traffic, snapshots = routed_runner_browser(monkeypatch, html, preview_urls=CREATE_URLS)
    results = asyncio.run(EventBuilder(lambda *_: None).run_many(
        'CabalM TH', [SPEC], {'cookies': [], 'origins': []}))
    assert len(results) == 1
    assert results[0]['saved'] is False and results[0]['made_id'] is None
    assert 'ผู้มีสิทธิ์รับรางวัล' in results[0]['error']
    assert snapshots[0]['submits'] == ['0']
    assert traffic == [('GET', CREATE_URLS[0])]


def event_calendar_html():
    # Reuse the network-boundary widget proven in Item Code, not its form.
    widget_html = itemcode_calendar_html()
    widget_html = widget_html[widget_html.index('<div role="dialog" id="other-calendar"'):]
    # Live options have no stable ID and carry the hour in a child span.
    widget_html = widget_html.replace(
        "option.textContent=String(number).padStart(2,'0');",
        "option.innerHTML='<span aria-hidden=\"true\"><svg></svg></span><span>'+String(number).padStart(2,'0')+'</span>';")
    buttons = ''
    for field, key, label in reversed(DATE_CONTROLS):
        buttons += ('<label>%s</label><button type="button" '
                    'onclick="document.body.dataset.dateDecoyClicks=1">decoy</button>'
                    '<section><label>Changed date label</label><button id="%s" type="button" '
                    'aria-haspopup="dialog" onclick="openCalendar(this)">เลือกวันและเวลา</button></section>'
                    % (label, field))
    outside = ''.join('<button id="%s" type="button" '
                      'onclick="document.body.dataset.dateDecoyClicks=1">outside date</button>' % field
                      for field, _, _ in DATE_CONTROLS)
    return (HEADER_HTML.replace('</aside>', outside + '</aside>')
            .replace('</form>', buttons + '</form>') + widget_html)


@pytest.mark.parametrize('url', CREATE_URLS)
def test_event_activity_and_claim_windows_target_their_own_ids_with_exact_seconds(url):
    missing, error, values = exercise_form(event_calendar_html(), url=url, spec={
        **SPEC, 'start_event': '2026-08-27 00:00:00', 'end_event': '2026-08-28 23:59:59',
        'start_claim': '2027-09-27 03:04:05', 'end_claim': '2027-09-28 23:59:59'})
    assert error is None
    assert values['dates'] == ['27 Aug 2026 00:00:00', '28 Aug 2026 23:59:59',
                               '27 Sep 2027 03:04:05', '28 Sep 2027 23:59:59']
    assert missing == ['ชุดรางวัล']
    assert values['dateDecoyClicks'] == '0'
    assert values['calendarDecoys'] == ['17', '16']
    assert values['submits'] == ['0']


@pytest.mark.parametrize(('field', 'key', 'label'), DATE_CONTROLS)
@pytest.mark.parametrize('fault', ('missing', 'duplicate', 'submit-type', 'hidden'))
def test_event_broken_date_id_cannot_use_labels_or_outside_form_controls(field, key, label, fault):
    before, form_html = event_calendar_html().split('<main>', 1)
    start = form_html.index('<button id="%s"' % field)
    end = form_html.index('</button>', start) + len('</button>')
    control = form_html[start:end]
    replacement = {
        'missing': '', 'duplicate': control + control,
        'submit-type': control.replace('type="button"', 'type="submit"'),
        'hidden': control.replace('<button ', '<button hidden '),
    }[fault]
    missing, error, values = exercise_form(before + '<main>' + form_html.replace(control, replacement),
                                          spec={**SPEC, key: '2026-10-08 23:59:59'})
    assert isinstance(error, AztekLocatorError)
    assert label in str(error)
    assert missing is None
    assert values['dateDecoyClicks'] == '0'
    assert values['calendarDecoys'] == ['17', '16']
    assert values['submits'] == ['0']


@pytest.mark.parametrize('fault', ('no-relation', 'duplicate-popup', 'wrong-popup-role'))
def test_event_date_popup_contract_failure_does_not_borrow_the_other_calendar(fault):
    html = event_calendar_html()
    if fault == 'no-relation':
        html = html.replace("trigger.setAttribute('aria-controls',dialog.id);", '')
    elif fault == 'duplicate-popup':
        html = html.replace('document.body.append(dialog);',
                            'document.body.append(dialog);document.body.append(dialog.cloneNode(true));')
    else:
        html = html.replace("dialog.setAttribute('role','dialog')", "dialog.setAttribute('role','listbox')")
    missing, error, values = exercise_form(html, spec={**SPEC, 'start_event': '2026-10-08 23:59:59'})
    assert isinstance(error, AztekLocatorError)
    assert 'วันเริ่มกิจกรรม' in str(error)
    assert missing is None
    assert values['calendarDecoys'] == ['17', '16']
    assert values['dateDecoyClicks'] == '0'
    assert values['submits'] == ['0']


@pytest.mark.parametrize(('field', 'key', 'label'), DATE_CONTROLS)
def test_event_datetime_readback_mismatch_names_the_affected_window(field, key, label):
    html = event_calendar_html().replace('minute.onblur=display;',
                                         "minute.onblur=()=>{second.value='00';display();};")
    missing, error, values = exercise_form(html, spec={**SPEC, key: '2026-10-08 23:59:59'})
    assert error is None
    assert label in missing
    assert values['dates'][[item[0] for item in DATE_CONTROLS].index(field)] == '08 Oct 2026 23:59:00'
    assert values['calendarDecoys'] == ['17', '16']
    assert values['submits'] == ['0']


def test_event_waits_for_a_lazily_mounted_calendar_relation():
    html = event_calendar_html().replace("trigger.setAttribute('aria-controls',dialog.id);", '')
    html = html.replace('document.body.append(dialog);',
                        "setTimeout(()=>{document.body.append(dialog);trigger.setAttribute('aria-controls',dialog.id);},250);")
    missing, error, values = exercise_form(html, spec={**SPEC, 'end_claim': '2027-09-28 23:59:59'})
    assert error is None
    assert values['dates'] == ['เลือกวันและเวลา', 'เลือกวันและเวลา',
                               'เลือกวันและเวลา', '28 Sep 2027 23:59:59']
    assert missing == ['วันเริ่มกิจกรรม', 'วันสิ้นสุดกิจกรรม', 'วันเริ่มรับรางวัล', 'ชุดรางวัล']
    assert values['calendarDecoys'] == ['17', '16']
    assert values['submits'] == ['0']


@pytest.mark.parametrize(('field', 'key', 'label'), DATE_CONTROLS)
def test_event_invalid_datetime_does_not_open_the_affected_calendar(field, key, label):
    missing, error, values = exercise_form(event_calendar_html(), spec={**SPEC, key: '2026-02-30 00:00:00'})
    assert error is None
    assert label in missing
    assert values['dates'] == ['เลือกวันและเวลา', 'เลือกวันและเวลา', 'เลือกวันและเวลา', 'เลือกวันและเวลา']
    assert values['calendarDecoys'] == ['17', '16']
    assert values['dateDecoyClicks'] == '0'
    assert values['submits'] == ['0']


@pytest.mark.parametrize('fault', ('wrong-hour-label', 'hidden-duplicate-hour'))
def test_event_hour_choices_require_exact_unique_labels_inside_the_related_listbox(fault):
    html = event_calendar_html()
    if fault == 'wrong-hour-label':
        html = html.replace("String(number).padStart(2,'0')+'</span>'",
                            "(number===23?'123':String(number).padStart(2,'0'))+'</span>'")
    else:
        html = html.replace('list.append(option);',
                            'list.append(option);if(number===23){const duplicate=option.cloneNode(true);duplicate.hidden=true;list.append(duplicate);}')
    missing, error, values = exercise_form(html, spec={**SPEC, 'end_event': '2026-10-08 23:59:59'})
    assert isinstance(error, AztekLocatorError)
    assert 'วันสิ้นสุดกิจกรรม' in str(error)
    assert missing is None
    assert values['calendarDecoys'] == ['17', '16']
    assert values['submits'] == ['0']


@pytest.mark.parametrize('url', CREATE_URLS)
def test_event_counters_use_form_ids_and_leave_named_and_outside_decoys_untouched(url):
    missing, error, values = exercise_form(COUNTER_HTML, url=url, spec={
        **SPEC, 'uses_per_user': '2', 'quantity': '200', 'remaining': '175'})
    assert error is None
    assert values['counters'] == ['2', '200', '175']
    assert values['counterDecoys'] == ['1', '0', '0']
    assert values['outside'] == ['outside-slug', 'outside-th', 'outside-en', '901', '902', '903']
    assert values['submits'] == ['0']
    assert missing == ['วันเริ่มกิจกรรม', 'วันสิ้นสุดกิจกรรม',
                       'วันเริ่มรับรางวัล', 'วันสิ้นสุดการรับรางวัล', 'ชุดรางวัล']


@pytest.mark.parametrize('spec_values', ({},
    {'uses_per_user': '', 'quantity': '', 'remaining': ''},
    {'uses_per_user': '1', 'quantity': 0, 'remaining': 0},
    {'uses_per_user': 0, 'quantity': '0', 'remaining': '0'},
))
def test_event_counter_defaults_and_zero_counts_keep_existing_behavior(spec_values):
    missing, error, values = exercise_form(COUNTER_HTML, spec={**SPEC, **spec_values})
    assert error is None
    assert values['counters'] == ['1', '0', '0']
    assert values['counterDecoys'] == ['1', '0', '0']
    assert not any(label in missing for _, _, label in COUNTER_FIELDS)
    assert values['submits'] == ['0']


@pytest.mark.parametrize(('field', 'key', 'label'), COUNTER_FIELDS)
@pytest.mark.parametrize('fault', ('missing', 'duplicate', 'wrong-type', 'hidden'))
def test_event_counter_broken_id_stops_without_named_or_outside_fallback(field, key, label, fault):
    # Modify only the owning form; the outside matching ID must never rescue it.
    before, form_html = COUNTER_HTML.split('<main>', 1)
    start = form_html.index('<input id="%s"' % field)
    end = form_html.index('>', start) + 1
    control = form_html[start:end]
    replacement = {
        'missing': '', 'duplicate': control + control,
        'wrong-type': control.replace('type="number"', 'type="text"'),
        'hidden': control.replace('<input ', '<input hidden '),
    }[fault]
    missing, error, values = exercise_form(before + '<main>' + form_html.replace(control, replacement))
    assert isinstance(error, AztekLocatorError)
    assert label in str(error)
    assert missing is None
    assert values['counterDecoys'] == ['1', '0', '0']
    assert values['outside'] == ['outside-slug', 'outside-th', 'outside-en', '901', '902', '903']
    assert values['submits'] == ['0']


@pytest.mark.parametrize(('field', 'key', 'label'), COUNTER_FIELDS)
def test_event_counter_rejected_readback_reports_the_specific_missing_field(field, key, label):
    before, form_html = COUNTER_HTML.split('<main>', 1)
    form_html = form_html.replace('<input id="%s"' % field,
                                 '<input oninput="this.value=\'7\'" id="%s"' % field)
    missing, error, values = exercise_form(before + '<main>' + form_html, spec={**SPEC, key: '9'})
    assert error is None
    assert label in missing
    assert values['counterDecoys'] == ['1', '0', '0']
    assert values['submits'] == ['0']


def test_event_waits_for_a_lazily_mounted_counter():
    control = '<input id="remaining" name="changed-remaining" type="number" value="83">'
    html = COUNTER_HTML.replace(control, '<span id="mount-counter"></span>')
    html += '''<script>setTimeout(() => {
        const field=document.createElement('input');field.id='remaining';field.type='number';
        field.name='changed-remaining';document.getElementById('mount-counter').replaceWith(field);
    }, 200);</script>'''
    missing, error, values = exercise_form(html, spec={**SPEC, 'remaining': '175'})
    assert error is None
    assert values['counters'] == ['1', '0', '175']
    assert 'คงเหลือ' not in missing
    assert values['counterDecoys'] == ['1', '0', '0']
    assert values['submits'] == ['0']


@pytest.mark.parametrize('url', CREATE_URLS)
def test_event_header_uses_owning_form_ids_despite_changed_names_and_order(url):
    missing, error, values = exercise_form(url=url)
    assert error is None
    assert values['header'] == ['requested-event', 'กิจกรรมที่ขอ', 'Requested event']
    assert values['decoys'] == ['keep-slug', 'keep-th', 'keep-en']
    assert values['outside'] == ['outside-slug', 'outside-th', 'outside-en']
    assert values['submits'] == ['0']
    assert missing == ['วันเริ่มกิจกรรม', 'วันสิ้นสุดกิจกรรม',
                       'วันเริ่มรับรางวัล', 'วันสิ้นสุดการรับรางวัล', 'ชุดรางวัล']


@pytest.mark.parametrize(('label', 'control'), (
    ('Slug', '<input id="slug" name="renamed-slug" value="event-generated">'),
    ('ชื่อ Event (ไทย)', '<input id="name_th" name="renamed-th">'),
    ('ชื่อ Event (อังกฤษ)', '<input id="name_en" name="renamed-en">'),
))
@pytest.mark.parametrize('fault', ('missing', 'duplicate', 'wrong-type'))
def test_event_header_broken_id_stops_without_filling_a_decoy(label, control, fault):
    replacement = {
        'missing': '',
        'duplicate': control + control,
        'wrong-type': control.replace('<input ', '<input type="number" '),
    }[fault]
    missing, error, values = exercise_form(HEADER_HTML.replace(control, replacement))
    assert isinstance(error, AztekLocatorError)
    assert label in str(error)
    assert missing is None
    assert values['decoys'] == ['keep-slug', 'keep-th', 'keep-en']
    assert values['outside'] == ['outside-slug', 'outside-th', 'outside-en']
    assert values['submits'] == ['0']


def test_event_does_not_guess_between_two_main_forms():
    html = HEADER_HTML.replace('</main>', '<form><input id="slug"></form></main>')
    missing, error, values = exercise_form(html)
    assert isinstance(error, AztekLocatorError)
    assert 'ฟอร์ม Event' in str(error)
    assert missing is None
    assert values['header'] == ['event-generated', '', '']
    assert values['decoys'] == ['keep-slug', 'keep-th', 'keep-en']
    assert values['submits'] == ['0', '0']


def test_event_empty_slug_clears_the_generated_placeholder_and_reports_missing():
    missing, error, values = exercise_form(spec={**SPEC, 'slug': ''})
    assert error is None
    assert values['header'] == ['', 'กิจกรรมที่ขอ', 'Requested event']
    assert 'Slug' in missing
    assert values['decoys'] == ['keep-slug', 'keep-th', 'keep-en']
    assert values['submits'] == ['0']


def test_event_waits_for_a_lazily_mounted_header_before_using_its_id():
    control = '<input id="name_en" name="renamed-en">'
    html = HEADER_HTML.replace(control, '<span id="mount-name"></span>')
    html += '''<script>setTimeout(() => {
        const field=document.createElement('input');field.id='name_en';field.name='renamed-en';
        document.getElementById('mount-name').replaceWith(field);
    }, 200);</script>'''
    missing, error, values = exercise_form(html)
    assert error is None
    assert values['header'] == ['requested-event', 'กิจกรรมที่ขอ', 'Requested event']
    assert 'ชื่อ Event (อังกฤษ)' not in missing
    assert values['decoys'] == ['keep-slug', 'keep-th', 'keep-en']
    assert values['submits'] == ['0']


def test_event_reports_a_header_value_that_does_not_read_back():
    html = HEADER_HTML.replace('<input id="name_th"',
                               '<input oninput="this.value=\'rejected\'" id="name_th"')
    missing, error, values = exercise_form(html)
    assert error is None
    assert values['header'] == ['requested-event', 'rejected', 'Requested event']
    assert 'ชื่อ Event (ไทย)' in missing
    assert values['decoys'] == ['keep-slug', 'keep-th', 'keep-en']
    assert values['submits'] == ['0']
