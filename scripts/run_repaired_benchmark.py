"""Two untouched metadata-selected PolyBench cases after model-free delivery repairs."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from benchmarks.polybench.metrics import aggregate
from benchmarks.polybench.prepare import write
from scripts import run_paper_benchmark as batch


def prepare(root):
    def prior_scores():
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in Path(".hx").glob("*/experiments/*/*/score.json")}
    historical = prior_scores()
    used = {json.loads(Path(p).read_text()).get("case") for p in historical}
    # Only consumed tasks have been exposed. Defensive exposure check also
    # excludes identifiers independently recorded in diagnostic manifests.
    for path in Path(".hx").glob("*/exposure.json"):
        used.update(json.loads(path.read_text()).get("cases", []))
    selected = json.loads(Path(".hx/polybench-v1/selection.json").read_text())["cases"]
    cases = [next(c["id"] for c in selected if c["split"] == "evaluation"
                  and c["repo"] == repo and c["id"] not in used)
             for repo in ("langchain-ai/langchain", "mui/material-ui")]
    batch.CASES = cases
    batch.prior_scores = prior_scores
    batch.prepare(root)
    plan = json.loads((root / "batch-plan.json").read_text())
    plan["selection_rule"] = "First unused and unexposed evaluation case within LangChain and MUI in pinned metadata order; no outcome filtering."
    plan["scheduler_sha256"][str(Path(__file__).resolve())] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    plan["runtime_version"] = "delivery-and-public-test-repair@1"
    plan["diagnostic_provenance"] = [".hx/delivery-diagnostics-v1", ".hx/delivery-repair-validation-v1",
                                     ".hx/mocha-lifecycle-probe-v1"]
    write(root / "batch-plan.json", plan)
    write(root / "batch-plan.lock.json", {"sha256": hashlib.sha256((root / "batch-plan.json").read_bytes()).hexdigest()})
    print(json.dumps({"event": "batch.frozen", "cases": cases}), flush=True)


def main(root):
    os.environ["PATH"] = "/opt/hx-codex/node_modules/.bin:" + os.environ["PATH"]
    prepare(root)
    batch.run(root)
    result = json.loads((root / "results.json").read_text())
    plan = json.loads((root / "batch-plan.json").read_text())
    completed = json.loads((root / "complete.json").read_text())
    result["metrics"] = aggregate(result["rows"], completed["time"] - plan["started"])
    write(root / "results.json", result)
    print(json.dumps(result["metrics"]), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    main(parser.parse_args().root.resolve())
