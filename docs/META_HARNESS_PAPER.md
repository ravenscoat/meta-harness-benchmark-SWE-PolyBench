# What HX takes from Meta-Harness

Source: [Meta-Harness: End-to-End Optimization of Model Harnesses](https://arxiv.org/pdf/2603.28052),
especially section 3 and appendix D, and its [released coding artifact](https://github.com/stanford-iris-lab/meta-harness-tbench2-artifact).

The important difference from HX's earlier Sol loop is executable code search
with filesystem experience. A proposer can inspect old source, scores and full
available public execution traces selectively instead of receiving only a
summary and returning three numeric knobs. Evaluation is performed by another
process, and unsuccessful candidates remain useful experience.

The paper's coding experiment uses the same Terminal-Bench tasks for discovery
and final measurement; its classification and math experiments also include
unseen evaluations. Its reported Claude results are not comparable scores for
our Luna worker. We keep separate validation here, and do not claim a paper
replication, perfected harness or leaderboard performance.

## Implemented adaptation

- `scripts.run_code_search` gives Sol a native isolated Git workspace containing
  harness source, an incumbent, search cases, and full explicitly selected public
  CLI prompts/commands/output from previous local attempts. It does not recursively
  import benchmark experiment directories or their private evaluator artifacts.
- Sol writes actual Python in `src/hx/failure_evidence.py`. This initial cheap
  search surface is a pure diagnostic extraction tool. It allows a new algorithm,
  rather than selecting from a predefined list of knob values. It does not yet
  search the whole harness or run end-to-end Luna coding tasks per candidate.
- The runner verifies that other supplied files were unchanged, checks the
  interface and restricted pure-code surface, and evaluates in a separate
  credential-free subprocess. Linux evaluation has CPU/address-space limits and
  an eight-second deadline. The AST restrictions are not a general Python sandbox.
- Search measures retention of actual error messages and excerpt character cost.
  A Pareto frontier retains candidates that trade quality against context size.
  Adoption requires strict dominance over the incumbent, no validation-quality
  regression, and the fixed workflow regression suite. Tests and scoring are
  outside the proposer. Character savings are not measured model-token savings.
- Validation cases and results are absent from the supplied proposer workspace;
  previous archives export only search experience on later invocations. These
  are small mechanism checks, not fresh public coding benchmark tasks. Do not
  repeatedly use the same validation set for adaptive tuning or call it untouched
  heldout evidence after doing so.
- Every attempt retains source, model events, prompts, logs, usage, scores and
  rejection/adoption decisions with SHA-256 seals. Existing coding scores are
  not overwritten or rerun. Explicit `--history` imports prior sealed search
  attempts; a changed archive fails closed.
- Luna now receives a bounded tool/environment snapshot alongside its automatic
  repository map. This follows the released artifact's environment bootstrap
  idea. Our snapshot reports controller tools without executing repository code;
  it explicitly warns that container environments can differ and availability
  does not prove installed dependencies or passing tests.

## Bounded operation

```bash
wsl -d Ubuntu -u root --cd /mnt/d/projects/Harness -- \
  /opt/hx-polybench-venv/bin/python -m scripts.run_code_search \
  .hx/paper-code-search-next --history .hx/paper-code-search-v1
```

Each invocation permits one Sol candidate, 30,000 reported tokens and a
180-second proposer deadline. Quota is checked before model work; no credits are
purchased or reset credits redeemed. Usage is reported at turn boundaries, so
the allowance is not an exact in-flight cost cap. A new root is mandatory.
There is no unbounded background self-modification loop.

If the proposer times out after logging a complete permitted-file patch, the
runner seals its failure and launches a separate model-free recovery identity.
The patch must replay exactly, satisfy the pure-code interface, dominate the
incumbent and pass validation/regressions. Partial or unreplayable drafts remain
rejected. Recovery does not rewrite the original outcome or issue another model
request.

Query prior experience without spending model tokens:

```bash
python -m scripts.code_search_history .hx/paper-code-search-v1
python -m scripts.code_search_history .hx/paper-code-search-v1 --diff
```

## Evidence and limits

The first cycle is recorded in `.hx/paper-code-search-v1`: Sol inspected the
public source and CLI traces, wrote a general diagnostic-selection algorithm,
then hit the 180-second deadline before final structured output. Its original
outcome is still failed. No completed usage event arrived: zero *reported*
tokens is not evidence of zero consumed tokens; model cost is unknown.

`.hx/paper-code-recovery-v1` independently reconstructed the complete patch from
the logged Git diff. It was rejected by regressions: nine checks lacked the
public runner module in their isolated fixture, and one legacy assertion
required exactly 2,000 excerpt characters rather than a nonempty maximum of
2,000. Both gate defects were corrected explicitly; the old rejection remains.

`.hx/paper-code-recovery-v2` evaluated the **same source hash**, passed 37 native
Linux regressions and automatically adopted the draft. No new model call was
made. Search diagnostic retention improved 3/4 to 4/4, while excerpts fell from
1,642 to 210 characters. Separate mechanism validation improved 2/3 to 3/3,
with 2,112 versus 621 excerpt characters. The validation set includes a no-error
fallback case and is tiny; it is not a coding benchmark. The original sealed
proposal, both recovery identities and all old coding scores are preserved.
An additional sealed `.hx/paper-experience-v1` stores the explicit public traces.

The adopted code prioritizes distinct exceptions/causes, limits verbose lines,
filters repeated warning noise, and adds stack/assertion context only when space
remains. It also handles zero and tiny character budgets. This is executable
tool code, not merely new prompt wording.

After adoption, 31 focused Windows checks and 34 final native Linux checks
passed; Ruff passed. All 39 historical coding score hashes were verified
unchanged. The source snapshot and report are in `.hx/paper-implementation-v1`.

Mechanism gains must be reported separately from coding performance. Automatic acceptance
does not establish causal solve-rate improvement. The former six reserved public
coding tasks are already consumed; a future end-to-end code-search evaluation
needs a new fixed development collection and fresh validation tasks.

Before claiming that this broader loop improves coding, measure candidate
resolution, completed workflow, real test execution and observed token/time
costs on those tasks. Keep verification, grading, credentials, budgets and task
identities outside generated-code adoption. The present cycle deliberately
does not spend another large side-by-side coding campaign.

Subsequent implementation: [executable worker-loop search](WORKER_LOOP_SEARCH.md)
now lets code select public inspections, bounded worker calls and optional source
context. The trusted engine still owns verification and budgets. One Sol proposal
exceeded its turn-boundary token target; its complete logged source was recovered
and compatibility-tested without another model call. It is an experimental
candidate, with no new benchmark accuracy measurement or automatic promotion.
