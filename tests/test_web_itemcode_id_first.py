"""Public Item Code runner against synthetic, network-isolated Aztek forms."""
import asyncio
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from playwright.async_api import async_playwright

from web.aztek_locator import AztekLocatorError
from web import activity_runner
from web.itemcode_runner import ItemCodeBuilder


HEADER_HTML = '''<main><h1>สร้าง Item Code</h1>
<form onsubmit="event.preventDefault(); this.dataset.submits='1'">
  <input name="name_th" data-decoy value="keep-th">
  <input name="name_en" data-decoy value="keep-en">
  <input name="slug" data-decoy value="keep-slug">
  <section><div><input id="name_th" name="renamed-th"></div></section>
  <section><input id="name_en" name="renamed-en"></section>
  <div><input id="slug" name="renamed-slug"></div>
  <div><button id="redeem_type" role="combobox" type="button">WINNER</button>
    <select onchange="this.previousElementSibling.textContent=this.selectedOptions[0].textContent">
      <option value="WINNER">WINNER</option><option value="ALL">ALL</option>
    </select></div>
  <input id="per_player_limit" name="per_player_limit" type="number" value="1">
  <label>เวลาเริ่มใช้งาน</label><button type="button">เลือกวันและเวลา</button>
  <label>เวลาสิ้นสุด</label><button type="button">เลือกวันและเวลา</button>
  <div><label>จำกัดจำนวน</label>
    <button id="is_limited" role="switch" type="button" aria-checked="false"
      onclick="this.setAttribute('aria-checked',this.getAttribute('aria-checked')==='true'?'false':'true')"></button>
  </div>
  <input id="quantity" name="quantity" type="number" value="7">
  <input id="remaining" name="remaining" type="number" value="6">
  <button type="submit">สร้าง Item Code</button>
</form></main>'''

SPEC = {'name_th': 'โค้ดที่ขอ', 'name_en': 'Requested code',
        'slug': 'requested-code', 'rewards': []}


def exercise_form(html=HEADER_HTML, spec=None):
    async def exercise():
        async with async_playwright() as driver:
            browser = await driver.chromium.launch(headless=True)
            context = await browser.new_context(service_workers='block')
            unexpected = []

            async def block(route):
                unexpected.append(route.request.url)
                await route.abort()

            await context.route('**/*', block)
            page = await context.new_page()
            await page.set_content(html)
            missing, error = None, None
            try:
                missing = await ItemCodeBuilder(lambda *_: None).fill_form(
                    page, dict(SPEC if spec is None else spec))
            except Exception as caught:
                error = caught
            values = await page.evaluate('''() => ({
                names: ['name_th','name_en','slug'].map(id =>
                    document.querySelector('[id="'+id+'"]')?.value),
                decoys: [...document.querySelectorAll('[data-decoy]')].map(e=>e.value),
                counts: [...document.querySelectorAll('input[name="quantity"],input[name="remaining"]')].map(e=>e.value),
                perUser: document.querySelector('[id="per_player_limit"]')?.value,
                limitState: document.querySelector('[id="is_limited"]')?.getAttribute('aria-checked'),
                idCounts: ['quantity','remaining'].map(id=>document.querySelector('[id="'+id+'"]')?.value),
                redeemText: document.querySelector('[id="redeem_type"]')?.textContent,
                redeemValue: document.querySelector('[id="redeem_type"]')?.parentElement.querySelector('select')?.value,
                typeDecoys: [...document.querySelectorAll('[data-type-decoy]')].map(e=>e.value),
                counterDecoys: [...document.querySelectorAll('[data-counter-decoy]')].map(e=>e.value),
                submits: [...document.querySelectorAll('form')].map(e=>e.dataset.submits || '0'),
                dates: ['start_at','end_at'].map(id=>document.getElementById(id)?.textContent),
                calendarDecoys: [...document.querySelectorAll('[data-calendar-decoy]')].map(e=>e.value),
                dateDecoyClicks: document.body.dataset.dateDecoyClicks || '0',
                rewardValues: JSON.parse(document.querySelector('#reward-values')?.textContent || '[]'),
                rewardDecoys: [...document.querySelectorAll('[data-reward-decoy]')].map(e=>e.value),
                outsideAdds: document.body.dataset.outsideAdds || '0',
                serverDecoys: [...document.querySelectorAll('[data-server-decoy]')].map(e=>e.value),
                pickerDecoys: [...document.querySelectorAll('[data-picker-decoy]')].map(e=>e.value),
                wrongPickerClicks: document.body.dataset.wrongPickerClicks || '0',
                bundleChanges: document.body.dataset.bundleChanges || '0'
            })''')
            await browser.close()
            assert unexpected == []
            return missing, error, values
    return asyncio.run(exercise())


def reward_html(base=HEADER_HTML):
    """Aztek mounts only the active set and retains each tab's form values."""
    html = base.replace('<button type="submit">สร้าง Item Code</button>', '''
      <button type="button" onclick="addReward()">+ เพิ่มของรางวัล</button>
      <div role="tablist"></div><section id="active-reward"></section>
      <output id="reward-values">[]</output>
      <button type="submit">สร้าง Item Code</button>''')
    # Legacy names/labels are plausible but do not identify the real fields.
    html = '<button type="button" onclick="document.body.dataset.outsideAdds=1">+ เพิ่มของรางวัล</button>' + html
    html += '''<aside>
      <input name="rewards.0.name_th" data-reward-decoy value="keep-th">
      <input name="rewards.0.name_en" data-reward-decoy value="keep-en">
      <input name="rewards.0.per_player_limit" data-reward-decoy value="99">
      <label>จำกัดจำนวน Code</label><button role="switch" type="button" aria-checked="false"></button>
      <input name="rewards.0.quantity" data-reward-decoy value="77">
      <input name="rewards.0.remaining" data-reward-decoy value="66">
      <textarea name="rewards.0.serial" data-reward-decoy>keep-codes</textarea>
    </aside><script>
      const rewards=[{name_th:'',name_en:'',per_player_limit:'1',is_limited:false,
        quantity:'7',remaining:'6',is_generate_code:'1',serial:'',prefix:'',amount:''}]; let activeReward=0;
      const panel=document.getElementById('active-reward');
      function showValues(){document.getElementById('reward-values').textContent=JSON.stringify(rewards);}
      function remember(){for(const field of panel.querySelectorAll('[data-field]')) {
        rewards[activeReward][field.dataset.field]=field.getAttribute('role')==='switch'
          ? field.getAttribute('aria-checked')==='true' : field.value;
      }showValues();}
      function renderReward(index) {
        activeReward=index;const r=rewards[index];panel.innerHTML='';
        const tabs=document.querySelector('main [role="tablist"]');tabs.innerHTML='';
        if(rewards.length>1) rewards.forEach((reward,i)=>{
          const tab=document.createElement('button');tab.type='button';tab.setAttribute('role','tab');
          tab.setAttribute('aria-selected',String(i===index));
          tab.innerHTML='<span>'+(i+1)+'</span><span>'+ (reward.name_th || 'ชุดที่ '+(i+1))+'</span>';
          tab.onclick=()=>{remember();panel.innerHTML='';setTimeout(()=>renderReward(i),150);};tabs.append(tab);
        });
        for(const [field,type] of [['name_th','text'],['name_en','text'],['per_player_limit','number']]) {
          const wrapper=document.createElement('div');const input=document.createElement('input');
          input.id='rewards.'+index+'.'+field;input.name='changed-'+index+'-'+field;input.type=type;
          input.dataset.field=field;input.value=r[field];input.oninput=remember;wrapper.append(input);panel.append(wrapper);
        }
        const toggle=document.createElement('button');toggle.type='button';toggle.id='rewards.'+index+'.is_limited';
        toggle.setAttribute('role','switch');toggle.setAttribute('aria-checked',String(r.is_limited));
        toggle.dataset.field='is_limited';toggle.onclick=()=>{r.is_limited=!r.is_limited;renderReward(index);};panel.append(toggle);
        if(r.is_limited) for(const field of ['quantity','remaining']) {
          const input=document.createElement('input');input.type='number';input.id='rewards.'+index+'.'+field;
          input.name='changed-'+field;input.dataset.field=field;input.value=r[field];input.oninput=remember;panel.append(input);
        }
        const wrapper=document.createElement('div');
        const trigger=document.createElement('button');trigger.type='button';trigger.setAttribute('role','combobox');
        trigger.id='rewards.'+index+'.is_generate_code';
        const select=document.createElement('select');select.dataset.field='is_generate_code';
        select.innerHTML='<option value="1">Fix Codes (ส่ง Code เอง)</option><option value="2">Server Generate (ระบบสุ่ม Code)</option>';
        select.value=r.is_generate_code;trigger.textContent=select.selectedOptions[0].textContent;
        select.onchange=()=>{trigger.textContent=select.selectedOptions[0].textContent;remember();renderCodeFields();};
        wrapper.append(trigger,select);panel.append(wrapper);
        const codeFields=document.createElement('section');panel.append(codeFields);
        function renderCodeFields(){
          codeFields.innerHTML='';
          if(r.is_generate_code==='2') for(const [field,type] of [['prefix','text'],['amount','number']]) {
            const input=document.createElement('input');input.id='rewards.'+index+'.'+field;
            input.type=type;input.name='changed-'+index+'-'+field;input.dataset.field=field;
            if(field==='prefix') input.maxLength=6;else input.min='1';
            input.value=r[field] || '';input.oninput=remember;codeFields.append(input);
          } else {
            const serial=document.createElement('textarea');serial.id='rewards.'+index+'.serial';
            serial.name='changed-serial';serial.dataset.field='serial';serial.value=r.serial;
            serial.oninput=remember;codeFields.append(serial);
          }
        }
        renderCodeFields();
        showValues();
      }
      function addReward(){remember();rewards.push({name_th:'',name_en:'',per_player_limit:'1',
        is_limited:false,quantity:'7',remaining:'6',is_generate_code:'1',serial:'',prefix:'',amount:''});
        panel.innerHTML='';setTimeout(()=>renderReward(rewards.length-1),150);}
      renderReward(0);
    </script>'''
    return html


