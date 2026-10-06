# Three simultaneous benchmark questions

The user explicitly requested three questions at the same time after MUI18141
passed official grading. New experiment: `.hx/parallel-three-v1`, scheduler
`scripts.run_parallel_three`. All older campaigns stay stopped.

Fixed questions: Svelte477, MUI36353 and MUI34207, the first three remaining
original evaluation cases with no scored or snapshot coding identity at selection.
No outcomes or accepted solutions were used to rank them. The original pinned
dataset, image identities, reference validations and official scorer are reused.
Runtime and recovered worker scaffold match the preceding successful MUI attempt;
the duplicate coverage-evidence issue remains observable rather than being hidden.

Each question has a separate process, experiment root, public artifacts,
native-ext4 SQLite state, workspace, immutable console snapshots and grader output.
Each child image ledger contains exactly one question: image-cache trimming cannot
remove another child's recorded image. All three images are preloaded serially
before concurrent model work starts. Preparation is not concurrent coding.

Workers are Sol6.1 in separate original-source test-author and implementation
contexts; actual behavioral base reproduction and immutable candidate replay
remain required. At most one public-feedback repair, 900,000 reported-token
workflow target, 600-second model calls, 2400-second workflow and 180-second public
checks per question. The shared four-hour envelope allows 3.6 million reported
tokens including active unscored work. Model-call admission is serialized under
a file lock with pending-call reserves; admitted requests execute concurrently.
Turn-boundary targets and pending-call reserves cannot prevent every large-turn
overshoot and are reported honestly.

User-authorized remaining-quota limits: primary below80%, weekly below98%, ordinary
usage allowed. Starting account check:10% primary/92% weekly. No purchases or
reset credits. Concurrent requests already admitted may finish after a quota stop;
subsequent model calls must pass a fresh guard. No task is silently rerun, dropped
or replaced. Parent launch records prevent automatic duplicate launches.

Host capacity before launch: Ubuntu7.8GB RAM, approximately6.8GB available,
2GB swap,887GB free native storage, no active worker containers. Existing per-container
limits are unchanged; they are ceilings rather than reserved host memory. Resource
failures, if observed, remain scored evidence. Four focused shared-budget/quota
checks and Ruff passed before launch.

Status: all three child processes launched. Svelte477 stopped before any model
request with `Unsupported Svelte build layout; validate a new public recipe`,
zero reported tokens and no accepted candidate or official grader call. This is a
worker-preparation failure, not observed buggy candidate behavior; its zero
unobserved-test count does not prove tests ran. The failed identity is retained.

MUI34207 completed successfully: official resolution and HX workflow success
both true, `ready_for_approval`, all required tests observed, no patch or grader
errors. Independent public candidate replay also passed. Reported usage540,588
tokens,650.31workflow seconds. Candidate `afff9d38dd09363b40b230f0a142cbc235c47229`.

MUI36353 also completed successfully: official resolution and HX workflow success
both true, `ready_for_approval`, all required tests observed, no patch or grader
errors. Reported usage590,354tokens,940.38workflow seconds. Candidate
`8cea6c81249714a28e1373ff58b79b96eccde054`.

Its initial public gate rejected duplicate coverage evidence for `r01/behavior`.
The allowed repair changed the test/evidence plan while preserving the source
candidate (`candidate.test_plan_revised` observed). Final public checks,
immutable independent candidate tests and official grading all passed. This
demonstrates the plan-only repair path resolving an actual workflow mapping issue.

## Final audited results

| Question | Official resolution | HX workflow | Classification | Reported tokens | Workflow seconds |
|---|---|---|---|---:|---:|
| Svelte477 | No official grading | Failed before model work | Unsupported worker build recipe | 0 | 7.16 |
| MUI36353 | Passed | Passed | Resolved after evidence-plan repair | 590,354 | 940.38 |
| MUI34207 | Passed | Passed | Resolved without revision | 540,588 | 650.31 |

All three allocated identities are scored and preserved:2/3official resolutions,
2/3end-to-end workflow successes. Both tasks that reached coding passed; this does
not remove the Svelte failure from the batch denominator. Usage was known for
all three. Total1,130,942reported tokens and1597.86summed workflow seconds;
25.25minutes batch wall time includes serial image preparation and grading.

Public worker-instantiation/usage timestamps demonstrate237.98seconds of actual
overlapping model execution between the two MUI tasks. All three child processes
launched, but Svelte failed before a model call, so three-way model concurrency
was not demonstrated. No image-tag collision, quota rejection, unknown usage,
scored grader infrastructure error or runtime mutation was observed. Last quota
checks before model work were at most22%primary/93%weekly; no resets or purchases.

Parent and children exited. `final-audit.json` verifies all106historical score
hashes, parent plan/scheduler/input/source locks, new score seals and the previous
MUI34207 checkpoint. It preserves author-before-implementation frozen events,
public checks, revision events and model intervals. No model calls or grader
reruns were made for the audit. The completed follow-up was removed.

Remaining concrete blocker: Svelte477 requires a separately validated public build
recipe. Its identity was not replaced or silently rerun. No live runtime repair
was made from these results.

Results will report official resolution separately
from public reproduction, candidate tests and HX workflow readiness. Three selected
tasks provide a concurrency diagnostic and small-sample evidence, not paired causal
improvement or leaderboard rank. At completion audit original hashes, actual model
overlap, each outcome, token usage and infrastructure failures without exposing
private grader data to workers.
