# HX delivery and public-test repairs

Latest React development follow-up: MUI 23229's original Luna attempt remains an
official failure. A separate repair informed by the public upstream PR now passes
all 99 official observed tests, with no missing required tests or grader/patch
errors. Its public suite passes 104 tests with two pending. The cause was a hidden
empty clear button and reserved spacing, rather than root-click dispatch. This
follow-up used no coding-worker calls and preserves all 85 indexed benchmark
scores and intermediate failures. It is reference-informed development evidence.
See [React Contract Repair](D:/projects/Harness/docs/REACT_CONTRACT_REPAIR.md).

This work follows the user's authorization to diagnose consumed benchmark
answers, fix general harness mechanisms, and then run a small fresh evaluation.
The original coding scores remain sealed. Inspected reference/test patches are
development material and are not placed in worker or future evaluation context.

## Confirmed causes

Both latest official patch rejections came from worker test edits colliding
with the benchmark test patch, which is installed first. LangChain 4579 added
the same test-file path that the evaluator had already created. MUI 18683 edited
test lines already changed by the evaluator. Both production portions applied
cleanly. Saved reference patches applied after the evaluator tests.

Raw application attempts, including the official git/patch fallback sequence,
are retained in `.hx/delivery-diagnostics-v1`. This used zero model calls and
verified 81 historical coding/grader score records unchanged. It supersedes
the earlier unconfirmed collision hypothesis without rewriting those reports.

MUI public execution also had two independent environment/lifecycle defects:
root-owned Babel cache writes caused an uncaught error; after disabling that
cache, all 11 assertions passed but Mocha kept its process alive. An explicit
public Mocha `--exit` probe completed with exit code zero and 11 passing tests.
The original cache failure and subsequent timeout remain recorded.

## Implemented runtime version

`delivery-and-public-test-repair@1` implements:

- A production delivery projection based only on conventional public test paths.
  Full source/test candidates remain immutable for public verification. Each
  delivery records included/excluded paths, candidate/base commits, and full and
  delivered patch SHA256. Raw Git bytes retain final whitespace/newline evidence.
  No private test patch is consulted by the production delivery algorithm.
- `BABEL_DISABLE_CACHE=1` in both worker and credential-free public verifier.
  Recognized test-only environment prefixes are moved into Docker environment
  fields automatically; shell commands and arbitrary environment assignments
  remain unsupported.
- Explicit exit after Mocha assertions for recognized direct runners and public
  package scripts. This uses public manifest inspection without running code.
  Actual executed argv/environment are recorded. Force exit does not establish
  absence of dangling resource handles; that limitation remains in verification.
- Actual worker-container tool inventory and test-environment evidence, in
  addition to the older controller environment snapshot. Tool availability and
  optional navigation availability are not reported as demonstrated model use.
- Generic guidance to trace supported inputs, defaults and lifecycle transitions
  and choose relevant compatibility regressions rather than one happy path.
- Outcome classification, readiness precision, tokens/workflow time per official
  success, and optional total wall time. Undefined cost per success is null when
  there are zero successes, never a misleading zero.

Existing token-headroom admission, verification after final-turn budget
overshoot, candidate preservation, one-revision bounds, and independent plan-only
revision replay remain active. Tests verify those protections. They do not impose
a hard token limit inside a model turn.

Production test-path classification is intentionally explicit and has limits:
unconventional test paths may remain; production code placed under conventional
test directories is excluded. Public verification of the full candidate does
not by itself prove the production projection meets private acceptance.

## Validation and diagnostic recovery

Focused Windows checks passed 61 tests; final native Linux delivery, protocol,
command, metrics, tool isolation, budget and plan-transition checks passed 68.
Ruff passed. An earlier native run passed 63 tests with a mounted-storage pytest
cache warning; the final run disabled pytest's cache and used a unique native
ext4 temporary directory. No failed check is counted as passing.

