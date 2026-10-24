"""Product Bundle/Primary behavior at the public form/runner seam; all HTTP intercepted."""
import asyncio

import pytest

from web.aztek_locator import AztekLocatorError
from web.product_runner import ProductBuilder
from test_web_itemcode_id_first import routed_runner_browser
from test_web_product_id_first import HEADER_HTML, SPEC, CREATE_URLS, exercise_form


def bundle_html(base=HEADER_HTML):
    section = '''<section><header><h2>Bundle</h2><div>
      <button type="button" aria-haspopup="dialog" data-slot="popover-trigger"
        onclick="openBundles(this)">เลือก bundle</button></div></header>
      <button type="button" role="checkbox" data-primary-decoy aria-checked="false"
        onclick="document.body.dataset.bundleDecoyChanges='1'">unrelated checkbox</button>
      <div data-selected-bundles></div><p data-bundle-count>0/20 Bundles</p>
    </section>'''
    return (base.replace('</aside>', '''<section><h2>Bundle</h2><button type="button"
      onclick="document.body.dataset.bundleDecoyChanges='1'">เลือก bundle</button></section></aside>''')
            .replace('</form>', section + '</form>') + '''<script>
      let selectedBundles=[], primaryBundle='';
      const catalog=['20810','2081','2082','2083'];
      function renderBundles(){
        const section=document.querySelector('main form [data-selected-bundles]');
        section.innerHTML=selectedBundles.map((id,index)=>`<div data-fixture-bundle="${id}">
          <div><p><span>Chosen bundle</span><span>#${id}</span></p><div>
            <button type="button" role="checkbox" id="bundle-primary-${index}"
              aria-checked="${id===primaryBundle}" onclick="primaryBundle='${id}';renderBundles()">Primary</button>
          </div></div></div>`).join('');
        document.querySelector('[data-bundle-count]').textContent=selectedBundles.length+'/20 Bundles';
      }
      function openBundles(trigger){
        const popup=document.createElement('div');popup.id='runtime-product-bundles';
        popup.setAttribute('role','dialog');popup.dataset.state='open';popup.dataset.slot='popover-content';
        trigger.setAttribute('aria-controls',popup.id);trigger.setAttribute('aria-expanded','true');
        const box=document.createElement('input');box.placeholder='ค้นหาด้วยชื่อหรือ id';popup.append(box);
        const results=document.createElement('div');popup.append(results);
        function show(){results.innerHTML='';for(const id of catalog.filter(id=>id.includes(box.value))){
          const row=document.createElement('button');row.type='button';row.innerHTML='<span>Choice</span><span>ID: '+id+'</span>';
          row.onclick=()=>{selectedBundles.push(id);if(!primaryBundle)primaryBundle=id;renderBundles();close();};results.append(row);
        }}
        box.oninput=()=>{results.innerHTML='';setTimeout(show,120);};show();
        function close(){popup.remove();document.querySelector('[data-other-popup]')?.remove();trigger.setAttribute('aria-expanded','false');}
        popup.onkeydown=e=>{if(e.key==='Escape')close();};
        const other=document.createElement('div');other.setAttribute('role','dialog');other.dataset.otherPopup='1';
        other.innerHTML='<input placeholder="ค้นหาด้วยชื่อหรือ id"><button type="button" onclick="document.body.dataset.bundleDecoyChanges=1">Unrelated ID: 2081</button>';
        document.body.append(popup,other);
      }
    </script>''')


@pytest.mark.parametrize('url', CREATE_URLS)
def test_product_bundle_picker_uses_own_popup_exact_ids_and_keeps_requested_primary(url):
    missing, error, values = exercise_form(bundle_html(), url=url, spec={
        **SPEC, 'bundle_ids':['2081','2082'], 'primary_bundle_id':'2082'})
    assert error is None
    assert values['bundles'] == [{'id':'2081','primary':'false'}, {'id':'2082','primary':'true'}]
    assert values['bundleDecoyChanges'] == '0'
    assert values['submits'] == ['0']
    assert missing == ['หมวดหมู่', 'สกุลเงิน', 'วันเริ่มขาย', 'วันสิ้นสุด', 'ประเภทการจำกัด']


