# Public PolyBench comparison: partial results

The user ended this campaign on 3 October 2026 (Asia/Karachi) to prioritize
executable harness improvements. It stopped at **27 of 51 scheduled trials**;
the original schedule had previously been reduced from 95. It is incomplete.
No heldout evaluation trial was run. Results cannot establish general improvement
or a public leaderboard ranking.

| Stage / approach | Officially resolved | Reported tokens | Workflow seconds |
|---|---:|---:|---:|
| Setup, Luna | 0/5 | 974,120 | 546.59 |
| Development, Luna alone | 4/10 | 2,747,291 | 990.03 |
| Development, original HX | 4/10 | 5,346,467 | 2,629.14 |
| Development, fixed Sol-policy HX | 1/2 | 1,161,359 | 363.34 |

The fixed Sol policy proposal consumed another 20,813 reported tokens and was not
a task trial. Workflow times exclude image download and official grading time.
Infra preparation attempts and their usage remain in the original exclusions;
these table totals cover scored task attempts only.

Original HX did not improve the aggregate development solve rate and consumed
about 1.95 times the tokens and 2.66 times the workflow time of Luna alone.
The two tuned runs add no new solve: Keras19775 passed and Keras19863 failed under
all three approaches. These are development results selected for diagnosis;
there is no independent evaluation evidence or paired uncertainty estimate on
untouched tasks.

## Outcome distinctions

- Setup: three candidate-patch rejections, one observed required-test failure,
  and one missing-required-test observation; no grader infrastructure error.
- Initial development: two candidate-patch rejections per approach. The Luna
  Prettier459 attempt failed before any model usage because of a missing Python
  alias. It remains a scored zero-token infrastructure failure. Its pair is
  confounded by the explicitly authorized transfer runtime amendment.
- Luna VSCode135805 made no changes. HX VSCode135805 lacked observations of 20
  required acceptance tests with no grader infrastructure error. Missing
  observations are not proof that the candidate source was behaviorally wrong.
- Official resolution and workflow handoff are distinct. Tuned Keras19775 was
  officially resolved but its workflow status was `needs_attention`.
- Whitespace/syntax verification can pass while official behavior fails; the
  original adapter did not independently enforce a public functional test.

All 27 score files, raw logs, predictions, fixed policy, dataset/image pins,
scope/runtime amendments and historical source locks remain under
`.hx/polybench-v1`. `experiments/termination.json` records the score hashes and
the final report hash; `report.at-termination.json` preserves the final table.
The original amended runtime is retained under
`experiments/runtime-source-amendment-1`. The live checkout now contains a new
development runtime and must not resume the old frozen scheduler.

The next batch is explicitly development-only, in `.hx/improvement-v1`.
See [HX improvement loop](HX_IMPROVEMENT_LOOP.md) for its mechanisms and limits.
# Separate overnight improvement batch

The later HX-only batch is complete and documented in
[MORNING_REPORT.md](MORNING_REPORT.md). Its final six reserved attempts officially
resolved one task, with zero end-to-end task_success. It did not resume or replace
this terminated comparison, and does not provide a paired improvement estimate.