def server_reward_html(base=HEADER_HTML):
    return reward_html(base) + '''<aside>
      <input name="rewards.0.prefix" data-server-decoy value="KEEP-A">
      <input name="rewards.0.amount" data-server-decoy value="91">
      <input name="rewards.2.prefix" data-server-decoy value="KEEP-B">
      <input name="rewards.2.amount" data-server-decoy value="92">
    </aside>'''


def bundle_reward_html(base=HEADER_HTML):
    html = reward_html(base).replace(
        'renderCodeFields();\n        showValues();',
        'renderCodeFields();renderBundle(index);\n        showValues();')
    html = html.replace('<section id="active-reward"></section>', '<div id="active-reward"></div>')
    html = html.replace('function addReward(){', '''
      function renderBundle(index){
        const r=rewards[index];let section=panel.querySelector('[data-bundle-section]');
        if(!section){section=document.createElement('div');section.dataset.bundleSection=index;panel.append(section);}
        section.innerHTML='<label>Bundle <span>*</span></label>';
        if(r.bundle_id){
          const row=document.createElement('div');const badge=document.createElement('span');
          badge.textContent='…loading';row.append(badge);
          const change=document.createElement('button');change.type='button';change.textContent='เปลี่ยน';
          change.onclick=()=>{document.body.dataset.bundleChanges=Number(document.body.dataset.bundleChanges||0)+1;
            r.bundle_id='';showValues();renderBundle(index);};row.append(change);section.append(row);
          setTimeout(()=>{badge.textContent='#'+r.bundle_id+' — Bundle selected';},150);
        } else {
          const button=document.createElement('button');button.type='button';button.textContent='เลือก bundle';
          button.dataset.slot='popover-trigger';button.setAttribute('aria-haspopup','dialog');
          button.setAttribute('aria-expanded','false');section.append(button);
          button.onclick=()=>{
            const dialog=document.createElement('div');dialog.id='runtime-bundle-'+index;
            dialog.setAttribute('role','dialog');dialog.dataset.state='open';dialog.dataset.slot='popover-content';
            button.setAttribute('aria-controls',dialog.id);button.setAttribute('aria-expanded','true');
            const box=document.createElement('input');box.type='text';box.placeholder='ค้นหาด้วยชื่อหรือ id';dialog.append(box);
            const results=document.createElement('div');dialog.append(results);
            function rows(){results.innerHTML='';for(const id of ['10010','1001','2002']){
              if(!id.includes(box.value))continue;
              const hit=document.createElement('button');hit.type='button';
              hit.innerHTML='<span>Bundle result</span><span>ID: '+id+'</span>';
              hit.onclick=()=>{r.bundle_id=id;showValues();dialog.remove();renderBundle(index);};results.append(hit);
            }}
            box.oninput=()=>{results.innerHTML='';setTimeout(rows,200);};
            box.onkeydown=e=>{if(e.key==='Escape'){dialog.remove();button.setAttribute('aria-expanded','false');}};
            document.body.insertBefore(dialog,document.getElementById('unrelated-picker'));rows();
          };
        }
      }
      function addReward(){''')
    return html + '''<div role="dialog" id="unrelated-picker" data-state="open">
      <input type="text" placeholder="ค้นหาด้วยชื่อหรือ id" data-picker-decoy value="keep-search">
      <button type="button" onclick="document.body.dataset.wrongPickerClicks=1">Wrong bundle ID: 1001</button>
      <button type="button" onclick="document.body.dataset.wrongPickerClicks=1">Wrong bundle ID: 2002</button>
    </div>'''


def test_reward_bundle_picker_selects_exact_ids_in_own_sets_not_other_portal():
    missing, error, values = exercise_form(bundle_reward_html(), {
        **SPEC, 'rewards': [
            {'name_th': 'หนึ่ง', 'name_en': 'One', 'code_list': 'A001', 'bundle_id': '1001'},
            {'name_th': 'สอง', 'name_en': 'Two', 'code_type': 'SERVER',
             'num_codes': '200', 'bundle_id': '2002'},
        ]})
    assert error is None
    assert [r.get('bundle_id') for r in values['rewardValues']] == ['1001', '2002']
    assert missing == ['เวลาเริ่มใช้งาน', 'เวลาสิ้นสุด']
    assert values['pickerDecoys'] == ['keep-search']
    assert values['wrongPickerClicks'] == '0'
    assert values['submits'] == ['0']


@pytest.mark.parametrize('existing,changes', [('1001', '0'), ('10010', '1')])
def test_reward_bundle_preserves_matching_selection_or_changes_different_id(existing, changes):
    html = bundle_reward_html().replace("prefix:'',amount:''}];", "prefix:'',amount:'',bundle_id:'%s'}];" % existing)
    missing, error, values = exercise_form(html, {
        **SPEC, 'rewards': [{'name_th': 'หนึ่ง', 'name_en': 'One', 'code_list': 'A001', 'bundle_id': '1001'}]})
    assert error is None
    assert values['rewardValues'][0]['bundle_id'] == '1001'
    assert values['bundleChanges'] == changes
    assert missing == ['เวลาเริ่มใช้งาน', 'เวลาสิ้นสุด']
    assert values['submits'] == ['0']
    assert values['pickerDecoys'] == ['keep-search']
    assert values['wrongPickerClicks'] == '0'


def test_reward_bundle_ignores_unrelated_widget_inside_same_form():
    base = HEADER_HTML.replace(
        '<input name="name_th" data-decoy', '''<div><label>Bundle <span>*</span></label>
        <button type="button" aria-haspopup="dialog" onclick="document.body.dataset.wrongPickerClicks=1">เลือก bundle</button>
        </div><input name="name_th" data-decoy''')
    missing, error, values = exercise_form(bundle_reward_html(base), {
        **SPEC, 'rewards': [{'name_th': 'หนึ่ง', 'name_en': 'One', 'code_list': 'A001', 'bundle_id': '1001'}]})
    assert error is None
    assert values['rewardValues'][0]['bundle_id'] == '1001'
    assert values['wrongPickerClicks'] == '0'
    assert values['pickerDecoys'] == ['keep-search']
    assert missing == ['เวลาเริ่มใช้งาน', 'เวลาสิ้นสุด']
    assert values['submits'] == ['0']


def test_missing_own_bundle_label_does_not_walk_out_to_another_widget():
    html = bundle_reward_html().replace("section.innerHTML='<label>Bundle <span>*</span></label>';",
                                      "section.innerHTML='<label>Unknown <span>*</span></label>';")
    html = html.replace('<div id="active-reward"></div>', '''<div>
      <div><label>Bundle <span>*</span></label><button type="button" aria-haspopup="dialog"
        onclick="document.body.dataset.wrongPickerClicks=1">เลือก bundle</button></div>
      <div id="active-reward"></div></div>''')
    _missing, error, values = exercise_form(html, {
        **SPEC, 'rewards': [{'name_th': 'หนึ่ง', 'name_en': 'One', 'code_list': 'A001', 'bundle_id': '1001'}]})
    assert isinstance(error, AztekLocatorError)
    assert 'ชุดรางวัลที่ 1: Bundle 1001' in str(error)
    assert values['wrongPickerClicks'] == '0'
    assert values['submits'] == ['0']


def test_reward_common_owner_cannot_escape_form_and_accept_outside_selected_bundle():
    html = bundle_reward_html().replace('<div id="active-reward"></div>',
                                       '<fieldset id="active-reward"></fieldset>')
    html = html.replace("section.innerHTML='<label>Bundle <span>*</span></label>';",
                        "section.innerHTML='<label>Unknown <span>*</span></label>';")
    html = '''<div><div><label>Bundle <span>*</span></label><div>
      <span>#1001 — Outside selected Bundle</span>
      <button type="button" onclick="document.body.dataset.wrongPickerClicks=1">เปลี่ยน</button>
    </div></div>''' + html + '</div>'
    _missing, error, values = exercise_form(html, {
        **SPEC, 'rewards': [{'name_th': 'หนึ่ง', 'name_en': 'One', 'code_list': 'A001', 'bundle_id': '1001'}]})
    assert isinstance(error, AztekLocatorError)
    assert 'ชุดรางวัลที่ 1: Bundle 1001' in str(error)
    assert values['rewardValues'][0].get('bundle_id') is None
    assert values['wrongPickerClicks'] == '0'
    assert values['submits'] == ['0']


