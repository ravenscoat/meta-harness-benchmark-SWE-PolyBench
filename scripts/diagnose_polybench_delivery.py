"""Model-free diagnostics on two consumed cases; private evidence stays in this root."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from benchmarks.polybench.prepare import read_rows, write

CASES = ["langchain-ai__langchain-4579", "mui__material-ui-18683"]


def run(argv, cwd):
    result = subprocess.run(argv, cwd=cwd, capture_output=True, timeout=60)
    return {"returncode": result.returncode,
            "stdout": result.stdout.decode(errors="replace"),
            "stderr": result.stderr.decode(errors="replace")}


def main(root):
    root.mkdir(parents=True, exist_ok=False)
    old = Path(".hx/paper-polybench-v1")
    images = json.loads((old / "images.json").read_text())
    rows = {r["instance_id"]: r for r in read_rows(old / "dataset.csv")}
    original_scores = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in Path(".hx").glob("*/experiments/*/*/score.json")}
    write(root / "exposure.json", {"cases": CASES,
        "reason": "User-authorized reference/test patch inspection of consumed tasks.",
        "classification": "Development diagnostics; never a fresh evaluation or score replacement.",
        "worker_access": False, "original_score_sha256": original_scores})
    for key in CASES:
        row = rows[key]
        trial = old / "experiments/heldout-results" / ("full-" + key + "-1")
        prediction = json.loads((trial / "prediction.json").read_text())["model_patch"]
        folder = root / key
        folder.mkdir()
        # Explicitly private files. No prompts or proposal runner reads this root.
        for name, content in [("reference.patch", row["patch"]),
                              ("test.patch", row["test_patch"]), ("candidate.patch", prediction)]:
            (folder / name).write_bytes(content.encode())
        results = {}
        with tempfile.TemporaryDirectory(prefix="delivery-", dir="/opt/hx-polybench-runtime/v1/infra-checks") as tmp:
            repo = Path(tmp) / "repo"
            subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", images[key]["repo_path"], str(repo)], check=True)
            base = images[key]["sanitized_base"]
            for label, patch in [("candidate_on_base", "candidate.patch"),
                                 ("candidate_after_tests", "candidate.patch"),
                                 ("reference_after_tests", "reference.patch")]:
                run(["git", "reset", "--hard", base], repo)
                run(["git", "clean", "-fd"], repo)
                if label != "candidate_on_base":
                    results[label + "_test_setup"] = run(["git", "apply", "--ignore-whitespace", str((folder / "test.patch").resolve())], repo)
                results[label] = run(["git", "apply", "--check", "--ignore-whitespace", str((folder / patch).resolve())], repo)
                if label == "candidate_after_tests":
                    results[label + "_official_git"] = run(["git", "apply", "-v", "--ignore-whitespace", "--reject", str((folder / patch).resolve())], repo)
                    results[label + "_official_fallback"] = run(["patch", "--batch", "--fuzz=5", "-p1", "-f", "-i", str((folder / patch).resolve())], repo)
        write(folder / "application.json", results)
        print(json.dumps({"case": key, "results": results}), flush=True)
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in original_scores.items())
    write(root / "complete.json", {"original_scores_unchanged": len(original_scores), "model_calls": 0})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    main(parser.parse_args().root.resolve())
