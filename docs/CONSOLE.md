# Live HX console

Version 7 public bug checks also emit `public contract PASS/BLOCKED`, the number
of recorded obligations evidenced, and missing-coverage feedback. This status is
separate from official resolution; see [coverage limitations](CONTRACT_COVERAGE.md).

Run these commands from `D:\projects\Harness` in PowerShell.
The monitor reads SQLite events and saved campaign reports without starting models,
changing runs or approving candidates. No additional package is needed.

Public bug verification now shows an original-source replay. Base command exits
are labelled as awaiting classification, followed by reproduction `PASS` or
`BLOCKED`. A base assertion failure can be expected evidence; a timeout or setup
failure is not. The [reproduction gate](REGRESSION_REPLAY.md) is separate from
official task scoring and adds no model calls.

## Watch coding runs

```powershell
.\.venv\Scripts\python.exe scripts\hx_console.py --state-dir .hx\live
```

Leave this terminal open while starting a task in a second terminal using the
existing `hx run` command with your task specification. The monitor discovers new
runs automatically. Use `--run RUN_ID` to watch a particular saved run.

The display attributes implementation/revision and correctness/security review to
Luna, consolidation to Sol, and verification to the Python harness. Recorded model
IDs appear beside each step. Parallel reviewers appear together. Recent commands,
file changes, public worker messages, reported token usage and verification outcomes
come from real recorded events. Hidden reasoning and full command outputs are not
displayed. Output previews are bounded and terminal controls are removed.

## Watch a benchmark campaign

The delivery-repair evaluation allocated two fresh SWE-PolyBench tasks using one
Luna worker. LangChain 6765 passed; the React task never started because the quota
guard stopped before model work. Watch the saved activity with:

```powershell
.\.venv\Scripts\python.exe scripts\hx_console.py --campaign .hx\harness-repair-evaluation-v1\experiments
```

Its frozen runtime, diagnostic provenance and outcomes are described in
[the repair report](HARNESS_REPAIR_REPORT.md). The earlier campaigns below are
historical, separate experiments.

Current work focuses on the single LangChain task. The model-free reproduction
helper prints image preparation and original/repaired test outcomes directly to
the terminal. Commands and saved evidence are in
[One Task Approval](D:/projects/Harness/docs/ONE_TASK_APPROVAL.md). A public replay
does not create another benchmark score or start a model worker.

The follow-on single React attempt is now prepared under
`.hx/one-react-evaluation-v1`. It waits for ordinary quota, then runs only MUI
23229. Its new envelope and safeguards are documented in
[One React Task](D:/projects/Harness/docs/ONE_REACT_TASK.md). Watch it with:

```powershell
.\.venv\Scripts\python.exe scripts\hx_console.py --campaign .hx\one-react-evaluation-v1\experiments
```

Version 1's waiting controller disappeared before coding started. The separately
recorded continuation `.hx/one-react-evaluation-v2` is complete with an official
behavioral failure. Its saved traces use the same console command with the v2
path. A public runner repair was validated after scoring; the score stays failed.
See [React Failure Report](D:/projects/Harness/docs/REACT_FAILURE_REPORT.md).

For the public SWE-PolyBench subset, use:

```powershell
.\.venv\Scripts\python.exe scripts\hx_console.py --campaign .hx\polybench-v1\experiments
```

This campaign exports atomic JSON snapshots from native Linux SQLite state.
The Windows monitor reads those snapshots without opening the Linux databases.
Controller stages also show environment preparation when no model is running.

```powershell
.\.venv\Scripts\python.exe scripts\hx_console.py --campaign .hx\sync-experiments-v4
```

This adds per-arm scores, scored trial count, recorded trial/proposal tokens,
Sol's policy proposals and independent task scores. This campaign is complete,
so the current display shows saved results rather than live model work. For the
next campaign, point `--campaign` at its output directory; it can be started before
the directory exists. Unsealed proposer logs are explicitly marked as potentially
running or interrupted, rather than assumed live.

Print a single snapshot without keeping a monitor open:

```powershell
.\.venv\Scripts\python.exe scripts\hx_console.py --campaign .hx\sync-experiments-v4 --once
```

Refresh defaults to two seconds; `--interval 1` changes it. Interactive terminals
redraw the view; redirected output emits successive plain snapshots. Ctrl+C exits
only the monitor and leaves workers running. Cancel a worker through the existing
`hx cancel RUN_ID` command with the appropriate state directory.

The display reports stored state, not process liveness: an interrupted process can
leave a run marked running. The last state-update timestamp helps identify that
condition. Tokens update when a model turn reports usage, not continuously while
generating. Approval readiness is separate from independent acceptance. A campaign
snapshot may temporarily lag a newly sealed score until its report is updated.

Validation: four focused tests passed for role attribution, simultaneous reviewers,
read-only behavior, approval/score separation and terminal output sanitization;
Ruff passed for the monitor and its tests. The prior full harness suite passed 60
tests before this addition. The monitor was also exercised on final campaign data.
