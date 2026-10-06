# One question using the remaining weekly allowance

The user explicitly authorized using the remaining 10% weekly quota for one
question and requested the official benchmark grading result. The new root is
`.hx/remaining-quota-benchmark-v1`; the stopped capture-repair attempt remains
unchanged. This is MUI18141 consumed development evidence, even though the
generic scheduler uses its `heldout-results` storage directory.

The runtime remains the verified file-backed capture runtime with the recovered
worker scaffold. Sol 6.1 authors independent tests on original source in a separate
context before implementation. Actual base reproduction is required. Candidate
checks replay those immutable tests independently; at most one public-feedback
repair is allowed. The official scorer and pinned task inputs remain unchanged.
Private grader data and accepted solutions are excluded from worker context.

The new plan records a three-hour deadline, 900,000 reported-token workflow
target, 1.2-million-token batch allowance and quota guards before model calls.
This attempt alone allows weekly usage below 98%, primary below 80%, and requires
ordinary usage to be allowed. Earlier campaigns retain their 90% guards.
No purchases or reset-credit redemption are authorized. Token targets are
checked at turn boundaries and can overshoot; quota percent is not a conversion
from reported tokens. The new guard passed its boundary check and Ruff.

Initial controller CLI check: 2% primary, 90% weekly. Controller PID697 started;
verify actual process identity before any process operation. All 104 prior scores,
source fingerprints, original inputs and scheduler hashes are locked.

## Completed: official benchmark resolution

The pinned official scorer resolved MUI18141: `official_resolved=true`, zero
required tests unobserved, no patch rejection and no grader infrastructure error.
Candidate commit: `a81ff5a7a9485c3669526b69ba1b53160fa9d498`.

Independent original-source reproduction was established before implementation,
and the immutable independent tests passed on the candidate. The implementer's
two public test commands and differential regression check also passed.
Complete report capture therefore worked through implementation and verification
in this real attempt.

HX nevertheless returned `needs_attention`, `task_success=false`: its public
contract-coverage gate rejected repeated evidence mappings for `r01/behavior`.
The handoff retained the accepted patch and verification. No repair was performed
because the remaining repair token headroom was insufficient. This is an unresolved
workflow/evidence-mapping issue, not an official task failure. No runtime repair or
regrading was performed during this audit.

Reported usage: 927,321 tokens, known usage; 534.84 workflow seconds (8.91 minutes),
excluding downloads/grading. The 900,000 workflow target was exceeded at a turn
boundary; usage stayed within the 1.2-million batch allowance. Last model-work
quota observation: 6% primary, 91% weekly. No purchases or resets.

Controller exited. `audit.json` verifies plan/scheduler/source locks, all 104
historical score hashes, public frozen-test evidence and this score/artifact hashes.
The completed follow-up was removed. This is one consumed development success,
not fresh heldout, paired causal improvement or leaderboard evidence.
