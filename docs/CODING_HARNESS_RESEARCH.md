# Coding harness infrastructure review

Reviewed 2026-10-05 after batch-reliability-v1 completed. Research only: no
new model calls, installations, benchmark identities or runtime changes.

## Primary sources

- Harbor: https://github.com/harbor-framework/harbor
- Harbor Codex adapter: https://github.com/harbor-framework/harbor/blob/main/src/harbor/agents/installed/codex.py
- mini-SWE-agent loop: https://github.com/SWE-agent/mini-swe-agent/blob/main/src/minisweagent/agents/default.py
- mini-SWE-agent evaluation: https://mini-swe-agent.com/latest/usage/swebench/
- Official SWE-bench scorer: https://github.com/SWE-bench/SWE-bench
- Meta-Harness onboarding: https://github.com/stanford-iris-lab/meta-harness/blob/main/ONBOARDING.md
- Codex event-based eval guidance: https://developers.openai.com/blog/eval-skills

Harbor explicitly supports Codex CLI, runs agents in environments, retains
trajectories, and its adapter supports native session resume. Its metrics separate
prompt, completion and cached tokens. It is a useful adapter reference; it is not
the official scorer for HX's pinned SWE-PolyBench campaign. Adopting it would
require a compatibility bridge that preserves original scoring and task inputs.

mini-SWE-agent separates agent, model and environment with a small query/action
loop and saved trajectories. Its default agent exposes cost, step, time and
consecutive-format-error limits. Cost limits are checked before calls and may
overshoot; copying this does not produce a hard provider-side spending ceiling.
It is an architectural reference, not a Codex CLI drop-in.

Meta-Harness belongs outside the task solver: generate executable candidates,
evaluate development outcomes and costs, retain failures, then freeze selection
before final evaluation. It does not guarantee cheap search or task correctness.

## Concrete HX evidence

The latest batch used 1768154 reported tokens: one official solve, one observed
official failure and one pre-implementation reproduction-gate stop. MUI34207's
230762 tokens were spent without implementation starting. Saved public replay
recorded 48 tests, 32 passes, 11 failures and five pending, yet classification was
inconclusive. The exact classifier cause needs public-log diagnosis; do not assume
all failures are valid issue regressions or weaken the acceptance gate blindly.

`src/hx/adapters.py` declares mid_task_resume false and reports input plus output
as aggregate tokens while retaining raw usage. These aggregates are not dollar
costs or unique context tokens; repeated and cached inputs must be broken out.

## Proposed next version

1. Extract per-role and per-call raw usage from existing public trajectories;
   report input, cached input, output, call count and time separately. Keep unknown
   usage explicit; do not infer actual dollars from subscription quota percentages.
2. Implement one task-local persistent Codex implementer session with a bounded
   public-feedback continuation, preserving session/workspace identity and logs.
   Different tasks and blind authors must never share sessions.
3. Make blind test authoring an optional development configuration. A failure to
   reproduce a bug should be recorded as insufficient evidence, not necessarily
   prevent a separately authorized solver from producing a candidate. Independent
   delivery replay and official results remain separate and unchanged.
4. Reuse pinned verified environment preparations; key any public-result cache by
   exact source tree, production patch, test overlay, command, environment/image,
   tool version and relevant configuration. Never cache across changed artifacts.
5. Replace proliferating experiment-specific schedulers with a common tested
   orchestration interface when practical; preserve historical runners and locks.
6. Use a small consumed development set to evaluate this simpler candidate at the
   same model/settings/budget, with cost and operational outcomes alongside official
   resolution. No full 382-task launch before this evidence exists.
7. Only then introduce the Meta-Harness proposer to search one executable
   mechanism at a time, with strict scope and budget and heldout separation.

These are proposed changes, not implemented repairs or demonstrated savings.
