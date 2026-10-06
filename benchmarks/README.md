# HX Fullstack Hard v1

An original, synthetic FastAPI + React coding benchmark. These are not copied
SWE-bench or Terminal-Bench tasks, and the results must not be described as scores
on those public benchmarks.

The collection has 12 independently reset Git repositories. Six are available to
the optimizer; six are reserved for evaluation after selecting a policy. All use
a transactional SQLite API and a real React/Vite frontend. The largest tasks
combine backend integrity constraints with asynchronous React state management.

| Search tasks | Reserved tasks |
|---|---|
| Concurrent idempotent creates | Durable replay and ownership isolation |
| Tenant isolation and atomic version preconditions | Transactional deduplicated bulk archive |
| Cursor pagination with timestamp ties | Omitted/null/false PATCH semantics and CAS |
| Query/tenant search races | Editor sessions and typing during save |
| Independent/repeated optimistic mutations | Refresh during pending edits |
| Composite workspace reliability repair | Composite workspace integrity repair |

Tasks specify their behavior openly. Acceptance implementations and reference
solutions stay outside worker repositories. Search acceptance results are available
to Sol as group pass/fail feedback; raw diagnostic logs remain evaluator-only.
Held-out tasks and results are excluded from Sol's copied history. This is logical
separation for trusted local workers, not an OS security boundary against a worker
deliberately searching the host filesystem.

## Prepare and validate

From the project root, install the pinned Node dependencies once:

```powershell
Push-Location benchmarks/fullstack
npm.cmd ci --ignore-scripts --no-audit --no-fund --cache D:/projects/Harness/.hx/npm-cache
Pop-Location
.\.venv\Scripts\python.exe -m hx challenge-suite .hx/challenges-v1
.\.venv\Scripts\python.exe -m hx --config benchmarks/campaign.toml challenge-validate .hx/challenges-v1/manifest.json .hx/validation-v1
```

Validation checks that every seeded case fails its private acceptance checks,
every reference passes them, and every reference passes existing Python tests,
React tests and the production build. These references and checks are AI-authored;
mechanical validation does not replace independent human review.

## Run real model experiments

```powershell
.\.venv\Scripts\python.exe -m hx --config benchmarks/campaign.toml optimize .hx/challenges-v1/manifest.json .hx/experiments-v1 --iterations 2 --repeats 1
```

This command makes real authenticated Codex calls:

1. One-shot Luna on the search tasks.
2. Current HX: Luna implementation, visible verification, two independent Luna
   reviews, Sol consolidation and at most one reviewed revision.
3. Sol inspects search source, scores and raw traces and proposes a declarative
   context policy. Python validates and evaluates it. Repeat for the bounded
   iteration count.
4. Freeze the best full-workflow policy on search success, breaking ties by
   observed tokens. Evaluate one-shot, standard HX and the winner on reserved
   tasks. No tuning occurs after reserved evaluation begins.

Policies can add reusable guidance, an environment snapshot and selected source
files. They cannot change models, budgets, test code, scope checks, review gates or
approval. This is a constrained context-policy search, not the paper's unrestricted
executable harness search.

The configured arms have the same per-task resource ceilings and model reasoning
setting. Their realized compute differs: HX spends on reviewers and revisions.
The report records observed input/output tokens and wall time rather than claiming
equal actual spend. Turn-boundary usage and between-case campaign checks can
overshoot a ceiling by the current operation. There is no hard dollar cap.

`REPORT.md` and `report.json` update after each task. Every trial has source,
configuration fingerprints, prompts, worker events and candidate patches.
Completed scores are reused only with matching task/policy/settings/runtime
identity. Interrupted full-workflow steps use HX's sealed evidence resume;
interrupted one-shot attempts require a new campaign to avoid changing the
baseline protocol. Evaluator interruption can require a new grading directory.

`--repeats 1` is a pilot. Use paired repeats and a larger, independently reviewed
task collection before making general capability claims. Failure, saturation or
regression is a valid outcome; the search does not guarantee improvement.

The first live campaign uses two trials per task. Tasks share one application's
schema and hook interfaces, so reserved results measure new repairs within that
application family, not transfer to unrelated projects. Acceptance exercises the
API and React hooks; it does not establish browser end-to-end behavior. The frozen
v1 repositories retain the initial illustrative UI wiring; the reusable template
now passes `X-Tenant`, unwraps the list response and proxies local API requests.
That later template correction is outside the frozen benchmark and its scores.

## Full-stack workflow outside experiments

A task specification with `frontend: true` enables offline frontend dependency
setup, Vitest and Vite build verification alongside pytest. The target repository
must use the supplied `frontend/package.json` layout and locked dependencies.
Allowed paths must explicitly permit frontend source edits. The existing local
dashboard remains separate from the React target application.

## Use the measured policy on your own task

After a campaign completes, the policy runner loads its frozen selection and keeps
the normal HX evidence, review and exact-commit approval gates:

```powershell
.\.venv\Scripts\python.exe scripts/policy_harness.py .hx/experiments-v1 --state-dir .hx/policy-runs --config hx.toml run path/to/task.json
```

It requires a complete paired reserved comparison and a success gain over standard
HX. If the selected policy has no reserved gain, it refuses automatic adoption.
`--experimental` explicitly permits further evaluation of that policy; it does not
approve or merge the resulting candidate. Use the same campaign and configuration
for subsequent `resume`, `approve` and `deny` commands.

Adoption also refuses quota-interrupted reserved comparisons. The runner verifies
measured policy targets against saved SQLite configuration fingerprints and keeps
those targets. Repair policies affect implementers; the advanced feature extension
also supports supplying guidance and current candidate context to read-only reviewers.

## Campaign supervision

Run a frozen campaign through `scripts/run_campaign.py` to retain controller logs
and stop scheduling after a scored provider-quota failure. For example:

```powershell
.\.venv\Scripts\python.exe scripts/run_campaign.py --timeout 28800 .hx/sync-experiments-v4 -- -m benchmarks.advanced.runner run .hx/sync-experiments-v4 --manifest .hx/sync-features-v7/manifest.json --config benchmarks/advanced/campaign.toml --iterations 2 --repeats 2 --max-tokens 24000000 --max-seconds 28800
```

A file named `stop-after-case` in the experiment directory asks the supervisor to
stop at the next scored case boundary. Remove the file and repeat the same command
to resume. Recorded scores and the original clock persist, including provider
failures. Aggregate envelopes do not change the fixed per-task worker settings.

## Sources consulted

- [Meta-Harness paper](https://arxiv.org/pdf/2603.28052): history-based proposal and evaluation loop.
- [SWE-bench](https://github.com/SWE-bench/SWE-bench): executable patch evaluation and reset environments.
- [Terminal-Bench](https://github.com/harbor-framework/terminal-bench): realistic terminal task environments and verification.
- [React effect documentation](https://react.dev/learn/synchronizing-with-effects): stale response cleanup patterns.
- [Langfuse datasets guidance](https://langfuse.com/docs/evaluation/experiments/datasets): versioned inputs, expected behavior and experiment records.
- [Codex non-interactive documentation](https://developers.openai.com/codex/noninteractive/): structured subprocess integration.
