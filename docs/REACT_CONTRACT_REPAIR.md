# React failure reproduction and development repair

MUI 23229 is a consumed development case. Its original Luna benchmark attempt remains an official failure, sealed with SHA256 `9cb7e1b861b488496745502b1104a78d84ab2f019374332ee27a1177df3d873d`. The work below used no coding-worker model calls and does not add a fresh evaluation success.

## What went wrong

Luna changed the root click handler and added a synthetic single-click test. That test passed without establishing that the reported dead zone had disappeared. Even the existing broader suite passed the saved candidate. Separately, an absolute Yarn path exposed a command-lifecycle defect in HX; that harness mechanism was repaired and replayed previously, without changing the failed score.

The first public-source diagnostic here tested mouse-down timing and repeated outline interactions. The saved candidate failed two assertions; a handler repair passed all five focused tests and 105 broader tests, with two pending. However, its separately frozen official development diagnostic still failed: 97 observed passing tests, two observed failures, zero missing required tests and no patch or infrastructure error. That failed approach remains preserved.

The [public upstream PR](https://github.com/mui/material-ui/pull/23229) identifies an invisible clear button occupying the empty input's end-adornment space. The control was hidden with CSS but still rendered, and the component reserved clear-icon layout space. Its rendering condition needed the existing `dirty` state. The case was explicitly marked reference-exposed development evidence before further source repair; it must never be described as fresh heldout evaluation. The public PR conversation was inspected; private reference/test patches were not supplied to a coding worker.

## Final repair

The second repair restores the original input hook and renders the clear control only when clearing has a purpose. It removes the obsolete conditional style/type entry and retains focus/hover visibility for actual clear controls. Production changes are in `Autocomplete.js` and its public type declaration; test changes remain in the full candidate and are excluded from official production delivery by public path conventions.

Five new public regressions all failed the saved Luna implementation. They test empty-value DOM absence, clear-icon layout allocation, selected-value clearing, free-solo typed text, and clearing selected tags when the text input is empty. Hidden-button DOM queries are essential: ordinary accessible-role queries can omit the invisible element. The repaired implementation passes all five.

The full public Autocomplete suite passes **104 tests, with two pending**. The focused tests are included in that count; counts must not be added. Two old empty-value accessibility fixtures were updated to assert one popup button rather than a hidden clear button plus popup. Their popup names/titles, tab order, listbox ownership and input ARIA assertions remain. Populated clear-control behavior is covered separately by the new focused regression.

A helper initially left trailing spaces while removing the worker's misleading test. HX rejected that verification even though the five behavior tests passed. The failed verification, its candidate and helper source are retained. A separate formatting commit and subsequent accessibility-fixture commit leave the production patch byte-identical. The full replay passes whitespace and behavior checks.

## Official development diagnostic

The final production patch was frozen before official grading. It **resolved officially in the development diagnostic**: 99 observed passing tests, zero failures, zero required tests missing, and no candidate-patch or infrastructure error. Grading took 24.83 seconds. No further source changes were made from that feedback.

Final candidate: `385bfb7fe624ff287a303e29e776a8eaef25cf8d`. The private score is sealed with SHA256 `2c2b0c9886557aa81dc22e160ce4dfb85adaea25a8bcefca42a23e3139a09c30`. The [aggregate result](D:/projects/Harness/.hx/react-contract-official-diagnostic-v2/aggregate.json) exposes outcome counts without evaluator test content. This is a reference-informed development pass, not another fresh benchmark success.

## Evidence

- [First public red/green diagnostic](D:/projects/Harness/.hx/react-contract-repair-v1/results.json)
- [Retained first official diagnostic](D:/projects/Harness/.hx/react-contract-official-diagnostic-v1/aggregate.json)
- [Reference exposure record](D:/projects/Harness/.hx/react-contract-reference-analysis-v2/exposure.json)
- [Five failing clear-button regressions](D:/projects/Harness/.hx/react-contract-reference-analysis-v2/red/public_test_1/stdout.txt)
- [Final public replay](D:/projects/Harness/.hx/react-contract-reference-analysis-v2/compatibility-fixture-correction/compatibility/verification.json)
- [Final candidate and production-delivery evidence](D:/projects/Harness/.hx/react-contract-reference-analysis-v2/compatibility-fixture-correction/green-candidate.json)
- [Production patch](D:/projects/Harness/.hx/react-contract-reference-analysis-v2/compatibility-fixture-correction/production.patch)

All 85 indexed historical benchmark scores were checked unchanged during these public replays. The [final integrity audit](D:/projects/Harness/.hx/react-contract-reference-analysis-v2/final-audit.json) also verifies both official diagnostic seals, the saved helper snapshots, unchanged runtime sources and clean original/final candidates. No HX-labelled diagnostic container remained after completion. Official diagnostic results are stored separately, and earlier failed diagnostics are preserved. Public checks run offline in the original pinned image as UID 1000 without model credentials. Mocha's explicit force-exit establishes completed assertions, not resource-cleanup correctness.

## Harness implications

The useful next mechanism was baseline regression replay: run a task-specific public test against the saved/base implementation before treating the candidate's green result as evidence. It is now implemented for bug tasks in the public benchmark adapter as `polybench-public-tests@6`; see [Regression Replay](D:/projects/Harness/docs/REGRESSION_REPLAY.md). For UI bugs, inspect actual rendered interactive targets, hidden DOM and layout conditions; a test that merely encodes the proposed handler change can validate the wrong fix. Red/green remains necessary differential evidence rather than proof of issue completeness. No new model solve-rate result is established by the integration.

Reference-assisted repair is learning evidence, not proof that Luna autonomously solved the case or that HX generally outperforms another harness. The recent fresh benchmark attempts remain LangChain 6765 passed and MUI 23229 failed. Reduce context/usage and freeze the next runtime before testing another genuinely unused task.
