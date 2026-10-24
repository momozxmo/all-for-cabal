"""Product media/language behavior at the public form boundary, synthetic HTTP only."""
import asyncio
import re

import pytest

from web.aztek_locator import AztekLocatorError
from web.product_runner import ProductBuilder
from test_web_itemcode_id_first import routed_runner_browser
from test_web_product_id_first import HEADER_HTML, SPEC, CREATE_URLS, exercise_form


def media_html():
    def tabs(kind):
        buttons, panels = '', ''
        # Deliberately different from global Thai/English and Thumbnail/Banner order.
        for lang, label in [('en', 'English'), ('th', 'ไทย')]:
            active = lang == 'th'
            buttons += '''<button type="button" role="tab" id="runtime-%s-%s-tab"
              aria-controls="runtime-%s-%s-panel" aria-selected="%s"
              onclick="switchLanguage(this)">%s</button>''' % (kind, lang, kind, lang, str(active).lower(), label)
            if kind == 'images':
                content = ''.join('''<div><label>%s</label><div><div role="button" tabindex="0">
                  <input type="file" class="hidden" data-fixture-slot="%s_%s"
                    accept="image/png,image/jpeg,image/webp,image/gif"></div></div></div>'''
                                  % (title, title.lower(), lang) for title in ('Banner', 'Thumbnail'))
            else:
                content = '''<iframe title="Rich Text Area" class="tox-edit-area__iframe"
                  id="tiny-react-changing-%s" data-fixture-editor="%s"
                  srcdoc="<body contenteditable='true'>keep-%s</body>"></iframe>''' % (lang, lang, lang)
            panels += '''<div role="tabpanel" id="runtime-%s-%s-panel" aria-labelledby="runtime-%s-%s-tab"
              data-state="%s" data-slot="tabs-content">%s</div>''' % (
                  kind, lang, kind, lang, 'active' if active else 'inactive', content)
        return '<div role="tablist">%s</div>%s' % (buttons, panels)

    sections = '<section><h2>รูปภาพสินค้า</h2>%s</section><section><h2>รายละเอียด</h2>%s</section>' % (tabs('images'), tabs('details'))
    return (HEADER_HTML.replace('</aside>', '<input type="file" data-fixture-slot="outside"></aside>')
            .replace('</form>', sections + '</form>') + '''<style>
      [data-state="inactive"],.hidden {display:none}
    </style><script>
      function switchLanguage(tab){const section=tab.closest('section');
        for(const t of section.querySelectorAll('[role="tab"]'))t.setAttribute('aria-selected',String(t===tab));
        for(const p of section.querySelectorAll('[role="tabpanel"]'))p.dataset.state=p.id===tab.getAttribute('aria-controls')?'active':'inactive';
      }
    </script>''')


def image_payloads():
    return {slot:{'name':slot+'.png', 'content_type':'image/png', 'bytes':slot.encode('ascii')}
            for slot in ['thumbnail_th','banner_th','thumbnail_en','banner_en']}


@pytest.mark.parametrize('url', CREATE_URLS)
def test_product_uploads_each_memory_image_to_its_language_and_label_not_global_index(url):
    # Global nth upload picks the outside input and crosses both labels/languages.
    missing, error, values = exercise_form(media_html(), url=url, spec={**SPEC, 'images':image_payloads()})
    assert error is None
    assert values['mediaFiles'] == {
        'outside': [],
        'banner_en': [{'name':'banner_en.png', 'type':'image/png', 'size':9, 'bytes':[98,97,110,110,101,114,95,101,110]}],
        'thumbnail_en': [{'name':'thumbnail_en.png', 'type':'image/png', 'size':12, 'bytes':[116,104,117,109,98,110,97,105,108,95,101,110]}],
        'banner_th': [{'name':'banner_th.png', 'type':'image/png', 'size':9, 'bytes':[98,97,110,110,101,114,95,116,104]}],
        'thumbnail_th': [{'name':'thumbnail_th.png', 'type':'image/png', 'size':12, 'bytes':[116,104,117,109,98,110,97,105,108,95,116,104]}],
    }
    assert values['editorTexts'] == {'en':'keep-en', 'th':'keep-th'}
    assert values['submits'] == ['0']