Saved MUI production code passed the unchanged official evaluator in a separately
recorded diagnostic: all required tests were observed, with no patch rejection
or grader error. Its original benchmark score remains unresolved. The first
cache-only public replay still timed out; the separate explicit Mocha lifecycle
probe passed. Artifacts are under `.hx/delivery-repair-validation-v1` and
`.hx/mocha-lifecycle-probe-v1`. LangChain's saved production patch also officially
resolved, with all required tests observed and no patch/grader error. Both original
scores remain unresolved. Its different header-merging implementation is an
acceptable tested alternative on this case, not a reason to imitate reference
code text. The new verifier additionally replayed MUI's original environment-
prefixed plan successfully under `.hx/adapted-public-verifier-v1`, with no model
revision or source change. Both diagnostics preserve 81 historical score hashes.

## Fresh evaluation

After diagnostics and validation complete, a separately locked two-case
evaluation selects the first unused and unexposed LangChain and MUI cases in the
original pinned metadata order. One Luna worker, at most one repair, original
dataset/images/scorer, no reviewers or task-level Sol calls. Two-hour/1.2M
reported-token batch cap; 400k per-trial admission limit can overshoot at turn
boundaries. Read-only account checks precede every model call; no credits are
purchased or redeemed. No runtime tuning occurs during this final batch.

The selected cases are LangChain 6765 and MUI 23229, recorded under
`.hx/harness-repair-evaluation-v1`. Repair provenance/source snapshots are sealed
under `.hx/harness-repair-v1`. Scheduler/freshness checks passed 36 Windows tests,
including explicit exclusion of reference-exposed cases. Account usage at launch
was 68% primary and 29% weekly; guards stop model calls at primary 80% or weekly
90% without purchasing or redeeming credits.

This small unpaired evaluation can demonstrate task completion. It cannot
establish a causal harness gain or leaderboard rank. Development diagnostics
are reported separately from fresh scores. These two tasks are untouched, but
their repository families were used for the consumed-task diagnostics: this is
task-held-out evidence within known repositories, not repository-held-out transfer.

## Fresh evaluation outcome

| Case | Official resolved | Public verified | Patch rejected | Required tests unobserved | Reported tokens | Workflow seconds |
|---|---:|---:|---:|---:|---:|---:|
| langchain-ai__langchain-6765 | True | True | False | 0 | 124,622 | 78.60 |

Fresh official resolutions: 1/1. End-to-end successes: 1/1. Reported tokens: 124,622; workflow time: 78.60s; total batch wall time: 2270.47s.

Sealed scores, public actor/tool evidence and full efficiency metrics are in the evaluation root's `audit.json` and `public-tool-audit.json`. Original results remain unchanged. These fresh tasks are separate from the two recovered development diagnostics. No baseline arm, causal improvement claim or leaderboard ranking is established.

The batch stopped with preserved evidence: account limits blocked model work;
no credits were redeemed. Primary account usage was 84%, weekly usage 31%.
The guard runs before model work; account usage is shared and may change during
image preparation. MUI 23229's pinned image finished downloading, but no coding
worker, task state or score was created for it. It is pending, not a failed coding
attempt and not part of the 1/1 denominator. The controller exited and no worker
containers remain.

The natural primary reset is **3 October 2026, 17:11:01 Pakistan time**. This is
after this batch's original two-hour deadline, so the stopped campaign is closed
and is not silently extended. The remaining React task requires a separately
recorded bounded continuation after quota permits, reusing this frozen runtime
and cached image. Keep its original fixed identity/selection and preserve the
completed LangChain score; do not select a replacement.

The completed fresh actor trace shows one Luna implementation call, no revision,
and no reviewer/Sol call. Automatic repository mapping, actual worker environment
inventory and patch replay ran; no optional navigation-tool invocation was found.
That tool's availability is therefore not evidence of its usefulness. The complete
case used one independently replayed public test command plus smoke checks, with
all official required tests subsequently observed. Readiness precision is 1/1 on
this tiny completed sample. Total batch wall time was 37.84 minutes, largely image
preparation; the one coding workflow was 78.60 seconds. This is task-completion
evidence, not a causal gain over a baseline.
