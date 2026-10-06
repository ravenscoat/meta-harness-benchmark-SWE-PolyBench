# Directory-based test-body classification

`public-base-regression@9` removes the suffix-only assumption from generated
runtime-exception classification. Actual Mocha Context frames now use the same
`is_test_path` convention as public test projection: suffix-named tests and files
inside `test`, `tests`, `__test__` or `__tests__` directories. Frames must name
JavaScript/TypeScript files. Dependency-tree, traversal and backslash paths are
rejected. Complete structured counts, a matching error message and generated
constructor throw remain required; hooks, setup errors and unknown failures
still fail closed. This change does not establish test relevance or completeness.

Exact model-free offline original-source replays succeeded for both sealed plans:

| Plan | Observed tests | Passes | Runtime failures | Gate |
| --- | ---: | ---: | ---: | --- |
| `test/runtime/missing-data-warning.test.js` | 31 | 23 | 8 | Reproduced |
| `test/missing-property-warnings/index.js` | 27 | 19 | 8 | Reproduced |

The directory plan was inconclusive under @8 and reproduces under @9. Both test
overlay hashes and executed commands match their original attempts. Actual public
builds and unchanged-production-source checks passed in pinned offline containers
as UID1000, without model credentials. Evidence lives under
`.hx/directory-test-classifier-repair-v1`, including `audit.json` and both replay
directories. All113historical score files and original inputs are unchanged.

Validation:67Linux focused checks passed;66Windows passed with one Linux-only
skip; Ruff passed. All108worker compatibility checks and the scripted-worker
fixture passed. The repaired runtime is archived and hash-verified under
`.hx/worker-loop-runtime-v12`; `validation.json` seals this evidence.

Zero model calls, official grader calls or new coding identities were consumed.
Completed benchmark scores remain unchanged. This is a reproduction-gate repair,
not an official Svelte477 solution. Further coding requires a new authorized
identity, runtime locks and quota/budget checks.