@pytest.mark.parametrize('before,after', [
    ("section.innerHTML='<label>Bundle <span>*</span></label>';",
     "section.innerHTML='<label>Unknown <span>*</span></label>';"),
    ('section.append(button);', 'section.append(button);panel.append(section.cloneNode(true));'),
    ("button.type='button';button.textContent='เลือก bundle';",
     "button.type='submit';button.textContent='เลือก bundle';"),
    ('section.append(button);', 'section.append(button);section.append(button.cloneNode(true));'),
    ("button.setAttribute('aria-controls',dialog.id);", "button.setAttribute('aria-controls','missing-popup');"),
    ("button.setAttribute('aria-controls',dialog.id);", "button.setAttribute('aria-controls',dialog.id+' another-id');"),
    ("dialog.setAttribute('role','dialog');", "dialog.setAttribute('role','region');"),
    ("const dialog=document.createElement('div');", "const dialog=document.createElement('section');"),
    ("document.body.insertBefore(dialog,document.getElementById('unrelated-picker'));rows();",
     "document.body.insertBefore(dialog,document.getElementById('unrelated-picker'));document.body.append(dialog.cloneNode(true));rows();"),
    ("box.placeholder='ค้นหาด้วยชื่อหรือ id';", "box.placeholder='unknown search';"),
    ("box.type='text';box.placeholder=", "box.type='number';box.placeholder="),
    ('dialog.append(box);', 'dialog.append(box);dialog.append(box.cloneNode(true));'),
    ("box.oninput=()=>{results.innerHTML='';", "box.oninput=()=>{box.value='9999';results.innerHTML='';"),
    ("['10010','1001','2002']", "['10010','2002']"),
    ('results.append(hit);', 'results.append(hit);results.append(hit.cloneNode(true));'),
    ("hit.type='button';", "hit.type='submit';"),
    ('r.bundle_id=id;', "r.bundle_id='10010';"),
    ('row.append(badge);', 'row.append(badge);row.append(badge.cloneNode(true));'),
    ("const badge=document.createElement('span');", "const badge=document.createElement('div');"),
    ("box.oninput=()=>{results.innerHTML='';", "box.oninput=()=>{document.getElementById('rewards.0.name_th').id='wrong-set-name';results.innerHTML='';"),
])
def test_broken_reward_bundle_contract_stops_without_other_portal_or_submit(before, after):
    html = bundle_reward_html().replace(before, after)
    assert html != bundle_reward_html()
    _missing, error, values = exercise_form(html, {
        **SPEC, 'rewards': [{'name_th': 'หนึ่ง', 'name_en': 'One', 'code_list': 'A001', 'bundle_id': '1001'}]})
    assert isinstance(error, AztekLocatorError)
    assert 'ชุดรางวัลที่ 1: Bundle 1001' in str(error)
    assert values['wrongPickerClicks'] == '0'
    assert values['pickerDecoys'] == ['keep-search']
    assert values['submits'] == ['0']


def test_server_fixed_server_sets_fill_own_ids_without_legacy_decoys():
    missing, error, values = exercise_form(server_reward_html(), {
        **SPEC, 'rewards': [
            {'name_th': 'สุ่มหนึ่ง', 'name_en': 'Server one', 'code_type': 'SERVER',
             'prefix': 'AAA', 'num_codes': '12'},
            {'name_th': 'คงที่', 'name_en': 'Fixed', 'code_type': 'FIX', 'code_list': 'MID001'},
            {'name_th': 'สุ่มสอง', 'name_en': 'Server two', 'code_type': 'SERVER',
             'prefix': 'BBB', 'num_codes': '34'},
        ]})
    assert error is None
    assert [(r['is_generate_code'], r['prefix'], r['amount'], r['serial'])
            for r in values['rewardValues']] == [
        ('2', 'AAA', '12', ''), ('1', '', '', 'MID001'), ('2', 'BBB', '34', '')]
    assert values['serverDecoys'] == ['KEEP-A', '91', 'KEEP-B', '92']
    assert missing == ['เวลาเริ่มใช้งาน', 'เวลาสิ้นสุด',
                       'ชุดรางวัลที่ 1: Bundle', 'ชุดรางวัลที่ 2: Bundle', 'ชุดรางวัลที่ 3: Bundle']
    assert values['submits'] == ['0']


@pytest.mark.parametrize('index', [0, 1])
@pytest.mark.parametrize('field,label', [('prefix', 'prefix'), ('amount', 'จำนวนโค้ดที่ต้องการ')])
@pytest.mark.parametrize('change', ['missing', 'duplicate', 'wrong-type'])
def test_server_field_contract_stops_before_fallback_or_submit(index, field, label, change):
    html = server_reward_html() + '''<script>
      const serverGuard=new MutationObserver(()=>{
        const target=document.getElementById('rewards.%s.%s');
        if(!target || target.dataset.mutated) return;
        target.dataset.mutated='yes';%s
      });serverGuard.observe(panel,{childList:true,subtree:true});
    </script>''' % (index, field, {
        'missing': "target.id='unknown-server-field';",
        'duplicate': 'target.parentElement.append(target.cloneNode(true));',
        'wrong-type': "target.type='checkbox';",
    }[change])
    _missing, error, values = exercise_form(html, {
        **SPEC, 'rewards': [
            {'name_th': 'หนึ่ง', 'name_en': 'One', 'code_type': 'SERVER', 'prefix': 'AAA', 'num_codes': '12'},
            {'name_th': 'สอง', 'name_en': 'Two', 'code_type': 'SERVER', 'prefix': 'BBB', 'num_codes': '34'},
        ]})
    assert isinstance(error, AztekLocatorError)
    assert 'ชุดรางวัลที่ %d' % (index + 1) in str(error) and label in str(error)
    assert values['serverDecoys'] == ['KEEP-A', '91', 'KEEP-B', '92']
    assert values['submits'] == ['0']


@pytest.mark.parametrize('prefix,amount,expected', [
    ('', '5', []), ('ABC', '', ['จำนวนโค้ดที่ต้องการ']),
    ('TOOLONG', '5', ['prefix']),
])
def test_server_optional_prefix_required_amount_and_readback(prefix, amount, expected):
    missing, error, values = exercise_form(server_reward_html(), {
        **SPEC, 'rewards': [{'name_th': 'หนึ่ง', 'name_en': 'One', 'code_type': 'SERVER',
                            'prefix': prefix, 'num_codes': amount}]})
    assert error is None
    assert missing == ['เวลาเริ่มใช้งาน', 'เวลาสิ้นสุด'] + [
        'ชุดรางวัลที่ 1: ' + label for label in expected] + ['ชุดรางวัลที่ 1: Bundle']
    assert values['submits'] == ['0']
    assert values['serverDecoys'] == ['KEEP-A', '91', 'KEEP-B', '92']


def test_lazy_server_fields_are_waited_for_after_mode_change():
    html = server_reward_html().replace(
        'remember();renderCodeFields();', 'remember();codeFields.innerHTML="";setTimeout(renderCodeFields,200);')
    missing, error, values = exercise_form(html, {
        **SPEC, 'rewards': [{'name_th': 'หนึ่ง', 'name_en': 'One', 'code_type': 'SERVER',
                            'prefix': 'LATE', 'num_codes': '50'}]})
    assert error is None
    assert (values['rewardValues'][0]['prefix'], values['rewardValues'][0]['amount']) == ('LATE', '50')
    assert missing == ['เวลาเริ่มใช้งาน', 'เวลาสิ้นสุด', 'ชุดรางวัลที่ 1: Bundle']
    assert values['serverDecoys'] == ['KEEP-A', '91', 'KEEP-B', '92']
    assert values['submits'] == ['0']


def test_reward_names_and_per_user_limit_follow_ids_not_legacy_names():
    _missing, error, values = exercise_form(reward_html(), {
        **SPEC, 'rewards': [{'name_th': 'รางวัลแรก', 'name_en': 'First reward',
                            'uses_per_user': '3', 'code_list': 'CODE-A'}]})
    assert error is None
    assert [(r['name_th'], r['name_en'], r['per_player_limit']) for r in values['rewardValues']] == [
        ('รางวัลแรก', 'First reward', '3')]
    assert values['submits'] == ['0']


def test_three_reward_sets_wait_for_own_tab_and_keep_distinct_names_and_limits():
    _missing, error, values = exercise_form(reward_html(), {
        **SPEC, 'rewards': [
            {'name_th': 'รางวัลแรก', 'name_en': 'First', 'uses_per_user': '3'},
            {'name_th': 'รางวัลสอง', 'name_en': 'Second', 'uses_per_user': '4'},
            {'name_th': 'รางวัลสาม', 'name_en': 'Third', 'uses_per_user': '5'},
        ]})
    assert error is None
    assert [(r['name_th'], r['name_en'], r['per_player_limit']) for r in values['rewardValues']] == [
        ('รางวัลแรก', 'First', '3'), ('รางวัลสอง', 'Second', '4'), ('รางวัลสาม', 'Third', '5')]
    assert values['outsideAdds'] == '0'
    assert values['submits'] == ['0']


