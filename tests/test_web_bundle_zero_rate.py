"""Zero is an explicit RANDOM rate, not a missing value. No live Aztek writes."""
from io import BytesIO
import asyncio

import pytest
from openpyxl import Workbook

from web.app import _clean_items, _clean_rewards
from web import bundle_runner
from test_web_bundle import FakePage, _builder
from test_web_validation import _connect_aztek, GAME


@pytest.mark.parametrize('source', ['paste', 'excel'])
@pytest.mark.parametrize('identity', ['11', 'CREDIT: Alz'])
def test_zero_rate_import_preserves_every_row_and_document_reference(client, source, identity):
    rows = [['Pack', 'RANDOM'], [identity, 1, 'Common', 0], ['12', 1, 'Rare', 100]]
    if source == 'paste':
        text = '\n'.join('\t'.join(map(str, row)) for row in rows)
        response = client.post('/api/bundles/import-text', json={'text': text})
    else:
        book = Workbook()
        for row in rows:
            book.active.append(row)
        out = BytesIO()
        book.save(out)
        book.close()
        response = client.post('/api/bundles/import', files={'file': ('zero.xlsx', out.getvalue())})
    assert response.status_code == 200
    sheet = response.json()['sheets'][0]
    assert sheet['errors'] == []
    bundle = sheet['bundles'][0]
    kind = 'items' if identity == '11' else 'rewards'
    assert bundle[kind][0]['rate'] == '0'
    assert bundle['document_reference'][kind][0]['rate'] == '0'
    assert bundle['items'][-1]['rate'] == '100'


@pytest.mark.parametrize('rate', [0, '0', '0.000'])
@pytest.mark.parametrize('kind', ['item', 'reward'])
def test_run_validation_preserves_zero_for_items_and_rewards(rate, kind):
    clean, entry = (_clean_items, {'id': '11'}) if kind == 'item' else (
        _clean_rewards, {'type': 'CREDIT', 'value': 'Alz', 'qty': '1'})
    assert clean([dict(entry, rate=rate)])[0]['rate'] == '0'


@pytest.mark.parametrize('rate', [0, '0'])
def test_form_filler_writes_explicit_zero_to_draw_chance(rate):
    page = FakePage(fields=[{'id': 'items.0.secret_chance',
                            'name': 'items.0.secret_chance', 'required': False}])
    asyncio.run(_builder()._fill_rates(page, [{'rate': rate}]))
    assert page.filled == [('input[id="items.0.secret_chance"]', ''),
                           ('input[id="items.0.secret_chance"]', '0')]


@pytest.mark.parametrize('rate', ['', '-0.001', '100.001', '0.0000'])
def test_invalid_random_rate_does_not_become_zero(client, rate):
    response = client.post('/api/bundles/import-text', json={
        'text': f'Pack\tRANDOM\n11\t1\tCommon\t{rate}\n12\t1\tRare\t100'})
    sheet = response.json()['sheets'][0]
    assert sheet['bundles'] == []
    assert any(error['row'] == 2 for error in sheet['errors'])


def test_zero_rates_do_not_bypass_random_total(client):
    response = client.post('/api/bundles/import-text', json={
        'text': 'Pack\tRANDOM\n11\t1\tCommon\t0\n12\t1\tRare\t99'})
    sheet = response.json()['sheets'][0]
    assert sheet['bundles'] == []
    assert any('100%' in error['message'] for error in sheet['errors'])


def test_preview_route_passes_zero_rates_without_enabling_save(client, monkeypatch):
    _connect_aztek(client)
    received = []

    class Builder:
        def __init__(self, log):
            pass

        async def run(self, **kwargs):
            received.append(kwargs)
            return {'added': 2, 'total': 2, 'rewards_added': 1,
                    'rewards_total': 1, 'kept_open': False}

    monkeypatch.setattr(bundle_runner, 'BundleBuilder', Builder)
    response = client.post('/api/bundles/run', json={
        'game': GAME, 'do_save': False, 'bundles': [{
            'name': 'Pack', 'bundle_type': 'RANDOM',
            'items': [{'id': '11', 'rate': 0}, {'id': '12', 'rate': '100'}],
            'rewards': [{'type': 'CREDIT', 'value': 'Alz', 'qty': '1', 'rate': 0}],
        }]})
    assert response.status_code == 200, response.text
    assert received[0]['items'][0]['rate'] == '0'
    assert received[0]['rewards'][0]['rate'] == '0'
    assert received[0]['do_save'] is False
    assert response.json()['results'][0]['saved'] is False
