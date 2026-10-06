# Lean task execution, development version 1

This opt-in version uses the native Codex task loop with no outer scaffold and
no mandatory separate blind test-author call. Existing independent-author engines,
historical scores and frozen archives are preserved. It is not yet a promoted
replacement or a demonstrated solve-rate/cost improvement.

## Implemented

- `LeanEngine` plugs into the common `runner.run_case` with an explicit `lean` arm.
  Existing roots/scored identities must not be reused. Consumed interrupted lean
  identities cannot silently resume through this scheduler.
- One engine-local native session per explicit run/task/model/schema/workdir.
  Repair restores that session by UUID, not `--last`; credentials and configuration
  are never exported with history. Only bounded regular matching rollout files are
  restored. Foreign paths, links, changed source trees and mismatched thread IDs
  fail closed. Failed model calls invalidate reusable history.
- Native history is transported to a fresh isolated worker container for repair.
  This preserves conversation, not a live process or arbitrary untracked files.
  Preparation still runs and containers are removed after each call. There is no
  interrupted-process resumption or cross-task sharing.
- Repair sends bounded public failure feedback instead of repeating orientation
  and full instructions. Source must match the last successfully exported tree.
- Verification reconstructs original source plus the exact production patch used
  by the official scorer and new solver-authored test files. Existing test edits
  are excluded. Existing tests remain unchanged. Green public results are still
  separate from official resolution; new tests are not blind independent authorship.
- Usage exposes input, cached input, uncached input and output independently.
  Cached input is a subset, never an extra charge in the aggregate token counter.
  Unknown usage stays unknown and monetary cost is not inferred from quota.

## Existing cost evidence

The completed three-task batch used 1768154 reported tokens: author782098
(44.23%), implementation862893, repair123163. There were1537792 cached-input
tokens,215043 uncached-input tokens and15319 output tokens. These counts are
not dollar costs. Removing authors does not establish a44% monetary saving.
The public usage report is `.hx/lean-runtime-development-v1/prior-batch-usage.json`.

## Validation

Final mechanism/compatibility checks:65 native-ext4 Linux tests and43 Windows
tests passed; Ruff passed. Windows sandbox Git shared-memory failure was retained
and the permitted rerun passed. Earlier fixture omissions and a too-short test
report were corrected before final checks.

Native transport smoke v1 captured the first session but stopped before its second
call for insufficient headroom:12418 reported tokens, no official grader/coding
trial. Its failure and original probe source are retained. Separate v2 smoke
passed two actual gpt-6.1-sol calls, recalled a marker from restored history and
kept source unchanged:37384 reported tokens, zero benchmark/official grading calls.
It proves transport, not cheaper task solving. Resumed histories may increase
prompt size; savings require task-level measurement.

## Bounded development check

`scripts.run_lean_development` uses the common scorer for one new MUI36353
consumed-development identity. The v1 root stopped before model execution because
the host launcher PATH omitted the pinned Linux Codex binary. Its original source,
stop and zero-consumption evidence are preserved. The corrected v2 root at
`.hx/lean-cost-development-v2` inherits the v1 start/deadline and allowance after
verifying the parent native state has no coding identity. Thirteen targeted
startup/session/replay tests passed on each platform after the launcher fix.
No blind author,
one repair, same gpt-6.1-sol medium reasoning.200000 workflow token target,
400000 reported-token batch allowance,1200s workflow and fixed1800s envelope.
Limits are checked at call/turn boundaries and can overshoot. Ordinary quota
must be primary<80%weekly<90%; no purchases or reset credits. Plan, runtime,
input and scheduler hashes are locked. All old scores stay sealed.

This selected repeat is a mechanism/cost probe, not fresh evaluation or a paired
causal comparison. Do not run the full benchmark or promote a candidate based on
this one outcome. No executable edits while its controller is active.

Research references and remaining orchestration/cache improvements are in
[CODING_HARNESS_RESEARCH.md](CODING_HARNESS_RESEARCH.md). Preparation caching is
not newly implemented here; existing pinned image caching is reused. Meta-Harness
candidate search is a later stage after the execution baseline is measured.

## Completed development result and subsequent instruction repair

MUI36353 officially resolved with all required tests observed, no patch rejection
or grader infrastructure error:275555 reported tokens and341.84 workflow seconds.
Its workflow remains `needs_attention`: existing public tests passed, but the new
regression was added inside an existing test file and therefore excluded from
independent delivery replay. Base reproduction and named contract coverage failed.
The gate correctly retained this evidence gap despite the official pass.

The earlier consumed attempt officially passed with682567 reported tokens and
1155.41 workflow seconds. This run used about60% fewer reported tokens and70% less
workflow time. It is a selected repeat, not paired causal evidence, general accuracy
improvement or measured dollar savings. Usage includes252544 cached input,
20244 uncached input and2767 output tokens. Workflow time excludes image pulls
and official grading. Usage exceeded the200000 turn-boundary target but stayed
within the400000 batch allowance. One implementer call; no author or repair call.
Native continuation was demonstrated separately by the two-call smoke, not this run.

After controller exit, the lean initial context now explicitly requires NEW test
files, named functional outcomes, and behavioral base reproduction. Existing test
edits remain excluded; no verification gate was weakened. Fourteen targeted Linux
and fourteen Windows checks and Ruff passed. A Windows sandbox Git permission
failure was retained and the permitted rerun passed. This instruction change is
archived separately as `lean-public-replay-contract@1`; it has no further model
validation. The completed trial's score, input locks and original runtime snapshot
remain unchanged. Audit and public usage: `.hx/lean-cost-development-v2/audit.json`
and `usage-report.json`. Do not restart the completed one-task scheduler.