def test_each_fixed_reward_uses_own_limit_counts_type_and_serial_ids():
    missing, error, values = exercise_form(reward_html(), {
        **SPEC, 'rewards': [
            {'name_th': 'จำกัด', 'name_en': 'Limited', 'limited': True,
             'quantity': '200', 'remaining': '123', 'code_list': ' A001\nA002 '},
            {'name_th': 'ไม่จำกัด', 'name_en': 'Unlimited', 'limited': False,
             'quantity': '999', 'remaining': '888', 'code_list': 'B001'},
        ]})
    assert error is None
    assert [(r['is_limited'], r['quantity'], r['remaining'], r['is_generate_code'], r['serial'])
            for r in values['rewardValues']] == [
        (True, '200', '123', '1', 'A001\nA002'), (False, '7', '6', '1', 'B001')]
    assert values['rewardDecoys'] == ['keep-th', 'keep-en', '99', '77', '66', 'keep-codes']
    assert missing == ['เวลาเริ่มใช้งาน', 'เวลาสิ้นสุด', 'ชุดรางวัลที่ 1: Bundle', 'ชุดรางวัลที่ 2: Bundle']
    assert values['submits'] == ['0']


@pytest.mark.parametrize('field,label', [
    ('name_th', 'ชื่อรางวัล (ไทย)'), ('name_en', 'ชื่อรางวัล (อังกฤษ)'),
    ('per_player_limit', 'จำนวนการใช้งานต่อ 1 User'),
    ('quantity', 'จำนวนครั้ง'), ('remaining', 'คงเหลือ'), ('serial', 'รายการ Code'),
])
@pytest.mark.parametrize('change', ['missing', 'duplicate', 'wrong-type'])
def test_broken_reward_id_stops_instead_of_filling_legacy_decoy(field, label, change):
    html = reward_html()
    html += '''<script>
      const mutateRewardPanel=new MutationObserver(()=>{
        const target=document.getElementById('rewards.0.%s');
        if(!target || target.dataset.mutated) return;
        target.dataset.mutated='yes';
        %s
      });mutateRewardPanel.observe(panel,{childList:true,subtree:true});
      panel.append(document.createElement('div'));
    </script>''' % (field, {
        'missing': "target.id='unknown-reward-field';",
        'duplicate': "panel.append(target.cloneNode(true));",
        'wrong-type': ("const input=document.createElement('input');input.id=target.id;input.dataset.mutated='yes';target.replaceWith(input);"
                       if field == 'serial' else "target.type='checkbox';"),
    }[change])
    _missing, error, values = exercise_form(html, {
        **SPEC, 'rewards': [{'name_th': 'หนึ่ง', 'name_en': 'One', 'limited': True,
                            'quantity': '200', 'remaining': '100', 'code_list': 'A001'}]})
    assert isinstance(error, AztekLocatorError)
    assert 'ชุดรางวัลที่ 1' in str(error) and label in str(error)
    assert values['rewardDecoys'] == ['keep-th', 'keep-en', '99', '77', '66', 'keep-codes']
    assert values['submits'] == ['0']


@pytest.mark.parametrize('change', ['duplicate-add', 'submit-add', 'missing-add',
                                  'wrong-index', 'duplicate-ordinal', 'multiple-active'])
def test_ambiguous_reward_add_or_tab_mapping_stops_before_next_set_or_submit(change):
    html = reward_html()
    if change == 'duplicate-add':
        html = html.replace('<div role="tablist">', '<button type="button">+ เพิ่มของรางวัล</button><div role="tablist">')
    elif change == 'submit-add':
        html = html.replace('type="button" onclick="addReward()"', 'type="submit" onclick="addReward()"')
    elif change == 'missing-add':
        html = html.replace('onclick="addReward()">+ เพิ่มของรางวัล', 'onclick="addReward()">renamed-add')
    elif change == 'wrong-index':
        html = html.replace('renderReward(rewards.length-1),150)', 'renderReward(0),150)')
    elif change == 'duplicate-ordinal':
        html = html.replace('(i+1)+\'</span>', '1+\'</span>')
    else:
        html = html.replace("String(i===index)", "'true'")
    _missing, error, values = exercise_form(html, {**SPEC, 'rewards': [
        {'name_th': 'หนึ่ง', 'name_en': 'One', 'code_list': 'A001'},
        {'name_th': 'สอง', 'name_en': 'Two', 'code_list': 'B001'},
    ]})
    assert isinstance(error, AztekLocatorError)
    assert 'ชุดรางวัลที่ 2' in str(error)
    assert all(r['name_th'] != 'สอง' for r in values['rewardValues'])
    assert values['outsideAdds'] == '0' and values['submits'] == ['0']


@pytest.mark.parametrize('field', ['is_limited', 'is_generate_code'])
def test_reward_widget_with_wrong_role_is_not_used(field):
    html = reward_html() + '''<script>
      document.getElementById('rewards.0.%s').setAttribute('role','checkbox');
    </script>''' % field
    _missing, error, values = exercise_form(html, {**SPEC, 'rewards': [
        {'name_th': 'หนึ่ง', 'name_en': 'One', 'code_list': 'A001'}]})
    assert isinstance(error, AztekLocatorError)
    assert 'ชุดรางวัลที่ 1' in str(error)
    assert values['submits'] == ['0']


def test_reward_add_changing_to_submit_while_waiting_never_submits():
    html = reward_html().replace('type="button" onclick="addReward()"',
                                 'type="button" disabled onclick="addReward()"')
    html += '''<script>
      document.getElementById('rewards.0.name_th').addEventListener('input',()=>setTimeout(()=>{
        const add=document.querySelector('main button[onclick="addReward()"]');
        add.type='submit';add.disabled=false;
      },1000));
    </script>'''
    _missing, error, values = exercise_form(html, {**SPEC, 'rewards': [
        {'name_th': 'หนึ่ง', 'name_en': 'One', 'code_list': 'A001'},
        {'name_th': 'สอง', 'name_en': 'Two', 'code_list': 'B001'},
    ]})
    assert isinstance(error, AztekLocatorError)
    assert 'ชุดรางวัลที่ 2' in str(error)
    assert len(values['rewardValues']) == 1
    assert values['submits'] == ['0']


@pytest.mark.parametrize('submit_tab', [False, True])
def test_initially_inactive_first_reward_is_opened_by_ordinal_not_edited_name(submit_tab):
    html = reward_html() + '''<script>
      rewards[0].name_th='ชื่อเก่าชุดหนึ่ง';
      rewards.push({name_th:'ชื่อเก่าชุดสอง',name_en:'Previous second',per_player_limit:'1',
        is_limited:false,quantity:'7',remaining:'6',is_generate_code:'1',serial:'KEEP-SECOND'});
      renderReward(1);
    </script>'''
    if submit_tab:
        html += '''<script>
          document.querySelector('main [role="tab"][aria-selected="false"]').type='submit';
        </script>'''
    _missing, error, values = exercise_form(html, {**SPEC, 'rewards': [
        {'name_th': 'ชื่อใหม่', 'name_en': 'Requested first', 'code_list': 'A001'}]})
    if submit_tab:
        assert isinstance(error, AztekLocatorError)
        assert values['rewardValues'][0]['name_th'] == 'ชื่อเก่าชุดหนึ่ง'
    else:
        assert error is None
        assert (values['rewardValues'][0]['name_th'], values['rewardValues'][0]['serial']) == ('ชื่อใหม่', 'A001')
    assert (values['rewardValues'][1]['name_th'], values['rewardValues'][1]['serial']) == ('ชื่อเก่าชุดสอง', 'KEEP-SECOND')
    assert values['submits'] == ['0']


def test_disabled_reward_add_reports_the_affected_set_without_submitting():
    html = reward_html().replace('type="button" onclick="addReward()"',
                                 'type="button" disabled onclick="addReward()"')
    _missing, error, values = exercise_form(html, {**SPEC, 'rewards': [
        {'name_th': 'หนึ่ง', 'name_en': 'One', 'code_list': 'A001'},
        {'name_th': 'สอง', 'name_en': 'Two', 'code_list': 'B001'},
    ]})
    assert isinstance(error, AztekLocatorError)
    assert 'เพิ่มชุดรางวัลที่ 2' in str(error)
    assert values['submits'] == ['0'] and len(values['rewardValues']) == 1


def test_reward_tab_that_does_not_activate_reports_its_set_without_submitting():
    html = reward_html() + '''<script>
      rewards.push({name_th:'',name_en:'',per_player_limit:'1',is_limited:false,
        quantity:'7',remaining:'6',is_generate_code:'1',serial:''});renderReward(1);
      document.querySelector('main [role="tab"][aria-selected="false"]').onclick=()=>{};
    </script>'''
    _missing, error, values = exercise_form(html, {**SPEC, 'rewards': [
        {'name_th': 'หนึ่ง', 'name_en': 'One', 'code_list': 'A001'}]})
    assert isinstance(error, AztekLocatorError)
    assert 'ชุดรางวัลที่ 1' in str(error)
    assert values['submits'] == ['0']


