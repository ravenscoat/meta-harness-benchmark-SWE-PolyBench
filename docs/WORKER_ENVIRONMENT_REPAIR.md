# Worker environment repair

Implemented on 4 October 2026 as `polybench-public-tests@8`. This addresses a
public execution failure in the previous Sol diagnostic, before any further
claim about coding quality.

## What changed

The old container transfer preserved installed dependencies and ignored build
artifacts. Some Svelte artifacts belonged to the image user, while source and
the model ran as UID/GID 1000. Public builds failed with EACCES. Direct Mocha
execution could also bypass npm's pretest build and use stale generated code.

`benchmarks/polybench/worker_environment.py` now defines a narrow recipe for the
old public Svelte build layout. Only its declared, ignored, untracked generated
outputs are staged with worker ownership and cleared: compiler, ssr, shared.js
and src/generators/dom/shared.ts. Dependencies are retained. Archive links,
escapes, oversized payloads and overlaps with tracked source are rejected.
Unknown Svelte layouts require a new validated recipe; other repositories do
not receive a guessed build command.

The actual worker runs the public build before model startup, before model
credentials are copied into the container. A failed build blocks startup and
retains logs. The worker receives the build/test recipe and is instructed to
rebuild after source edits. Candidate verification independently rebuilds in
its disposable container before functional tests. Original-source reproduction
also rebuilds after restoring original production source and overlaying public
test edits. Build success alone never counts as behavioral evidence.

Model execution gets its own attempt window after preparation, capped by the
remaining global workflow deadline. Preparation still counts toward workflow
elapsed time. On interrupted implementations HX attempts a bounded diagnostic
patch export before container removal. It is untrusted, may include concurrent
writes, is never applied to the host and is never accepted as a candidate. This
is diagnostic preservation, not validated mid-task resume. New scores explicitly
record whether completed-turn usage was observed for every instantiated worker.
An unknown token count must not be described as zero consumption.

## Actual validation

`.hx/worker-environment-v1/report.json` records a credential-free, offline probe
in the exact pinned Svelte 728 image, with worker UID/GID 1000:

- Old preparation reproduced EACCES writing src/generators/dom/shared.ts.
- Repaired preparation and the public build passed.
- All 29 public keyed-block baseline smoke tests passed.
- Tracked source remained clean after build/tests.
- A controlled public-source marker appeared in rebuilt shared.js. This proves
  source-to-artifact connection, not repair of the issue.
- All 88 inventoried historical score files were unchanged. This includes score
  artifacts, not a claim that 88 independent coding trials were completed.
- The diagnostic took 24.59 seconds and made no model calls.

Regression checks: 138 native Linux checks passed, followed by 13 targeted
checks including three additional build-order/startup checks. Windows passed
129 with nine Linux-only skips, followed by all 13 targeted checks. The initial
sandboxed Windows run retained eight Git shared-memory failures; the permitted
rerun passed. Ruff passed for changed runtime, tests and new scripts.

## Bounded development attempt

`.hx/worker-environment-development-v1` freezes the repaired runtime and a new
identity for the already consumed Svelte 728 case. It uses one 6.1 Sol worker,
at most one public-feedback repair, 600 seconds per model attempt, 1800 seconds
per workflow and a three-hour batch deadline. The workflow target is 400,000
reported tokens; the batch allowance is 800,000. Turn-boundary limits can
overshoot and interrupted usage can be unknown.

The original issue's public gist is cached into the task statement for the
offline worker; its source and bytes are recorded. Reference solutions and
private evaluator tests are not included. The original public solution was
previously inspected by the operator, and this case already had an attempt:
this is selected development evidence, never untouched evaluation or a causal
comparison. The larger attempt window is another difference from the old run.

At preparation the account was at 93% primary usage, above the 80% start
threshold. That waiting controller subsequently disappeared and its original
three-hour envelope expired without any native coding identity or score.
`termination.json` preserves this state; the original plan was not extended.

On the user's renewed request to test Svelte 728, a separate batch,
`.hx/worker-environment-development-v2`, started with primary usage at 1%.
It used the same frozen runtime and limits and is now complete. Both batches
preserve old scores and did not redeem credits or buy them.

## Svelte 728 result

The new development candidate **passed the official SWE-PolyBench evaluation**.
All required tests were observed, with no grader infrastructure error and no
candidate patch rejection. Candidate commit:
`4c0ab5292a62a90b8199caabfd8674197e9f42d4`.

- One actual `gpt-6.1-sol` implementer call; no model reviewers or revision.
- The worker's real public preflight build passed.
- HX independently rebuilt and replayed the candidate: 60 tests passed,
  six existing pending tests, zero failures. Public contract coverage passed.
- Original-source replay rebuilt successfully: 51 passed, six pending and
  nine failed report entries. Three are real `ERR_ASSERTION` failures showing
  two displayed items instead of three, four and five. The other six are the
  repository runner's `skipping test, already failed` follow-up entries.
- The conservative public reproduction classifier called that mixed report
  inconclusive. HX therefore recorded `visible_verified=false` and
  `task_success=false`, even though official resolution is true.
- Further model repair was skipped: completed-turn usage reached 480,149
  reported tokens, above the 400,000 workflow target. Usage is known; per-turn
  limits can overshoot. Workflow time was 217.62 seconds, excluding grading
  and other outer-controller work.

The official score is preserved as originally recorded. The workflow attention
flag is not being retroactively cleared. A future classifier repair must
distinguish verified runner follow-up entries from arbitrary non-assertion
errors, retain genuine setup/hook failures, and use a new runtime identity.
No additional model attempt is needed to diagnose this public report issue.

That [classifier repair](SVELTE_CLASSIFIER_REPAIR.md) is now implemented in
version 9. Fresh-container reverification of the exact candidate passes every
public check and records a separate ready_for_approval recovery handoff, with
zero model calls or official regrades. The historical version-8 record remains
unchanged.

`audit.json` verifies the score, actual model call count, all frozen runtime/input
locks and all 88 historical score-file hashes. Score SHA256:
`61f54a32e9156506600b4834a18037b5cc3eeca855a3816e6774aa1737dab372`.
This proves one selected development task can be officially resolved through
the repaired environment; it does not establish general solve-rate improvement
or an unbiased benchmark score.

## Remaining work

This recipe fixes one confirmed environment failure. Other repositories still
need public worker preflights derived from their actual build/runtime contracts.
Checkpoint recovery needs validated replay before it can become candidate
recovery. The existing Sol code-search surface remains primarily diagnostic
extraction; extending it to executable preparation/test mechanisms requires
separate bounded development experiments and independent outcome measurement.

The design follows the environment-bootstrap observation in the
[Meta-Harness paper](https://arxiv.org/html/2603.28052v1), reproducible startup in
[Anthropic's harness guidance](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents),
and explicit startup/reproduction commands in
[mini-SWE-agent](https://mini-swe-agent.com/latest/usage/swebench/).
These are design sources, not evidence of an HX solve-rate improvement.
