# Svelte reproduction classifier repair

Implemented on 4 October 2026 as `polybench-public-tests@9`, with
`public-base-regression@3`. The unchanged Svelte 728 candidate now passes
independent public verification and has a separately recorded
**ready_for_approval** recovery handoff.

## Cause and correction

The public Svelte runner remembers which sample has already failed. If another
shared/inline variant executes after that failure, it deliberately throws
`skipping test, already failed`. The old classifier required every failed JSON
entry to be an assertion. It rejected three real assertion failures followed
by six runner-generated entries as inconclusive.

The new exception requires all of the following:

- The repository is Svelte and the original public runner matches an explicitly
  approved SHA256, `8174388346cfb3b8a2d9edab9747d32a775fd50aaa60c46ed6f9b1de5e65b340`.
- The runner in the replay container is byte-for-byte identical to the original
  tracked runner, even after the public test overlay.
- A real assertion failure for that same runtime sample appears first.
- The follow-up has the exact known message and runner stack location, with a
  shared/inline variant of the same sample and a consistent report failure count.

Unknown errors, orphan or out-of-order skips, another sample, changed runner
source, hook/setup failures and malformed counts remain blocking. Follow-up
entries are not passing tests and never establish reproduction on their own.
This exception is restricted to the verified public runner version. Worker
test code/output remains untrusted, and red/green is not independent proof of
issue completeness.

## Validation and recovery

Windows: 88 passed, one native-Linux-only skip. Native Linux: 89 passed. These
include assertion/follow-up ordering, same-sample association, wrong provenance,
changed runner, unknown errors, hook failure and count mismatch checks, plus the
existing public regression/build checks. Ruff passed.

`.hx/svelte-classifier-reverification-v1` records an actual fresh-container
reverification of candidate `4c0ab5292a62a90b8199caabfd8674197e9f42d4`:

- Public builds, candidate tests, original-source reproduction and contract
  coverage all passed their checks.
- Original-source replay is now correctly classified as `behavioral_failure`;
  the reproduction gate reports `reproduced`.
- The new verification recovery handoff is `ready_for_approval` and verified.
- No model call, source edit to the candidate, or official regrade occurred.
- All 90 inventoried historical score artifacts and the sealed inputs/source
  fingerprints remained unchanged during reverification.

The original official result remains **passed**. Its historical workflow record
still says needs_attention because it ran under version 8; that record and score
were not rewritten. The recovery is a new verification identity and does not
count as another coding trial or official benchmark success. Original score SHA:
`61f54a32e9156506600b4834a18037b5cc3eeca855a3816e6774aa1737dab372`.

Evidence: `plan.json`, `plan.lock.json`, `verification.json`, `handoff.json`,
`report.json`, public execution logs and archived runtime source in the recovery
root. The bounded model-free driver is `scripts/reverify_svelte_classifier.py`.