@pytest.mark.parametrize('url', CREATE_URLS)
def test_product_details_fill_their_own_language_not_the_image_tabs_or_first_iframe(url):
    # The images tablist appears first, so a page-wide Thai/English lookup is wrong.
    _missing, error, values = exercise_form(media_html(), url=url, spec={
        **SPEC, 'details_th':'รายละเอียดที่ขอ', 'details_en':'Requested English details'})
    assert error is None
    assert values['editorTexts'] == {'en':'Requested English details', 'th':'รายละเอียดที่ขอ'}
    assert all(files == [] for files in values['mediaFiles'].values())
    assert values['submits'] == ['0']


def test_product_disabled_upload_is_not_written_or_reported_ready():
    html = media_html().replace('type="file" class="hidden"', 'type="file" disabled class="hidden"')
    _missing, error, values = exercise_form(html, spec={
        **SPEC, 'images':{'thumbnail_th':image_payloads()['thumbnail_th']}})
    assert isinstance(error, AztekLocatorError)
    assert 'thumbnail_th' in str(error)
    assert all(files == [] for files in values['mediaFiles'].values())
    assert values['submits'] == ['0']


@pytest.mark.parametrize('kind', ['images', 'details'])
@pytest.mark.parametrize('fault', ['submit-tab', 'duplicate-tab', 'missing-relation', 'wrong-panel', 'wrong-labelledby'])
def test_product_broken_language_contract_never_fills_another_panel(kind, fault):
    html = media_html()
    tab = re.search(r'<button[^>]+id="runtime-%s-en-tab"[^>]*>English</button>' % kind, html).group()
    if fault == 'submit-tab':
        html = html.replace(tab, tab.replace('type="button"', 'type="submit"'))
    elif fault == 'duplicate-tab':
        html = html.replace(tab, tab + tab)
    elif fault == 'missing-relation':
        html = html.replace(tab, tab.replace('aria-controls=', 'data-removed-controls='))
    elif fault == 'wrong-panel':
        other = 'details' if kind == 'images' else 'images'
        html = html.replace(tab, tab.replace('runtime-%s-en-panel' % kind, 'runtime-%s-en-panel' % other))
    else:
        html = html.replace('aria-labelledby="runtime-%s-en-tab"' % kind, 'aria-labelledby="unrelated-tab"')
    spec = ({'images':{'banner_en':image_payloads()['banner_en']}} if kind == 'images'
            else {'details_en':'Requested English details'})
    _missing, error, values = exercise_form(html, spec={**SPEC, **spec})
    assert isinstance(error, AztekLocatorError)
    assert ('รูปภาพสินค้า' if kind == 'images' else 'รายละเอียด') in str(error)
    assert all(files == [] for files in values['mediaFiles'].values())
    assert values['editorTexts'] == {'en':'keep-en', 'th':'keep-th'}
    assert values['submits'] == ['0']


@pytest.mark.parametrize('fault', ['duplicate-label', 'missing-file', 'duplicate-file', 'wrong-input-type', 'rejected-file'])
def test_product_image_contract_break_does_not_upload_into_another_field(fault):
    html = media_html()
    if fault == 'duplicate-label':
        html = html.replace('<label>Thumbnail</label>', '<label>Thumbnail</label><label>Thumbnail</label>')
    elif fault == 'missing-file':
        html = re.sub(r'<input[^>]+data-fixture-slot="thumbnail_en"[^>]*>', '', html)
    elif fault == 'duplicate-file':
        target = re.search(r'<input[^>]+data-fixture-slot="thumbnail_en"[^>]*>', html).group()
        html = html.replace(target, target + '<input type="file">')
    elif fault == 'wrong-input-type':
        target = re.search(r'<input[^>]+data-fixture-slot="thumbnail_en"[^>]*>', html).group()
        html = html.replace(target, target.replace('type="file"', 'type="text"'))
        # Snapshot observes File objects only, not text input values.
        html = html.replace('data-fixture-slot="thumbnail_en"', 'data-not-file="thumbnail_en"')
    else:
        html = html.replace('data-fixture-slot="thumbnail_en"', 'data-fixture-slot="thumbnail_en" onchange="this.value=\'\'"')
    _missing, error, values = exercise_form(html, spec={
        **SPEC, 'images':{'thumbnail_en':image_payloads()['thumbnail_en']}})
    assert isinstance(error, AztekLocatorError)
    assert 'thumbnail_en' in str(error)
    assert all(files == [] for files in values['mediaFiles'].values())
    assert values['editorTexts'] == {'en':'keep-en', 'th':'keep-th'}
    assert values['submits'] == ['0']


