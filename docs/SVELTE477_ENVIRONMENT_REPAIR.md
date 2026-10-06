# Svelte477 worker environment repair

Svelte477 stopped in the three-question batch before any model call because the
worker supported only `node src/shared/_build.js && rollup -c`. Its public source
uses `npm run build:main && npm run build:shared && npm run build:ssr` instead.
The original scored failure is retained; no task identity was resumed or replaced.

`worker_environment.recipe` now recognizes this second, exact public layout as
`svelte-public-build@2-legacy-rollup`. It requires all three exact Rollup script
entries and their existing config files. Generated outputs are only `compiler`,
`ssr` and `shared.js`; the newer recipe's generated TypeScript file is omitted.
The existing tracked-path, ignored-path, symlink, archive and ownership protections
continue to apply. Other layouts and substituted arbitrary subcommands still fail
closed. Worker, candidate and original-source public replay share this preparation.

## Actual verification

- 71 native Linux recipe, ownership, report-capture and public-command checks passed;
  Ruff passed.
- The old recipe's unsupported-layout error was reproduced from the preserved
  pre-repair module on the exact original source.
- The actual pinned Svelte477 image built all three outputs offline as UID1000,
  with no CLI or credential mounts. Its existing public parser suite passed all
  59 tests, with zero failures or pending tests.
- Tracked source stayed clean before a controlled disposable-container probe.
  An added public export was rebuilt into `shared.js`, proving source-to-artifact
  freshness. The input base repository was not modified.
- All 111 historical score files checked by the diagnostic kept their hashes,
  including nested parallel task scores and official scorer records.
- Zero model calls or official grader calls were made. This is environment and
  mechanism evidence, not a new Svelte coding success or benchmark resolution.

Evidence: `.hx/svelte477-environment-repair-v1/report.json`, build/test/rebuild
logs, original module snapshot, historical-score lock and final audit. The new
worker compatibility archive under `.hx/worker-loop-runtime-v10` passed all108
compatibility checks and the real scripted-worker fixture, with zero model calls.
Any future model experiment must select the new archive and create new locks;
old completed schedulers and identities remain closed.
