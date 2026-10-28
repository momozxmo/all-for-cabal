"""Private, immutable image attachments use real HTTP, storage and decoding."""
import base64
from copy import deepcopy
from hashlib import sha256
from io import BytesIO

from PIL import Image
import pytest
from sqlalchemy import select

from web.models import Job
from test_new_item_import_api import one_draft
from test_new_item_reference_api import confirm


def image_bytes(fmt='PNG', color='red'):
    stream = BytesIO()
    with Image.new('RGB', (2, 2), color) as image:
        image.save(stream, format=fmt)
    return stream.getvalue()


def attach(client, draft, content=None, *, mime='image/png', name='image.png', revision=None):
    return client.post('/api/new-items/drafts/' + draft['draft_id'] + '/image',
        data={'revision': draft['revision'] if revision is None else revision},
        files={'file': (name, image_bytes() if content is None else content, mime)})


@pytest.mark.parametrize('fmt,mime,name', [('PNG', 'image/png', 'pic.png'),
    ('JPEG', 'image/jpeg', 'pic.jpg'), ('WEBP', 'image/webp', 'pic.webp')])
def test_attachment_is_private_immutable_and_referenced_by_digest(client, test_database, fmt, mime, name):
    draft = one_draft(client)
    content = image_bytes(fmt)
    response = attach(client, draft, content, mime=mime, name=name)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved['revision'] == draft['revision'] + 1
    assert saved['values']['image_key'] == 'sha256:' + sha256(content).hexdigest()
    fetched = client.get('/api/new-items/drafts/' + draft['draft_id'] + '/image')
    assert fetched.status_code == 200 and fetched.content == content
    assert fetched.headers['content-type'].startswith(mime)
    assert 'no-store' in fetched.headers['cache-control']
    assert fetched.headers['x-content-type-options'] == 'nosniff'
    assert base64.b64encode(content).decode() not in client.get('/api/new-items/history').text
    assert base64.b64encode(content).decode() not in client.get('/api/new-items/drafts').text
    frozen = confirm(client, saved)
    assert frozen['submitted_values']['image_key'] == saved['values']['image_key']
    assert frozen['references'][0]['original']['image_key'] is None


@pytest.mark.parametrize('content,mime', [(b'<html>not a picture</html>', 'image/png'),
    (b'\x89PNG\r\n\x1a\ntruncated', 'image/png'), (b'<svg onload="alert(1)"></svg>', 'image/svg+xml')])
def test_fake_or_truncated_image_never_changes_draft(client, content, mime):
    draft = one_draft(client)
    response = attach(client, draft, content, mime=mime)
    assert response.status_code == 400, response.text
    assert client.get('/api/new-items/drafts').json()['drafts'][0]['revision'] == draft['revision']
    assert client.get('/api/new-items/drafts').json()['drafts'][0]['values']['image_key'] is None


def test_declared_mime_must_match_decoded_format(client):
    draft = one_draft(client)
    assert attach(client, draft, image_bytes('JPEG'), mime='image/png').status_code == 400


def test_image_limit_uses_image_size_not_small_json_limit(client):
    draft = one_draft(client)
    # PNG allows trailing bytes: valid image larger than the generic2MB mutation cap.
    content = image_bytes() + b'\0' * (2 * 1024 * 1024 + 1)
    response = attach(client, draft, content)
    assert response.status_code == 200, response.text
    assert client.get('/api/new-items/drafts/' + draft['draft_id'] + '/image').content == content
    updated = response.json()
    assert attach(client, updated, b'x' * 5_000_001).status_code == 413


