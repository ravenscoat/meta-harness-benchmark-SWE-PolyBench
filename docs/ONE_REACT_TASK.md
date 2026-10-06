# Next task: MUI 23229

## Latest verified state

The consumed case has since been repaired in a separate reference-informed
development diagnostic: all 99 official observed tests passed, with no missing
required tests or patch/grader errors. Five new public regressions fail the saved
Luna patch; the final public suite passes 104 tests with two pending. No coding
worker model calls were used for this diagnostic. The original benchmark attempt
remains a failure. See [React Contract Repair](D:/projects/Harness/docs/REACT_CONTRACT_REPAIR.md).

The continuation completed. MUI 23229 did not resolve officially: the patch applied, all required tests were observed, and there were no grader infrastructure errors. A public Mocha timeout exposed an absolute-path command-normalization bug; that mechanism was repaired after scoring and replayed without replacing the original result. See [React Failure Report](D:/projects/Harness/docs/REACT_FAILURE_REPORT.md). No coding controller remains active for this completed task. The remaining paragraphs preserve the earlier scheduling history.

At 2026-10-03 14:13 UTC / 19:13 Pakistan time, the first queued controller was absent and had never started a coding attempt. Its saved phase remained quota waiting, with zero tokens and zero scores; no exit record exists, so the exact exit cause is unknown. The automatic-start expectation did not hold. This scheduling failure is preserved in [scheduling-failure.json](D:/projects/Harness/.hx/one-react-evaluation-v1/scheduling-failure.json); it is not a coding score. The old batch window is not extended.

Ordinary quota is now available (1% primary, 34% weekly at the check). The same still-unattempted React task continues under a separately frozen three-hour plan in `.hx/one-react-evaluation-v2`. Runtime, settings, image, scorer, one-worker policy and budgets remain unchanged. This run is monitored during the active turn rather than left waiting unattended. Earlier preparation and waiting details below describe version 1.

The user authorized one fresh React benchmark attempt after the confirmed LangChain 6765 pass. Exact task: `mui__material-ui-23229`, from the original pinned SWE-PolyBench evaluation selection. The earlier two-task campaign never started this React task; its LangChain score remains sealed.

## Prepared attempt

- New evidence root: [one-react-evaluation-v1](D:/projects/Harness/.hx/one-react-evaluation-v1/batch-plan.json).
- Runtime: `delivery-and-public-test-repair@1`, unchanged from the successful LangChain attempt. Source, prompts, dataset, image, settings and scheduler are locked before model work.
- One `gpt-6-luna` worker; no reviewer or Sol task-level calls. At most one repair based on independently replayed public checks.
- Existing trial target: 400,000 reported tokens; batch guard: 600,000 reported tokens, retaining turn-boundary overshoots honestly. No new call starts with less than 150,000 batch-token headroom.
- Worker timeout 240 seconds, public-check timeout 180 seconds, workflow timeout 1,200 seconds.
- New three-hour envelope starts at preparation and includes quota waiting. It does not extend any previous campaign.
- No purchases, reset-credit redemption, case substitutions or silent retries of scored/interrupted identities.

## Quota waiting

Initial account check: primary usage 97%, weekly usage 33%. The controller is running and waiting; zero coding trials and zero model tokens have been recorded for this task. Earliest start is 2026-10-03 12:11:11 UTC / 17:11:11 Pakistan time, ten seconds after the expected natural reset. It reads actual quota again before starting and before every model call, requiring ordinary usage plus primary below 80% and weekly below 90%. A reset time is not permission to ignore the actual usage check.

The controller owns the wait, so no manual restart is needed while it remains active. Its current process identity and phases are saved in [controller.json](D:/projects/Harness/.hx/one-react-evaluation-v1/controller.json) and [phase.json](D:/projects/Harness/.hx/one-react-evaluation-v1/experiments/phase.json). Do not duplicate it. Unavailable quota eventually stops at the fixed deadline rather than extending the plan.

## Evidence and interpretation

The controller saves actor traces, worker commands, exact candidate and delivered production patch, independent public verification, official outcome, usage, elapsed workflow time and total wall time. Private grader content stays outside model context. Total wall time includes waiting; workflow time does not.

[results.json](D:/projects/Harness/.hx/one-react-evaluation-v1/results.json) and [REPORT.md](D:/projects/Harness/.hx/one-react-evaluation-v1/experiments/REPORT.md) report one planned task. Public readiness, official resolution, missing observations, patch rejection, absent candidates and grading infrastructure errors remain separate. This single known-repository task cannot establish a causal harness gain or a leaderboard score.

The new scheduler's deadline/headroom guards and refusal to replace scored, exposed or interrupted tasks passed 12 relevant Windows checks and the same 12 native Linux checks. Ruff passed. The queued task itself is not counted as a pass or failure before it runs.

Watch saved/current activity in PowerShell from `D:\projects\Harness`:

```powershell
.\.venv\Scripts\python.exe scripts\hx_console.py --campaign .hx\one-react-evaluation-v1\experiments
```

If the controller has exited, inspect its stop, results and score locks before taking action. The only relevant controller command is:

```powershell
wsl -d Ubuntu -u root --cd /mnt/d/projects/Harness -- /opt/hx-polybench-venv/bin/python -m scripts.run_one_react_benchmark .hx/one-react-evaluation-v1
```

This is not permission to rerun an interrupted or scored task. The scheduler retains such identities and stops instead.
