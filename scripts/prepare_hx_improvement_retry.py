"""New runtime version after a retained, zero-token schema startup failure."""
import json
import shutil
from pathlib import Path

from benchmarks.polybench.prepare import sha, write


def prepare():
    old = Path(".hx/improvement-v1")
    new = Path(".hx/improvement-v2")
    if new.exists():
        raise RuntimeError("Version 2 already exists; do not overwrite it")
    failures = list((old / "experiments/search-history").glob("*/score.json"))
    assert len(failures) == 1
    failure = json.loads(failures[0].read_text())
    assert failure["observed_tokens"] == 0
    assert "invalid_json_schema" in failure["error"]
    write(old / "stop-after-case.json", {"reason": "Retained invalid output-schema failure; replaced by separately versioned development runtime."})
    (old / "stop-after-case").write_text("Superseded after retained schema failure", encoding="utf-8")
    new.mkdir()
    for name in ("dataset.csv", "storage.json", "selection.json", "images.json", "settings.toml"):
        shutil.copy2(old / name, new / name)
    for directory in ("public", "preflight"):
        shutil.copytree(old / directory, new / directory)
    (new / "experiments").mkdir()
    plan = json.loads((old / "plan.json").read_text())
    plan.update(version=2, scheduler_sha256=sha(Path("scripts/run_hx_improvement.py")),
                parent_failure={"score": str(failures[0]), "sha256": sha(failures[0]),
                    "reported_tokens": 0, "correction": "Required verification_commands in Codex structured output schema; added schema regression check."})
    # Retain the original improvement batch's start and three-hour envelope.
    write(new / "plan.json", plan)
    write(new / "plan.lock.json", {"sha256": sha(new / "plan.json")})
    print(json.dumps({"root": str(new), "retained_zero_token_failure": str(failures[0])}))


if __name__ == "__main__":
    prepare()
