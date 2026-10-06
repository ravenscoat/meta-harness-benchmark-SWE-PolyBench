# React task outcome and harness repair

## Scored attempt

Task `mui__material-ui-23229` ran in `.hx/one-react-evaluation-v2` using the frozen `delivery-and-public-test-repair@1` harness and one `gpt-6-luna` worker. It did **not** resolve officially. The production patch applied, all required tests were observed, and there were no grader infrastructure errors. This is an observed behavioral failure.

Candidate: `85a7cfdd37e41bcfef4c357f221c26aa8466583d`. Luna changed the Autocomplete root click handler to open the popup for targets outside the input and buttons, and added one focused public regression. That regression reported one passing assertion, but its process stayed alive and hit the 180-second verifier timeout. HX marked public verification failed and handed off as `needs_attention`.

Reported usage was 484,476 tokens, above the 400,000 turn-boundary target; no additional repair worker call started. Workflow time was 394.97 seconds; batch wall time was 444.65 seconds. Reported tokens are usage, not monetary cost.

The original score remains sealed with SHA256 `9cb7e1b861b488496745502b1104a78d84ab2f019374332ee27a1177df3d873d`.

- [Original score](D:/projects/Harness/.hx/one-react-evaluation-v2/experiments/heldout-results/full-mui__material-ui-23229-1/score.json)
- [Candidate production patch](D:/projects/Harness/.hx/one-react-evaluation-v2/experiments/heldout-results/full-mui__material-ui-23229-1/prediction.json)
- [Original public verification](D:/projects/Harness/.hx/one-react-evaluation-v2/experiments/heldout-results/full-mui__material-ui-23229-1/state/runs/r-9a5c14fc90a64e9f/artifacts/verify_0.json)
- [Batch metrics](D:/projects/Harness/.hx/one-react-evaluation-v2/results.json)

## Harness bug repaired after scoring

The command started with `/usr/local/nvm/versions/node/v16.20.2/bin/yarn`. Command validation supported that executable basename, but Mocha lifecycle normalization compared only literal `yarn`, `npm` and `pnpm` strings. It therefore missed the public package.json Mocha script and never appended its existing `--exit` handling.

The repair uses the supported executable basename consistently. It retains the exact executable path, original argv evidence, public-manifest-only discovery and explicit `--no-exit` semantics. It adds no shell execution or broader command allowance. Verifier version is now `polybench-public-tests@5`. Before/after source copies and hashes are preserved under `.hx/absolute-test-runner-repair-v1`; the failed task used version 4 and is not rescored.

Mocha force-exit occurs after assertions and does not establish cleanup of dangling resources. That limitation remains recorded.

Validation: 45 relevant Windows checks passed, the same 45 native Linux checks passed, and Ruff passed. New regressions cover absolute npm/yarn/pnpm paths, npm argument separators, explicit `--no-exit` and non-Mocha scripts.

## Real public diagnostic replay

The same candidate was replayed offline with UID 1000, no model credentials, no model calls and no private evaluator access:

| Diagnostic | Observed result |
| --- | --- |
| Original worker-selected command with repaired normalization | Exit 0; one passing test; Yarn finished in 17.71 seconds |
| Broader existing Autocomplete suite | Exit 0; 100 passing, 2 pending; Yarn finished in 20.39 seconds |

These executions overlap; their counts must not be added as distinct tests. Pending tests are not passing evidence. All 85 indexed historical scores were verified unchanged. These replays establish the command repair, not official correctness or another benchmark win.

- [Replay results and adaptations](D:/projects/Harness/.hx/absolute-test-runner-repair-v1/results.json)
- [Focused output](D:/projects/Harness/.hx/absolute-test-runner-repair-v1/original_plan/public_test_1/stdout.txt)
- [Broader suite output](D:/projects/Harness/.hx/absolute-test-runner-repair-v1/broader_public_suite/public_test_1/stdout.txt)
- [Score integrity proof](D:/projects/Harness/.hx/absolute-test-runner-repair-v1/complete.json)

## Next correctness work

This correctness work is now completed as consumed-case development. Five public
clear-button regressions fail the saved Luna patch; the repaired public suite has
104 passing tests and two pending. A separately frozen, reference-informed
official diagnostic resolves with all 99 observed tests passing and no missing
required tests or grader/patch errors. The invisible empty clear button and its
reserved layout space were the actual defect; handler-only changes did not fix
it. The original failed score and the failed intermediate diagnostics remain
unchanged. No new coding-worker calls were used. See
[React Contract Repair](D:/projects/Harness/docs/REACT_CONTRACT_REPAIR.md).

The numbered list below preserves the earlier plan. Automatic baseline regression
replay is now integrated in the benchmark adapter; see
[Regression Replay](D:/projects/Harness/docs/REGRESSION_REPLAY.md). Context/usage
reduction remains future work. This task must not be used again as fresh evaluation.

1. Reconstruct the missing Autocomplete behavior from the public issue, source and realistic interaction sequences. Passing existing tests does not explain away the official failure.
2. Add a targeted public regression that fails the saved candidate before proposing another production fix. If accepted-reference comparison is needed, quarantine this consumed task as development evidence and keep evaluator material out of coding-worker context.
3. Fix and replay that regression under a separately recorded development identity. Preserve the original failed score; a development replay is not a fresh benchmark result.
4. Measure and reduce worker context/usage before another paid task. The current token target is not an in-flight hard cap.
5. Freeze the resulting runtime before one genuinely unused evaluation task. Do not repeat this task and present it as held out.

The two recent fresh selected tasks have one official success (LangChain 6765) and one official failure (MUI 23229). Both repositories were used for development. This small, unpaired sample establishes neither a general harness advantage nor a leaderboard rank.