def calendar_html():
    html = HEADER_HTML.replace(
        '<label>เวลาเริ่มใช้งาน</label><button type="button">เลือกวันและเวลา</button>',
        '<label>เวลาเริ่มใช้งาน</label><button type="button" onclick="document.body.dataset.dateDecoyClicks=1">decoy</button>'
        '<label>Changed start label</label><button id="start_at" type="button" aria-haspopup="dialog" onclick="openCalendar(this)">เลือกวันและเวลา</button>')
    html = html.replace(
        '<label>เวลาสิ้นสุด</label><button type="button">เลือกวันและเวลา</button>',
        '<label>Changed end label</label><button id="end_at" type="button" aria-haspopup="dialog" onclick="openCalendar(this)">เลือกวันและเวลา</button>')
    return html + '''
      <div role="dialog" id="other-calendar" data-state="open">
        <input aria-label="นาที" data-calendar-decoy value="17">
        <input aria-label="วินาที" data-calendar-decoy value="16">
      </div>
      <script>
      const calendarMonths=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      function openCalendar(trigger) {
        const dialog=document.createElement('div');dialog.id='runtime-'+trigger.id;
        dialog.setAttribute('role','dialog');dialog.dataset.state='open';
        trigger.setAttribute('aria-controls',dialog.id);trigger.setAttribute('aria-expanded','true');
        dialog.innerHTML=`
          <select aria-label="Choose the Month">${calendarMonths.map((m,i)=>`<option value="${i}">${m}</option>`).join('')}</select>
          <select aria-label="Choose the Year"><option>2026</option><option>2027</option></select>
          <table><tbody></tbody></table>
          <button type="button" role="combobox" aria-label="ชั่วโมง">00</button>
          <input aria-label="นาที" value="00"><input aria-label="วินาที" value="00">`;
        document.body.append(dialog);
        const month=dialog.querySelector('[aria-label="Choose the Month"]');month.value='9';
        const year=dialog.querySelector('[aria-label="Choose the Year"]');
        const hour=dialog.querySelector('[aria-label="ชั่วโมง"]');
        const minute=dialog.querySelector('[aria-label="นาที"]');
        const second=dialog.querySelector('[aria-label="วินาที"]');let day='';
        function display() {if(day) trigger.textContent=day.padStart(2,'0')+' '+calendarMonths[+month.value]+' '+year.value+' '+hour.textContent+':'+minute.value.padStart(2,'0')+':'+second.value.padStart(2,'0');}
        function grid() {
          const tbody=dialog.querySelector('tbody');tbody.innerHTML='';
          for(const number of [8,27,28]) {
            const cell=document.createElement('td');cell.setAttribute('role','gridcell');
            cell.dataset.day=year.value+'-'+String(+month.value+1).padStart(2,'0')+'-'+String(number).padStart(2,'0');
            const button=document.createElement('button');button.type='button';button.dataset.day=(+month.value+1)+'/'+number+'/'+year.value;button.textContent=number;
            button.onclick=()=>{day=String(number);display();};cell.append(button);tbody.append(cell);
          }
        }
        month.onchange=grid;year.onchange=grid;grid();
        minute.onblur=display;second.onblur=display;
        hour.onclick=()=>{
          const list=document.createElement('div');list.id='runtime-hours-'+trigger.id;list.setAttribute('role','listbox');list.dataset.state='open';
          hour.setAttribute('aria-controls',list.id);
          for(let number=0;number<24;number++) {
            const option=document.createElement('div');option.setAttribute('role','option');option.textContent=String(number).padStart(2,'0');
            option.onclick=()=>{hour.textContent=option.textContent;minute.value='00';second.value='00';list.remove();display();};list.append(option);
          }document.body.append(list);
        };
        dialog.onkeydown=event=>{if(event.key==='Escape'){dialog.remove();trigger.setAttribute('aria-expanded','false');}};
      }
      </script>'''


def test_code_window_follows_date_ids_and_only_owning_calendar_controls():
    missing, error, values = exercise_form(calendar_html(), {
        **SPEC, 'start_time': '2026-08-27 00:00:00', 'end_time': '2027-09-28 23:59:59'})
    assert error is None
    assert values['dates'] == ['27 Aug 2026 00:00:00', '28 Sep 2027 23:59:59']
    assert missing == ['ชุดรางวัล']
    assert values['calendarDecoys'] == ['17', '16']
    assert values['dateDecoyClicks'] == '0'
    assert values['submits'] == ['0']


@pytest.mark.parametrize('change', ['missing-id', 'duplicate-id', 'submit-type',
                                  'no-relation', 'wrong-popup-role', 'duplicate-popup-id',
                                  'duplicate-minute', 'duplicate-year'])
def test_broken_calendar_contract_stops_without_using_other_popup_or_submitting(change):
    html = calendar_html()
    if change == 'missing-id':
        html = html.replace('id="start_at"', 'id="other-start"')
    elif change == 'duplicate-id':
        html = html.replace('</form>', '<button id="start_at" type="button">extra</button></form>')
    elif change == 'submit-type':
        html = html.replace('id="start_at" type="button"', 'id="start_at" type="submit"')
    elif change == 'no-relation':
        html = html.replace("trigger.setAttribute('aria-controls',dialog.id);", '')
    elif change == 'wrong-popup-role':
        html = html.replace("dialog.setAttribute('role','dialog')", "dialog.setAttribute('role','listbox')")
    elif change == 'duplicate-popup-id':
        html = html.replace('document.body.append(dialog);', 'document.body.append(dialog);document.body.append(dialog.cloneNode(true));')
    elif change == 'duplicate-minute':
        html = html.replace('<input aria-label="นาที" value="00">', '<input aria-label="นาที" value="00"><input aria-label="นาที" value="00">')
    else:
        html = html.replace('<table><tbody>', '<select aria-label="Choose the Year"><option>2026</option></select><table><tbody>')
    _missing, error, values = exercise_form(html, {**SPEC, 'start_time': '2026-10-08 00:00:00'})
    assert isinstance(error, AztekLocatorError)
    assert 'เวลาเริ่มใช้งาน' in str(error)
    assert values['calendarDecoys'] == ['17', '16']
    assert values['dateDecoyClicks'] == '0'
    assert values['submits'] == ['0']


def test_calendar_waits_for_late_popup_relation_and_mount():
    html = calendar_html().replace(
        "trigger.setAttribute('aria-controls',dialog.id);", '')
    html = html.replace('document.body.append(dialog);', "setTimeout(()=>{document.body.append(dialog);trigger.setAttribute('aria-controls',dialog.id);},250);")
    missing, error, values = exercise_form(html, {**SPEC, 'start_time': '2026-10-08 03:04:05'})
    assert error is None
    assert values['dates'][0] == '08 Oct 2026 03:04:05'
    assert missing == ['เวลาสิ้นสุด', 'ชุดรางวัล']
    assert values['submits'] == ['0']


def test_calendar_retries_bounded_readback_after_time_component_resets_seconds():
    html = calendar_html().replace('minute.onblur=display;', '''
        let firstMinuteCommit=true;
        minute.onblur=()=>{if(firstMinuteCommit){second.value='00';firstMinuteCommit=false;}display();};''')
    missing, error, values = exercise_form(html, {**SPEC, 'start_time': '2026-10-08 23:59:59'})
    assert error is None
    assert values['dates'][0] == '08 Oct 2026 23:59:59'
    assert missing == ['เวลาสิ้นสุด', 'ชุดรางวัล']
    assert values['submits'] == ['0']


def test_calendar_readback_that_never_matches_remains_incomplete_without_submit():
    html = calendar_html().replace('minute.onblur=display;', "minute.onblur=()=>{second.value='00';display();};")
    missing, error, values = exercise_form(html, {**SPEC, 'start_time': '2026-10-08 23:59:59'})
    assert error is None
    assert values['dates'][0] == '08 Oct 2026 23:59:00'
    assert missing == ['เวลาเริ่มใช้งาน', 'เวลาสิ้นสุด', 'ชุดรางวัล']
    assert values['submits'] == ['0']


@pytest.mark.parametrize('value', ['2026-02-30 00:00:00', '2026-10-08 24:00:00', 'bad date'])
def test_invalid_code_window_does_not_open_or_fill_calendar(value):
    missing, error, values = exercise_form(calendar_html(), {**SPEC, 'start_time': value})
    assert error is None
    assert values['dates'] == ['เลือกวันและเวลา', 'เลือกวันและเวลา']
    assert missing == ['เวลาเริ่มใช้งาน', 'เวลาสิ้นสุด', 'ชุดรางวัล']
    assert values['dateDecoyClicks'] == '0'
    assert values['submits'] == ['0']


