# Saved official failure classified

An aggregate-only diagnostic examined the original Svelte477 scorer result and
independently decoded its saved Mocha JSON report. No test names, assertions,
private test patches, commands or log contents were exposed to model context.
No model or evaluator was run again.

The production patch applied successfully. There was no grader infrastructure
error, patch rejection or missing required-test observation. Of four required
new-behavior tests, two passed and two failed. All 556 required existing-behavior
tests passed. Six unique failed test names were observed overall, four outside
the required scoring sets. The scorer's passed and failed sets exactly match
the independently decoded report.

This establishes the failing scoring category: required new behavior. It rules
out required existing-test regressions, missing required observations, patch
application and JSON parsing as explanations for this particular saved result.
It does not establish which public behavior is missing. The 30-test expanded
public suite still passes, so it does not yet detect that gap.

The raw reporter counts differ from unique-name counts because the pinned
scorer uses test-name sets. Preserve the official definition; do not replace
scoring or interpret the larger raw pass count as task resolution.

Next development work should target public requirements and supported behavior
with independent probes. Private failed assertions and accepted solutions must
remain outside worker/test-author context. Any renewed coding attempt needs a
new identity and sufficient quota; this diagnostic did not launch one.

Evidence: `.hx/svelte477-failure-classification-v1/audit.json` and its lock record
input score/log/dataset hashes. All 115 historical score files remain unchanged.
