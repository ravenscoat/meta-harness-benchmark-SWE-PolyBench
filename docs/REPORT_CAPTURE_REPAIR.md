# Public report capture repair

The latest MUI18141 attempt stopped before implementation because its Mocha JSON report ended mid-object. Reading all captured bytes could not recover bytes the producer never delivered. Its failed score remains unchanged.

The new file-backed capture adapter runs explicit `--reporter json` public commands with stdout and stderr redirected to temporary regular files, then collects both files and preserves the command exit status. Both original-source reproduction and candidate public verification use the adapter. Arguments remain separate argv values; repository arguments are not evaluated as shell code. File-size, combined-log and execution-time limits remain in force. Incomplete reports still cannot establish reproduction.

Node documents synchronous regular-file writes on POSIX and asynchronous pipe writes; forced process exit can discard pending pipe output: [process I/O documentation](https://nodejs.org/api/process.html#a-note-on-process-io). A regression check exercises an immediate Node exit after writing a six-million-character JSON value and confirms complete capture and the original nonzero exit code.

## Verification

- 102 native Linux capture, regression, classification, public-check and independent-challenge checks passed. Ruff passed.
- All three exact frozen public test plans replayed successfully in the actual offline worker image on original source: 26 passes / 6 failures, 31 / 9, and 26 / 8. These expected behavioral failures establish reproduction; they are not successful bug fixes.
- The previously truncated third report is now complete and classified as behavioral failure.
- All 104 historical score files retained their hashes. No model requests or official grader calls were made for this repair.

Evidence is under `.hx/report-capture-repair-v1`: `replay.json`, `integrity.json`, raw replay logs and `audit.json`. Runtime base-regression version is now `public-base-regression@7`. No old scored attempt was resumed or replaced.

The report-capture blocker is repaired and verified. A new coding attempt is still needed to establish whether a generated implementation passes independent public checks and the official grader. This repair alone provides no solve-rate or leaderboard evidence.

## Authorized coding attempt: quota blocked before model work

The user authorized a new attempt under `.hx/capture-repair-benchmark-v1`.
The recovered executable worker passed 107 compatibility checks against this
runtime in `.hx/worker-loop-runtime-v9`. The new plan pins MUI18141, Sol 6.1,
one repair, a 900,000-token workflow target and a 1.2-million-token batch allowance
within three hours. All historical scores, inputs, scheduler and source hashes
are locked before model work.

The controller's CLI check reported 60% primary and 90% weekly usage. Its existing
weekly threshold requires usage below 90%. Weekly reset is October 9, 2026,
21:10:41 UTC, outside the attempt deadline. The verified waiting controller was
stopped before authoring or implementation; `controller.exited.json` confirms
exit. Zero task identities, model tokens and official grading calls were consumed.
`quota-stop.json` and `audit.json` preserve the reason and integrity checks.
No monitor remains running. A later attempt needs a new explicit envelope;
this plan is not silently extended or resumed after expiry.