def test_hour_option_changed_to_submit_control_stops_without_submitting():
    html = calendar_html().replace('<form onsubmit=', '<form id="fixture-form" onsubmit=')
    html = html.replace("const option=document.createElement('div');",
                        "const option=document.createElement('button');option.type='submit';option.setAttribute('form','fixture-form');")
    html = html.replace('list.remove();display();', 'display();')
    _missing, error, values = exercise_form(html, {**SPEC, 'start_time': '2026-10-08 23:59:59'})
    assert values['submits'] == ['0']
    assert isinstance(error, AztekLocatorError)
    assert 'เวลาเริ่มใช้งาน' in str(error)


def test_itemcode_names_follow_verified_ids_despite_renamed_fields_and_decoys():
    missing, error, values = exercise_form()
    assert error is None
    assert values['names'] == ['โค้ดที่ขอ', 'Requested code', 'requested-code']
    assert values['decoys'] == ['keep-th', 'keep-en', 'keep-slug']
    assert missing == ['เวลาเริ่มใช้งาน', 'เวลาสิ้นสุด', 'ชุดรางวัล']
    assert values['submits'] == ['0']


@pytest.mark.parametrize('replacement', [
    '<input name="renamed-th">',
    '<input id="name_th"><input id="name_th">',
    '<input id="name_th"><input id="name_th" hidden>',
    '<button id="name_th" type="button">wrong control</button>',
    '<input id="name_th" type="number">',
    '<input id="name_th" hidden>',
])
def test_broken_name_id_stops_without_using_name_decoy_or_submitting(replacement):
    html = HEADER_HTML.replace('<input id="name_th" name="renamed-th">', replacement)
    _missing, error, values = exercise_form(html)
    assert isinstance(error, AztekLocatorError)
    assert 'ชื่อ Item Code (ไทย)' in str(error)
    assert values['decoys'] == ['keep-th', 'keep-en', 'keep-slug']
    assert values['submits'] == ['0']


def test_name_id_outside_owning_form_does_not_replace_missing_name():
    html = HEADER_HTML.replace('id="name_th" name="renamed-th"', 'name="renamed-th"')
    html = '<input id="name_th" value="outside">' + html
    _missing, error, values = exercise_form(html)
    assert isinstance(error, AztekLocatorError)
    assert values['names'][0] == 'outside'
    assert values['decoys'] == ['keep-th', 'keep-en', 'keep-slug']
    assert values['submits'] == ['0']


def test_two_main_forms_stop_instead_of_selecting_the_first():
    html = HEADER_HTML.replace('</main>', '<form><input id="name_th"></form></main>')
    _missing, error, values = exercise_form(html)
    assert isinstance(error, AztekLocatorError)
    assert 'ฟอร์ม Item Code' in str(error)
    assert values['names'] == ['', '', '']
    assert values['submits'] == ['0', '0']


def test_unrelated_form_outside_main_is_not_filled():
    html = HEADER_HTML + '<form><input name="name_th" data-decoy value="outside"></form>'
    missing, error, values = exercise_form(html)
    assert error is None
    assert values['names'] == ['โค้ดที่ขอ', 'Requested code', 'requested-code']
    assert values['decoys'] == ['keep-th', 'keep-en', 'keep-slug', 'outside']
    assert missing == ['เวลาเริ่มใช้งาน', 'เวลาสิ้นสุด', 'ชุดรางวัล']
    assert values['submits'] == ['0', '0']


@pytest.mark.parametrize('limited,expected', [(True, ['40', '40']), (False, ['7', '6'])])
def test_code_wide_counters_are_only_filled_when_limit_is_enabled(limited, expected):
    _missing, error, values = exercise_form(spec={
        **SPEC, 'limited': limited, 'quantity': '40', 'remaining': '40'})
    assert error is None
    assert values['counts'] == expected
    assert values['submits'] == ['0']


def test_per_user_limit_uses_numeric_id_instead_of_renamed_name_decoy():
    html = HEADER_HTML.replace(
        '<input id="per_player_limit" name="per_player_limit"',
        '<input name="per_player_limit" type="number" data-counter-decoy value="99">'
        '<input id="per_player_limit" name="changed-counter"')
    _missing, error, values = exercise_form(html, {**SPEC, 'uses_per_user': '5'})
    assert error is None
    assert values['perUser'] == '5'
    assert values['counterDecoys'] == ['99']
    assert values['submits'] == ['0']


def test_limit_switch_follows_id_not_label_decoy_and_waits_for_count_fields():
    html = HEADER_HTML.replace('<div><label>จำกัดจำนวน</label>', '''
      <div><label>จำกัดจำนวน</label><button role="switch" type="button" aria-checked="false"
        onclick="this.setAttribute('aria-checked','true')"></button></div>
      <input name="quantity" type="number" data-counter-decoy value="17">
      <input name="remaining" type="number" data-counter-decoy value="16">
      <div><label>Changed limit label</label>''')
    html = html.replace("onclick=\"this.setAttribute('aria-checked',this.getAttribute('aria-checked')==='true'?'false':'true')\"",
      '''onclick="this.setAttribute('aria-checked','true');setTimeout(()=>{
        document.getElementById('late-counts').innerHTML=
        '<input id=quantity name=changed-quantity type=number><input id=remaining name=changed-remaining type=number>';
      },200)"''')
    html = html.replace('<input id="quantity" name="quantity" type="number" value="7">', '<div id="late-counts"></div>')
    html = html.replace('<input id="remaining" name="remaining" type="number" value="6">', '')
    _missing, error, values = exercise_form(html, {
        **SPEC, 'limited': True, 'quantity': '200', 'remaining': '123'})
    assert error is None
    assert values['limitState'] == 'true'
    assert values['idCounts'] == ['200', '123']
    assert values['counterDecoys'] == ['17', '16']
    assert values['submits'] == ['0']


def test_redeem_type_uses_id_owning_select_despite_misleading_options_elsewhere():
    html = HEADER_HTML.replace('<div><button id="redeem_type"', '''
      <select data-type-decoy><option value="WINNER">WINNER</option><option value="ALL">ALL</option></select>
      <div><button id="redeem_type"''')
    _missing, error, values = exercise_form(html)
    assert error is None
    assert values['redeemValue'] == 'ALL'
    assert values['redeemText'] == 'ALL'
    assert values['typeDecoys'] == ['WINNER']
    assert values['submits'] == ['0']


@pytest.mark.parametrize('replacement', [
    '<input name="per_player_limit" type="number">',
    '<input id="per_player_limit" type="number"><input id="per_player_limit" type="number">',
    '<input id="per_player_limit" type="text">',
])
def test_per_user_limit_contract_break_stops_before_save(replacement):
    html = HEADER_HTML.replace('<input id="per_player_limit" name="per_player_limit" type="number" value="1">', replacement)
    _missing, error, values = exercise_form(html)
    assert isinstance(error, AztekLocatorError)
    assert 'จำนวนการใช้งานต่อ 1 User' in str(error)
    assert values['submits'] == ['0']


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'wrong-role', 'bad-state', 'no-change'])
def test_limit_switch_contract_break_stops_without_submitting(change):
    html = HEADER_HTML
    if change == 'missing':
        html = html.replace('id="is_limited"', 'id="other-switch"')
    elif change == 'duplicate':
        html = html.replace('</form>', '<button id="is_limited" role="switch" type="button" aria-checked="false"></button></form>')
    elif change == 'wrong-role':
        html = html.replace('id="is_limited" role="switch"', 'id="is_limited" role="checkbox"')
    elif change == 'bad-state':
        html = html.replace('aria-checked="false"', 'aria-checked="mixed"')
    else:
        html = html.replace("this.setAttribute('aria-checked',this.getAttribute('aria-checked')==='true'?'false':'true')", 'void 0')
    _missing, error, values = exercise_form(html, {**SPEC, 'limited': True, 'quantity': '200', 'remaining': '200'})
    assert isinstance(error, AztekLocatorError)
    assert 'จำกัดจำนวน' in str(error)
    assert values['idCounts'] == ['7', '6']
    assert values['submits'] == ['0']


@pytest.mark.parametrize('field,label', [('quantity', 'จำนวนครั้งที่สามารถใช้งานได้'), ('remaining', 'จำนวนคงเหลือ')])
@pytest.mark.parametrize('change', ['missing', 'duplicate', 'wrong-type'])
def test_code_wide_count_contract_break_stops_before_save(field, label, change):
    html = HEADER_HTML
    if change == 'missing':
        html = html.replace('id="%s"' % field, 'id="other-%s"' % field)
    elif change == 'duplicate':
        html = html.replace('</form>', '<input id="%s" type="number"></form>' % field)
    else:
        html = html.replace('id="%s" name="%s" type="number"' % (field, field),
                            'id="%s" name="%s" type="text"' % (field, field))
    _missing, error, values = exercise_form(html, {**SPEC, 'limited': True, 'quantity': '200', 'remaining': '200'})
    assert isinstance(error, AztekLocatorError)
    assert label in str(error)
    assert values['submits'] == ['0']


