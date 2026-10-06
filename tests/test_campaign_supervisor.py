import json
import sys

from scripts.run_campaign import launch


def test_quota_stops_controller_before_further_scheduling(tmp_path):
    marker = tmp_path / "unavailable_trial_started"
    program = (
        "import json,time;from pathlib import Path;"
        "print(json.dumps({'event':'case.finished','error':'Codex turn failed: usage limit reached'}),flush=True);"
        "time.sleep(2);"
        f"Path({str(marker)!r}).write_text('incorrectly scheduled')"
    )
    result = launch([sys.executable, "-c", program], tmp_path, timeout=10)
    assert result["status"] == "quota_stop"
    assert not marker.exists()
    assert (
        json.loads(
            (
                tmp_path
                / "controller-attempts"
                / next((tmp_path / "controller-attempts").iterdir()).name
                / "supervisor.json"
            ).read_text()
        )["status"]
        == "quota_stop"
    )


def test_functional_failure_does_not_stop_campaign(tmp_path):
    program = "import json;print(json.dumps({'event':'case.finished','error':'process timed out after 240s'}));print('next trial')"
    result = launch([sys.executable, "-c", program], tmp_path, timeout=10)
    assert result["status"] == "completed"
    assert (
        "next trial"
        in (
            tmp_path
            / "controller-attempts"
            / next((tmp_path / "controller-attempts").iterdir()).name
            / "stdout.txt"
        ).read_text()
    )


def test_operator_stop_waits_for_scored_boundary(tmp_path):
    (tmp_path / "stop-after-case").write_text("wait for fresh quota")
    program = "import json,time;print(json.dumps({'event':'case.finished','error':None}),flush=True);time.sleep(2);print('next trial')"
    result = launch([sys.executable, "-c", program], tmp_path, timeout=10)
    assert result["status"] == "operator_stop"
    assert (
        "next trial"
        not in (next((tmp_path / "controller-attempts").iterdir()) / "stdout.txt").read_text()
    )
