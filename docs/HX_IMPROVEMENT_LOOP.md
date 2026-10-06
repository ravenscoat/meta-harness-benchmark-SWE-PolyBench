# HX improvement loop

On 3 October 2026 (Asia/Karachi), the user ended the public comparison campaign
and authorized failure-driven harness development. The controller stopped during
image preparation before another worker started. The 27 scored trials remain in
`.hx/polybench-v1`; termination records their hashes. The 51-trial campaign is
incomplete. Its locks, fixed Sol policy, source snapshots and raw evidence remain
unchanged. The live checkout is now a new development version; it must not resume
the old frozen scheduler.

## Evidence motivating this change

Initial development: current HX officially resolved 4/10 tasks, as did Luna alone.
HX consumed 5,346,467 reported tokens and 2,629.14 workflow seconds; Luna consumed
2,747,291 tokens and 990.03 seconds. These times exclude image pulls and grading.
One Luna trial was a zero-token infrastructure failure. Two Sol-tuned development
trials resolved 1/2, without a new solve relative to the original approaches.
There are no heldout comparisons and no demonstrated harness improvement.

The repository adapter's automatic checks covered whitespace and Python syntax,
not public behavioral tests. Model review and extra context did not reliably
correct that evidence gap. Public test replay is the first mechanism to improve.

## Implemented changes

- Workers return up to three bounded test command argv lists with their summary.
  The orchestrator binds the plan to the exact derived candidate and persists it
  in candidate evidence; worker claims of a pass are not accepted as test results.
- PolyBench verification replays supported public test runners in a fresh offline
  disposable container as UID 1000, without model credentials. Logs, exit status
  and timeouts enter verification evidence. Missing, unsupported or failing plans
  fail verification and enter the existing revision loop.
- Whitespace and syntax checks remain. Public tests are chosen by the worker;
  passing them does not prove relevance, completeness or success on private tests.
- Empty review findings skip the Sol grouping call. Failed checks, review gaps
  and blocking findings retain their existing effect on handoff decisions.
- A separate runner executes only HX in `.hx/improvement-v1`, with three
  development probes, one revision, 600,000 reported tokens per run and a
  three-hour batch envelope. No baseline or tuned-policy arms are scheduled.

## Development protocol

The first batch contains Keras19775 (previously solved control), Keras19863
(observed behavioral failure), and Keras18975 (prior baseline patch rejection).
This selection deliberately uses development outcomes and is not an unbiased
benchmark. Existing pinned images and official scorer are reused. New identities
and scores cannot overwrite the original campaign. All evaluation tasks remain
reserved. Do not feed private grader logs, patches or tests into model context.

Run from Ubuntu WSL:

```text
/opt/hx-polybench-venv/bin/python -m scripts.run_hx_improvement .hx/improvement-v1
```

Before starting, check account limits and controller processes. Never duplicate a
run, redeem reset credits or buy credits. Retain failed attempts and diagnose
public execution traces before another development version. Future fixes should
target observed causes, with bounded development reruns explicitly identified as
new experiments. Test the final version on reserved tasks after development; use
published leaderboard scores as external reference, not proof HX improves Luna.

## Startup correction

Version 1 retained a scored zero-token infrastructure failure: Codex rejected
the worker output schema because the new verification command field had a default
and was absent from the schema's required keys. The corrected contract requires
the field (an empty list still explicitly fails public verification). A regression
test checks that every output property is required. Version 2 lives separately
in `.hx/improvement-v2`, retains the original three-hour envelope start, and links
the failed score by hash. Use that directory in the run command above. Version 1
must not resume or overwrite its failed score. This correction is infrastructure
repair, not evidence of coding improvement.

## First execution evidence

The corrected version's Keras19775 worker returned a focused public pytest plan
for the linspace tests. HX replayed that plan against candidate
`26ac8c2c0c633bd9a0d251915009c3c94f5da2a1` in a separate offline container:
**63 tests passed, 5,432 deselected**. Syntax and whitespace also passed. This
confirms public test execution is connected to the workflow; it does not
establish an improved solve rate. Official grading and the remaining probes
were pending when this observation was recorded.

After the schema correction, 40 Windows public-check/workflow tests and 18 Linux
output-schema/public-check tests passed, and Ruff passed. An additional Linux
workflow run using Windows-mounted fixture temporary files was interrupted after
pytest capture failures (`FileNotFoundError` while truncating a temporary file).
Its native-ext4 rerun is separate evidence; do not count the failed run as passed.
That rerun subsequently passed all **22 workflow tests** in 73.75 seconds.

## First official outcome

Keras19775 is now officially resolved with all required tests observed, no
infrastructure or patch-application errors, and workflow status
`ready_for_approval`. The run used **354,048 reported tokens** and **137.39 workflow
seconds**. Its public test replay passed and the empty-findings consolidation
call was actually skipped, as recorded by `consolidation.skipped`.

This task was already solved by the earlier approaches. It is a positive control
showing the new mechanisms operate without preventing that solve, not a new solve
or evidence of a solve-rate improvement. Keras19863 and Keras18975 remain pending.

## Second outcome and next weaknesses

