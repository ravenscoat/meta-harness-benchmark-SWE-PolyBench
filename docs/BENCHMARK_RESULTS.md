# HX final benchmark results

Completed 2 October 2026. **100 final model trials; 60 passing harness tests; Ruff passed.**
No benchmark trials remain. Neither campaign demonstrated a reserved success gain,
so no policy was promoted and no candidate was approved, merged or deployed.

## What was evaluated

GPT-6 Luna implemented changes and independently reviewed correctness and security.
GPT-6.1 Sol consolidated findings and proposed two declarative context policies
per campaign. Python enforced scope, budgets, verification, revisions and evidence.
Each trial used fresh Codex CLI sessions and a fresh candidate workspace.

The collection contains 16 original FastAPI/React tasks, each repeated twice:
12 repairs (six search, six reserved) and four synchronization features (two search,
two reserved). One-shot Luna was compared with standard HX and policy variants.
Repair search used four arms and reserved evaluation two, totaling 72 trials.
Feature search used four arms and reserved evaluation three, totaling 28 trials.
Optimizer proposals are additional model calls, not counted as task trials.

Policies changed instructions, source context and environment snapshots; they did
not rewrite executable harness code or train model weights. Repair policies reached
the implementer. The separately frozen feature extension also supplied policy
context to correctness/security reviewers and converted bounded verification
timeouts into failed checks that could receive a revision. This extension was an
operator implementation change before the final campaign, not optimizer output.

Selection maximized search successes, breaking ties by fewer observed tokens.
Selection was frozen before reserved evaluation. Feature proposals received 48
prior repair search traces, excluding repair reserved data and provisional pilots.

## Search results

| Campaign / arm | Successes | Observed task tokens | Workflow seconds |
|---|---:|---:|---:|
| Repair: one-shot | 8/12 | 1,126,837 | 1,714.5 |
| Repair: standard HX | 9/12 | 4,233,814 | 2,867.7 |
| Repair: tuned-1 | 8/12 | 3,896,363 | 2,225.8 |
| Repair: tuned-2 | 8/12 | 3,692,488 | 2,010.2 |
| Features: one-shot | 3/4 | 640,969 | 656.3 |
| Features: standard HX | 4/4 | 1,553,290 | 1,050.4 |
| Features: tuned-1 | 4/4 | 2,037,132 | 1,286.4 |
| Features: tuned-2 | 4/4 | 1,348,238 | 971.6 |

Repair selected standard HX. Features selected tuned-2, “Transition-contract-context.”
It emphasized state across asynchronous/transaction boundaries, preserving newly
queued work, rejection/cleanup metadata and focused interleaving evidence.
Its feature search task tokens were **13.2% lower** than standard HX at equal success.
Sol proposal costs were another 632,068 repair tokens and 931,554 feature tokens.
These extra calls and search trials prevent treating that reduction as net savings.

## Reserved results

| Campaign / arm | Successes | Observed task tokens | Workflow seconds |
|---|---:|---:|---:|
| Repair: one-shot | 8/12 | 1,911,790 | 1,835.6 |
| Repair: standard HX | 8/12 | 3,373,735 | 2,342.7 |
| Features: one-shot | 2/4 | 1,280,589 | 851.3 |
| Features: standard HX | 2/4 | 2,726,606 | 1,602.8 |
| Features: tuned-2 | 2/4 | 2,705,287 | 1,578.1 |

Repair pairs had eight shared passes and four shared failures: no changed outcomes.
Each feature comparison (one-shot to standard, standard to tuned-2) had one
improvement and one regression: **zero net success gain**. Feature tuned-2 used
about 0.8% fewer reserved task tokens than standard HX, which is descriptive
and does not establish general efficiency. Normal adoption correctly refuses
this policy because reserved success did not improve.

A task counted as successful only with independent acceptance and successful
visible verification/handoff. Approval readiness alone was insufficient. One
standard feature trial passed private acceptance but exceeded its token budget
before verified handoff and counted as unsuccessful. A tuned trial succeeded with
`needs_attention`; that status still requires a human decision before adoption.

## Evaluator audit and interruptions

The frozen private queue evaluator omitted the standard Storage `removeItem`
method. Original runs, grades and selection were preserved. A separate compatible
Storage evaluator passed three reference solutions and rejected three seeded
failures, then rescored the exact commits of **all 20 queue candidates**.
All overall outcomes stayed unchanged and tuned-2 remained the search winner.
One candidate's failing test count fell from four to two, leaving actual
error-state/version-rebase failures. The completed audit certificate is checked
by the normal adoption guard; the reserved-improvement gate still rejects promotion.

Two first-policy repair search trials were quota-affected operational failures;
they are retained and should not be interpreted as clean model-capability failures.
No reserved trial was quota-interrupted. Feature scheduling paused after a scored
case and resumed after the normal quota reset, retaining scores and the original
campaign clock. A transient Windows report-replacement failure started no model
trial. Earlier invalid feature pilots remain on disk but are excluded from these
100 trials. Local regression tests overlapped one feature workflow; timings are
not isolated measurements.

## Interpretation and next work

This is a local synthetic benchmark in one shared application family, with two
repeats per task. Tests and references were AI-authored and mechanically validated,
without independent human ground truth. These results do not establish transfer
to unrelated projects, a SWE-bench/Terminal-Bench score or replication of the paper.
React verification used hook tests and production builds; there is no automated
browser end-to-end benchmark. Observed tokens may omit usage from failed processes;
workflow times exclude private grading, proposal calls and setup. No dollar cost
claim is made.

Observed failures include concurrent enqueue loss, conflict version rebasing,
error-state erasure, work completed after unmount, stalled React tests and review
findings that missed real defects or proposed changes against the task contract.
Next work should address these using fresh search tasks, independently reviewed
repositories and browser tests, then freeze a new policy before new reserved tests.
Stronger isolation is needed before evaluating hostile code.

## Evidence

- [Architecture](ARCHITECTURE.md) and [failure notes](FAILURE_NOTES.md).
- [Repair report](../.hx/experiments-v1/REPORT.md) and [paired analysis](../.hx/experiments-v1/ANALYSIS.md).
- [Feature report](../.hx/sync-experiments-v4/REPORT.md) and [paired analysis](../.hx/sync-experiments-v4/ANALYSIS.md).
- [Compatible Storage audit](../.hx/sync-storage-audit-v8/ANALYSIS.md) and [certificate](../.hx/sync-storage-audit-v8/audit.json).
- Final feature source archive: `.hx/sync-experiments-v4/runtime-source-v7`.
- Validated collection: `.hx/sync-features-v7/manifest.json`.

Repair runtime fingerprint: `a3a55c349db197fcd5ea6f189b359a8b0cd4491eb3f43e8a216b0ab3d5a4efb7`.
Feature extension fingerprint: `ea038b28669e4aac02e76e09fcb33f6a29f6a78ad722dd6eff0a5ab12cf61f9b`.
