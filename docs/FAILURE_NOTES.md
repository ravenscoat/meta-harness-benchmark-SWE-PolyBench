# What the coding traces exposed

These observations come from saved real Codex CLI trials. They are failure
diagnoses, not proof that any proposed policy generalizes. Frozen repair trials
are retained even when the operator subsequently adds a capability elsewhere.

## React test stalls

One-shot optimistic-update workers produced hook fixtures that recreated inputs
on render. Effect-driven state updates could then loop until the test process
exhausted memory or hit its 90-second verification limit. Passing private hook
acceptance alone was insufficient for task success when visible verification hung.
Some worker timeouts report zero usage because the model never emitted a final
usage event; zero recorded tokens do not mean zero actual cost.

The advanced feature extension turns bounded visible-test timeouts into failed
checks so a reviewer/revision cycle can address them. Cancellation, overall
budget exhaustion and integrity errors still abort. Both standard and tuned arms
of that extension use this fixed capability; it is an operator change, not a
Sol-generated policy improvement. The frozen repair runtime retains its original
behavior.

The first reserved full-HX refresh-race trial reproduced this limitation: private
search/board acceptance passed, but visible verification timed out before reviewers
could run. A review loop cannot repair a failure that the controller never sends
to it. This is separate from policy quality.

## Invented client requirements

In the first tuned tenant/version search trial, review introduced an additional
authentication credential beyond the task's X-Tenant contract. Tests were adjusted
to the new credential, and the workflow reached approval readiness while private
acceptance failed. Review can therefore make a solution less compatible even
when its own tests pass. The second proposed repair policy emphasized preserving
the supplied client contract, but its aggregate search success did not improve.

## False inspection gaps

In tuned-2/search-race/repeat-2, the correctness reviewer reported a missing
`frontend/src/api.js` despite acknowledging that it had inspected the actual
inline fetcher. This triggered a revision. The implementer returned no changes,
and the runtime rejected that empty revision. The initial candidate passed both
visible verification and private acceptance, but the failed workflow did not
count as a successful task.

In full/replay-isolation/heldout/repeat-2, a reviewer requested private acceptance
evidence that is intentionally unavailable during review. The resulting revision
passed, but the trace does not establish a meaningful code defect or a causal
benefit from that extra cycle.

The advanced extension permits policies to supply guidance and optional current
candidate source/environment to read-only reviewers. Static review instructions,
scope checks, source findings and human gates stay authoritative. Sol is informed
of this fixed capability before proposing feature policies. Its effect must be
measured; it is not assumed to solve these gaps.

## Approval readiness versus independent acceptance

Both tuned-2 combined search trials reached `ready_for_approval` but failed private
archive/editor checks; one also failed optimistic-board checks. Visible tests and
review agreement are evidence, not complete correctness proofs. Benchmark scoring
requires independent acceptance and successful visible verification. Approval
readiness is reported separately, and no live candidate is automatically approved.

## Concurrent outbox enqueue

In feature single/durable-outbox/search/repeat-2, the worker cached the pending
array at the start of flush, then computed acknowledgement removal from that
same array after awaiting the network. Work enqueued during the await lived in
the current pending ref but was absent from the cached array. Persisting the
derived remainder could discard that newer work instead of rebasing and sending
it. Five of six private hook checks passed; the concurrent-enqueue/rebase check
failed. Visible tests passed, so this is a concrete correctness failure rather
than a provider or controller interruption.

## Evaluator storage assumptions

The frozen feature evaluator used a substitute with `getItem` and `setItem`,
but omitted `removeItem`, which is valid on the task's default `localStorage`.
This produced misleading errors for implementations that removed an empty queue.
The operator preserved raw grades and separately rescored the exact candidate
commits using a substitute with compatible Storage methods. Three correct queue
references passed and three seeded failures failed this evaluator. All
20 queue candidate audits changed no overall task outcomes, though the first standard
reserved candidate's failing test count fell from four to two. Its remaining
error-state/version-rebase defects were genuine. The audit is complete, and tuned-2 remains selected under the corrected search scores.

Frozen campaign policies were not changed after reserved feedback. Normal adoption requires a completed
hash-verified audit covering every graded queue candidate and preserving both
outcomes and selection. Changed outcomes require a clean follow-up evaluation.

## Provider availability

Two first-policy repair search trials were affected by a provider usage-limit
interruption. They remain in the raw operational results and are marked as
interruptions in analysis. They should not be read as clean model-capability
failures. A campaign supervisor now stops scheduling after the first recorded
quota failure; an operator can also request a stop at a scored case boundary.
Normal policy adoption rejects quota-interrupted reserved comparisons.

See the campaign `ANALYSIS.md`, each trial's `score.json`, and its SQLite state,
worker events, patches and review artifacts for the underlying evidence. These
are original synthetic tasks in a shared application family, with AI-authored,
mechanically validated references; they do not establish a public benchmark score.

## Final held-out queue failures

The selected policy still missed version rebasing after a conflict in one trial,
and persisted an acknowledgement after unmount in another. Its reserved score
was 2/4, matching standard HX, with one paired improvement and one regression.
A standard-HX trial passed private acceptance but exceeded its token budget
before verified handoff, so it correctly counted as unsuccessful. These failures
remain evidence for a fresh search collection, not permission to retune on the
reserved tasks.

The subsequent runtime changes are documented in [IMPROVEMENTS.md](IMPROVEMENTS.md).
They require fresh reserved tasks to measure a gain.
