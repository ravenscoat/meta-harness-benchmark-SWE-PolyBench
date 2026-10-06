# Single-Luna harness

The subsequent [Sol outer loop](HX_META_LOOP.md) adds gated automatic configuration
adoption, completed-result recovery, focused failure excerpts and public fixture
cache handling. That document records both rejected proposals and live failures.

The working checkout now defaults to `workflow = "single"` in `hx.toml`.
One Luna implementer produces a candidate; Python validates it, executes checks,
and sends failed checks back for at most one repair. There are no correctness,
security or Sol calls in this mode. `workflow = "reviewed"` retains the older flow.

This is a new development runtime. Historical experiment roots, scores and
source snapshots retain their original provenance. Completed schedulers must not
be restarted against this changed checkout. The six consumed reserved tasks are
not fresh evaluation data.

## Runtime tools and state

- Automatic repository mapping runs on each implementation workspace. It ranks
  tracked public Python/JS/TS files, extracts bounded symbol outlines, identifies
  nearby tests and declared test scripts, and records `tool.repository_map`.
  It does not execute repository code. Symlinks, gitlinks and known private
  artifacts are omitted. Lexical relevance is a hint, not dependency analysis.
- Patch replay exports a binary-capable Git diff and runs `git apply --check`
  against a fresh original-base clone before verification. The exact delivery
  patch and `tool.patch_replay` event are retained. This checks application to
  HX's sanitized source; it does not guarantee an upstream scorer will accept it.
- Existing FastAPI and React verifiers run independently of the worker. The
  PolyBench adapter replays worker-selected functional commands offline.
  That adapter now accepts installed Mocha/Jest/Vitest entrypoints, including
  `yarn mocha`, `pnpm vitest` and `./node_modules/.bin/mocha`, without adding
  `npx`, dependency installation or shell wrappers to the allowed shapes.
- Git candidate commits, patch hashes, raw logs and cached verification form
  durable checkpoints. Repairs receive at most eight failed-check summaries,
  each capped at 2,000 characters, rather than model review reports.
- A changed test plan can preserve the source candidate and be independently
  replayed. Empty implementations and unchanged no-op revisions stay rejected.
- Approval requires successful executable verification for the exact candidate.
  The handoff explicitly records `reviewed = false`; it does not invent a review.

## Cost choices

The default configuration uses `gpt-6-luna`, one repair and one attempt per step.
The existing 400,000 reported-token guard and command/run deadlines remain.
Usage arrives at turn boundaries, so this is not an exact in-flight spending cap.
Successful first-pass fixtures now use one scripted implementer call rather than
four model-role calls. Actual Luna token savings and solve rates need live evidence.

Run a new task with a separate state directory:

```powershell
.\.venv\Scripts\python.exe -m hx --state-dir .hx\single-luna run .hx\demo\tasks\missing-task.json
```

For an inexpensive runtime smoke check, append `--adapter fake`. The fixture
worker is scripted; passing it proves runtime wiring, not model competence.

## Research informing the changes

[Anthropic's tool design guidance](https://www.anthropic.com/engineering/writing-tools-for-agents)
recommends a few tools aimed at concrete workflows, concise outputs and measuring
actual tool use. [mini-SWE-agent](https://mini-swe-agent.com/latest/) demonstrates
a simple coding-agent control flow. These are design references; published scores
from other models/environments are not comparable HX baselines.

[Official Codex non-interactive documentation](https://developers.openai.com/codex/noninteractive)
describes structured event output used by CLI automation. HX retains those traces.
[Langfuse's evaluation guidance](https://langfuse.com/academy/evaluate/choosing-what-to-evaluate)
informs the distinction between observed task outcomes, workflow completion and
cost. No Langfuse service or paid dependency was added.

## Validation and limits

Initial checks: 47 Windows tests and 74 Linux tests passed across single-worker,
existing workflow, public-command, plan-transition and repository-map behavior.
Linux reported a pytest cache-write warning; all assertions passed. The focused
repair-feedback test and single-mode approval checks passed in a final 12-test
focused run. Ruff passed for changed Python files. All validation used scripted
fixtures and executable checks, with no additional model tokens spent.

This version has not had a live Luna evaluation yet. There is no claim of improved
solve rate. Browser interaction and API exploration tools remain future work;
current React/API checks are the existing executable verifiers. A context map is
generated automatically, but it cannot prove the worker read or used each entry.
