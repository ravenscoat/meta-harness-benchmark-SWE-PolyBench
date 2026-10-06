# Frozen-runtime transfer blocker

The reduced campaign stopped at 14/51 scored trials. The first Prettier Luna-alone
run failed before model work because the frozen transfer code invokes `python`,
while the pinned image provides `/usr/bin/python3` without a `python` alias.
This is an infrastructure failure with zero reported model tokens, not evidence
of a coding failure. Its scored result and raw evidence remain intact.

A proposed shell-based transfer correction is saved separately under
`.hx/polybench-v1/experiments/runtime-amendment-proposal/portable-transfer.patch`.
The frozen runtime and source lock have not been modified. A model-free test in
the actual pinned Prettier image passed exact source-tree transfer, clean status,
and staging as UID1000. Evidence is in that directory's `check.json`.

The user approved a runtime amendment to continue the remaining
37 trials without rerunning, excluding, or replacing any scored result. The
final report must disclose the version boundary and the infrastructure failure.
The original runtime snapshot, source lock, scope amendment and aggregate report
were preserved before establishing the amended lock. Original envelope start,
limits, dataset, selection, scorer and task budgets remain unchanged.
`experiments/runtime-amendment-1.json` records authorization, both source hashes,
the version boundary and hashes for all 14 retained scores. The original snapshot
is `runtime-source`; the amended snapshot is `runtime-source-amendment-1`.
All untouched evaluation arms will use this same amended runtime. The Prettier
459 single/full pair cannot establish a fair coding advantage because its single
run failed on infrastructure before this correction; report that separately.

Four matched development Keras cases are complete: HX resolved 2/4 and Luna alone
1/4. One HX-only success corresponds to a rejected Luna patch. This is limited
development evidence; no Sol-tuned or untouched evaluation comparison exists yet.