def test_limit_switch_changing_to_submit_while_disabled_never_submits_form():
    html = HEADER_HTML.replace('id="is_limited" role="switch"',
                               'id="is_limited" disabled role="switch"')
    html += '''<script>
      document.getElementById('per_player_limit').addEventListener('input',()=>setTimeout(()=>{
        const button=document.getElementById('is_limited');
        button.type='submit';button.disabled=false;
      },1500));
    </script>'''
    _missing, error, values = exercise_form(html, {
        **SPEC, 'limited': True, 'quantity': '200', 'remaining': '200'})
    assert values['submits'] == ['0']
    assert isinstance(error, AztekLocatorError)
    assert 'จำกัดจำนวน' in str(error)
    assert values['idCounts'] == ['7', '6']


@pytest.mark.parametrize('change', ['missing-id', 'duplicate-id', 'wrong-role',
                                  'missing-native', 'duplicate-native', 'multiple-native',
                                  'duplicate-option', 'missing-option', 'stale-display'])
def test_redeem_widget_contract_break_stops_without_selecting_decoy(change):
    html = HEADER_HTML.replace('<div><button id="redeem_type"', '''
      <select data-type-decoy><option value="WINNER">WINNER</option><option value="ALL">ALL</option></select>
      <div><button id="redeem_type"''')
    if change == 'missing-id':
        html = html.replace('id="redeem_type"', 'id="other-type"')
    elif change == 'duplicate-id':
        html = html.replace('</form>', '<button id="redeem_type" role="combobox" type="button">ALL</button></form>')
    elif change == 'wrong-role':
        html = html.replace('id="redeem_type" role="combobox"', 'id="redeem_type" role="switch"')
    elif change == 'missing-native':
        html = html.replace('<select onchange=', '<div data-not-select onchange=').replace('</select></div>', '</div></div>')
    elif change == 'duplicate-native':
        html = html.replace('</select></div>', '</select><select><option value="ALL">ALL</option></select></div>')
    elif change == 'multiple-native':
        html = html.replace('<select onchange=', '<select multiple onchange=')
    elif change == 'duplicate-option':
        html = html.replace('</select></div>', '<option value="ALL">ALL again</option></select></div>')
    elif change == 'missing-option':
        html = html.replace('<option value="ALL">ALL</option>\n', '<option value="OTHER">OTHER</option>\n')
    else:
        html = html.replace('this.previousElementSibling.textContent=this.selectedOptions[0].textContent', 'void 0')
    _missing, error, values = exercise_form(html)
    assert isinstance(error, AztekLocatorError)
    assert 'ประเภท Item Code' in str(error)
    assert values['typeDecoys'] == ['WINNER']
    assert values['submits'] == ['0']


def test_clipped_native_redeem_select_works_through_verified_id_association():
    html = HEADER_HTML.replace('<select onchange=', '''<select aria-hidden="true"
      style="position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip:rect(0,0,0,0)" onchange=''')
    _missing, error, values = exercise_form(html)
    assert error is None
    assert values['redeemValue'] == 'ALL'
    assert values['redeemText'] == 'ALL'
    assert values['submits'] == ['0']


def test_non_actionable_native_redeem_select_stops_without_forcing_selection():
    html = HEADER_HTML.replace('<select onchange=', '<select aria-hidden="true" style="display:none" onchange=')
    _missing, error, values = exercise_form(html)
    assert isinstance(error, AztekLocatorError)
    assert 'ประเภท Item Code' in str(error)
    assert values['redeemValue'] == 'WINNER'
    assert values['redeemText'] == 'WINNER'
    assert values['submits'] == ['0']


def test_redeem_type_waits_for_requested_option_to_mount():
    html = HEADER_HTML.replace(
        '<option value="WINNER">WINNER</option><option value="ALL">ALL</option>', '')
    html += '''<script>
      document.getElementById('per_player_limit').addEventListener('input',()=>setTimeout(()=>{
        document.getElementById('redeem_type').nextElementSibling.innerHTML=
          '<option value="WINNER">WINNER</option><option value="ALL">ALL</option>';
      },300));
    </script>'''
    _missing, error, values = exercise_form(html)
    assert error is None
    assert values['redeemValue'] == 'ALL'
    assert values['redeemText'] == 'ALL'
    assert values['submits'] == ['0']


def routed_runner_browser(monkeypatch, html):
    """Replace only external browser traffic; retain the real runner lifecycle."""
    traffic, snapshots = [], []

    class Starter:
        async def start(self):
            driver = await async_playwright().start()

            async def launch(**kwargs):
                browser = await driver.chromium.launch(**kwargs)
                original_new_context = browser.new_context

                async def new_context(**kwargs):
                    context = await original_new_context(**kwargs)

                    async def serve(route):
                        request = route.request
                        traffic.append((request.method, request.url))
                        if (request.method == 'GET' and urlsplit(request.url).path in (
                                '/combo/cabalm/itemcodes/create',
                                '/combo/cabalmsea/itemcodes/create',
                                '/combo/cabalpc/itemcodes/create',
                                '/combo/cabalpcsea/itemcodes/create')):
                            await route.fulfill(body=html, content_type='text/html; charset=utf-8')
                        else:
                            await route.abort()

                    await context.route('**/*', serve)
                    original_close = context.close

                    async def close():
                        for page in context.pages:
                            if not page.is_closed():
                                snapshots.append(await page.evaluate('''() => ({
                                    names: ['name_th','name_en','slug'].map(id=>document.querySelector('[id="'+id+'"]')?.value),
                                    submits: [...document.querySelectorAll('form')].map(e=>e.dataset.submits || '0'),
                                    ...(document.querySelector('#reward-values') ? {
                                      rewards: JSON.parse(document.querySelector('#reward-values').textContent)
                                    } : {})
                                })'''))
                        await original_close()

                    context.close = close
                    return context

                browser.new_context = new_context
                return browser

            return SimpleNamespace(chromium=SimpleNamespace(launch=launch), stop=driver.stop)

    monkeypatch.setattr(activity_runner, 'async_playwright', Starter)
    return traffic, snapshots


@pytest.mark.parametrize('game,url', [
    ('CabalM TH', 'https://aztek-tools-v2.combo-interactive.com/combo/cabalm/itemcodes/create'),
    ('CabalM SEA', 'https://aztek-tools-v2.combo-interactive.com/combo/cabalmsea/itemcodes/create'),
    ('CabalPC TH', 'https://aztek-tools-v2.combo-interactive.com/combo/cabalpc/itemcodes/create'),
    ('CabalPC SEA', 'https://aztek-tools-v2.combo-interactive.com/combo/cabalpcsea/itemcodes/create'),
])
def test_preview_readiness_uses_name_id_even_when_name_attribute_changes(monkeypatch, game, url):
    html = HEADER_HTML.replace('name="name_th" data-decoy', 'name="old-name" data-decoy')
    traffic, snapshots = routed_runner_browser(monkeypatch, html)
    result = asyncio.run(ItemCodeBuilder(lambda *_: None).run(
        game, SPEC, {'cookies': [], 'origins': []}))
    assert result['missing'] == ['เวลาเริ่มใช้งาน', 'เวลาสิ้นสุด', 'ชุดรางวัล']
    assert snapshots == [{'names': ['โค้ดที่ขอ', 'Requested code', 'requested-code'],
                          'submits': ['0']}]
    assert traffic == [('GET', url)]


@pytest.mark.parametrize('game,path', [
    ('CabalM TH', 'cabalm'), ('CabalM SEA', 'cabalmsea'),
    ('CabalPC TH', 'cabalpc'), ('CabalPC SEA', 'cabalpcsea'),
])
def test_game_preview_verifies_both_date_windows_without_submit(monkeypatch, game, path):
    traffic, snapshots = routed_runner_browser(monkeypatch, calendar_html())
    result = asyncio.run(ItemCodeBuilder(lambda *_: None).run(game, {
        **SPEC, 'start_time': '2026-08-27 00:00:00', 'end_time': '2027-09-28 23:59:59'},
        {'cookies': [], 'origins': []}))
    assert result['missing'] == ['ชุดรางวัล']
    assert snapshots == [{'names': ['โค้ดที่ขอ', 'Requested code', 'requested-code'], 'submits': ['0']}]
    assert traffic == [('GET', 'https://aztek-tools-v2.combo-interactive.com/combo/%s/itemcodes/create' % path)]


@pytest.mark.parametrize('game,path', [
    ('CabalM TH', 'cabalm'), ('CabalM SEA', 'cabalmsea'),
    ('CabalPC TH', 'cabalpc'), ('CabalPC SEA', 'cabalpcsea'),
])
def test_game_preview_preserves_two_rewards_without_any_write(monkeypatch, game, path):
    traffic, snapshots = routed_runner_browser(monkeypatch, reward_html(calendar_html()))
    result = asyncio.run(ItemCodeBuilder(lambda *_: None).run(game, {
        **SPEC, 'start_time': '2026-08-27 00:00:00', 'end_time': '2027-09-28 23:59:59',
        'rewards': [{'name_th': 'หนึ่ง', 'name_en': 'One', 'code_list': 'A001'},
                    {'name_th': 'สอง', 'name_en': 'Two', 'code_list': 'B001'}],
    }, {'cookies': [], 'origins': []}))
    assert result['missing'] == ['ชุดรางวัลที่ 1: Bundle', 'ชุดรางวัลที่ 2: Bundle']
    assert [(r['name_th'], r['serial']) for r in snapshots[0]['rewards']] == [
        ('หนึ่ง', 'A001'), ('สอง', 'B001')]
    assert snapshots[0]['submits'] == ['0']
    assert traffic == [('GET', 'https://aztek-tools-v2.combo-interactive.com/combo/%s/itemcodes/create' % path)]


