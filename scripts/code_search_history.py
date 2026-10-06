"""Query immutable code-search candidates without a model call."""
import argparse
import difflib
import json
from pathlib import Path

from hx.code_search import seal, sha
from hx.models import HXError


def read(root: Path) -> dict:
    lock = json.loads((root / "archive-lock.json").read_text())
    actual = {n: h for n, h in seal(root).items() if n != "archive-lock.json"}
    if actual != lock["files"]:
        raise HXError("Archive inventory changed")
    for name, expected in lock["files"].items():
        path = root / name
        if Path(name).is_absolute() or ".." in Path(name).parts or path.is_symlink():
            raise HXError("Invalid archive path")
        if sha(path.read_bytes()) != expected:
            raise HXError("Archive changed: " + str(path))
    score_path = root / "candidate-search/score.json"
    outcome_path = root / "adoption.json"
    return {"root": str(root), "score": json.loads(score_path.read_text()) if score_path.exists() else None,
        "outcome": json.loads(outcome_path.read_text()) if outcome_path.exists() else
        json.loads((root / "failure.json").read_text())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", type=Path, nargs="+")
    parser.add_argument("--diff", action="store_true")
    args = parser.parse_args()
    for root in args.roots:
        row = read(root)
        if args.diff:
            before, after = root / "incumbent.py", root / "candidate.py"
            if before.exists() and after.exists():
                print("".join(difflib.unified_diff(before.read_text().splitlines(True),
                    after.read_text().splitlines(True), fromfile=str(before), tofile=str(after))))
        else:
            print(json.dumps(row))


if __name__ == "__main__":
    main()