@pytest.mark.parametrize('fault', ['duplicate-frame', 'wrong-editor', 'readonly-body', 'rejected-text'])
def test_product_editor_contract_failure_stops_without_overwriting_other_language(fault):
    html = media_html()
    target = next(frame for frame in re.findall(r'<iframe.*?</iframe>', html, re.S)
                  if 'data-fixture-editor="en"' in frame)
    if fault == 'duplicate-frame':
        html = html.replace(target, target + '<iframe title="Rich Text Area" srcdoc="<body contenteditable=true></body>"></iframe>')
    elif fault == 'wrong-editor':
        html = html.replace(target, target.replace('title="Rich Text Area"', 'title="Unrelated frame"'))
    elif fault == 'readonly-body':
        html = html.replace(target, target.replace("contenteditable='true'", "contenteditable='false'"))
    else:
        html = html.replace(target, target.replace("contenteditable='true'", "contenteditable='true' oninput='this.textContent=String(999)'"))
    _missing, error, values = exercise_form(html, spec={**SPEC, 'details_en':'Requested English details'})
    assert isinstance(error, AztekLocatorError)
    assert 'รายละเอียด' in str(error)
    assert values['editorTexts']['th'] == 'keep-th'
    assert all(files == [] for files in values['mediaFiles'].values())
    assert values['submits'] == ['0']


def test_product_only_requested_media_language_is_changed():
    _missing, error, values = exercise_form(media_html(), spec={
        **SPEC, 'details_th':'', 'details_en':'Only English',
        'images':{'banner_en':image_payloads()['banner_en']}})
    assert error is None
    assert values['editorTexts'] == {'en':'Only English', 'th':'keep-th'}
    assert values['mediaFiles']['banner_en'][0]['name'] == 'banner_en.png'
    assert all(files == [] for slot, files in values['mediaFiles'].items() if slot != 'banner_en')
    assert values['submits'] == ['0']


def test_product_empty_optional_media_does_not_require_any_media_controls():
    _missing, error, values = exercise_form(HEADER_HTML, spec={
        **SPEC, 'details_th':'', 'details_en':'', 'images':{}})
    assert error is None
    assert values['submits'] == ['0']


def test_product_media_contract_failure_keeps_queue_identity_without_submit(monkeypatch):
    html = media_html().replace('<label>Thumbnail</label>', '<label>Thumbnail</label><label>Thumbnail</label>')
    traffic, snapshots = routed_runner_browser(monkeypatch, html, preview_urls=(CREATE_URLS[0],))
    results = asyncio.run(ProductBuilder(lambda *_:None).run_many('CabalM TH', [
        {**SPEC, 'slug':'keep-media', 'group':'keep-group', 'images':image_payloads()}], {}))
    assert len(results) == 1
    result = results[0]
    assert result['saved'] is False and result['made_id'] is None
    assert result['slug'] == 'keep-media' and result['group'] == 'keep-group'
    assert result['name'] == 'สินค้าที่ขอ' and 'thumbnail_th' in result['error']
    assert snapshots[-1]['submits'] == ['0']
    assert traffic == [('GET', CREATE_URLS[0])]
