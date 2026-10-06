# Smaller first benchmark

The user authorized reducing the remaining 88 trials to 44 after seven trials
were scored. The new target is **51 total task trials**, with one separate Sol
policy proposal. One active HX trial finished during the scheduler switch, so
the campaign resumed with eight scored trials and 43 remaining.

The original 35-case selection, pinned dataset, official scorer, per-task
budgets, frozen coding runtime, source lock, campaign start and 24-hour/50M-token
limits remain intact. Completed outcomes are retained. The original report is
saved as `experiments/report.before-scope-amendment.json`.

The amended schedule contains five setup trials, all 20 development Luna/HX
comparisons, eight tuned-development trials, and 18 evaluation trials. Sol still
proposes one bounded general policy after all 20 initial development comparisons.
The first eight development tasks in the original order receive tuned runs.

Six untouched evaluation cases are selected using repository round robin in the
original metadata order, preserving case order within each repository. Selection
uses no evaluation outcomes or patch contents. These cases cover Transformers,
LangChain, Svelte, Serverless and Material UI; each receives all three arms with
rotated execution order. The paired evaluation sample is six rather than 20, so
uncertainty is substantially greater and this is an exploratory first benchmark.

`experiments/scope-amendment.json` contains the exact schedule and hashes; its
separate lock protects the amendment. `scripts/run_polybench_reduced.py` schedules
the existing frozen runtime and updates aggregate progress to 51. Individual
scores are neither rerun nor overwritten. The original 95-trial scheduler is
retained for audit but must not be resumed for this amended campaign.
