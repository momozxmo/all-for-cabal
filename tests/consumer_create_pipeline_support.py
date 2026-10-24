"""Downstream public API/runner verification; all HTTP is synthetic/blocked.

Input is the actual consumer drafts exported from the existing Finder/Bundle UI
pipeline. Event-plan Product origin is still a matching fixture; Shop uses the real API.
Operator-required fields below are explicit test choices, not imported values.
"""
from copy import deepcopy
from datetime import datetime
from email.parser import BytesParser
from email.policy import default
import json

from test_web_event_result_id_first import event_result_html
from test_web_itemcode_id_first import itemcode_confirmation_html, routed_runner_browser
from test_web_product_create_id_first import REQUEST as PRODUCT_OPERATOR_FIELDS
from test_web_product_result_id_first import result_html as product_result_html
from test_web_validation import GAME


def _completed_draft(draft, name):
    job = deepcopy(draft)
    job['client_key'] = draft.get('client_key') or draft.get('id') or draft.get('key')
    assert job['client_key'], draft
    job.update(name_th=name, name_en=name, slug=name, uses_per_user='1')
    for index, reward in enumerate(job.get('rewards', []), 1):
        reward.update(name_en=reward.get('name_en') or reward['name_th'],
                      uses_per_user='1', limited=False,
                      code_type='FIX', code_list=f'PIPELINE-{index}')
    return job


def _submit(client, monkeypatch, *, path, key, job, html, create_url, write_url, response, made_id):
    writes = []
    traffic, snapshots = routed_runner_browser(
        monkeypatch, html, preview_urls=(create_url,),
        synthetic_write_url=write_url, synthetic_write_json=response,
        context_options={'service_workers': 'block'}, write_audit=writes)
    payload = {'game': GAME, 'do_save': True, key: [job]}
    if key == 'products':
        submitted = client.post(path, data={'payload': json.dumps(payload)})
    else:
        submitted = client.post(path, json=payload)
    assert submitted.status_code == 200, submitted.text
    outcome = submitted.json()
    assert (outcome['planned'], outcome['created']) == (1, 1), outcome
    result = outcome['results'][0]
    assert (result['client_key'], result['saved'], result['made_id'], result['error']) == (
        job['client_key'], True, made_id, None), f'Consumer own result mismatch: {outcome}'
    assert traffic == [('GET', create_url), ('POST', write_url + '?owner=form')]
    assert len(snapshots) == 1
    assert snapshots[0]['submits'] == ['1'] and snapshots[0]['confirms'] == '1'
    assert len(writes) == 1
    if key == 'products':
        message = BytesParser(policy=default).parsebytes(
            ('Content-Type: ' + writes[0]['content_type'] + '\r\n\r\n' + writes[0]['body']).encode())
        fields = {part.get_param('name', header='content-disposition'):
                  part.get_content() for part in message.iter_parts()}
        assert json.loads(fields['bundle_ids']) == job['bundle_ids']
        assert fields['primary_bundle_id'] == job['primary_bundle_id']
        assert fields['th[name]'] == job['name_th']
        assert fields['en[name]'] == job['name_en']
        for control, field in (('show_at', 'start_at'), ('hide_at', 'end_at')):
            assert fields[control] == datetime.fromisoformat(job[field]).strftime('%d %b %Y %H:%M:%S')
    else:
        body = json.loads(writes[0]['body'] or '{}')
        assert [r['bundle_id'] for r in body.get('rewards', [])] == [
            r['bundle_id'] for r in job['rewards']], f'Synthetic POST lost Bundle IDs: {writes}'
    return snapshots[0], result


