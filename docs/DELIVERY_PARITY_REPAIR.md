# Verify the tree that benchmark delivery actually sends

**Superseded blocking policy:** the Svelte-only gate described below was removed
by `blind-public-challenge@4`; obsolete original expectations are not a reliable
feature gate. See [independent delivery repair](INDEPENDENT_DELIVERY_REPAIR.md)
for the corrected isolation mechanism and subsequent official control results.
The following records the earlier experiment, not current gating behavior.

Public source inspection found that Svelte477's candidate changed the DOM
generator from throwing missing-data errors to logging warnings, and updated
existing runtime tests from error expectations to warning expectations. The
public verifier ran the full candidate. `production_patch` excluded those test
changes from benchmark delivery. These are different trees.

Model-free offline replay of the exact production-only patch confirmed the
public mismatch: the same worker command observed **27 passes and 4 failures**,
all `Expected a runtime error` from the original missing-data fixtures. The
full candidate had passed35tests. The new tests excluded from delivery also
explain why the two command executions selected different counts.

This does **not** prove the official failure's cause. Existing public tests can
encode expectations superseded by a requested feature. No private evaluator
patch, commands or logs were inspected, and no official regrading occurred.
The prior official result stays unresolved.

`public-delivery-parity@1` replays the exact production projection in a separate
offline container as UID1000, resolves commands against original public
manifests, rebuilds source, verifies changed paths equal the delivery projection
and rejects tracked-source mutation. Public reports and patch hashes are saved.

`blind-public-challenge@3` applies this guard to the validated Svelte environment
when existing test files were changed. A failed projection check blocks a green
handoff even if worker and immutable independent tests pass. Feedback includes
the public mismatch and explicitly warns against restoring obsolete behavior
solely to satisfy old tests. Other repository environments are not covered by
this initial guard. A conflict may need diagnosis beyond the current one-repair
budget; it is not automatically evidence of incorrect requested behavior.

Evidence: `.hx/svelte477-delivery-parity-v1/audit.json` and
`replay/delivery-parity.json`. All115historical score files are unchanged; zero
model calls, new task attempts or official grader calls were spent.25focused
Linux and25Windows checks passed, including a transition test proving delivery
mismatch blocks two otherwise-green check sets. The initial sandboxed Windows
run had23passes/2Git shared-memory startup failures; evidence is retained and
the permitted rerun passed. All108worker compatibility checks and the scripted
fixture passed. Runtime-v13 is archived/hash-verified for future experiments;
old benchmark identities are never resumed or overwritten. `validation.json`
seals the native validation and source/archive hashes. No new model trial ran.
