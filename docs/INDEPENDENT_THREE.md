# Independent challenge verification and three-task evaluation

The user authorized improving HX and then testing exactly three benchmark tasks.
The completed root is `.hx/independent-three-v2`. It preserves all prior outcomes and
locks its plan, scheduler, source snapshot, public statements, dataset, images,
official scorer and settings before model work. Old schedulers remain stopped.

## Implemented changes

* A fresh Sol call inspects **original source and public issue only**, before an
  implementation exists. It may add at most five new conventional test files,
  with a combined patch under 24,000 bytes and at most two functional commands.
  Production changes and changes to existing tests are rejected by code.
* HX independently executes that test overlay on original production source.
  A recognized behavioral failure is required before implementation. Import,
  setup, empty-run and timeout errors do not qualify. Failure to establish a
  regression is retained as a workflow failure, not an official behavioral fail.
* Challenge tests are frozen in a separate artifact/workspace. The implementer
  cannot rewrite them through its candidate. A fresh replay overlays them onto
  the actual candidate in a separate workspace. File collisions, tampering and
  failed assertions block verification even when self-authored checks pass.
* Independent failures enter the existing bounded repair loop. On revision the
  worker gets the fixed public challenge patch and commands, plus focused failed
  assertions. A test-plan-only correction remains possible for its own plan;
  the independent challenge remains immutable.
* Each workflow targets 700,000 reported tokens with a 150,000-token repair
  reserve. A new initial implementation also requires 350,000 tokens of remaining
  headroom. Limits are checked at turn boundaries and may overshoot; interrupted
  unknown usage stops additional attempts. Model attempts remain 600 seconds,
  workflow deadline 2,400 seconds, verification timeout 180 seconds, one repair.
* Public contract extraction now handles emoji headings, skips image-only
  presentation lines, and avoids deriving numeric boundaries from markup or
  fenced examples. Genuine limit requirements still need distinct boundary
  witnesses. This is `public-contract-coverage@2`.

This is `blind-public-challenge@1` under `polybench-public-tests@11`. The same
`gpt-6.1-sol` model authors tests and implementation in separate fresh contexts.
This reduces direct patch-conditioned test selection but cannot eliminate
correlated blind spots. It is not an independent model, semantic proof, or a
guarantee of official correctness. Public checks and official grading remain
separate; delivery excludes conventional public test paths. Private evaluator
content and accepted solutions do not enter test-author or implementer context.

## Fixed tasks and scope

| Order | Original evaluation task | Public issue |
| --- | --- | --- |
| 1 | serverless/serverless 7374 | RC file rewrites reset tracking preferences and IDs |
| 2 | serverless/serverless 7277 | SNS redrive queue policy needs ARN and URL references |
| 3 | mui/material-ui 28190 | React Autocomplete freeSolo text disappears on blur |

Selection used original metadata order: two unscored Serverless bugs and the
first unscored MUI bug. Prior scored cases and unscored coding identities visible
in saved snapshots were excluded. Original environment gates remain valid.
No accepted solution or official outcome was used to rank these tasks. This is
three-task selected evaluation with no paired baseline, not a leaderboard score
or evidence of a causal improvement. The earlier reference-guided repairs remain
development diagnostics and are excluded.

Envelope: four hours from preparation, 2.6 million reported tokens including test
authoring, at most three task identities. Near 80% primary or 90% weekly account
usage, additional calls stop; no credits are purchased or reset credits redeemed.
Never duplicate a controller, rerun a scored/interrupted identity, substitute a
task, silently extend the envelope or change the frozen runtime from results.

## Validation and monitoring

73 combined native Linux workflow/protocol/regression checks passed; 19 Windows
scope/protocol/budget checks passed; three scheduler-scope tests passed on Windows;
Ruff passed. Integration checks demonstrate that a failed blind challenge blocks
green self-checks and that the original candidate remains unchanged by replay.
Initial test-fixture errors (short report and nested Git fixture) were corrected
before these successful runs; no model trial was involved.

Version 1 stopped before any model call because Settings previously capped repair
reserve at 80,000. Its plan/locks/stop/results/source snapshot are retained. The
bound is now 200,000 and the requested 150,000 reserve is validated before model
work. Version 2 records the startup evidence hashes and inherits version 1's
original envelope start and deadline; it does not restart the clock. No coding
identity was consumed in version 1. Follow-up validation: 25 Windows checks
passed; 34 Linux compatibility checks passed. An initial sandboxed Windows Git
shared-memory failure was retained and the permitted rerun passed.

Use `results.json`, `experiments/phase.json`, `quota.json`, `stop.json`, native
state descriptors and immutable console snapshots to inspect progress. Check the
real process inventory. The following was the launch command; this completed
root must not be restarted or its scored identities rerun:

```powershell
wsl -d Ubuntu -u root --cd /mnt/d/projects/Harness -- /opt/hx-polybench-venv/bin/python -m scripts.run_independent_three .hx/independent-three-v2
```

Report each original reproduction, frozen-test hash, candidate replay, repair,
usage, workflow status and aggregate official result separately. Missing official
observations, no accepted candidate, patch rejection and infrastructure failure
must not be presented as observed behavioral failures.

## Final result, verified 2026-10-04

A subsequent [official-code-inspired repair](META_HARNESS_OFFICIAL_ADAPTATION.md)
created development runtime @12 and separate zero-model public command probes.
It does not replace these outcomes or authorize restarting this completed root.

All three identities completed as workflow failures at `independent_base`, with
`Unsupported public test runner`. Test-author patches were retained, but none
established independent base reproduction, reached implementation, produced an
accepted implementation candidate, or reached official grading.

| Task | Reported tokens | Workflow seconds | Classification |
| --- | ---: | ---: | --- |
| Serverless 7374 | 209,313 | 152.62 | Unsupported public test command |
| Serverless 7277 | 215,624 | 163.41 | Unsupported public test command |
| MUI 28190 | 517,500 | 261.47 | Unsupported public test command |
| Total | 942,437 | 577.49 | Three harness failures before coding |

Usage is known for all three; there are no retained unscored coding runs. Batch
wall time was 1,200.47 seconds including its inherited startup clock. Workflow
time is not total download/grading time, and token counts are not monetary cost.
The score fields `official_resolved=false` and zero unobserved-test counts do not
establish observed official test failures: no official candidate was submitted.

Both Serverless authors selected `node node_modules/mocha/bin/mocha --reporter
json ...`; MUI selected Node-invoked cross-env followed by that Mocha entrypoint.
`public_test_argv` accepts Mocha executable/bin aliases, conventional package
test scripts, pytest, and `node --test`, but rejects these Node script entrypoints.
`regression_check` therefore failed in command normalization before independent
execution. Author guidance did not specify this exact entrypoint restriction,
and validation did not cover these model-produced command shapes. Existing
fixture checks passing did not establish real command compatibility. The test
authors' own execution is not independent base-reproduction evidence.

No live runtime repair, score replacement, or new attempt was made from these
results. The next version needs a shared author/replay runner contract, validated
before a full task is consumed; bounded command correction and narrow known
entrypoint support should be tested with these exact public argv fixtures and
actual offline containers. That work must retain this batch as failed evidence
and use new experiment identities for any later model trials.

`audit.json` seals all three new score hashes. A final validation independently
verified plan, scheduler, frozen source/input, parent startup and all 98 historical
score hashes; all matched. Ubuntu process inventory and Docker inventory showed
no active controller or worker container. Follow-up monitoring is stopped because
the three authorized identities are spent. These results establish neither a
solve-rate gain nor leaderboard performance.