def test_image_is_owned_and_arbitrary_key_cannot_be_rebound(client, test_database, client_for, other_member):
    draft = one_draft(client)
    image = attach(client, draft)
    assert image.status_code == 200, image.text
    other = client_for(other_member)
    assert other.get('/api/new-items/drafts/' + draft['draft_id'] + '/image').status_code == 404
    assert attach(other, draft).status_code == 404
    own_draft = one_draft(other)
    rejected = other.patch('/api/new-items/drafts/' + own_draft['draft_id'], json={
        'revision': own_draft['revision'], 'values': {'image_key': image.json()['values']['image_key']}})
    assert rejected.status_code == 400
    with test_database.session() as db:
        source = db.get(Job, draft['draft_id'])
        target = db.get(Job, own_draft['draft_id'])
        config = deepcopy(target.config)
        config['image_asset_id'] = source.config['image_asset_id']
        config['draft']['values']['image_key'] = source.config['draft']['values']['image_key']
        target.config = config
    assert other.post('/api/new-items/confirm', json={'game': 'CabalPC TH', 'selected': [{
        'id': own_draft['draft_id'], 'revision': own_draft['revision']}]}).status_code == 409


def test_stale_upload_and_confirmed_draft_cannot_change_image(client, test_database):
    draft = one_draft(client)
    attached = attach(client, draft)
    assert attached.status_code == 200, attached.text
    with test_database.session() as db:
        before = len(list(db.scalars(select(Job).where(Job.tool == 'new_item_image'))))
    assert attach(client, draft, image_bytes(color='blue')).status_code == 409
    updated = attached.json()
    confirm(client, updated)
    assert attach(client, updated, image_bytes(color='blue')).status_code == 409
    with test_database.session() as db:
        assert len(list(db.scalars(select(Job).where(Job.tool == 'new_item_image')))) == before


def test_changed_stored_content_cannot_be_confirmed(client, test_database):
    draft = one_draft(client)
    attached = attach(client, draft)
    assert attached.status_code == 200, attached.text
    with test_database.session() as db:
        job = db.get(Job, draft['draft_id'])
        asset = db.get(Job, job.config['image_asset_id'])
        config = deepcopy(asset.config)
        config['content_b64'] = base64.b64encode(image_bytes(color='blue')).decode()
        asset.config = config
    response = client.post('/api/new-items/confirm', json={'game': 'CabalPC TH', 'selected': [{
        'id': draft['draft_id'], 'revision': attached.json()['revision']}]})
    assert response.status_code == 409


@pytest.mark.parametrize('second_color,groups', [('red', 1), ('blue', 2)])
def test_image_digest_controls_group_identity_not_private_asset_id(client, second_color, groups):
    from web.new_item_domain import group_drafts
    first = attach(client, one_draft(client))
    second = attach(client, one_draft(client), image_bytes(color=second_color))
    assert first.status_code == second.status_code == 200
    combined = group_drafts([first.json(), second.json()])
    assert len(combined) == groups
    assert sum(len(draft['occurrences']) for draft in combined) == 2


def test_image_requires_authentication(anonymous_client):
    assert anonymous_client.get('/api/new-items/drafts/' + 'a' * 32 + '/image').status_code == 401


def test_remove_image_only_clears_draft_binding(client, test_database):
    draft = one_draft(client)
    uploaded = attach(client, draft)
    assert uploaded.status_code == 200
    response = client.delete('/api/new-items/drafts/' + draft['draft_id'] + '/image',
                             params={'revision': uploaded.json()['revision']})
    assert response.status_code == 200, response.text
    assert response.json()['values']['image_key'] is None
    assert client.get('/api/new-items/drafts/' + draft['draft_id'] + '/image').status_code == 404
    with test_database.session() as db:
        assert len(list(db.scalars(select(Job).where(Job.tool == 'new_item_image')))) == 1
    assert confirm(client, response.json())['submitted_values']['image_key'] is None


@pytest.mark.parametrize('kind', ['large_dimensions', 'animated'])
def test_large_or_animated_images_are_not_accepted(client, kind):
    stream = BytesIO()
    if kind == 'large_dimensions':
        with Image.new('1', (5000, 5000)) as picture:
            picture.save(stream, format='PNG')
    else:
        with Image.new('RGB', (2, 2), 'red') as first, Image.new('RGB', (2, 2), 'blue') as second:
            first.save(stream, format='PNG', save_all=True, append_images=[second], duration=100)
    draft = one_draft(client)
    assert attach(client, draft, stream.getvalue()).status_code == 400
