"""Model-free replay of the failed Svelte worker environment and its repair."""
import argparse
import json
import time
from pathlib import Path

from benchmarks.polybench import containers, runner
from benchmarks.polybench.prepare import sha, write
from benchmarks.polybench.test_environment import docker_environment
from benchmarks.polybench.worker_environment import build_check, prepare_generated
from hx.check_execution import command_check
from hx.process import clean_env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    original = Path(".hx/sol-coverage-evaluation-v1")
    _, images, client, settings = runner.resources(original)
    case = images["sveltejs__svelte-728"]
    workspace = Path(case["repo_path"])
    historical = {str(p.resolve()): sha(p) for p in Path(".hx").glob("*/experiments/*/*/score.json")}
    container, workdir = containers.create(client, case, runner.BINARY, offline=True)
    events = []
    def emit(kind, data):
        events.append({"kind": kind, "data": data})
        write(root / "events.json", events)
    saved = containers.prepare_generated
    started = time.monotonic()
    report = {"model_calls": 0, "case": case["id"], "user": "1000:1000", "network": "none"}
    try:
        # Reproduce the old population behavior in this disposable container only.
        containers.prepare_generated = lambda *a: None
        containers.populate(container, workdir, workspace, case)
        containers.prepare_generated = saved
        before = build_check(container, workdir, workspace, case, root / "before",
            settings, lambda: None, emit)
        report["before"] = before.model_dump()
        prepare_generated(container, workdir, workspace, case)
        after = build_check(container, workdir, workspace, case, root / "after",
            settings, lambda: None, emit)
        report["after"] = after.model_dump()
        if not after.passed:
            raise RuntimeError("Repaired worker build still fails")
        test = command_check("public_baseline_smoke", ["docker", "exec", "-u", "1000:1000",
            *docker_environment(), "-w", workdir, container.id,
            "./node_modules/.bin/mocha", "--opts", "mocha.opts", "--grep", "each-block-keyed",
            "--reporter", "json", "--exit"], workspace, clean_env(), root / "baseline-smoke",
            settings, lambda: None, emit)
        report["smoke"] = test.model_dump()
        clean = containers.command(container, ["git", "status", "--porcelain"], workdir).strip() == b""
        report["tracked_source_clean"] = clean
        # Controlled public-source mutation verifies build provenance, not task resolution.
        marker = "HX_PUBLIC_BUILD_PROVENANCE_PROBE"
        containers.command(container, ["node", "-e",
            "require('fs').appendFileSync('src/shared/utils.js', '\\nexport function hxEnvironmentProbe() { return \\\"" + marker + "\\\"; }\\n');"],
            workdir, "1000:1000")
        rebuilt = build_check(container, workdir, workspace, case, root / "source-mutation",
            settings, lambda: None, emit)
        artifact = containers.read_file(container, workdir + "/shared.js")
        report["source_change_rebuilt"] = rebuilt.passed and marker.encode() in artifact
        report["historical_scores_unchanged"] = all(sha(Path(p)) == expected for p, expected in historical.items())
        report["historical_score_count"] = len(historical)
        report["passed"] = (not before.passed and after.passed and test.passed and clean
            and report["source_change_rebuilt"] and report["historical_scores_unchanged"])
        if not report["passed"]:
            raise RuntimeError("Worker environment diagnostic did not meet all criteria")
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        containers.prepare_generated = saved
        container.remove(force=True)
        report["seconds"] = time.monotonic() - started
        write(root / "report.json", report)
        print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
