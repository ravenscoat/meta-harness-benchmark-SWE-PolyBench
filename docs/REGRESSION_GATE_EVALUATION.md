# Fresh reproduction-gate evaluation

One SWE-PolyBench task completed under the frozen `polybench-public-tests@6`
runtime. The task is `huggingface__transformers-26164`, a Whisper generation bug.
Selection used the first unused Bug Fix in the original pinned evaluation
metadata order, excluding scored, exposed and interrupted coding identities.
Its environment validation predates this attempt; no previous coding worker
attempt exists for this case.

Experiment: `.hx/regression-gate-evaluation-v1`. The plan and source locks were
written before model work. All 85 indexed historical score files are sealed by
hash. No old campaign is resumed and no prior score is replaced.

The workflow uses one `gpt-6-luna` implementer, at most one public-feedback repair,
and no reviewer or Sol task calls. Existing settings use a 400,000 reported-token
turn-boundary target, 240-second worker attempts, 180-second verification checks
and a 1,200-second workflow deadline. The new experiment has one task slot, a
three-hour envelope and 600,000 reported tokens, with quota checks before model
calls. Token reporting can overshoot at a completed turn; it is not a hard
in-flight cap. No credits are purchased or redeemed.

The candidate must pass its public checks and show recognized behavioral failure
when those tests replay on original production code. Setup errors, hangs and
unknown output are insufficient reproduction evidence. The pinned official
scorer runs separately; private test patches, commands and logs do not enter
worker context.

Track official resolution separately from workflow readiness, public reproduction
classification, rejected patches, missing observations and infrastructure errors.
Report tokens, workflow seconds and total wall time. One selected task in a
previously used development repository cannot establish a general solve-rate
advantage or leaderboard rank. Red/green does not prove test relevance or
completeness.

The scheduler freshness/budget checks passed seven Windows and seven native
Linux tests, and Ruff passed. The reproduction mechanism's earlier validation
and limitations are in [REGRESSION_REPLAY.md](D:/projects/Harness/docs/REGRESSION_REPLAY.md).

## Completed outcome

**Official unresolved; public verification passed; HX marked ready.** The patch
applied, all required official tests were observed, and there were no grader
infrastructure or candidate-patch errors. This is an observed official failure,
not an infrastructure exclusion or a missing-test result. The original score is
sealed and must not be rerun or replaced.

| Measure | Observed |
| --- | --- |
| Coding model calls | One Luna implementation; zero revision/reviewer/Sol calls |
| Official resolution | Failed |
| Public verification / reproduction | Passed / passed |
| Reported tokens | 235,680 |
| Workflow time | 255.49 seconds |
| Total wall time | 740.14 seconds, including image preparation and scoring |
| Candidate | `e7fa93397d2901aa3f8afacdae58d1fa5a0b5624` |
| Run | `r-f4c9d9ac72fc47c2` |
| Score SHA256 | `93ccd7aebf14d7ba6dd14d3fda448e79a5956e4a98faf7a65c16e810ecc1a5f2` |

Both selected pytest commands passed on the candidate: the focused command
reported one pass; the broader command reported three passes and one skip.
These commands overlap, so their counts must not be added. Both base replays
failed the same newly added output-length assertion (`22 != 20`), establishing
one genuine red/green regression rather than two distinct regressions.

The deployed production patch changed one prompt-slicing expression. The public
issue also describes combined prompt/new-token overflow and explicitly requests
clear handling of that limit. The added regression covers one output-length
case, and the patch adds no explicit combined-limit validation. This is a
concrete completeness concern from public issue/source/test evidence; it is not
an identification of the exact private failing assertion. No private test
patches, commands or logs were read for this analysis.

The experiment demonstrates the new gate executing correctly on a fresh task,
and demonstrates that red/green alone is insufficient for task readiness. It
does not demonstrate improved official solve rate. A useful next repair is a
public contract-coverage gate that checks distinct requested behaviors and
boundary cases before accepting readiness. This case is now consumed
development evidence; a future fresh assessment requires another unused case
and a separately frozen runtime.

The controller exited. Process/container inventory found no active HX controller
or containers. The completion audit verifies all 85 indexed historical score
files, all 117 frozen source/input files, plan and scheduler hashes, the exact
candidate across implementation/verification/scoring, and one actual Luna call.
The audit helper initially failed to import project modules when launched
directly from its evidence directory. That helper-only startup error is
preserved in `audit-startup-error.json`; the self-contained correction audited
the existing result without repeating coding, public verification or grading.

Evidence:

- [Plan](D:/projects/Harness/.hx/regression-gate-evaluation-v1/batch-plan.json)
- [Results](D:/projects/Harness/.hx/regression-gate-evaluation-v1/results.json)
- [Phase](D:/projects/Harness/.hx/regression-gate-evaluation-v1/experiments/phase.json)
- [Completion audit](D:/projects/Harness/.hx/regression-gate-evaluation-v1/audit.json)
- [Sealed score](D:/projects/Harness/.hx/regression-gate-evaluation-v1/experiments/heldout-results/full-huggingface__transformers-26164-1/score.json)

Historical command used for this completed identity (do not restart it):

```powershell
wsl -d Ubuntu -u root --cd /mnt/d/projects/Harness -- /opt/hx-polybench-venv/bin/python -m scripts.run_regression_gate_benchmark .hx/regression-gate-evaluation-v1
```

Never prepare the same root again, silently rerun a scored task or extend its
envelope. The controller uses the shared single-evaluation lock. Frozen coding
source and scheduler dependencies must remain unchanged while it runs.

Subsequent development added the [version 7 coverage gate](CONTRACT_COVERAGE.md).
Its separate model-free diagnostic blocks this saved incomplete candidate for
missing public length-limit witnesses. This does not change the sealed official
failure or count as another benchmark attempt.
