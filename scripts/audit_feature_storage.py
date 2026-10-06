"""Rescore frozen queue candidates using a standard-compatible Storage mock.

This never changes a campaign score, selection, policy, runtime or model trial.
"""

import argparse
import hashlib
import json
from pathlib import Path

from hx.challenge_eval import npm_command, prepare_frontend
from hx.config import canonical
from hx.git import clone, git
from hx.models import HXError
from hx.process import clean_env, execute
from hx.store import atomic_write, now


def compatible_program(source):
    old = "setItem:(k,v)=>m.set(k,v),m"
    if source.count(old) != 1:
        raise HXError("unexpected frozen storage mock; audit needs an explicit review")
    return source.replace(
        old,
        "setItem:(k,v)=>{m.set(String(k),String(v));},"
        "removeItem:k=>{m.delete(String(k));},clear:()=>m.clear(),"
        "key:i=>[...m.keys()][i]??null,get length(){return m.size;},m",
    )


def check(source, commit, directory, program):
    certificate = directory / "result.json"
    identity = {"commit": commit, "program_sha": hashlib.sha256(program.encode()).hexdigest()}
    if certificate.exists():
        saved = json.loads(certificate.read_text("utf-8"))
        if saved["identity"] != identity:
            raise HXError("audit identity mismatch")
        return saved
    repo = clone(source, directory / "workspace", commit)
    prepare_frontend(repo, directory / "dependencies")
    private = repo / "frontend/__hx_storage_audit.test.jsx"
    private.write_text(program, "utf-8")
    try:
        code, _, err = execute(
            npm_command("test", "--", "__hx_storage_audit.test.jsx", "--maxWorkers=1"),
            repo / "frontend",
            clean_env(),
            directory / "queue",
            90,
            lambda: None,
        )
        result = {"identity": identity, "passed": code == 0, "error": err[-2000:] if code else None}
    except HXError as error:
        result = {"identity": identity, "passed": False, "error": str(error)}
    atomic_write(certificate, canonical(result))
    return result


def audit(campaign, directory, references):
    frozen = campaign / "runtime-source-v7/benchmarks/advanced/private_queue.test.jsx"
    program = compatible_program(frozen.read_text("utf-8"))
    directory.mkdir(parents=True, exist_ok=True)
    atomic_write(directory / "compatible_queue.test.jsx", program.encode())
    validation = []
    for case in ("durable-outbox", "fullstack-sync", "sync-recovery"):
        for kind in ("reference", "seeded"):
            source = references / case / kind / "workspace"
            commit = git(source, "rev-parse", "HEAD")
            checked = check(source, commit, directory / "validation" / case / kind, program)
            validation.append({"case": case, "kind": kind, **checked})
    valid = all(r["passed"] == (r["kind"] == "reference") for r in validation)
    atomic_write(directory / "validation.json", canonical({"valid": valid, "rows": validation}))
    if not valid:
        raise HXError("compatible-storage evaluator failed reference validation")
    report_path = campaign / "report.json"
    report = json.loads(report_path.read_text("utf-8"))
    # A boundary stop can leave REPORT one row behind the already sealed score.
    known = {r["identity"]: r for r in report["rows"]}
    for split in ("search-history", "heldout-results"):
        for score in (campaign / split).glob("*/score.json"):
            row = json.loads(score.read_text("utf-8"))
            if row["identity"] in known and known[row["identity"]] != row:
                raise HXError("report disagrees with sealed score")
            known[row["identity"]] = row
    report["rows"] = list(known.values())
    audited = []
    corrected = json.loads(json.dumps(report))
    for row in corrected["rows"]:
        if "queue" not in row["acceptance"]["groups"]:
            continue
        name = f"{row['arm']}-{row['case']}-{row['repeat']}"
        source = campaign / "private-evaluation" / name / "workspace"
        commit = row["acceptance"]["candidate_commit"]
        result = check(source, commit, directory / "trials" / name, program)
        previous = row["task_success"]
        row["acceptance"]["groups"]["queue"] = result["passed"]
        row["acceptance"]["passed"] = all(row["acceptance"]["groups"].values())
        row["task_success"] = bool(row["acceptance"]["passed"] and row["visible_verified"])
        audited.append(
            {
                "trial": name,
                "original_success": previous,
                "corrected_success": row["task_success"],
                **result,
            }
        )
        print(
            json.dumps(
                {
                    "event": "storage_audit.finished",
                    "trial": name,
                    "original_success": previous,
                    "corrected_success": row["task_success"],
                }
            ),
            flush=True,
        )
    totals = {}
    for row in corrected["rows"]:
        key = f"{row['split']}/{row['arm']}"
        value = totals.setdefault(key, {"n": 0, "passed": 0, "tokens": 0, "seconds": 0})
        value["n"] += 1
        value["passed"] += row["task_success"]
        value["tokens"] += row["observed_tokens"]
        value["seconds"] += row["seconds"]
    for value in totals.values():
        value["rate"] = value["passed"] / value["n"]
    corrected["totals"] = totals
    corrected["evaluation_note"] = (
        "Post-selection compatible-Storage audit of the same frozen candidates; original scores remain unchanged. No model reruns or policy tuning."
    )
    atomic_write(directory / "report.json", canonical(corrected))
    selected = min(
        [
            (k.split("/")[1], v)
            for k, v in totals.items()
            if k.startswith("search/") and k != "search/single"
        ],
        key=lambda pair: (-pair[1]["passed"], pair[1]["tokens"]),
    )[0]
    summary = {
        "created_at": now(),
        "program_sha": hashlib.sha256(program.encode()).hexdigest(),
        "original_report_sha": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "validated": valid,
        "campaign_complete": (campaign / "complete.json").exists(),
        "original_selected": report["winner_selected_on_search"],
        "corrected_selected": selected,
        "rows": audited,
        "totals": totals,
        "note": corrected["evaluation_note"],
    }
    atomic_write(directory / "audit.json", canonical(summary))
    unchanged = all(r["original_success"] == r["corrected_success"] for r in audited)
    atomic_write(
        campaign / "evaluation-audit.json",
        canonical(
            {
                "normal_adoption_blocked": not (
                    summary["campaign_complete"]
                    and valid
                    and unchanged
                    and selected == summary["original_selected"]
                ),
                "reason": "Original v7 Storage mock omitted removeItem. Separate compatible-method rescoring retains all originals; adoption requires completed, validated, unchanged outcomes and unchanged selection.",
                "audit_directory": str(directory.resolve()),
                "audit_sha": hashlib.sha256((directory / "audit.json").read_bytes()).hexdigest(),
                "all_audited_outcomes_unchanged": unchanged,
            }
        ),
    )
    print(
        json.dumps(
            {
                "event": "storage_audit.complete",
                "validated": valid,
                "totals": totals,
                "corrected_selected": selected,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign", type=Path)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--references", type=Path, default=Path(".hx/sync-validation-v7"))
    args = parser.parse_args()
    audit(args.campaign, args.directory, args.references)
