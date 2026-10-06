# Worker preflight and public requirement repair

Implemented after the completed lean-three batch, preserving all recorded scores.
No new model or official grading calls were made for this repair.

## Changes

- `svelte-public-build@3-rollup-typescript` recognizes the saved Svelte3 public
  `rollup -c && npm run tsd` build only with exact declaration-generation stages
  and required compiler/runtime files. The explicit generated-output list is
  cleared and ownership staged as before; tracked paths and symlinks still fail.
- `public-contract-coverage@3` excludes HTML issue-template comments and fenced
  or single-backtick code blocks from expected-behavior requirements. Visible
  behavior and inline code remain. The eight-requirement limit still fails closed.
  The original public issue hash remains recorded; no private grader content used.
- Future `run_lean_three` roots exercise actual offline worker population, build,
  public test manifest, Mocha dependency, UID1000 writable workspace and clean
  tracked source for ALL tasks before coding. A failed preparation receipt stops
  model admission. Reference-image validation alone is no longer sufficient.
  This dependency smoke is scoped to these Node/Mocha repository families; it is
  not a universal Python/browser environment validator.

## Validation and retained failures

41 focused Windows and41 native-ext4 Linux tests passed; Ruff passed. Checks cover
the narrow build signature, unsupported layouts, cleanup after population failure,
commented headings, single-backtick code, meaningful requirement preservation,
coverage overflow, and existing build/coverage behavior. Initial test insertion
errors were corrected; the Windows sandbox Git permission failure was retained
and the permitted run passed. Separate Windows session/protocol/independent-challenge
compatibility checks passed34 tests.
The same34 compatibility checks passed on native Linux. Together the focused and
compatibility suites passed75 checks per platform. Final hashes, validation and
complete changed-source archive are in the v2 root's `final-validation.json` and
`complete-source` directory; no model work was spent on these checks.

Actual offline UID1000 Svelte7422 preflight PASSED. In a separate disposable source
clone, generated compiler VERSION matched `3.46.6-hx-source-marker`, establishing
source-to-artifact freshness. Three public source-unit tests and115 parser tests
passed with explicitly bounded Mocha commands, named JSON output and unchanged
tracked source. These are mechanism tests, not a Svelte coding/official success.
The original pinned source and all benchmark inputs remain unchanged.

The first diagnostic's `npm run test:unit` also loaded broader `test/test.ts`
through `.mocharc.js` and failed. Its failure/tail is retained under
`.hx/worker-parser-repair-v1`; it is NOT counted as a passing full-suite run. Its
precise behavioral failures were not diagnosed, and the helper did not retain
the complete failing output. The separate bounded v2 diagnostic records complete
stdout/stderr, command results and source marker under
`.hx/worker-parser-repair-v2`. No full-suite correctness claim is made.

The saved MUI issue now produces3 visible requirements with no inventory overflow,
hidden template instructions or code delimiters. This does not retroactively turn
the old workflow green or prove semantic completeness of tests.

127 retained score-file hashes were verified unchanged (including aggregate grader
score files; this count is not distinct benchmark tasks). Source snapshots and
locks are preserved under both diagnostic roots. No changes to official scorer,
accepted solutions, dataset, images or sealed scores. The old Svelte attempt still
records its zero-token worker setup failure. A future model attempt requires a
new identity and must be reported separately.
