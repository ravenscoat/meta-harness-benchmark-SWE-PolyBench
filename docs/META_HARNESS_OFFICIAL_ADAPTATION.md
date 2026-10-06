# Official Meta-Harness comparison and HX repair

Inspected 2026-10-04. The official repository is archived read-only for research
at `.hx/research/meta-harness-official`, commit
`8123ccabe2b19fa1123090b2e5f1bacc20963ce8`. Its code was inspected, not installed
or launched. This repair uses the design, not a copied Harbor/Anthropic runtime.

Sources:

* [Domain interface and evaluation boundaries](https://github.com/stanford-iris-lab/meta-harness/blob/8123ccabe2b19fa1123090b2e5f1bacc20963ce8/ONBOARDING.md).
* [Terminal agent evolution controller](https://github.com/stanford-iris-lab/meta-harness/blob/8123ccabe2b19fa1123090b2e5f1bacc20963ce8/reference_examples/terminal_bench_2/meta_harness.py).
* [Proposer constraints and editable surface](https://github.com/stanford-iris-lab/meta-harness/blob/8123ccabe2b19fa1123090b2e5f1bacc20963ce8/reference_examples/terminal_bench_2/.claude/skills/meta-harness-terminal-bench-2/SKILL.md).
* [Optimized coding artifact](https://github.com/stanford-iris-lab/meta-harness-tbench2-artifact).

## What the code actually contributes

The Terminal-Bench example asks an optimizer to create executable agent variants,
then validates the imported class and runs a one-task smoke test before larger
evaluation. Candidate code, hypotheses, results and trajectories persist. Its
editable surface includes tools, command execution, the agent loop and context
handling. The optimized artifact describes an initial sandbox environment
snapshot. This is not a SWE-PolyBench solution pack or a drop-in Codex CLI adapter;
the released agent uses Harbor and Anthropic/LiteLLM interfaces.

The onboarding guidance separates final test access from search. The Terminal-
Bench example itself evolves on its full task set, so its final repeated-task
score is not evidence of untouched repository transfer. HX should keep explicit
search/final separation instead of treating repeated consumed tasks as heldout.

## HX comparison

| Mechanism | Existing HX | Required direction |
| --- | --- | --- |
| Executable candidate search | `run_code_search` edits only `failure_evidence.py` | Extend to an isolated agent execution/context interface; keep evaluator fixed |
| Experience access | Explicit public files, immutable archives | Save complete public worker trajectories and exact runtime per candidate |
| Runtime smoke gate | Many fixture tests; actual returned command shapes missed | Test the same command contract in a real worker/verifier environment before broader runs |
| Candidate selection | Pure-tool evidence/cost frontier | Task-resolution evidence plus operational reliability and observed token/time costs |
| Search versus final | Historical frozen roots and protected official evaluator | Consume failed final tasks into development explicitly; keep a new final pool outside proposer context |

The full agent-code search direction is not implemented by this repair. Existing
tool search remains narrow, and neither fixture scores nor this compatibility
repair establish better coding resolution.

## Implemented single-mechanism repair

New development runtime: `polybench-public-tests@12`,
`blind-public-challenge@2`, `public-runner-contract@2`.

The last three attempts all stopped before implementation when the test author
returned real Node-invoked Mocha/cross-env commands rejected by our replay
allowlist. This was a harness interface mismatch. It did not show three incorrect
implementation patches or three observed official test failures.

* Recognize only the exact local Mocha Node entrypoints, with optional `./`.
* Normalize the exact cross-env Node wrapper and the existing three fixed test
  environment assignments into container environment parameters.
* Preserve command lists; detect Mocha lifecycle and append `--exit` unless an
  explicit exit/no-exit choice is present.
* Expose the same structured runner contract to blind authors and implementers.
* Validate author command compatibility when accepting a challenge, before
  starting its base reproduction stage. Unsupported plans still fail closed.

Arbitrary Node scripts, interpreter injection flags, shell wrappers, path look-
alikes and unknown environment assignments remain unsupported. Command shape
acceptance is not a security boundary for arbitrary repository code or proof of
test honesty; execution remains isolated, offline and without model credentials.

## Actual validation and limitations

Final focused suite: 84 Windows tests passed, one Linux-only test skipped; 85
native Linux tests passed. Ruff passed. Tests cover exact failed command shapes,
unchanged plans, environment normalization, adversarial look-alikes, early plan
rejection and isolated author context. An initial test insertion accidentally
moved an existing assertion into the next test; that NameError was corrected
before the final suites. No model request was involved.

`scripts.probe_public_runner_contract` performed separate zero-model public
development diagnostics on retained challenge artifacts. It did not call the
official grader, create new coding scores, or alter old scores:

| Retained task | Container execution outcome |
| --- | --- |
| MUI 28190 | Exact retained command independently executed: 120 tests, 109 passed, 5 failed behaviorally, 6 pending. Base reproduction established. |
| Serverless 7374 | Pinned image absent from cache; no test execution. Command compatibility covered by fixtures only. |
| Serverless 7277 | Pinned image absent from cache; no test execution. Command compatibility covered by fixtures only. |

These are consumed development diagnostics. The five MUI assertion failures are
expected on original production code and demonstrate independent execution;
there is no implementation candidate or official success. Serverless execution
remains unvalidated until its exact pinned images are available. The diagnostic
did not pull replacement images or silently turn missing-image errors into passes.

Evidence lives in `.hx/meta-harness-adaptation-v1`; before-source copies and the
completed original batch's runtime snapshot remain available. The probe's exact
executed helper was saved before a subsequent closure-binding lint fix. Original
score/input locks are not rewritten. Old schedulers must remain stopped; their
live source fingerprint now deliberately differs from the new development code.

## Next implementation boundary

Update: the bounded outer worker-loop interface described here is now implemented
and tested. See [worker-loop search](WORKER_LOOP_SEARCH.md) for its exact scope,
the retained proposal budget failure, zero-model recovery and adoption limits.

Before spending more model tokens, implement an isolated candidate interface for
the worker execution loop and context construction, extending the existing code
search runner instead of building another unrelated scheduler. A candidate gets
only explicitly exported public development experience. Sol proposes one code
mechanism; an external evaluator validates imports, runner contract, real offline
smoke execution, then a small locked development set under a fixed worker model.
Record rejected candidates and operational failures, compare task outcomes and
cost against the current incumbent, and promote only after regression and task
evidence. Freeze selection before a new untouched final set. Do not optimize the
official scorer or feed private tests/accepted solutions into the proposer.

The execution repair and bounded worker-loop search are implemented. Arbitrary
Codex-internal agent-code replacement is outside this interface. Neither change
establishes that HX now beats a benchmark.
