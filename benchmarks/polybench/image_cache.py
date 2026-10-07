"""Bound cache growth by releasing only this campaign's recorded image tags."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from benchmarks.polybench.prepare import write
from hx.models import HXError

VERSION = "batch-image-lifecycle@3"


def retained_images(root, ledger):
    """Opt-in bounded retention, pinned as an input before batch preparation."""
    path = root / "image-retention.json"
    if not path.exists():
        return set()
    policy = json.loads(path.read_text())
    cases = policy.get("cases")
    selected = {c["id"] for c in json.loads((root / "selection.json").read_text())["cases"]}
    if (
        policy.get("version") != VERSION
        or not isinstance(cases, list)
        or not 1 <= len(cases) <= 3
        or any(not isinstance(c, str) for c in cases)
        or len(set(cases)) != len(cases)
        or set(cases) != selected
    ):
        raise HXError("Invalid bounded batch image retention policy")
    return {case["image_id"] for key, case in ledger.items() if key in cases}


def previous_image(root):
    path = root / "image-cache.json"
    return json.loads(path.read_text())["image_id"] if path.exists() else None


def remember_image(root, image):
    write(root / "image-cache.json", {"image_id": image.id})
    # Retain the previous image during the pull to reuse shared dependency
    # layers, then release its tags once the replacement image is available.
    trim_images(image.client, root, keep=[image.id])


def trim_images(client, root: Path, keep=()):
    ledger = root / "images.json"
    if not ledger.exists():
        return
    entries = json.loads(ledger.read_text())
    keep = set(keep) | retained_images(root, entries)
    from benchmarks.polybench.storage_lifecycle import release_images, retired_images

    release_images(
        client,
        [*entries.values(), *retired_images(root)],
        keep=keep,
        emit=lambda row: print(json.dumps({"event": "image.cache.cleanup", **row}), flush=True),
    )


def ensure_image(client, root: Path, case):
    trim_images(client, root, keep=[case["image_id"], previous_image(root)])
    try:
        image = client.images.get(case["image_id"])
    except Exception as exc:
        if getattr(exc, "status_code", None) != 404:
            raise
        from benchmarks.polybench.preflight import check_storage

        check_storage(root, client)
        references = [
            d
            for d in case["image_digests"]
            if re.fullmatch(r"ghcr\.io/[^\s@]+@sha256:[0-9a-f]{64}", d)
        ]
        if not references:
            raise HXError("validated image has no immutable registry digest") from exc
        print(json.dumps({"event": "image.cache.pull", "case": case["id"]}), flush=True)
        record = root / "image-pulls" / (case["id"] + "-" + str(time.time_ns()))
        record.mkdir(parents=True, exist_ok=False)
        receipt = {
            "version": VERSION,
            "reference": references[0],
            "expected_image_id": case["image_id"],
            "complete": False,
        }
        try:
            # The SDK model pull can conceal a streamed registry error behind
            # its final inspect of the requested reference. Preserve the stream
            # and inspect by the validated content ID, not a store-specific alias.
            with (record / "events.jsonl").open("w") as logs:
                for event in client.api.pull(references[0], stream=True, decode=True):
                    logs.write(json.dumps(event) + "\n")
                    logs.flush()
                    if event.get("error") or event.get("errorDetail"):
                        raise HXError(
                            "Pinned image pull failed: "
                            + str(event.get("error") or event["errorDetail"])[:2000]
                        )
            image = client.images.get(case["image_id"])
            if image.id != case["image_id"]:
                raise HXError("cached benchmark image identity changed")
            receipt.update(complete=True, observed_image_id=image.id)
        except Exception as error:
            receipt["error"] = str(error)
            raise
        finally:
            write(record / "receipt.json", receipt)
    if image.id != case["image_id"]:
        raise HXError("cached benchmark image identity changed")
    image.tag("polybench_" + case["language"].lower() + "_" + case["id"].lower())
    remember_image(root, image)
    return image
