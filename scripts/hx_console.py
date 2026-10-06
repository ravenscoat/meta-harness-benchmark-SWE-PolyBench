"""Read-only terminal monitor for HX runs and benchmark campaigns."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path


def clean(value: object, limit: int = 180) -> str:
    # Worker output is untrusted; never forward terminal control sequences.
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(value))
    text = "".join(c for c in text if c.isprintable() or c in "\n\t")
    return " ".join(text.split())[:limit]


def actor(step: str, model: str = "") -> str:
    if step.startswith("consolidate"):
        return f"Sol / consolidation ({model or 'model not recorded'})"
    if step.startswith(("implement", "revision", "revise")):
        return f"Luna / implementation ({model or 'model not recorded'})"
    if step.startswith(("correctness", "security")):
        return f"Luna / {step.split('_')[0]} review ({model or 'model not recorded'})"
    return "Harness / verification" if step.startswith("verify") else "Harness"


def detail(kind: str, data: dict) -> str:
    if kind == "worker.event":
        item = data.get("item") or {}
        category = item.get("type", data.get("type", "event"))
        if category == "command_execution":
            command = re.sub(r'^"[^"\n]*[\\/]([^"\\/]+)"', r'\1', str(item.get('command', '')))
            code = item.get("exit_code")
            status = f"FAILED (exit {code})" if code not in (None, 0) else item.get("status", "")
            return f"command {status}: {clean(command)}"
        if category == "file_change":
            return "files: " + clean(", ".join(c.get("path", "") for c in item.get("changes", [])))
        if category == "agent_message":
            return "message: " + clean(item.get("text", ""))
        if category == "error":
            return "error: " + clean(data.get("message") or data.get("error") or "worker error")
        # No hidden reasoning content or full command output in the display.
        return clean(category)
    if kind == "verification.check":
        if str(data.get("name", "")).startswith("base_test_"):
            outcome = "exit 0" if data.get("passed") else "nonzero/timeout"
            return f"base replay {outcome}; awaiting reproduction classification"
        return f"{'PASS' if data.get('passed') else 'FAIL'} {clean(data.get('name', 'check'))}"
    if kind == "verification.regression.started":
        return "checking original production code against public regressions"
    if kind == "verification.regression":
        categories = [c.get("category", "unknown") for c in data.get("commands", [])]
        return f"reproduction {'PASS' if data.get('passed') else 'BLOCKED'} / {clean(data.get('category', 'unknown'))}: {clean(', '.join(categories))}"
    if kind == "verification.started":
        return f"running {clean(data.get('name', 'check'))} / limit {data.get('timeout_seconds', '?')}s"
    if kind == "verification.contract_coverage":
        return (f"public contract {'PASS' if data.get('passed') else 'BLOCKED'} / "
                f"{data.get('covered', 0)}/{data.get('required', '?')} obligations evidenced / "
                + clean(data.get('problems', [])))
    if kind == "verification.timeout":
        return f"TIMEOUT {clean(data.get('name', 'check'))}; diagnostics sent to repair feedback"
    if kind == "revision.planned":
        return f"revision {data.get('revision')}: checks {clean(data.get('failed_checks', []))}; blockers {clean(data.get('blocking_sources', []))}"
    if kind == "revision.skipped":
        return "human attention required: " + clean(data.get("reason", "inspection gap"))
    if kind == "candidate.test_plan_revised":
        return "test plan revised / exact source commit preserved / independent verification next"
    if kind == "consolidation.skipped":
        return "Sol call saved: no review findings to group"
    if kind == "worker.usage":
        return f"reported tokens: {data.get('tokens', 0):,}"
    if kind == "worker.instantiated":
        return f"session started / sandbox {clean(data.get('sandbox', 'unknown'))}"
    return clean(data.get("error") or kind)


def read_runs(db: Path, run_id: str | None = None) -> list[dict]:
    snapshot = db.parent / "console-snapshot.json"
    if (db.parent / "native-state.json").exists():
        for attempt in range(5):
            try:
                versions = sorted(db.parent.glob("console-snapshot.*.json"))
                if versions:
                    snapshot = versions[-1]
                entries = json.loads(snapshot.read_text("utf-8")) if snapshot.exists() else []
                break
            except (PermissionError, FileNotFoundError):
                if attempt == 4:
                    raise
                time.sleep(0.01)
        return [e for e in entries if not run_id or e["run"]["id"] == run_id]
    if not db.exists():
        return []
    with sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True, timeout=1) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("BEGIN")
        runs = conn.execute("SELECT body FROM runs ORDER BY rowid DESC").fetchall()
        output = []
        for row in runs:
            run = json.loads(row[0])
            if run_id and run["id"] != run_id:
                continue
            steps = [dict(r) for r in conn.execute(
                "SELECT id,status FROM steps WHERE run_id=? ORDER BY rowid", (run["id"],)
            )]
            models = {}
            for event in conn.execute(
                "SELECT step_id,data FROM events WHERE run_id=? AND type='worker.instantiated' ORDER BY seq",
                (run["id"],),
            ):
                models[event[0]] = json.loads(event[1]).get("model", "")
            events = [dict(e) for e in conn.execute(
                "SELECT seq,ts,type,step_id,data FROM events WHERE run_id=? ORDER BY seq DESC LIMIT 8",
                (run["id"],),
            )][::-1]
            output.append({"run": run, "steps": steps, "models": models, "events": events})
        return output


def frame(state_dir: Path, campaign: Path | None = None, run_id: str | None = None,
          overnight: Path | None = None) -> str:
    lines = ["HX  |  Luna workers + Sol judgment", "=" * 72]
    if overnight:
        registry = overnight / "experiments.json"
        if registry.exists():
            entries = json.loads(registry.read_text())["roots"]
            if entries:
                campaign = Path(entries[-1]["root"]) / "experiments"
                lines.append("Overnight stage: " + clean(entries[-1]["stage"]))
        usage_file = overnight / "ledger.json"
        if usage_file.exists():
            usage = json.loads(usage_file.read_text())
            lines.append(f"Additional reported tokens: {usage['additional_reported_tokens']:,} / {usage['max_additional_reported_tokens']:,}")
        quota_file = overnight / "quota.json"
        if quota_file.exists():
            quota = json.loads(quota_file.read_text())
            lines.append(f"Last account check: primary {quota['primary']['usedPercent']}% / weekly {quota['secondary']['usedPercent']}% used")
    databases = [state_dir / "state.sqlite3"]
    scores = {}
    if campaign:
        phase_path = campaign / "phase.json"
        if phase_path.exists():
            phase = json.loads(phase_path.read_text("utf-8"))
            lines.append(f"Controller: {clean(phase.get('phase', ''))}/{clean(phase.get('split', ''))} | {clean(phase.get('stage', ''))} | {clean(phase.get('case', ''))}")
            if phase.get("status"):
                lines.append("Docker: " + clean(phase["status"]) + " " + clean(phase.get("progress", {})))
        databases = sorted(campaign.glob("search-history/*/state/state.sqlite3"))
        databases += sorted(campaign.glob("heldout-results/*/state/state.sqlite3"))
        databases += sorted(campaign.glob("setup-results/*/state/state.sqlite3"))
        databases += sorted(campaign.glob("proposals/state/state.sqlite3"))
        for descriptor in campaign.glob("**/state/native-state.json"):
            db = descriptor.parent / "state.sqlite3"
            if db not in databases:
                databases.append(db)
        report_path = campaign / "report.json"
        if report_path.exists():
            report = json.loads(report_path.read_text("utf-8"))
            rows = report.get("rows", [])
            scores = {r.get("run_id"): r for r in rows if r.get("run_id")}
            progress = f"{len(rows)}/{report['planned_trials']}" if report.get("planned_trials") else str(len(rows))
            lines += [f"Campaign: {clean(campaign.name)} | {'COMPLETE' if (campaign / 'complete.json').exists() else 'NOT COMPLETE'}",
                      f"Scored: {progress} | Official resolved: {sum(bool(r.get('official_resolved', r.get('task_success'))) for r in rows)} | Selected: {clean(report.get('winner_selected_on_search', 'pending'))}"]
            tokens = sum(r.get("observed_tokens", 0) for r in rows) + report.get("proposer_tokens", 0)
            lines.append(f"Reported tokens (scored trials + proposals): {tokens:,}")
            for arm, total in report.get("totals", {}).items():
                lines.append(f"  {clean(arm):26} solved {total['passed']}/{total['n']}")
            for row in rows[-3:]:
                groups = row.get("acceptance", {}).get("groups", {})
                lines.append(f"  Last score: {clean(row.get('arm', '?'))}/{clean(row.get('case', '?'))} #{row.get('repeat', '?')} {'PASS' if row.get('task_success') else 'FAIL'} / " + clean(", ".join(f"{name}={'PASS' if passed else 'FAIL'}" for name, passed in groups.items())))
        for proposal in sorted((campaign / "proposals").glob("*")):
            if not proposal.is_dir():
                continue
            policy = proposal / "policy.json"
            if policy.exists():
                value = json.loads(policy.read_text("utf-8"))
                lines.append(f"Sol / policy {clean(proposal.name)}: COMPLETE / {clean(value.get('name', 'policy'))}")
            elif (proposal / "stdout.txt").exists():
                lines.append(f"Sol / policy {clean(proposal.name)}: unsealed log; may be running or interrupted")
                with (proposal / "stdout.txt").open("rb") as stream:
                    stream.seek(0, 2)
                    stream.seek(max(0, stream.tell() - 65536))
                    tail = stream.read().decode("utf-8", errors="replace")
                for raw in reversed(tail.splitlines()):
                    try:
                        event = json.loads(raw)
                    except ValueError:
                        continue
                    if isinstance(event, dict):
                        lines.append("  Last proposer event: " + detail("worker.event", event))
                        break
        policy_path = campaign / "proposals/policy.json"
        if policy_path.exists():
            policy = json.loads(policy_path.read_text("utf-8"))
            lines.append("Sol / policy: COMPLETE / " + clean(policy.get("name", "policy")))
    entries = []
    for db in databases:
        try:
            entries.extend((db, r) for r in read_runs(db, run_id))
        except (sqlite3.Error, ValueError, OSError) as exc:
            lines.append(f"Waiting for readable state: {clean(db)} / {clean(exc)}")
    entries.sort(key=lambda pair: pair[1]["run"].get("updated_at", ""), reverse=True)
    active = [pair for pair in entries if pair[1]["run"]["status"] in {"running", "pending"}]
    shown = active or entries[:1]
    if not shown:
        lines.append("Waiting for a run. Monitor does not start workers.")
    elif not active:
        lines.append("No run recorded as active. Showing the latest saved run.")
    for db, entry in shown[:4]:
        run = entry["run"]
        lines += ["-" * 72, f"Task: {clean(run['task']['id'])} | {clean(run['status'])}",
                  f"Run: {clean(run['id'])} | Tokens: {run.get('observed_tokens', 0):,}",
                  f"Last state update: {clean(run.get('updated_at', ''))}"]
        if entry["events"]:
            lines.append("Latest event: " + clean(entry["events"][-1]["ts"]))
        if campaign:
            lines.append(f"Trial: {clean(db.parents[1].name)}")
        if run["id"] in scores:
            score = scores[run["id"]]
            lines.append(f"Independent task score: {'PASS' if score.get('task_success') else 'FAIL'} (separate from handoff status)")
        for step in entry["steps"]:
            lines.append(f"  {clean(step['status']):10} {clean(step['id']):20} {actor(step['id'], entry['models'].get(step['id'], ''))}")
        lines.append("Recent recorded activity:")
        for event in entry["events"]:
            data = json.loads(event["data"])
            step = event["step_id"] or ""
            lines.append(f"  {clean(event['ts'][11:19])} {actor(step, entry['models'].get(step, ''))}: {detail(event['type'], data)}")
        if run.get("error"):
            lines.append("Error: " + clean(run["error"]))
    lines += ["-" * 72, "Recorded state, not a process heartbeat. Tokens update when a turn reports usage.",
              "Ctrl+C closes this monitor; workers keep running. No approvals are issued."]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path(".hx/live"))
    parser.add_argument("--campaign", type=Path)
    parser.add_argument("--overnight", type=Path, help="follow the active overnight stage and budget ledger")
    parser.add_argument("--run", dest="run_id")
    parser.add_argument("--once", action="store_true", help="print one saved-state snapshot")
    parser.add_argument("--interval", type=float, default=2)
    args = parser.parse_args(argv)
    if args.interval < 0.25:
        parser.error("--interval must be at least 0.25 seconds")
    try:
        while True:
            try:
                output = frame(args.state_dir, args.campaign, args.run_id, args.overnight)
            except (OSError, ValueError) as exc:
                output = "HX | Waiting for readable report: " + clean(exc)
            if sys.stdout.isatty() and not args.once:
                print("\x1b[2J\x1b[H", end="")
            print(output, flush=True)
            if args.once:
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