def test_product_missing_primary_id_does_not_fall_back_to_anonymous_checkbox():
    html = bundle_html().replace('id="bundle-primary-${index}"', 'data-removed-id="bundle-primary-${index}"')
    _missing, error, values = exercise_form(html, spec={
        **SPEC, 'bundle_ids':['2081','2082'], 'primary_bundle_id':'2082'})
    assert isinstance(error, AztekLocatorError)
    assert 'Primary' in str(error)
    assert values['bundleDecoyChanges'] == '0'
    assert values['submits'] == ['0']


@pytest.mark.parametrize('initial', ["['2081','2082']", "['2081']"])
def test_product_preserves_an_already_selected_bundle_list_without_adding_duplicates(initial):
    html = bundle_html() + '<script>selectedBundles=%s;primaryBundle=selectedBundles.at(-1);renderBundles();</script>' % initial
    missing, error, values = exercise_form(html, spec={
        **SPEC, 'bundle_ids':['2081','2082'], 'primary_bundle_id':'2082'})
    assert error is None
    assert values['bundles'] == [{'id':'2081','primary':'false'}, {'id':'2082','primary':'true'}]
    assert 'Bundle list/count' not in missing
    assert values['submits'] == ['0']


@pytest.mark.parametrize('fault', ['duplicate-id', 'wrong-type', 'swapped-ids', 'rejected-check', 'multiple-checked'])
def test_product_broken_primary_contract_never_submits_or_uses_another_checkbox(fault):
    html = bundle_html()
    if fault == 'duplicate-id':
        html = html.replace('</div></div></div>`', '<input hidden id="bundle-primary-${index}"></div></div></div>`')
    elif fault == 'wrong-type':
        html = html.replace('<button type="button" role="checkbox" id="bundle-primary-',
                            '<button type="submit" role="checkbox" id="bundle-primary-')
    elif fault == 'swapped-ids':
        html = html.replace('id="bundle-primary-${index}"', 'id="bundle-primary-${1-index}"')
    else:
        action = 'void(0)' if fault == 'rejected-check' else "this.setAttribute('aria-checked','true')"
        html = html.replace("primaryBundle='${id}';renderBundles()", action)
    _missing, error, values = exercise_form(html, spec={
        **SPEC, 'bundle_ids':['2081','2082'], 'primary_bundle_id':'2082'})
    assert isinstance(error, AztekLocatorError)
    assert 'Primary' in str(error)
    assert values['bundleDecoyChanges'] == '0'
    assert values['submits'] == ['0']


@pytest.mark.parametrize('fault', ['missing-relation', 'duplicate-popup', 'wrong-popup-role',
                                  'duplicate-search', 'wrong-search-type', 'duplicate-hit', 'submit-hit', 'no-hit'])
def test_product_picker_contract_failure_does_not_borrow_unrelated_popup_or_row(fault):
    html = bundle_html()
    if fault == 'missing-relation':
        html = html.replace("trigger.setAttribute('aria-controls',popup.id);", '')
    elif fault == 'duplicate-popup':
        html = html.replace('document.body.append(popup,other);', 'document.body.append(popup,other,popup.cloneNode(true));')
    elif fault == 'wrong-popup-role':
        html = html.replace("popup.setAttribute('role','dialog');", "popup.setAttribute('role','alertdialog');")
    elif fault == 'duplicate-search':
        html = html.replace('popup.append(box);', 'popup.append(box,box.cloneNode(true));')
    elif fault == 'wrong-search-type':
        html = html.replace("box.placeholder=", "box.type='number';box.placeholder=")
    elif fault == 'duplicate-hit':
        html = html.replace("['20810','2081','2082','2083']", "['2081','2081']")
    elif fault == 'submit-hit':
        html = html.replace("row.type='button';", "row.type='submit';")
    else:
        html = html.replace("['20810','2081','2082','2083']", '[]')
    _missing, error, values = exercise_form(html, spec={**SPEC, 'bundle_ids':['2081']})
    assert isinstance(error, AztekLocatorError)
    assert 'Bundle' in str(error)
    assert values['bundles'] == []
    assert values['bundleDecoyChanges'] == '0'
    assert values['submits'] == ['0']


