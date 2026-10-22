"""Public request policy for the checked-all Bundle action; no browser/live access."""
import pytest


@pytest.mark.parametrize('value', ['true', 'false', 1, 0, None, [], {}])
def test_manual_checked_requires_explicit_boolean(client, value):
    response = client.post('/api/bundles/run', json={
        'game': 'CabalM TH', 'do_save': True, 'manual_checked': value,
        'bundles': [{'client_key': 'one', 'name': 'Pack', 'items': [{'id': '91', 'qty': '1'}]}]})
    assert response.status_code == 422


def test_manual_checked_cannot_change_preview_into_creation(client):
    response = client.post('/api/bundles/run', json={
        'game': 'CabalM TH', 'manual_checked': True,
        'bundles': [{'client_key': 'one', 'name': 'Pack', 'items': [{'id': '91', 'qty': '1'}]}]})
    assert response.status_code == 400
    assert 'สร้างจริง' in response.json()['detail']
