# Executable worker-loop search

HX now has an opt-in executable scaffold around its worker calls. This extends
the existing code-search command using the official Meta-Harness repository's
pattern of code candidates, archived experience and external execution gates.
It is not a replacement for Codex CLI's internal agent or an accuracy claim.

## What the candidate controls

`next_action(state)` selects bounded public repository inspection, worker calls,
optional source-context omission, namespaced guidance and phase-local memory.
HX permits at most two inspections, two delegate calls and five actions per
phase. The default scaffold delegates once. Roles other than implementer retain
their existing adapter. Model selection remains in the experiment settings.

The candidate cannot remove the task, independent challenge or verification
contract, change the official evaluator, access credentials, raise budgets or
accept its own result. Calls share the model-attempt deadline and enforce token
headroom. HX validates each worker result against the original output schema.
Finish requires a completed worker result; external verification still decides
readiness. State is reset between phases and tasks.

Scaffold code runs in a fresh isolated Python subprocess with bounded inputs,
outputs and time, and Linux CPU/memory limits. Its source hash is checked on each
decision. AST restrictions reject filesystem/network/reflection capabilities;
this restricted policy interface is not a general sandbox for arbitrary code.

## Recorded search outcome

One `gpt-6.1-sol` proposal was run in an isolated offline carrier repository,
with explicitly exported public development traces. The 60,000-token target
was checked at turn boundaries: the completed turn reported 236,297 tokens.
The budget guard stopped the proposal and its original failure is preserved in
`.hx/worker-loop-search-v1`. No model retry or benchmark task was run.

A separate zero-model recovery extracted the complete source from the logged,
successful `cat candidate_scaffold.py` command. Its SHA256 is
`7160bf5950a799266b330115b1c2a530c99c71a859df605447339bd56bcec3db`.
The original interrupted container export failed; recovery therefore does not
establish whole-workspace integrity for the original proposal.

The recovered policy performs one focused repository inspection before one
worker call and removes duplicate optional inventories when useful matches
exist. It passed a real FastAPI fixture with a scripted worker and independent
verification. Compatibility revalidations use separate immutable roots;
`worker-loop-runtime-v6` is the final current-runtime validation identity.
Eligibility means it may be selected for a new experiment, not that it improved
coding accuracy. All 101 historical coding scores are preserved.

Interrupted draft cleanup now uses the worker's public HOME, narrow Git safety
configuration and a shared 30-second cleanup deadline. Diagnostic staging and
export exclude root/nested node_modules, .venv and Python cache artifacts.
For the optimizer, export is further restricted to its one editable file,
`candidate_scaffold.py`; carrier lockfiles are excluded by that exact scope.
Drafts remain unaccepted and never get applied to the host. Failed probes v1–v5
are retained separately from the final v6 actual-container probe, which passed
as UID1000, offline, with the host source unchanged and zero model/grader calls.
Final Windows worker-loop/environment checks: 34 passed. Earlier broader Windows
and Linux compatibility checks: 112 passed on each platform; final Linux gates
passed 107 checks and are recorded in the sealed v6 runtime archive. Archive
integrity and current-runtime hashes were verified again before selection into
`.hx/worker-loop-selection-v1`, a diagnostic root with no coding task execution.

## Usage and evidence boundary

Run a new search with `python -m scripts.run_code_search --surface worker-loop
NEW_ROOT`. The default `--surface evidence` retains the older evidence-tool
search. Zero-model revalidation uses `--surface worker-loop --finalize-loop
RECOVERED_ROOT NEW_VALIDATION_ROOT`.

`scripts.worker_scaffold_search.select_for_experiment` selects an eligible,
hash-matching candidate into a new unfrozen experiment. The runner locks both
`worker-scaffold.py` and its selection lock. Selection fails if runtime hashes
have changed or the experiment is already frozen. Existing experiment roots
remain unchanged and their old schedulers stay stopped.

The next performance measurement must use a new explicitly bounded task
experiment. Keep a fixed worker model, record actual calls/tools/test execution,
official outcomes and token/time cost, and distinguish command compatibility
from coding quality. No official-grader success or benchmark improvement was
measured by this implementation turn. No automatic performance promotion was
made, and no more model work should start without checking account limits.
