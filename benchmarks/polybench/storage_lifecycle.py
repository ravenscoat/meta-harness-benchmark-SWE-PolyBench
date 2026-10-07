"""Release recorded regenerable image caches without deleting benchmark evidence."""

from __future__ import annotations

import json

from hx.models import HXError

VERSION = "retired-benchmark-cache@1"


def recorded_images(directory):
    records = []
    for pattern in ("*/images.json", "*/tasks/*/images.json"):
        for path in directory.glob(pattern):
            value = json.loads(path.read_text())
            if isinstance(value, dict):
                records.extend(
                    c
                    for c in value.values()
                    if isinstance(c, dict)
                    and str(c.get("image_reference", "")).startswith(
                        "ghcr.io/timesler/swe-polybench.eval."
                    )
                )
    return records


def retired_images(current_root):
    """Only sibling roots with a completed controller receipt are disposable."""
    directory = current_root
    while directory.name != ".hx" and directory.parent != directory:
        directory = directory.parent
    if directory.name != ".hx":
        return []
    owner = current_root
    while owner.parent != directory:
        owner = owner.parent
    if not (owner / "controller.json").exists():
        return []
    records = []
    for root in directory.iterdir():
        if (
            root.is_dir()
            and root.resolve() != owner.resolve()
            and (root / "controller.exited.json").exists()
        ):
            path = root / "images.json"
            if path.exists():
                value = json.loads(path.read_text())
                records.extend(
                    c
                    for c in value.values()
                    if isinstance(c, dict)
                    and str(c.get("image_reference", "")).startswith(
                        "ghcr.io/timesler/swe-polybench.eval."
                    )
                )
    return records


def release_images(client, records, keep=(), emit=lambda value: None):
    """Never force removal; preserve any unknown tag/digest or container use."""
    grouped = {}
    for case in records:
        key = case["image_id"]
        entry = grouped.setdefault(key, set())
        alias = "polybench_" + case["language"].lower() + "_" + case["id"].lower()
        entry.add(alias + "@" + key)
        entry.update(
            [
                case["image_reference"],
                *case.get("image_digests", []),
                "polybench_" + case["language"].lower() + "_" + case["id"].lower() + ":latest",
            ]
        )
    outcomes = []
    for key, owned in grouped.items():
        row = {"image_id": key, "status": "kept"}
        if key in set(keep):
            row["reason"] = "active working set"
        else:
            try:
                image = client.images.get(key)
            except Exception as exc:
                if getattr(exc, "status_code", None) != 404:
                    raise
                row["status"] = "already_absent"
                outcomes.append(row)
                emit(row)
                continue
            if image.id != key:
                raise HXError("Recorded cache image identity changed")
            references = set(image.tags) | set(image.attrs.get("RepoDigests", []) or [])
            if references - owned:
                row["reason"] = "unrelated references"
            elif client.containers.list(all=True, filters={"ancestor": key}):
                row["reason"] = "container uses image"
            else:
                row["references"] = sorted(references)
                for ref in sorted(references):
                    try:
                        client.images.remove(ref, force=False)
                    except Exception as exc:
                        if getattr(exc, "status_code", None) != 404:
                            raise
                try:
                    client.images.get(key)
                except Exception as exc:
                    if getattr(exc, "status_code", None) != 404:
                        raise
                else:
                    client.images.remove(key, force=False)
                row["status"] = "released"
        outcomes.append(row)
        emit(row)
    return outcomes
