# HX overnight report — completed

The allocated batch finished at **03:08 UTC on 3 October 2026** (08:08 Pakistan
time), before the 08:28 UTC deadline. All three new development attempts and all
six reserved HX-only attempts are scored. The controller exited; the follow-up
is paused. No further trial is scheduled.

**Official results: development v3 2/3; reserved evaluation 1/6.** No reserved
attempt satisfied both HX workflow success and official resolution. Mechanisms
improved, but these results do not establish a benchmark gain or leaderboard rank.

## Implemented changes

- HX independently replays worker-selected public functional tests against the
  exact candidate in fresh offline containers. Syntax/whitespace alone cannot
  satisfy verification; missing or failing plans enter revision.
- Empty reviewer findings skip the Sol consolidation call.
- Changed test plans can be revised without fabricated source edits. Candidate
  commit, diff hash and changed-file evidence stay fixed; verification runs again.
  Empty initial implementations and unchanged no-op revisions remain rejected.
- Conventional test and test:<suffix>/test-<suffix> npm/yarn/pnpm scripts are
  supported, including npm run test-browser. Arbitrary shell/build/install
  commands remain rejected. Direct Mocha entry points are still unsupported.
- Optional repository navigation ranks tracked source/tests and shows bounded
  Python symbols and approximate JavaScript outlines. It is delivered through a
  **single-file read-only mount**, never the benchmarks directory. The tool is
  fingerprinted and snapshotted. Discovery output is not test evidence.
- Correctness guidance separates impact severity from readiness: concretely
  evidenced supported-contract or requested-behavior regressions may block at
  medium severity; uncertain risks must retain explicit gaps.
- Workers are asked for focused regressions and relevant compatibility checks
  within the same three-command and execution limits.
- The staged runner locks scope/settings/scheduler, checks account quota before
  image work and workers, counts scored/interrupted usage, and reserves time/token
  headroom. The console distinguishes official resolution from workflow status.

## Selected development evidence

Version 2, retained earlier probes:

| Task | Official result | Workflow | Reported tokens | Workflow seconds |
|---|---|---|---:|---:|
| Keras19775 | Resolved | Ready for approval | 354,048 | 137.39 |
| Keras19863 | Unresolved | Plan-only revision rejected | 553,237 | 163.44 |
| Keras18975 | Resolved | Token budget exhausted during revision | 607,462 | 211.27 |

Total: **2/3 official resolutions**, one ready workflow, **1,514,747 tokens** and
**512.10 workflow seconds**. The resolved tasks had been solved earlier; these
selected probes are not new heldout gains.

Version 3, three explicitly new identities:

| Task | Official result | Workflow | Reported tokens | Workflow seconds |
|---|---|---|---:|---:|
| Keras19863 | Unresolved | Ready for approval | 520,031 | 149.67 |
| Prettier3515 | Resolved | Ready for approval | 471,457 | 158.56 |
| VSCode127071 | Resolved | Token budget exhausted during revision | 674,538 | 364.45 |

Total: **2/3 official resolutions**, two ready workflows, **1,666,026 tokens** and
**672.67 workflow seconds**. All required tests were observed, with no grader or
patch-application error. The scores are sealed in the v3 audit.

Keras's focused build/summary regression passed (one test, 44 deselected), but
official grading failed. Both reviewers reported a structured-input limitation
as medium/nonblocking; those reports were not independent behavioral proof.

Prettier's write-status repair passed 16 public tests and nine snapshots, then
official grading. VS Code's original patch officially passed, but the workflow
rejected its test-browser plan before execution and exhausted the token budget
during revision. The matcher was repaired at a stopped boundary; its scored
identity was preserved, not rerun.

## Final reserved evaluation

The final runtime was frozen before these six tasks. Original dataset, images,
source metadata and official scorer were retained. Workers were Luna; Sol grouped
genuine nonempty findings. No baseline/tuned arms or task replacements were added.

| Task | Official result | Workflow | Outcome classification | Tokens | Workflow seconds |
|---|---|---|---|---:|---:|
| Transformers29449 | Unresolved | Failed at second correctness review token limit | Patch rejected; 106 required tests unobserved | 613,288 | 286.89 |
| LangChain4420 | Unresolved | Ready for approval | Patch rejected; one required test unobserved | 186,094 | 176.97 |
| Svelte6759 | Unresolved | Implementation token limit | No accepted candidate | 654,244 | 198.30 |
| Serverless2842 | Unresolved | Ready for approval | Official test failure; all required tests observed | 492,322 | 213.13 |
| MUI26807 (React) | **Resolved** | Revision token limit | Official success despite failed HX workflow | 739,286 | 620.46 |
| Transformers16198 | Unresolved | Needs attention | Official test failure; all required tests observed | 350,846 | 163.23 |

