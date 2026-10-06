# Fresh full-stack comparison

The frozen campaign completed **24/24 trials** on October 2, 2026. One-shot Luna
scored **7/8**; archived HX and improved HX each scored **8/8**. No provider
interruption affected a final trial. The controller exited successfully.

Both full-workflow arms are saturated on this collection. The updated runtime has
not improved task success over the archived runtime here. A harder, independently
reviewed collection is needed to assess that claim.

## Results

| Arm | Task success | Observed tokens | Workflow seconds | Controller revisions |
|---|---:|---:|---:|---:|
| One-shot Luna | 7/8 | 2,112,060 | 1,520.7 | 0 |
| Archived core HX | 8/8 | 2,670,793 | 1,752.7 | 0 |
| Improved core HX | 8/8 | 3,081,525 | 2,051.3 | 1 |

All 24 candidates passed real-browser acceptance and final visible verification.
One candidate failed private backend acceptance. Each full-workflow arm produced
eight `ready_for_approval` handoffs. Total reported usage was **7,864,378 tokens**;
supervisor wall time was approximately **93.3 minutes**, including private grading.

| Paired comparison | Both pass | Treatment-only pass | Baseline-only pass | Both fail |
|---|---:|---:|---:|---:|
| One-shot → archived HX | 7 | 1 | 0 | 0 |
| Archived → improved HX | 8 | 0 | 0 | 0 |

The raw one-shot-to-HX difference is 12.5 percentage points, entirely due to the
specification-sensitive replay check discussed below. The improved runtime's
success difference is **zero**. It used about **15.4% more observed tokens** and
**17.0% more workflow seconds** than archived HX. Those are descriptive costs,
not evidence of a statistically established efficiency difference.

The final integrity audit matched all **76 frozen source/configuration entries**.
Improved HX recorded one `revision.planned` recovery and zero
`verification.timeout` or `revision.skipped` events. Timeout recovery and gap-only
handoff therefore remain locally tested features, not mechanisms challenged by
these model trials. No policy was promoted.

## Protocol

Four new synthetic FastAPI/React tasks cover seat booking, stock transfer,
integer-cent invoice allocation and atomic inbox acknowledgement. Each has two
repeats in three arms: archived one-shot Luna (`single`), archived core HX (`full`)
and the improved core HX (`improved`). Luna implements and reviews; Sol consolidates
reviews in the two full workflows. The runtime improvements were operator-authored.
This campaign does not run a Sol policy search or select a winning policy.

All tasks were reserved prospectively. Sources, prompts, graders, task settings
and schedule were frozen before valid model trials. Arms use the same per-task
ceilings: medium reasoning, 300-second model attempt, 90-second verification,
1,200-second workflow and 800,000 observed tokens; at most one controller revision.
Actual compute differs. Scheduling rotates arm order deterministically. Success
requires private backend and real-browser acceptance plus visible verification
and an eligible completed handoff. Readiness alone is insufficient.

Private browser checks run a localhost FastAPI server, Vite and headless Edge via
Playwright. They exercise delayed real API responses, typing during submission,
submission coalescing and A/B/A owner switching with late responses. Backend
checks cover restart replay, owner isolation, integer arithmetic, validation,
rollback and competing writes. Four broken seeds fail both private groups; all
four references pass both groups and visible checks.

## Interpretation limits

The improved invoice-allocation repeat 2 exercised `revision.planned`: its initial
React regression test failed, the exact failure entered the repair plan, and one
revision passed visible checks and both private groups. Comparing saved source
shows the React hook itself did not change during that revision; the worker fixed
the test's asynchronous `act` usage and added a backend SQLite integer bound after
a reviewer finding. This demonstrates a working feedback path and repair of a
worker-authored test, not evidence that the controller repaired a frontend bug.
The initial candidate was not privately graded, so no before/after private-success
gain can be inferred for this individual revision.

These are AI-authored tasks and references with mechanical validation. They share
a SQLite scaffold and React editor contract, so they are not four independently
reviewed real-world projects. Two repeats per task are a small sample. Browser
coverage does not exhaust error/unmount branches or all asynchronous interleavings.
This is a local benchmark, not a public coding-benchmark score or paper replication.

The frozen replay check adds an extra field to an already successful request and
expects HTTP 409 for changed content. In `single-stock-transfer-2`, the candidate
rejects unexpected fields before replay lookup and returns 422 instead. The task
requires 409 for changed replay content and 422 for validation failures, but does
not explicitly state precedence when both apply. Preserve the raw failure; treat
any apparent harness advantage resting on it as specification-sensitive evidence,
not proof of stronger transaction handling. No grader was changed after scoring.
As a post-hoc sensitivity view, omitting that task/repeat pair from all three arms
leaves **7/7 in each arm**. This does not replace the frozen raw scores.

Workflow seconds exclude private grading and outer dependency preflight. Local
monitoring and small regression checks overlapped some trials, so timing is
descriptive rather than an isolated speed experiment. Observed tokens include
reported cached input and are not dollar costs. This bundle comparison cannot
identify which individual prompt or runtime change caused an outcome.

## Evidence

- Campaign and scores: `.hx/fresh-experiments-v3/report.json` and `REPORT.md`.
- Paired analysis: `.hx/fresh-experiments-v3/analysis.json` and `ANALYSIS.md`.
- Completion and integrity/mechanism audit: `complete.json` and
  `integrity-and-mechanisms.json` in the campaign directory.
- Source/configuration hashes: `.hx/fresh-experiments-v3/frozen-sha256.json`.
- Seed/reference validation: `.hx/fresh-validation-v4/validation.json`.
- Saved per-trial events, candidate patches, visible reports and private logs remain
  separate under the campaign directory.
- Excluded v1 retains 13 dependency setup failures before any model was instantiated;
  v2 retains one cancelled transport attempt with no completed model turn. Neither
  contributes to valid task scores. See the [protocol](../benchmarks/fresh/README.md).
- Runtime validation: prior full suite **73 passed**; the four console and three new
  campaign tests passed together (**7 passed**); repository Ruff passed.

The original [100-trial results](BENCHMARK_RESULTS.md) remain separate historical
evidence. No candidate has been approved, merged, pushed or deployed.
