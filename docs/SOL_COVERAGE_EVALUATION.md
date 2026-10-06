# One official task with 6.1 Sol

The user authorized a single diagnostic with 6.1 Sol after discussing a stronger
worker. The coding runtime is frozen as `polybench-public-tests@7`, including
the validated public contract coverage gate. This is a new experiment identity:
`.hx/sol-coverage-evaluation-v1`.

The metadata-selected task is `sveltejs__svelte-728`, the first unused Bug Fix
evaluation case in the original pinned selection. Prior scores, exposure records
and interrupted identities are excluded without filtering by outcomes. The task
uses its original validated environment and official SWE-PolyBench scorer.

Worker: `gpt-6.1-sol`, medium reasoning, single-worker workflow, no separate
reviewer calls. At most one repair and one attempt per step. The existing 400,000
reported-token workflow target and 600,000 batch allowance are checked at turn
boundaries and may overshoot. The new experiment has a three-hour deadline;
account checks precede model work, with no purchases or reset-credit redemption.

Status: complete, with an implementation timeout and no accepted candidate.
The single Sol call ran out of its attempt window after 236.747 seconds;
workflow time was 245.21 seconds, total wall time 466.04 seconds. No repair,
coverage verification or official grading ran. Official resolution is false in
the preserved score because no candidate was delivered, not because official
tests demonstrated incorrect behavior. A zero unobserved-test count in this
no-candidate path does not establish that tests ran.

The CLI supplied no completed-turn token total before timing out. Recorded usage
is zero, but actual consumption is unknown and must not be advertised as free.
`audit.json` confirms one actual 6.1 Sol implementer call, no official grader
call, all 87 prior score files unchanged and frozen sources/inputs unchanged.

Public trace observations: Sol inspected keyed-block and binding source, created
a regression sample, iterated fixture expectations, and obtained a public failure
showing only two of four expected keyed items. A build command also failed with
`EACCES` writing `shared.js`, a pre-existing image-owned generated file. The
attempt ended before an implementation artifact was accepted. This trace does
not isolate how much the build-permission problem versus the time limit affected
the result, or show that changing models solves the harness's problems.

Next development priority: independently validate public build/test preparation
and generated-artifact permissions before another model attempt. Preserve this
scored timeout; any future development retry needs a separate identity and must
not be described as fresh heldout evaluation on Svelte 728.

Evidence: `batch-plan.json`, `settings.toml`, `experiments/source-lock.json`,
`quota.json`, `results.json` and subsequent score/audit files in the experiment
root. The scheduler is `scripts/run_sol_coverage_benchmark.py`; old schedulers
and old score identities remain separate.

One different task cannot isolate model effects from task difficulty. There is
no paired Luna result on this task, no causal harness-improvement claim and no
leaderboard claim. Public coverage mapping does not prove assertion semantics.