Keras19863 finished unresolved at 553,237 reported tokens and 163.44 workflow
seconds. The public regression test passed, but the worker also proposed
`git diff --check` as a public behavioral test. The verifier rejected that second
command, correctly distinguishing it from a functional test. The resulting
revision returned a corrected public-test plan without editing source; the
implementation step rejected it as `worker made no changes`. The original
candidate still failed official tests, with all required tests observed and no
grader infrastructure or patch-application error. Public test success did not
establish complete behavior.

Two concrete weaknesses are now visible: workers need clearer separation of
functional tests and automatic smoke checks, and a revision that repairs only
the test plan needs an explicit evidence-preserving transition without pretending
the source changed. Do not fabricate a source edit to satisfy the no-change gate.
Address these in a separately versioned runtime after this batch stops; preserve
the unresolved score. These findings came from public workflow evidence, not
private test contents.

The original development scheduler stopped on every workflow error. Scheduler
amendment 1 now stops on operational errors while retaining coding failures and
continuing independent probes. Seven scheduler regression tests and Ruff passed.
The old/new scheduler hashes, previous plan/lock, and both score hashes are
preserved under `.hx/improvement-v2/scheduler-amendment-1.json`. Coding runtime,
case order, task budgets and original envelope start remain unchanged. The
controller resumed only the pending Keras18975 task; neither prior score reran.

## Completed version 2 and overnight version 3

Version 2 completed all three development probes: **2/3 officially resolved**,
but only one workflow reached `ready_for_approval`. Total usage was **1,514,747
reported tokens** and **512.10 workflow seconds**. Keras18975 passed official
tests with all required tests observed, while its workflow failed during revision
after exhausting its reported-token budget (607,462 tokens). It encountered the
same extra smoke-command test-plan problem as Keras19863. The 600,000-token limit
is checked at reported turn boundaries, so its observed total exceeded the cap.
All three scores are sealed by hash in `.hx/improvement-v2/audit.json`.

Version 3 repairs plan-only revisions while preserving the exact source commit,
diff hash and changed-file evidence, emits `candidate.test_plan_revised`, and
replays independent verification. Empty initial implementations and unchanged
no-op revisions still fail. Worker instructions distinguish functional test
plans from the automatic smoke checks. Empty Sol consolidation remains skipped.
Linux native-ext4 checks passed 77 workflow/protocol/source-transfer tests;
18 corrected Windows plan-transition, quota/budget and console checks passed.
Two earlier test failures were assertion-message mismatches, corrected and rerun.

The overnight runner checks ordinary account usage through the installed CLI's
read-only API before image preparation and again before starting workers. It
does not redeem credits or issue model requests during quota checks. Primary
usage at 80% or weekly usage at 90% stops scheduling for a natural reset. A
shared ledger counts pending version 2 usage plus new scored and interrupted
attempts, and reserves token headroom before starting a new trial. Stage plans,
settings and scheduler dependencies are locked. Reserved evaluation requires
completed development and a separate final-runtime freeze.

The console can follow stages and usage with:

```text
.venv/Scripts/python.exe -m scripts.hx_console --overnight .hx/overnight-20261003
```

It labels official resolution separately and displays saved Sol calls and
source-preserving test-plan revisions from recorded events. It does not infer
process liveness or grant approvals.

## Final overnight runtime and reserved stage

All three v3 development attempts are sealed in `.hx/improvement-v3/audit.json`:
two official resolutions, two ready workflows, 1,666,026 reported tokens and
672.67 workflow seconds. VSCode127071 officially passed despite a workflow
failure: the verifier rejected its legitimate `npm run test-browser` plan, and
revision exhausted the reported-token budget. No score was rerun or replaced.

After the controller exited, `overnight-final-1` repaired conventional test script
names, added optional bounded repository navigation via a single-file read-only
mount, and clarified that concrete supported-contract regressions may block
even at medium severity. Tool code is included in protocol/source fingerprints.
The entire benchmarks directory is never mounted to workers. Final validation:
95 Linux checks, 41 Windows checks (one symlink skip), seven Linux post-compatibility
tool/mount checks, Ruff, and the actual worker adapter in the Python 3.7.3 VS Code
image with no credentials, disabled network, immutable tool and clean source.
The older-Python probe failure was retained and repaired. Final additions have
fixture/container validation but no separate development model validation.

`.hx/overnight-20261003/final-runtime-amendment.json` and its source snapshot
preserve provenance. All 33 historical sealed scores were rechecked unchanged.
Reserved evaluation in `.hx/overnight-evaluation-v1` is complete in the unchanged
six-task order. It resolved 1/6 officially, with 0/6 end-to-end task_success:
MUI's correct patch coexisted with an HX workflow token-budget failure. Other
outcomes were two patch rejections, two observed official failures and one
implementation-budget failure without an accepted candidate. No grader
infrastructure error occurred. Final evidence is sealed in its audit.json.

Serverless demonstrated exact-source plan-only revision followed by successful
public replay, while failing official tests. Two empty consolidations skipped
Sol. No optional navigation invocation was found in the six completed public
worker event traces; tool availability is not demonstrated use. Final source and
prompts remained frozen, and results were not used for source tuning.

Total additional recorded overnight usage was 5,309,568 of six million tokens.
All allocated trials completed, the controller exited and no further trial is
scheduled. The morning report distinguishes verification, workflow status,
official resolution, missing observations, costs and small-sample uncertainty.
Further improvement needs a new development scope and fresh evaluation cases.
