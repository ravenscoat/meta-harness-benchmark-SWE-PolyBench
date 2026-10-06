# Single-Luna evaluation on unused SWE-PolyBench tasks

The user required benchmark tasks rather than local FastAPI demonstrations.
This new batch uses two previously unused cases from the pinned original
SWE-PolyBench evaluation selection:

1. `langchain-ai__langchain-4579`: Python WebBaseLoader request-header behavior.
2. `mui__material-ui-18683`: React useMediaQuery hydration isolation.

Selection uses the first unused case within those repository families in the
original metadata order. It does not filter by new outcomes. Both original
environment/reference validations passed. Old benchmark coding scores are
sealed and unchanged; no original scheduler is resumed.

Root: `.hx/paper-polybench-v1`. The plan, settings, runtime, public task statements,
dataset, image identities, original scorer and scheduler are locked before
workers start. One Luna attempt per task, at most one repair; no model reviewers
or per-task Sol calls. The legacy storage arm name is `full`, while `workflow =
"single"` determines actual behavior. Actor traces, not arm names, establish
which models ran.

The new batch permits two trials, two hours and 1.2 million reported tokens,
with per-trial 400,000 reported tokens, a 240-second worker deadline, 180-second
public-check deadline and 1,200-second workflow deadline. Usage arrives at turn
boundaries and can overshoot. Quotas and remaining batch headroom are checked
before each model call; no reset credits are redeemed or purchased. Interrupted
attempts count toward usage and cannot be silently rerun.

The worker sees public source/tests and task statements. HX independently
replays public test commands; the official SWE-PolyBench scorer subsequently
checks the delivered patch. Grader patches, tests and logs are not placed in
worker context. Runtime stays frozen across both evaluation cases; failures
are reported, not used to tune it mid-batch.

`results.json` and `experiments/report.json` distinguish official resolution,
successful workflow, patch rejection, absent candidate, missing required-test
observations and grading infrastructure errors. `score-lock.json` preserves
completed outcome hashes. No candidate means no evidence that official tests
ran, even if its missing-test counter is zero.

This is a tiny selected evaluation with no comparison arm. A success is evidence
that the current harness solved that task; it cannot establish a causal gain,
general solve rate or leaderboard rank.

## Completed results

| Evaluation case | Official result | HX public verification | Reported tokens | Workflow seconds |
|---|---|---|---:|---:|
| LangChain 4579 | Candidate patch rejected | Passed; ready for approval | 186,822 | 87.73 |
| Material UI 18683 | Candidate patch rejected | Failed; needs attention | 326,884 | 418.21 |

**Official resolutions: 0/2. End-to-end successes: 0/2.** Total reported tokens:
513,706. Total workflow time: 505.93 seconds; this excludes image downloads and
official grading. There were no scorer infrastructure errors. One required
LangChain test and 25 required MUI tests were unobserved because patch application
failed. These scores do not establish an observed official behavioral failure.

Both candidates passed HX's patch replay against the unchanged base. The
LangChain serialized prediction was byte-identical to that replayed patch.
This exposes an unresolved gap between base replay and the official scorer's
patch-application context. The cause has not been established; no private grader
patches or logs were fed to models, and the scorer was not modified.

The MUI worker first supplied environment assignments as executable argv, which
the public command validator rejected. Its single plan-only repair preserved
candidate commit `2b8b82cf80930bf32c1423b81dfbca20e72ef137` and changed the command
to `npm run test:unit -- --grep useMediaQuery`. Independent replay then reported
11 passing tests and one uncaught Babel cache-permission error, before the
180-second timeout. This is a concrete public runtime problem; it does not
prove the candidate's requested behavior is wrong. No additional repair was
allowed, and the failed verification remains recorded.

Actor traces show one Luna implementation call for LangChain and implementation
plus one Luna revision for MUI. There were no reviewer or Sol calls inside either
task. Both used automatic repository mapping, environment snapshots and patch
replay. All frozen source hashes were checked unchanged after completion; all
77 historical score files captured in the plan (coding outcomes and grader
aggregate records) remained unchanged. The first checkpoint and both final
score seals passed their audit.

The batch is closed. `results.json`, `audit.json`, `public-tool-audit.json`,
`score-lock.json` and the frozen source snapshot preserve the evidence. The next
engineering priorities are official patch-delivery compatibility and writable
or disabled public test caches, before spending more model tokens. Further fixes
must use a separately recorded runtime version, not rewrite these results or
rerun these identities as fresh evaluations.
