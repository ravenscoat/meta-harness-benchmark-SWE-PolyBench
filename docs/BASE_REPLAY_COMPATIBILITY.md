# Svelte base-replay compatibility repair

`public-base-regression@10` inventories the original Git tree before reading the
optional legacy `test/runtime/index.js` runner. Missing files and nonregular
entries skip that narrow attestation policy. Genuine Git/container errors still
raise; unknown runner bytes and modified active runners remain unattested.
No setup error or followup skip is counted as a behavioral regression.

Validation: 61 Linux checks; 60 Windows checks and one symlink skip covered on
Linux; Ruff passed. The first test invocation named a nonexistent test module
and ran no tests; the corrected runs above completed.

Actual offline UID1000 replay under `.hx/base-replay-compatibility-v1` used the
saved Svelte7422 public tests with original production source. Both commands
executed after the build, with no model or official grader calls. Key-block:
36 tests, 33 passed, one reference-inequality assertion and two followup skips
failed. Component-slot: 189/189 passed. The mixed assertion/skip report remains
**inconclusive**, not a passing regression receipt: the newer TypeScript runner
is not covered by the legacy followup attestation policy. Broader compatibility
support needs its own attestation and negative tests; the gate stays closed.

All 129 historical score-file hashes verified unchanged (file count includes
aggregate scorer records, not 129 distinct tasks). Svelte7422's official pass
and failed workflow remain sealed. This replay demonstrates repair of the
missing-file execution failure only; it does not overwrite the old score or
establish causal accuracy improvement.
