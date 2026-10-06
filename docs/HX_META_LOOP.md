# Sol outer loop and Luna worker

The newer [paper-based code-search loop](META_HARNESS_PAPER.md) adds executable
tool proposals and filesystem access to public history. The configuration-only
loop described below remains available and its historical outcomes are intact.

The current development runtime uses one `gpt-6-luna` implementer. A separate
`gpt-6.1-sol` call analyzes a batch of public failure evidence and proposes bounded
runtime settings. Python validates the proposal, runs regressions and a real
FastAPI fixture using a scripted adapter, then adopts the configuration without
asking for routine human approval. The meta call is outside the task loop.

Sol currently controls three executable knobs: repository matches (3–8), failed
check excerpt size (800–2,500 characters), and minimum reported-token headroom
before another model call (5,000–80,000). It cannot disable verification, change
grading, increase budgets or replace task results. These controls are enforced
in Python. Acceptance is a compatibility gate, not proof of better solve rates.

## Improvements from observed failures

1. Completed candidates can be validated and independently tested after a
   final-turn token overrun. Further model calls remain gated by headroom. A
   failed candidate is retained with a `needs_attention` handoff when repair
   cannot be afforded. This does not enforce an exact in-flight token cap.
2. Local Codex CLI shutdown timeouts can recover an already completed,
   schema-valid final result. A timeout without a completed-turn event or valid
   result remains a failure. This recovery is in the local CLI adapter; it is
   not claimed as validated recovery for the Docker adapter.
3. Failure excerpts preserve traceback and error lines before warning noise.
   Raw logs remain available. Compact context still cannot prove test coverage.
4. Public tokenizer preparation now copies only the named public Idefics cache
   into the UID-1000 home. Public verifier containers prepare dependencies before
   receiving candidate source, then disconnect networks before test execution.
   Missing caches raise an operational error. No model credentials are provided
   to these verification containers. This change has regression validation;
   no new real Transformers task trial was run to demonstrate the cache repair.
5. React checks resolve native Linux npm's JS entrypoint, including Ubuntu's
   `/usr/share/nodejs` layout, and avoid a Windows `npm.cmd` inherited through
   WSL's PATH.

## Sol proposal attempts

- `.hx/meta-single-v1`: retained zero-token CLI startup failure.
- `.hx/meta-single-v2`: Sol used 14,293 reported tokens. Its rationale requested
  8,000 feedback characters while its executable value was 800. The initial
  compatibility gate accepted it; the discrepancy was subsequently identified,
  recorded in `rollback.json`, and the configuration restored. The adoption
  record remains preserved, rather than being rewritten as a rejection.
- `.hx/meta-single-v3`: Sol used 14,628 tokens. The new consistency gate rejected
  another numeric contradiction; no configuration was adopted.
- `.hx/meta-single-v4`: Sol used 14,756 tokens. Its consistent proposal passed
  57 regressions and an independent FastAPI fixture. It was automatically adopted:
  five repository matches, 2,500 feedback characters, 60,000 minimum headroom.

Sol's three nonzero proposals cost 43,677 reported tokens. Runtime checks are
still necessary: schema-valid model output can contradict its own rationale.
The numeric consistency check covers explicit feedback-from/to assertions; it
does not generally prove that all natural-language reasoning is correct.

## Live evidence

One new selected local FastAPI Luna smoke attempt was run with a 120-second
worker deadline and a 120,000 reported-token threshold. It reported 172,656
tokens (134,656 cached input tokens are already included), made the correct
404 change and wrote a valid final result, then hit the CLI shutdown deadline.
Its original outcome remains `failed` in `.hx/single-luna-live-v1/result.json`.
The overshoot illustrates why final-turn reporting is not a precise spend cap.

A separate **model-free** replay in `.hx/single-luna-replay-v1/recovery.json`
applied that preserved patch to a fresh workspace and passed independent FastAPI
tests and acceptance, reaching `ready_for_approval`. It seals the original failed
result hash. This supports the recovery mechanism and the candidate's behavior;
it is not a replacement score or a new model solve. Total new reported model
usage for this work was 216,333 tokens. No credits were purchased or redeemed.

## Running the outer loop

The runner checks account quota first, uses an ephemeral native authentication
home, removes it afterwards, and refuses to overwrite an existing attempt.
Use a new experiment root each time:

```bash
wsl -d Ubuntu -u root --cd /mnt/d/projects/Harness -- \
  /opt/hx-polybench-venv/bin/python -m scripts.run_meta_review \
  .hx/meta-next --state-dir /opt/hx-polybench-runtime/v1/state/YOUR_RUN_STORE
```

`--state-dir` exports bounded completed-run evidence from HX's runtime store,
omitting acceptance/private diagnostics and raw model/grader logs. Alternatively
`--evidence` accepts the saved public audit format. `--public-outcomes` may add
public workflow status, usage and runtime errors from a results file. Historical
private evaluator patches, commands and logs must not be supplied.

Each invocation performs one Sol proposal and automated acceptance cycle, with
25,000 reported-token allowance and a 180-second model deadline. These are
turn-boundary observations, not exact billing caps. There is no background
watcher or unbounded self-modification loop. Sol's current automatic adoption
surface is runtime configuration; arbitrary generated code changes are not
automatically adopted by this runner.

## Remaining evidence gaps

Final changed-path validation passed 33 Linux tests and 12 focused Windows tests,
and Ruff passed. Earlier broader Linux runs exposed two npm lookup failures;
those failures were retained in the session evidence and corrected. The final
Linux suite includes the corrected portability, cancellation, completed-result,
budget, fixture-isolation and single-worker cases. No new model call was used to
validate those code repairs.

The six former reserved tasks are consumed. Their historical scores are intact;
there is no improved public benchmark result for this new runtime. New coding
evaluations should use fresh cases or explicitly named development retries.
We still need evidence about regression breadth, context usefulness and actual
cost on harder tasks. Browser interaction remains outside this implementation.
