# Bounded batch image retention and digest-pull diagnostics

Repair follows the stopped `.hx/lean-reliability-three-v2` batch. No old result,
input, stop record or original envelope is replaced or resumed.

`batch-image-lifecycle@2` adds an opt-in `image-retention.json` input for exactly
the selected batch cases, at most three. `run_lean_three` records it before
preflight and seals it in the plan. Cache trimming honors those retained image
IDs through reference checks, worker checks and coding. The existing disk-space
guard and protections for unrelated tags and live/stopped containers remain.
Campaigns without this policy retain their previous bounded sequential cache.

Pinned digest reacquisition now consumes Docker's decoded pull stream, records
all events and fails on registry errors. It then inspects the pinned image ID,
checking exact identity before aliasing; it does not depend on the SDK's final
lookup of a digest alias. No mutable-tag fallback or image substitution added.

Twenty focused retention, digest-error, identity, batch and worker-isolation
checks passed on Linux and permitted Windows execution. Ruff passed. The first
sandboxed Windows compatibility run hit the existing Git shared-memory sandbox
restriction; its permitted rerun passed and evidence remains in the transcript.

Public GHCR manifest probe returned HTTP200 for the recorded MUI digest and
original tag, with identical manifest digest. No model authentication was used
or token printed. This confirms registry pin validity, not local pull success.

Actual model-free validation is in `.hx/image-lifecycle-repair-v1`. Initial
digest probe session62741/PID599 is active; lifecycle validation session91557/
PID801 waits for it rather than duplicating its pull. Both identities must be
checked against actual process inventory. After loading all images, validation
checks each image remains available across repeated stage transitions and
exercises all three real offline UID1000 worker environments. Its fixed
30-minute deadline and source fingerprints are recorded. Zero model/official
coding calls; no new batch has been launched. Actual validation is pending.

Completion requires audit.json with real receipts and all historical score
hashes unchanged, or preserved validation-failure.json. Do not call this a
successful coding benchmark or completed real-environment repair before that
evidence exists.

## Completed validation

The exact MUI digest pull completed successfully with 76,564 saved progress
events and no pull error. Local inspection by image ID and digest both matched
the pin. The original mutable tag was absent, which is expected after pulling
by digest and is not treated as changed image content. The original stopped
batch's failed SDK reacquisition remains preserved; its deeper transient error
is not retrospectively claimed as reproduced.

First validation preserved a real additional failure: Svelte1376 uses public
Svelte2.2 `node src/shared/_build.js && rollup -c && rollup -c rollup.store.config.js`,
which had no worker recipe. All first helpers exited before the next repair.
`svelte-public-build@4-rollup-store` now requires that exact command, version2
and the compiler/shared/SSR/store source/config files. It clears and rebuilds
only ignored outputs: compiler, ssr, shared.js, src/compile/shared.ts and
store.umd.js; tracked-source and symlink protections remain.

New `.hx/image-lifecycle-repair-v2` preserves the prior failure by hash.
**All three actual offline UID1000 worker preparation checks passed**: MUI42412,
Svelte1376 and Serverless8159. Svelte's real compiler/SSR/shared/store build
passed; MUI/Serverless checks exercised installed test-runner dependencies and
writable clean source (no extra build recipe configured for those families).
All three pinned images remained inspectable through repeated worker and
coding-admission image-check stages. Forty checks passed on each platform and
Ruff passed. All129 historical score-file hashes, the stopped batch's original
plan/stop and repair source hashes verified unchanged. Source snapshots, audit
and final-validation seals are saved. No model or official coding calls.

The repair is complete as image lifecycle/worker preparation evidence, not as
new benchmark task success. No new coding batch launched or old root resumed.
Helpers exited; monitoring removed.