@pytest.mark.parametrize('game,path', [
    ('CabalM TH', 'cabalm'), ('CabalM SEA', 'cabalmsea'),
    ('CabalPC TH', 'cabalpc'), ('CabalPC SEA', 'cabalpcsea'),
])
def test_game_preview_preserves_server_and_fixed_rewards_without_writes(monkeypatch, game, path):
    traffic, snapshots = routed_runner_browser(monkeypatch, server_reward_html(calendar_html()))
    result = asyncio.run(ItemCodeBuilder(lambda *_: None).run(game, {
        **SPEC, 'start_time': '2026-08-27 00:00:00', 'end_time': '2027-09-28 23:59:59',
        'rewards': [{'name_th': 'สุ่ม', 'name_en': 'Generated', 'code_type': 'SERVER',
                     'prefix': 'AFC', 'num_codes': '200'},
                    {'name_th': 'คงที่', 'name_en': 'Fixed', 'code_list': 'FIX001'}],
    }, {'cookies': [], 'origins': []}))
    assert result['missing'] == ['ชุดรางวัลที่ 1: Bundle', 'ชุดรางวัลที่ 2: Bundle']
    assert [(r['is_generate_code'], r['prefix'], r['amount'], r['serial'])
            for r in snapshots[0]['rewards']] == [('2', 'AFC', '200', ''), ('1', '', '', 'FIX001')]
    assert snapshots[0]['submits'] == ['0']
    assert traffic == [('GET', 'https://aztek-tools-v2.combo-interactive.com/combo/%s/itemcodes/create' % path)]


@pytest.mark.parametrize('game,path', [
    ('CabalM TH', 'cabalm'), ('CabalM SEA', 'cabalmsea'),
    ('CabalPC TH', 'cabalpc'), ('CabalPC SEA', 'cabalpcsea'),
])
def test_game_preview_keeps_distinct_bundle_ids_and_seconds_without_writes(monkeypatch, game, path):
    traffic, snapshots = routed_runner_browser(monkeypatch, bundle_reward_html(calendar_html()))
    result = asyncio.run(ItemCodeBuilder(lambda *_: None).run(game, {
        **SPEC, 'start_time': '2026-08-27 00:00:00', 'end_time': '2027-09-28 23:59:59',
        'rewards': [{'name_th': 'หนึ่ง', 'name_en': 'One', 'code_list': 'FIX001', 'bundle_id': '1001'},
                    {'name_th': 'สอง', 'name_en': 'Two', 'code_type': 'SERVER',
                     'num_codes': '200', 'bundle_id': '2002'}],
    }, {'cookies': [], 'origins': []}))
    assert result['missing'] == []
    assert [r['bundle_id'] for r in snapshots[0]['rewards']] == ['1001', '2002']
    assert snapshots[0]['submits'] == ['0']
    assert traffic == [('GET', 'https://aztek-tools-v2.combo-interactive.com/combo/%s/itemcodes/create' % path)]


def test_second_bundle_failure_preserves_queue_identity_and_first_bundle_without_retry(monkeypatch):
    html = bundle_reward_html().replace('dialog.append(box);',
        'dialog.append(box);if(index===1)dialog.append(box.cloneNode(true));')
    traffic, snapshots = routed_runner_browser(monkeypatch, html)
    spec = {**SPEC, 'rewards': [
        {'name_th': 'หนึ่ง', 'name_en': 'One', 'code_list': 'FIX001', 'bundle_id': '1001'},
        {'name_th': 'สอง', 'name_en': 'Two', 'code_list': 'FIX002', 'bundle_id': '2002'},
    ]}
    results = asyncio.run(ItemCodeBuilder(lambda *_: None).run_many(
        'CabalM TH', [spec, {**spec, 'slug': 'second-code'}], {'cookies': [], 'origins': []}))
    assert [r['slug'] for r in results] == ['requested-code', 'second-code']
    assert all(not r['saved'] and r['made_id'] is None and
               'ชุดรางวัลที่ 2: Bundle 2002' in r['error'] for r in results)
    assert snapshots[0]['rewards'][0]['bundle_id'] == '1001'
    assert snapshots[0]['rewards'][1].get('bundle_id') is None
    assert snapshots[0]['submits'] == ['0']
    assert traffic == [('GET', 'https://aztek-tools-v2.combo-interactive.com/combo/cabalm/itemcodes/create')] * 2


def test_broken_server_amount_keeps_queue_identity_and_never_submits(monkeypatch):
    html = server_reward_html().replace(
        "input.id='rewards.'+index+'.'+field;\n            input.type=type;",
        "input.id=(index===1 && field==='amount'?'unknown.':'rewards.')+index+'.'+field;\n            input.type=type;")
    assert html != server_reward_html()
    traffic, snapshots = routed_runner_browser(monkeypatch, html)
    spec = {**SPEC, 'rewards': [
        {'name_th': 'คงที่', 'name_en': 'Fixed', 'code_list': 'FIX001'},
        {'name_th': 'สุ่ม', 'name_en': 'Generated', 'code_type': 'SERVER', 'num_codes': '200'},
    ]}
    results = asyncio.run(ItemCodeBuilder(lambda *_: None).run_many(
        'CabalM TH', [spec, {**spec, 'slug': 'second-code'}], {'cookies': [], 'origins': []}))
    assert [r['slug'] for r in results] == ['requested-code', 'second-code']
    assert all(not r['saved'] and r['made_id'] is None and
               'ชุดรางวัลที่ 2: จำนวนโค้ดที่ต้องการ' in r['error'] for r in results)
    assert snapshots[0]['submits'] == ['0']
    assert traffic == [('GET', 'https://aztek-tools-v2.combo-interactive.com/combo/cabalm/itemcodes/create')] * 2


def test_broken_second_reward_keeps_queue_identity_without_submitting_or_retrying(monkeypatch):
    html = reward_html().replace("input.id='rewards.'+index+'.'+field;", "input.id=(index===1?'unknown.':'rewards.')+index+'.'+field;")
    traffic, snapshots = routed_runner_browser(monkeypatch, html)
    spec = {**SPEC, 'rewards': [{'name_th': 'หนึ่ง', 'name_en': 'One', 'code_list': 'A001'},
                               {'name_th': 'สอง', 'name_en': 'Two', 'code_list': 'B001'}]}
    results = asyncio.run(ItemCodeBuilder(lambda *_: None).run_many(
        'CabalM TH', [spec, {**spec, 'slug': 'second-code'}], {'cookies': [], 'origins': []}))
    assert [r['slug'] for r in results] == ['requested-code', 'second-code']
    assert all(not r['saved'] and r['made_id'] is None and 'ชุดรางวัลที่ 2' in r['error'] for r in results)
    assert snapshots[0]['submits'] == ['0']
    assert traffic == [('GET', 'https://aztek-tools-v2.combo-interactive.com/combo/cabalm/itemcodes/create')] * 2


def test_lazy_name_control_is_waited_for_before_filling():
    html = HEADER_HTML.replace('<input id="name_th" name="renamed-th">', '''
        <div id="late-name"></div><script>
          setTimeout(()=>{document.getElementById('late-name').innerHTML=
            '<input id="name_th" name="renamed-th">';},200);
        </script>''')
    missing, error, values = exercise_form(html)
    assert error is None
    assert values['names'] == ['โค้ดที่ขอ', 'Requested code', 'requested-code']
    assert missing == ['เวลาเริ่มใช้งาน', 'เวลาสิ้นสุด', 'ชุดรางวัล']
    assert values['submits'] == ['0']


def test_queue_stops_each_broken_header_before_save_without_retrying_write(monkeypatch):
    html = HEADER_HTML.replace('<input id="slug" name="renamed-slug">',
                               '<input id="slug"><input id="slug">')
    traffic, snapshots = routed_runner_browser(monkeypatch, html)
    specs = [dict(SPEC), {**SPEC, 'name_th': 'รายการที่สอง', 'slug': 'second-code'}]
    results = asyncio.run(ItemCodeBuilder(lambda *_: None).run_many(
        'CabalM TH', specs, {'cookies': [], 'origins': []}))
    assert len(results) == 2
    assert all(not r['saved'] and r['made_id'] is None and 'Slug' in r['error'] for r in results)
    assert [r['slug'] for r in results] == ['requested-code', 'second-code']
    assert [s['submits'] for s in snapshots] == [['0']]
    assert traffic == [('GET', 'https://aztek-tools-v2.combo-interactive.com/combo/cabalm/itemcodes/create')] * 2
