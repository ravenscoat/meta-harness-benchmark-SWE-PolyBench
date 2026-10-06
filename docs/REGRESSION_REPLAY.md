# Independent reproduction gate

The public benchmark adapter now uses `polybench-public-tests@6`. A bug candidate must pass its public checks and then establish a recognized behavioral failure when the same public tests run against original production code. This is an executable verifier change, with no additional worker, reviewer or Sol call.

The original benchmark scores and runtime snapshots remain unchanged. Old frozen campaigns must not resume against this development runtime; a future model attempt needs a new root and source fingerprint.

## Execution

The candidate runs in the existing credential-free public verification container. If its checks fail, base replay is deferred and ordinary bounded repair receives the failed candidate evidence. If they pass, that container is removed before the independent base container starts, avoiding concurrent memory allocation.

The base container uses the same pinned image and public dependency preparation. HX restores the original commit and overlays only regular files classified as public tests by existing path conventions. Production changes are absent. The patch is bounded to 50 files and two MB; symlinks/gitlinks and unsafe paths are rejected. The existing command whitelist, argv normalization, three-command maximum, verification timeouts and workflow cancellation/deadline controls apply. The container runs tests offline as UID 1000 without model credentials and is removed even on cancellation.

A source-tree comparison detects tracked or nonignored source changes made during the base test run. Ignored runtime outputs remain outside this comparison. Known package-script changes outside test paths are not overlaid; commands that therefore cannot start are inconclusive/setup evidence, not reproduction.

## Interpretation

At least one base command must show recognized behavioral test failure, and every other base command must show recognized test execution passing or failing behaviorally. Candidate commands must all pass separately.

The bounded parser recognizes common pytest test-failure summaries, Mocha assertion failures, Jest/Vitest assertion summaries and Node assertion output. Collection/import errors, hooks, syntax/setup errors, timeouts, empty test runs, unknown output and source mutation cannot establish reproduction. Unrecognized legitimate failures may require a clearer focused assertion or supported runner output. This is intentionally conservative; it is not a universal runner parser.

**Red/green does not prove issue completeness or relevance.** A contrived or unrelated assertion can also distinguish two versions. Worker-authored tests and their output remain untrusted; this mechanism does not provide adversarial test attestation. Independent official evaluation stays separate. UI tests must inspect the actual interactive target, hidden DOM/layout state and related transitions instead of merely exercising a proposed handler. The limitation is recorded in successful verification and worker guidance.

Feature tasks retain their existing verification path. The new mandatory gate applies to bug tasks in the PolyBench adapter; the native FastAPI verifier is unchanged.

## Observed validation

| Saved public candidate | Candidate public checks | Base replay | New gate |
| --- | --- | --- | --- |
| LangChain 6765 original successful candidate | Three tests passed | One test failed, two passed | Pass |
| MUI 23229 reference-informed development repair | Five focused tests passed | Five assertion failures | Pass |
| MUI 23229 original Luna candidate | Its one selected test passed | Element-lookup failure without recognized assertion evidence | Blocked as inconclusive |

The last row does not mean HX independently discovered the hidden clear-button root cause. Its parser rejected insufficiently classified reproduction evidence. An explicit but incomplete proxy assertion could still pass; that limitation has a regression test.

All three probes used the actual pinned worker dependency containers, the same candidate/source identities and no model or private-grader calls. No benchmark was rescored. The [probe results](D:/projects/Harness/.hx/regression-replay-runtime-v1/probes/results.json) preserve raw public commands and results; [completion audit](D:/projects/Harness/.hx/regression-replay-runtime-v1/probes/completion-audit.json) verifies all 85 historical scores and unchanged protocol sources during replay. This is development mechanism evidence, not a fresh solve-rate measurement.

The replay/command/delivery suite passed 76 Windows checks with one symlink skip, and 77 native Linux checks including that symlink case. Ruff passed. The first Windows fixture run had a CRLF mismatch in the test helper; its fixture now sets Git's `core.autocrlf=false`, matching the native byte-preserving path. A Linux pytest cache warning did not affect the 77 passed checks. The probe helper's final audit initially failed on Windows-relative backslash paths under Linux; all three real replay outcomes had completed. That audit error is retained, its path normalization corrected, and an independent completion audit finished without rerunning any probe.

The console labels base command exits as awaiting classification, then shows reproduction `PASS` or `BLOCKED`. An expected base assertion failure is not presented as an overall workflow failure before classification. Console/single-workflow validation passed 19 Windows checks; the seven console checks also passed on native Linux. Across these separate suites, validation is 95 Windows passed with one symlink skip and 84 Linux passed.

Implementation: [regression.py](D:/projects/Harness/benchmarks/polybench/regression.py), [verifier integration](D:/projects/Harness/benchmarks/polybench/engine.py), [tests](D:/projects/Harness/tests/test_polybench_regression.py). Before/after protocol snapshots and the source lock are in `.hx/regression-replay-runtime-v1`.

A separately frozen fresh model evaluation has now completed on Transformers
26164. The new gate reproduced a real output-length regression and the candidate
passed its public checks, but official resolution failed with every required
test observed and no patch/grader infrastructure error. This is direct evidence
that red/green reproduction is insufficient for task completeness. See
[Fresh gate evaluation](D:/projects/Harness/docs/REGRESSION_GATE_EVALUATION.md).
The saved development probes and this one fresh selected task do not establish
an improvement to Luna's general solve rate or guarantee future benchmark passes.
