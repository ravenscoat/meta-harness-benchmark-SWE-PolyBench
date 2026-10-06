# Harness improvements after the first benchmark

These implementation changes address observed failure classes. They are operator
changes, not Sol-generated policy gains. The completed 100-trial benchmark and
its frozen runtime archives remain historical evidence. New code and prompts
change the runtime fingerprint, so old runs cannot resume under this revision.

## Verification failures reach the repair loop

Child command timeout now has a distinct `ProcessTimeout` type. Visible backend
and React checks convert that timeout into a failed check with bounded stdout and
stderr tails. The process runner terminates the child tree before returning
feedback. Other checks continue, so a stalled React test does not hide a build
result. Coverage reporting timeouts become an explicit coverage gap.

Cancellation, global token/time exhaustion, log limits, startup failures and
integrity errors continue to abort. The controller rechecks its global limit
before accepting timeout feedback. Private evaluator diagnostics remain separate.

## Revision work is explicit

Each revision gets an exact-candidate repair plan containing failed check evidence,
original blocking source findings and unresolved inspection gaps. Reviews and Sol
consolidation remain attached. Sol cannot erase a source blocker. The plan guides
the worker to the reason a revision is needed instead of asking it to infer that
reason from several reports.

If visible verification passed and the only handoff blocker is missing inspection,
the harness stops with `needs_attention` and retains the unchanged verified
candidate. It does not spend a revision on an arbitrary edit. The inspection gap
remains in the handoff and still prevents human approval through the normal gate.
Failed checks and concrete source blockers still receive bounded revisions.

## Workers and reviewers inspect transitions

Implementer guidance requests tests for state changing during asynchronous work,
retry and cleanup; stable inputs for effect-driven test fixtures; and diagnosis
before repeating stalled commands. Correctness review uses the actual repository
layout, preserves specified clients, and distinguishes concrete reachable defects
from unavailable private acceptance or untested risks. These are general failure
classes; no case-specific answers or reserved evaluator contents were added.

The console now explains check start, timeout, revision planning and gap-only
handoff events. Its output remains read-only.

## How to assess this revision

Local regression checks verify real timeout cleanup/diagnostics, continued
full-stack verification, unchanged abort behavior, gap-only handoff/approval
blocking and revisions preserving source blockers. These checks establish runtime
behavior, not model-quality improvement.

The next model evaluation must use a fresh collection and a frozen new runtime,
with new reserved cases not consulted while developing these changes. Compare
one-shot Luna, the archived baseline and this revision under the same task limits.
Include unrelated repositories and browser behavior. Do not rerun the old reserved
set and report the resulting tuning as generalization.

Validation completed: **73 tests passed** in the full suite (one existing
dependency deprecation warning); the nine focused repair-feedback tests also
passed after strengthening the failed-check evidence assertion. Repository Ruff
checks passed. The subsequent frozen 24-trial comparison is complete: archived
and improved HX both scored 8/8, versus one-shot Luna 7/8. Improved HX exercised
one failed-test repair, used more observed compute, and showed no success gain
over archived HX. Timeout and gap-only paths were not exercised. The one-shot
failure depends on ambiguous validation/replay precedence. See
[fresh results](FRESH_BENCHMARK_RESULTS.md). Historical results remain unchanged.
