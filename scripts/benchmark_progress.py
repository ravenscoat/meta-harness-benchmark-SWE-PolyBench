import argparse
import json
import sqlite3
from pathlib import Path


def progress(root):
    output = {
        "directory": str(root.resolve()),
        "complete": (root / "complete.json").exists(),
        "active": [],
    }
    report_path = root / "report.json"
    if report_path.exists():
        report = json.loads(report_path.read_text("utf-8"))
        output.update(
            completed_trials=len(report["rows"]),
            totals=report["totals"],
            selected=report["winner_selected_on_search"],
        )
    for split in ("search-history", "heldout-results"):
        for db in (root / split).glob("*/state/state.sqlite3"):
            with sqlite3.connect("file:" + db.as_posix() + "?mode=ro", uri=True) as connection:
                for (body,) in connection.execute("SELECT body FROM runs"):
                    run = json.loads(body)
                    if run["status"] == "running":
                        steps = [
                            {"id": i, "status": s}
                            for i, s in connection.execute(
                                "SELECT id,status FROM steps WHERE run_id=?", (run["id"],)
                            )
                        ]
                        output["active"].append(
                            {"trial": db.parents[1].name, "run": run["id"], "steps": steps}
                        )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directories", nargs="+", type=Path)
    print(json.dumps([progress(p) for p in parser.parse_args().directories], indent=2))
