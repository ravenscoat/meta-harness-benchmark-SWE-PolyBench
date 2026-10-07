import json
from types import SimpleNamespace

import pytest

from benchmarks.polybench.storage_lifecycle import release_images, retired_images
from hx.models import HXError


class Missing(Exception):
    status_code = 404


def fixture():
    case = {
        "id": "x",
        "language": "JavaScript",
        "image_id": "sha256:abc",
        "image_reference": "ghcr.io/timesler/swe-polybench.eval.x:v1.1",
        "image_digests": ["ghcr.io/timesler/swe-polybench.eval.x@sha256:abc"],
    }
    refs = [case["image_reference"], case["image_digests"][0]]
    image = SimpleNamespace(id=case["image_id"], tags=[refs[0]], attrs={"RepoDigests": [refs[1]]})
    deleted = []
    present = [True]

    def get(key):
        if not present[0]:
            raise Missing()
        return image

    def remove(ref, force):
        assert not force
        deleted.append(ref)
        if ref in refs:
            refs.remove(ref)
        if not refs:
            present[0] = False

    client = SimpleNamespace(
        images=SimpleNamespace(get=get, remove=remove),
        containers=SimpleNamespace(list=lambda **kw: []),
    )
    return case, image, client, deleted


@pytest.mark.parametrize("reason", ["keep", "unknown_tag", "unknown_digest", "container"])
def test_cleanup_preserves_active_or_unrelated_images(reason):
    c, image, client, deleted = fixture()
    if reason == "unknown_tag":
        image.tags.append("my-app:latest")
    if reason == "unknown_digest":
        image.attrs["RepoDigests"].append("ghcr.io/unrelated@sha256:abc")
    if reason == "container":
        client.containers.list = lambda **kw: [object()]
    rows = release_images(client, [c], keep=[c["image_id"]] if reason == "keep" else [])
    assert not deleted and rows[0]["status"] == "kept"


def test_cleanup_releases_tag_and_digest_and_emits_receipt():
    c, image, client, deleted = fixture()
    events = []
    rows = release_images(client, [c, c], emit=events.append)
    assert len(rows) == 1 and rows[0]["status"] == "released"
    assert set(deleted) == {c["image_reference"], c["image_digests"][0]}
    assert events == rows
    assert release_images(client, [c])[0]["status"] == "already_absent"


def test_identity_change_and_removal_error_fail_closed():
    c, image, client, deleted = fixture()
    image.id = "changed"
    with pytest.raises(HXError, match="identity"):
        release_images(client, [c])
    assert not deleted
    image.id = c["image_id"]

    def broken(*args, **kwargs):
        raise RuntimeError("busy")

    client.images.remove = broken
    with pytest.raises(RuntimeError, match="busy"):
        release_images(client, [c])


def test_only_stopped_sibling_campaigns_enter_automatic_cleanup(tmp_path):
    c, _, _, _ = fixture()
    directory = tmp_path / ".hx"
    directory.mkdir()
    current = directory / "current"
    current.mkdir()
    (current / "controller.json").write_text("{}")
    for name in ["stopped", "active", "current"]:
        root = directory / name
        root.mkdir(exist_ok=True)
        (root / "images.json").write_text(json.dumps({"x": c}))
    (directory / "stopped/controller.exited.json").write_text("{}")
    (current / "controller.exited.json").write_text("{}")
    assert retired_images(current) == [c]
    assert retired_images(tmp_path / "other") == []


def test_exact_docker_generated_alias_digest_is_owned():
    c, image, client, deleted = fixture()
    alias = "polybench_javascript_x@" + c["image_id"]
    image.attrs["RepoDigests"].append(alias)
    assert release_images(client, [c])[0]["status"] == "released"
    assert alias in deleted


def test_current_campaign_trim_removes_recorded_digest_alias(tmp_path):
    from benchmarks.polybench.image_cache import trim_images

    c, image, client, deleted = fixture()
    image.attrs["RepoDigests"].append("polybench_javascript_x@" + c["image_id"])
    (tmp_path / "images.json").write_text(json.dumps({"x": c}))
    trim_images(client, tmp_path)
    assert deleted


def test_wrong_content_addressed_alias_is_not_owned():
    c, image, client, deleted = fixture()
    image.attrs["RepoDigests"].append("polybench_javascript_x@sha256:other")
    assert release_images(client, [c])[0]["status"] == "kept"
    assert not deleted
