# Complete public report ingestion

The authorized repair changes `public-base-regression@6`: complete stdout and
stderr are read under a shared budget matching the existing log allowance,
capped at20MB. No large stream is silently discarded. An output exceeding that
budget produces explicit report_oversized evidence and cannot establish a pass
or reproduction from stderr alone. Timeout and setup errors remain blockers.
Structured counts/failure details are extracted before creating concise evidence;
the original complete logs and original Check remain available.

48 focused native Linux checks passed, including an integration test invoking
regression_check with a >2MB report, oversized-output rejection and mixed setup/
timeout cases. Ruff passed. The unchanged worker policy is revalidated under
`.hx/worker-loop-runtime-v8`. Prior failed scores are never rewritten.

Model-free actual offline UID1000 replays used both exact frozen test patches and
commands on original production code. Both now establish reproduction:

| Preserved parent attempt | Public passes | Public failures | New base gate |
|---|---:|---:|---|
| worker-loop-benchmark-v1 | 26 | 6 | reproduced |
| label-repair-benchmark-v1 | 31 | 9 | reproduced |

Evidence lives in `.hx/report-ingestion-repair-v1/replay.json` and per-parent
regression.json; all103 historical scores remained unchanged. These are public
base reproductions, not implementation successes or official grader passes.
The container replay used zero model calls, zero official grader calls and no
model credentials. The original author/test artifacts remain intact.

The separately authorized coding attempt uses root
`.hx/report-repair-benchmark-v1`, MUI18141 as consumed development, the same pinned
source/image/public issue and official scorer, GPT-6.1 Sol, unchanged worker-loop
policy, independent original-source authoring and one repair maximum. It requires
both real model-free replay results before any model work. The new3h envelope
retains the previous explicit900k workflow target/1.2M batch allowance and150k
repair reserve,600s model attempts/2400s workflow. Turn-boundary overshoot is
possible. Quota guards and no-purchase/no-reset rules remain.

## Completed new attempt: incomplete producer output

The new task stopped at independent base reproduction before implementation.
The fixed ingestion path read all6,127,616stdout bytes and79stderr bytes under
its20MB limit; it did not discard the report. However, stdout ended inside a
deeply nested object and was not complete JSON. The decoder failed at end of
file; structured_reports yielded no report, so the gate remained inconclusive.

The report header stated34 tests,26 passes and8 failures. Those header counts
are observed public reporter output, not official grader passes, and cannot
substitute for a complete validated failure report. The author returned a plan
using Mocha JSON with --exit. Whether the producer's exit behavior caused the
truncation has not yet been established. No accepted implementation candidate
or official candidate grading occurred. Do not classify this as a wrong solution.

Usage was known:398,157reported tokens,243.20workflow seconds. Scaffold
inspection/delegate/finish ran. All103prior score hashes and runtime/input/
scheduler locks verified unchanged. audit.json preserves the score hash,raw
output hash,decoder failure and header counts. No rerun/replacement was made;
the completed monitor was removed. The model-free ingestion repair remains
proven on both complete saved reports; it does not guarantee producers emit
complete reports.

Follow-up completed: [file-backed report capture](REPORT_CAPTURE_REPAIR.md)
now replays all three exact frozen plans successfully, including the truncated
report case. All 104 old scores remain unchanged; no model or official calls.

Original next technical investigation: reliably capture a compact complete structured
test report, validate its completeness before using counts, and test actual
process exit/output behavior as well as malformed/truncated reporters. More
classifier special cases or treating header counts as a pass would not fix this.

No fresh heldout, causal improvement or leaderboard
claim is supported. Final audit must distinguish reproduction, accepted source
candidate, independent public checks and official grading, preserving all failures.
