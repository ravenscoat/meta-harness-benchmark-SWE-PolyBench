import json
from types import SimpleNamespace

import pytest

from benchmarks.polybench.image_cache import VERSION, ensure_image, remember_image, retained_images
from hx.models import HXError


class MissingImage(Exception):
    status_code = 404


def case(name):
    digest = 'sha256:' + name * 64
    return {'id': name, 'language': 'JavaScript', 'image_id': digest,
            'image_reference': 'ghcr.io/hx/' + name + ':v1',
            'image_digests': ['ghcr.io/hx/' + name + '@' + digest]}


def test_all_selected_images_survive_successive_remember_and_trim(tmp_path):
    cases = [case(n) for n in 'abc']
    (tmp_path / 'selection.json').write_text(json.dumps({'cases': cases}))
    (tmp_path / 'images.json').write_text(json.dumps({c['id']: c for c in cases}))
    (tmp_path / 'image-retention.json').write_text(json.dumps(
        {'version': VERSION, 'cases': list('abc')}))
    removed = []
    images = {c['image_id']: SimpleNamespace(id=c['image_id'], tags=[c['image_reference']])
              for c in cases}
    client = SimpleNamespace(images=SimpleNamespace(get=lambda n: images[n],
        remove=lambda *a, **k: removed.append(a)),
        containers=SimpleNamespace(list=lambda **k: []))
    for image in images.values():
        image.client = client
        remember_image(tmp_path, image)
    assert removed == []
    assert len(retained_images(tmp_path, {c['id']: c for c in cases})) == 3


@pytest.mark.parametrize('names', [list('abcd'), ['a', 'a'], ['other'], []])
def test_retention_rejects_unbounded_or_unselected_policies(tmp_path, names):
    (tmp_path / 'selection.json').write_text(json.dumps({'cases': [case('a')]}))
    (tmp_path / 'image-retention.json').write_text(json.dumps(
        {'version': VERSION, 'cases': names}))
    with pytest.raises(HXError, match='retention policy'):
        retained_images(tmp_path, {})


def pull_fixture(tmp_path, monkeypatch, events, observed_id=None):
    c = case('a')
    monkeypatch.setattr('benchmarks.polybench.preflight.check_storage', lambda *a: None)
    pulled = []
    calls = []
    def get(name):
        calls.append(name)
        if not pulled:
            raise MissingImage()
        return SimpleNamespace(id=observed_id or c['image_id'],
            tag=lambda *a: calls.append('tag'), client=client)
    def pull(ref, **kwargs):
        assert ref == c['image_digests'][0]
        assert kwargs == {'stream': True, 'decode': True}
        yield from events
        pulled.append(ref)
    client = SimpleNamespace(images=SimpleNamespace(get=get), api=SimpleNamespace(pull=pull))
    return c, client, calls


def test_successful_pull_inspects_content_id_instead_of_digest_alias(tmp_path, monkeypatch):
    c, client, calls = pull_fixture(tmp_path, monkeypatch, [{'status': 'Download complete'}])
    image = ensure_image(client, tmp_path, c)
    assert image.id == c['image_id']
    assert calls == [c['image_id'], c['image_id'], 'tag']
    receipt = json.loads(next(tmp_path.glob('image-pulls/*/receipt.json')).read_text())
    assert receipt['complete'] is True


def test_streamed_registry_error_is_preserved_and_not_hidden_by_inspect(tmp_path, monkeypatch):
    c, client, calls = pull_fixture(tmp_path, monkeypatch, [{'error': 'manifest unknown'}])
    with pytest.raises(HXError, match='manifest unknown'):
        ensure_image(client, tmp_path, c)
    assert calls == [c['image_id']]
    receipt = json.loads(next(tmp_path.glob('image-pulls/*/receipt.json')).read_text())
    assert receipt['complete'] is False
    assert 'manifest unknown' in receipt['error']
    assert 'manifest unknown' in next(tmp_path.glob('image-pulls/*/events.jsonl')).read_text()


def test_changed_image_id_is_rejected_before_aliasing(tmp_path, monkeypatch):
    c, client, calls = pull_fixture(tmp_path, monkeypatch, [], observed_id='sha256:changed')
    with pytest.raises(HXError, match='identity changed'):
        ensure_image(client, tmp_path, c)
    assert 'tag' not in calls
