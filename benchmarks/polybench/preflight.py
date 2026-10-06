from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path

from benchmarks.polybench.containers import extract_base
from benchmarks.polybench.grader import grade, register_vendor
from benchmarks.polybench.image_cache import previous_image, remember_image, trim_images
from benchmarks.polybench.prepare import read_rows, sha, write


def reference_valid(base, gold):
    # Follow the pinned upstream resolution rule. P2P observation coverage is
    # diagnostic: upstream requires no observed P2P failures, not full presence.
    return bool(base["with_logs"] and not base["resolved"] and gold["resolved"]
                and not base["infrastructure_error"] and not gold["infrastructure_error"])


def check_storage(root: Path, client):
    docker_root = Path(client.info()["DockerRootDir"])
    disks = [docker_root]
    if os.environ.get("WSL_DISTRO_NAME"):
        storage = json.loads((root / "storage.json").read_text(encoding="utf-8-sig"))
        if storage["distribution"] != os.environ["WSL_DISTRO_NAME"]:
            raise RuntimeError("Docker storage verification belongs to a different WSL distribution")
        if storage["docker_root"] != str(docker_root):
            raise RuntimeError("Docker data root changed; verify its physical storage again")
        disks.append(Path(storage["host_mount"]))
    for disk in disks:
        if not disk.exists():
            raise RuntimeError(f"Docker storage path is unavailable: {disk}")
        if shutil.disk_usage(disk).free < 40 * 1024**3:
            raise RuntimeError(f"Insufficient Docker storage headroom on {disk}: need 40 GiB free before pulling another image")


def preflight(root: Path, vendor: Path, split: str):
    import docker
    register_vendor(vendor)
    manifest = json.loads((root / "selection.json").read_text())
    if sha(root / "dataset.csv") != manifest["dataset_sha256"]:
        raise ValueError("pinned dataset changed")
    rows = {r["instance_id"]: r for r in read_rows(root / "dataset.csv")}
    client = docker.from_env(timeout=1800)
    images_file = root / "images.json"
    images = json.loads(images_file.read_text()) if images_file.exists() else {}

    def phase(stage, key, **extra):
        write(root / "experiments/phase.json", {"phase": "preflight", "split": split,
              "stage": stage, "case": key, "updated": time.time(), **extra})

    for case in manifest["cases"]:
        if case["split"] != split:
            continue
        key = case["id"]
        directory = root / "preflight" / key
        saved = directory / "validation.json"
        if saved.exists():
            print(json.dumps({"event": "setup.cached", "case": key,
                              "valid": json.loads(saved.read_text())["valid"]}), flush=True)
            continue
        directory.mkdir(parents=True, exist_ok=True)
        # Check the verified physical backing drive, not an assumed C: location.
        # A transient storage block must not invalidate a task.
        trim_images(client, root, keep=[previous_image(root)])
        check_storage(root, client)
        try:
            reference = "ghcr.io/timesler/swe-polybench.eval.x86_64." + key.lower() + ":v1.1"
            print(json.dumps({"event": "image.pull", "case": key, "reference": reference}), flush=True)
            phase("image_pull", key)
            updated = 0
            for event in client.api.pull(reference, stream=True, decode=True):
                if event.get("error"):
                    raise RuntimeError("Docker image pull failed: " + event["error"])
                if time.monotonic() - updated > 5:
                    phase("image_pull", key, status=event.get("status", ""),
                          progress=event.get("progressDetail", {}), layer=event.get("id", ""))
                    updated = time.monotonic()
            image = client.images.get(reference)
            alias = "polybench_" + case["language"].lower() + "_" + key.lower()
            image.tag(alias)
            case = {**case, "image_id": image.id, "image_reference": reference,
                    "image_digests": image.attrs.get("RepoDigests", [])}
            storage = json.loads((root / "storage.json").read_text(encoding="utf-8-sig"))
            execution_root = storage.get("execution_root")
            if execution_root:
                case["execution_root"] = execution_root
            repo = (Path(execution_root) / "bases" if execution_root else root / "bases") / key
            case["sanitized_base"] = extract_base(client, case, repo)
            case["repo_path"] = str(repo.resolve())
            images[key] = case
            write(images_file, images)
            remember_image(root, image)
            row = rows[key]
            phase("grade_base", key)
            print(json.dumps({"event": "grader.base", "case": key}), flush=True)
            # Unlike upstream's empty-prediction shortcut, this actually executes
            # hidden tests on the unchanged base in a fresh container.
            base = grade(row, "", directory / "base", client)
            print(json.dumps({"event": "grader.reference", "case": key}), flush=True)
            phase("grade_reference", key)
            gold = grade(row, row["patch"], directory / "reference", client)
            valid = reference_valid(base, gold)
            result = {"case": key, "valid": bool(valid), "base_resolved": base["resolved"],
                      "reference_resolved": gold["resolved"],
                      "reference_unobserved_tests": len(gold["expected_tests_unobserved"]),
                      "gate_version": "official-resolution@2",
                      "dataset_sha256": manifest["dataset_sha256"], "image_id": image.id}
        except Exception as exc:
            result = {"case": key, "valid": False, "infrastructure_error": f"{type(exc).__name__}: {exc}"}
        write(saved, result)
        phase("validated" if result["valid"] else "validation_failed", key)
        print(json.dumps({"event": "setup.finished", **result}), flush=True)
    return images


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--vendor", type=Path, required=True)
    parser.add_argument("--split", choices=["setup", "development", "evaluation"], default="setup")
    args = parser.parse_args()
    preflight(args.root.resolve(), args.vendor.resolve(), args.split)