def create_consumers_from_drafts(client, monkeypatch, drafts):
    """Keep IDs from the real upstream result; don't manufacture handoff IDs."""
    assert set(drafts) == {'/itemcodes', '/events', '/products'}
    assert len(drafts['/itemcodes']) == len(drafts['/events']) == 2
    assert len(drafts['/products']) == 2
    for target in ('/itemcodes', '/events'):
        assert [r['bundle_id'] for draft in drafts[target] for r in draft['rewards']] == ['42', '43']

    code_write = 'https://admin-api-v2.combo-interactive.com/cabalm/itemcode/events'
    code_html = itemcode_confirmation_html().replace('/synthetic-itemcode-write', code_write)
    code_html = code_html.replace('10010', '420').replace('1001', '42').replace('2002', '43')
    # Test-only wire schema, serialized from the form's actual filled state.
    # This is not evidence of a live Aztek request schema or persisted record.
    original = "{method:'POST'})"
    assert code_html.count(original) == 1
    code_html = code_html.replace(original, "{method:'POST',body:JSON.stringify({rewards:"
        "JSON.parse(document.getElementById('reward-values').textContent)})})")
    for index, (draft, expected_bundle) in enumerate(zip(drafts['/itemcodes'], ('42', '43')), 1):
        code = _completed_draft(draft, f'pipeline-code-{index}')
        code.update(limited=False, start_time='2026-08-27 00:00:00',
                    end_time='2027-09-28 23:59:59')
        snapshot, _ = _submit(
            client, monkeypatch, path='/api/itemcodes/run', key='itemcodes', job=code,
            html=code_html, create_url='https://aztek-tools-v2.combo-interactive.com/combo/cabalm/itemcodes/create',
            write_url=code_write, response={'id': 500 + index}, made_id=str(500 + index))
        assert [r['bundle_id'] for r in snapshot['rewards']] == [expected_bundle]

    event_html = event_result_html().replace('10010', '420').replace('1001', '42').replace('2002', '43')
    original = "document.querySelector('main form input[id=slug]').value})"
    assert event_html.count(original) == 1
    event_html = event_html.replace(original,
        "document.querySelector('main form input[id=slug]').value,rewards:"
        "JSON.parse(document.getElementById('reward-values').textContent)})")
    for index, (draft, expected_bundle, event_id) in enumerate(zip(
            drafts['/events'], ('42', '43'), ('11111111-2222-4333-8444-555555555555',
                                            '44444444-2222-4333-8444-555555555555')), 1):
        event = _completed_draft(draft, f'pipeline-event-{index}')
        event.update(quantity='1', remaining='1', start_event='2026-08-27 00:00:00',
                     end_event='2026-08-27 23:59:59', start_claim='2026-08-27 00:00:00',
                     end_claim='2026-08-27 23:59:59')
        snapshot, _ = _submit(
            client, monkeypatch, path='/api/events/run', key='events', job=event,
            html=event_html, create_url='https://aztek-tools-v2.combo-interactive.com/combo/cabalm/events/create',
            write_url='https://admin-api-v2.combo-interactive.com/cabalm/event/events',
            response={'success': True, 'data': {'data': {'id': event_id, 'slug': f'pipeline-event-{index}'}}},
            made_id=event_id)
        assert [r['bundle_id'] for r in snapshot['rewards']] == [expected_bundle]

    create_products_from_drafts(client, monkeypatch, drafts['/products'])


def create_products_from_drafts(client, monkeypatch, drafts, *, preserve_source_fields=False):
    """Consume UI drafts; preserve imported Shop values when requested by that case."""
    assert len(drafts) == 2
    for index, (draft, expected_bundle, product_id) in enumerate(zip(
            drafts, ('42', '43'), (
                '22222222-2222-4333-8444-555555555555',
                '33333333-2222-4333-8444-555555555555')), 1):
        assert draft['bundle_ids'] == [expected_bundle]
        assert draft['primary_bundle_id'] == expected_bundle
        product = {**deepcopy(PRODUCT_OPERATOR_FIELDS), **deepcopy(draft)}
        product.update(client_key=draft.get('client_key') or draft.get('id') or draft.get('key'),
                       name_th=draft['name_th'] if preserve_source_fields else f'pipeline-product-{index}',
                       name_en=draft['name_en'] if preserve_source_fields else f'pipeline-product-{index}',
                       category_id='category-9', prices=deepcopy(PRODUCT_OPERATOR_FIELDS['prices']),
                       start_at=draft['start_at'] if preserve_source_fields else PRODUCT_OPERATOR_FIELDS['start_at'],
                       end_at=draft['end_at'] if preserve_source_fields else PRODUCT_OPERATOR_FIELDS['end_at'])
        assert product['client_key'] and product['source_group_key']
        # Audit the actual filled Bundle/Primary DOM state at the browser boundary.
        html = product_result_html().replace('20810', '420').replace('2081', '42').replace('2082', '43')
        if preserve_source_fields:
            # Shop start defaults to today's date; the old fixture only had day17/27/28.
            html = html.replace('for(const number of [17,27,28])',
                                'for(const number of Array.from({length:31},(_,i)=>i+1))')
        html += '''<pre id="reward-values">{}</pre><script>
          const previousRenderBundles=renderBundles;
          renderBundles=()=>{previousRenderBundles();document.getElementById('reward-values').textContent=
            JSON.stringify({bundle_ids:selectedBundles,primary_bundle_id:primaryBundle});};
        </script>'''
        original = "fetch('https://admin-api-v2.combo-interactive.com/cabalm/shop/products?owner=form',{method:'POST',body});"
        assert html.count(original) == 1
        html = html.replace(original, '''body.append('bundle_ids',JSON.stringify(
          [...document.querySelectorAll('main form [data-fixture-bundle]')].map(e=>e.dataset.fixtureBundle)));
          body.append('primary_bundle_id',document.querySelector(
            'main form [data-fixture-bundle] button[aria-checked="true"]').closest('[data-fixture-bundle]').dataset.fixtureBundle);
          for(const id of ['show_at','hide_at'])body.append(id,
            document.querySelector('main form button[id="'+id+'"]').textContent);
        ''' + original)
        snapshot, result = _submit(
            client, monkeypatch, path='/api/products/run', key='products', job=product,
            html=html, create_url='https://aztek-tools-v2.combo-interactive.com/combo/cabalm/shop/products/create',
            write_url='https://admin-api-v2.combo-interactive.com/cabalm/shop/products',
            response={'success': True, 'data': {'data': {'id': product_id, 'name': product['name_th']}}},
            made_id=product_id)
        assert snapshot['rewards'] == {'bundle_ids': [expected_bundle], 'primary_bundle_id': expected_bundle}
        assert result['source_group_key'] == draft['source_group_key']
