# Executed generated-component runtime exceptions

The completed Svelte477 attempt stopped before implementation because the public
base-reproduction classifier recognized assertion failures but missed exceptions
thrown by generated application constructors inside test bodies.

`public-base-regression@8` recognizes this narrow pattern: a matching structured
Error/TypeError/RangeError message, a top generated-constructor throw frame, an
actual Mocha Context frame in a conventional test file, and complete consistent
test/pass/failure/pending counts. Hooks, compile/loader errors, mismatched messages,
missing counts, test-only throws and mixed unknown failures remain rejected.
Existing setup, timeout and oversized-report handling remains active. This does
not classify arbitrary runtime errors or establish issue relevance.

Model-free actual replay used the exact sealed test-author patch and command on
the pinned offline original-source Svelte image as UID1000. It rebuilt source and
observed **31 tests: 23 passed, 8 missing-data runtime failures, 0 pending**. The
reproduction gate now accepts these observed failures instead of returning
inconclusive. The overlay hash matches the original run; production source was
unchanged. Evidence: `.hx/runtime-exception-classifier-repair-v1/audit.json` and
`actual-replay/regression.json`.

Validation: 55 focused Linux tests passed; Windows passed 54 with one Linux-only
skip. All108 worker-loop compatibility checks and the scripted-worker fixture
passed; the repaired runtime is archived under `.hx/worker-loop-runtime-v11`.
These compatibility checks are not model coding-performance evidence.
Ruff passed. The first replay launcher lacked the project import path;
its startup failure was retained and the corrected launcher executed the replay.
All **112 historical score files** and original input artifacts remain unchanged.
Zero model calls, new coding attempts or official grader calls were made.

The old coding attempt remains completed and unmodified. This repairs the
reproduction mechanism; it does not solve Svelte477 or establish an official
benchmark pass. A future coding run needs a new identity and budget/quota checks.