Total: **1/6 officially resolved (16.7%)**, **3,036,080 reported tokens** and
**1,658.98 workflow seconds**. The 95% Wilson interval is approximately
**3.0%–56.4%**, illustrating small-sample uncertainty. These six selected cases are
not a random representative estimate of the entire public benchmark.

The six outcomes comprise one official resolution, two patch-application
rejections, two observed official test failures and one implementation-budget
failure without an accepted candidate. There were **zero grader infrastructure
errors**. Patch rejection and absent tests are not observed behavioral failures;
Svelte's zero unobserved-test field does not imply execution when no candidate
was accepted.

Workflow statuses were two ready-for-approval, one needs-attention and three
failed. **End-to-end task_success was 0/6**: the only officially correct patch
failed HX's workflow. Public verification passed for three candidates, none of
which resolved officially.

## What the public execution evidence proves

- Serverless demonstrated one real **plan-only revision**: its unsupported direct
  Mocha command changed to npm test while the candidate commit stayed fixed.
  Independent replay then passed. This proves the mechanism works, not that the
  task was solved; official tests failed.
- Two empty consolidations skipped Sol calls, on Serverless and Transformers16198.
- The optional navigation tool was available, but **no invocation was found in
  any of the six completed public worker event traces**. Availability cannot be
  claimed as demonstrated worker use or a performance gain.
- Transformers29449's public test could not load the tiny-random-idefics tokenizer
  fixture offline. Its official outcome was separately a patch rejection.
- LangChain's two public tests passed despite official patch rejection.
- MUI's planned yarn mocha command was rejected before replay. A reviewer also
  reported a medium blocking concern, which was not independently confirmed.
  Revision exhausted the token budget, while official tests passed the original
  candidate. This exposes a mismatch between workflow gates and official success;
  it does not establish that the reviewer concern was a real defect.
- Transformers16198 passed a focused public regression and a compatibility class
  (one test, then 36 passed/10 skipped), but official tests failed. Its review
  honestly retained a network/checkpoint inspection gap.

Exact argv plans, execution-log presence, verification outcomes, candidate commits,
public reviews and score hashes are recorded in the final audit. Private grader
patches/commands/logs were not fed to workers or policy, and the frozen runtime
was not tuned from reserved feedback.

## Validation and preserved evidence

Final additions passed **95 native Linux checks**, **41 Windows focused checks
with one symlink skip**, then **seven Linux tool/mount checks** after compatibility
repairs. Linux covers the skipped symlink path. Ruff passed.

The actual adapter ran navigation and Python AST extraction in the Python 3.7.3
VS Code image, as UID1000 with an immutable tool, disabled network, no model
credentials and clean sanitized source. Earlier model-free probes passed in
Python 3.9 and 3.10 images. Helper import-path and older-Python compatibility
failures were retained, then fixed before freeze.

All **39 sealed historical/completed scores** were rechecked: old comparison 27,
v2 three, v3 three and final reserved six. Checkpoint-2 and checkpoint-4 hashes
were preserved and verified. Version 1's zero-token schema failure and launcher
startup error remain retained separately. No scored identity was replaced.

All 38 final source files stayed unchanged after freeze. The full Linux source
lock also verified pinned data, CLI, vendored scorer and settings. Final additions
had fixture/container validation but **no separate development model validation**:
the three new development slots had already been spent.

Evidence locations:

- .hx/overnight-evaluation-v1/audit.json — final identities, classifications,
  uncertainty, costs, score seals and public command execution.
- .hx/overnight-evaluation-v1/public-evidence-audit.json — public verification and
  review traces, plan-only transitions and observed tool references.
- .hx/overnight-20261003/final-runtime-amendment.json, final-runtime.json and
  final-runtime-source — frozen version provenance.
- .hx/overnight-20261003/completion.json — completed scope and audit hash.
- .hx/improvement-v3/audit.json and .hx/improvement-v2/audit.json — development.
- The terminated old comparison and earlier source snapshots remain untouched.

## Costs, limits and remaining weaknesses

Additional recorded overnight usage was **5,309,568/6,000,000 tokens**:
607,462 from the pending final v2 trial, 1,666,026 from new v3 development and
3,036,080 from reserved evaluation. The first two v2 trials preceded this envelope.
No interrupted attempt is pending. No extra trial was started, no credits were
bought/redeemed, and the primary account reset naturally.

Reported tokens include cached input and are not a monetary bill. Workflow seconds
exclude image downloads and official grading. Per-turn accounting overshot the
600,000 cap on several attempts, most notably MUI at 739,286.

The next priorities are broader legitimate test-runner support, reserving budget
for verification/revision, limiting context/output growth, improving public
fixture availability, validating patch transfer/application independently, and
checking reviewer precision and regression breadth. New evaluations would need
fresh cases; these reserved cases are now consumed.

The harness has better evidence and revision mechanisms. **Reliable task-level
improvement remains unproven**, and this batch is far from a leaderboard result.
MUI supplies React repository coverage, not an end-to-end FastAPI/React browser
benchmark. No further source change was made from heldout results.