@pytest.mark.parametrize('initial', ["['2082','2081']", "['2083']"])
def test_product_conflicting_existing_bundles_are_preserved_without_adding_or_removing(initial):
    html = bundle_html() + '<script>selectedBundles=%s;primaryBundle=selectedBundles[0];renderBundles();</script>' % initial
    _missing, error, values = exercise_form(html, spec={**SPEC, 'bundle_ids':['2081','2082']})
    assert isinstance(error, AztekLocatorError)
    assert [b['id'] for b in values['bundles']] == (['2082','2081'] if '2081' in initial else ['2083'])
    assert values['bundleDecoyChanges'] == '0' and values['submits'] == ['0']


def test_product_lazy_popup_and_primary_ids_are_waited_for():
    html = bundle_html().replace("trigger.setAttribute('aria-controls',popup.id);",
        "setTimeout(()=>trigger.setAttribute('aria-controls',popup.id),150);")
    html = html.replace("document.querySelector('[data-bundle-count]').textContent=", """
      for(const b of section.querySelectorAll('[id^="bundle-primary-"]')){const id=b.id;b.removeAttribute('id');setTimeout(()=>b.id=id,150);}
      document.querySelector('[data-bundle-count]').textContent=""")
    _missing, error, values = exercise_form(html, spec={
        **SPEC, 'bundle_ids':['2081','2082'], 'primary_bundle_id':'2082'})
    assert error is None
    assert values['bundles'] == [{'id':'2081','primary':'false'}, {'id':'2082','primary':'true'}]
    assert values['submits'] == ['0']


def test_product_bundle_names_with_hash_numbers_do_not_become_extra_selected_ids():
    html = bundle_html().replace('Chosen bundle</span>', 'Chosen bundle #777</span>')
    missing, error, values = exercise_form(html, spec={**SPEC, 'bundle_id':'2081'})
    assert error is None and 'Bundle list/count' not in missing
    assert values['bundles'] == [{'id':'2081','primary':'true'}]
    assert values['submits'] == ['0']


def test_product_queue_keeps_identity_after_primary_contract_break_without_create(monkeypatch):
    html = bundle_html().replace('id="bundle-primary-${index}"', 'data-removed-id="bundle-primary-${index}"')
    traffic, snapshots = routed_runner_browser(monkeypatch, html, preview_urls=(CREATE_URLS[0],))
    results = asyncio.run(ProductBuilder(lambda *_:None).run_many('CabalM TH', [
        {**SPEC, 'bundle_ids':['2081','2082'], 'primary_bundle_id':'2082', 'slug':'keep-product', 'group':'keep-group'}], {}))
    assert len(results) == 1
    result = results[0]
    assert result['saved'] is False and result['made_id'] is None
    assert result['name'] == 'สินค้าที่ขอ' and result['slug'] == 'keep-product' and result['group'] == 'keep-group'
    assert 'Primary' in result['error']
    assert snapshots[-1]['submits'] == ['0'] and traffic == [('GET', CREATE_URLS[0])]


def test_product_stale_bundle_popup_is_not_selected_after_trigger_relation_changes():
    html = bundle_html().replace("row.type='button';", """row.type='button';row.disabled=true;
      setTimeout(()=>{trigger.setAttribute('aria-controls','unrelated-owner');row.disabled=false;},180);""")
    _missing, error, values = exercise_form(html, spec={**SPEC, 'bundle_ids':['2081']})
    assert isinstance(error, AztekLocatorError)
    assert values['bundles'] == []
    assert values['bundleDecoyChanges'] == '0'
    assert values['submits'] == ['0']
