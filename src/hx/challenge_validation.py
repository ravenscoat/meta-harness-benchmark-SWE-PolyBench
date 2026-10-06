from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hx.challenge_eval import FullstackVerifier, grade
from hx.challenge_suite import ASSETS
from hx.config import canonical, load_task
from hx.git import clone, derive
from hx.models import Candidate, Settings
from hx.store import atomic_write


def validate_suite(manifest_path: Path, directory: Path, settings: Settings) -> dict:
    manifest = json.loads(manifest_path.read_text("utf-8"))
    directory = directory.resolve()
    rows = []
    for case in manifest["cases"]:
        task = load_task(Path(case["task"]))
        base = task.base_commit
        broken = Candidate(
            base_commit=base,
            input_commit=base,
            candidate_commit=base,
            changed_files=[],
            workspace=task.repo,
            diff_sha256=hashlib.sha256(b"").hexdigest(),
        )
        seeded = grade(broken, case["groups"], directory / case["id"] / "seeded", settings)
        repo = clone(Path(task.repo), directory / case["id"] / "gold", base)
        (repo / "backend/app.py").write_bytes((ASSETS / "backend_reference.py").read_bytes())
        (repo / "frontend/src/hooks.jsx").write_bytes(
            (ASSETS / "fullstack/src/hooks.jsx").read_bytes()
        )
        gold = derive(repo, base, base, task)
        accepted = grade(gold, case["groups"], directory / case["id"] / "reference", settings)
        visible = FullstackVerifier(settings).run(
            gold, task, directory / case["id"] / "visible", lambda: None, lambda *_: None
        )
        row = {
            "case": case["id"],
            "split": case["split"],
            "seeded": seeded,
            "reference": accepted,
            "visible": visible.passed,
            "valid": not seeded["passed"] and accepted["passed"] and visible.passed,
        }
        rows.append(row)
        print(
            json.dumps(
                {
                    "event": "validation",
                    "case": case["id"],
                    "valid": row["valid"],
                    "seeded": seeded["groups"],
                    "reference": accepted["groups"],
                    "visible": visible.passed,
                }
            ),
            flush=True,
        )
        atomic_write(
            directory / "validation.json",
            canonical(
                {
                    "valid": all(r["valid"] for r in rows),
                    "manifest": manifest["fingerprint"],
                    "rows": rows,
                }
            ),
        )
    result = {
        "valid": all(r["valid"] for r in rows),
        "manifest": manifest["fingerprint"],
        "rows": rows,
    }
    atomic_write(manifest_path.parent / "validation.json", canonical(result))
    return result
