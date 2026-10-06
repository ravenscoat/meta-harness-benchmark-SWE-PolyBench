# Evidence and project status

Status at publication: 6 October 2026, Pakistan time. This page reports selected experiment evidence rather than a pooled benchmark score.

## Official task outcomes

The completed repaired lean batch officially resolved all three selected tasks:

| Task | Official resolved | HX workflow | Reported tokens | Workflow seconds |
| --- | --- | --- | ---: | ---: |
| MUI42412 | Yes | `needs_attention`: public base reproduction inconclusive | 372,857 | 467.96 |
| Svelte1376 | Yes | `needs_attention`: coverage-binding issue | 325,899 | 145.40 |
| Serverless8159 | Yes | Ready | 260,147 | 96.95 |
| **Total** | **3/3** | **1 ready; 2 evidence concerns** | **958,903** | **710.30** |

All required official tests were observed for these three; no patch rejection or grader infrastructure error was recorded. Full narrative: [repaired lean batch](LEAN_REPAIRED_THREE.md).

This sample is small and selected. It has no paired baseline and does not establish causal improvement or leaderboard rank. The initial ten-case development comparison resolved four cases in each arm, HX and Luna alone, and included a retained baseline infrastructure failure. Later repeats are explicitly consumed development evidence.

## Thirty-task environment survey

Fixed allocation: ten MUI, ten Svelte and ten Serverless cases. Three uncoded anchors plus 27 additional metadata-selected cases; no substitutions after outcomes.

| First-pass category | Cases | Meaning |
| --- | ---: | --- |
| Environment and runner smoke passed | 16 | Actual offline worker preparation and synthetic installed-runner check passed. |
| Unsupported legacy build layout | 2 | Svelte1049 and Svelte630 required narrow historical recipes. |
| Receipt validation rejected passing output | 4 | Legacy Mocha included leading whitespace in `fullTitle`. |
| Container command failed | 1 | Svelte6564 recipe checked an absent/nonignored `action` runtime output. |
| Blocked before worker checks | 7 | Host backing-drive space fell below the retained 40-GiB image-pull guard. |

All 30 received outcomes; only 23 reached worker checks. Model coding calls, official grader calls and reported model tokens were zero. The first-pass audit verified 135 historical score files and its plan/source/input seals.

The seven code/validator flags have implemented repairs: exact Svelte1 build recipes, source-aware optional action output, and whitespace-normalized exact smoke-name validation. Thirty-five Windows and 35 Linux regression checks passed. Four saved original smoke reports now validate, and the three actual saved public layouts yield ignored/untracked output recipes.

**Fresh offline container rechecks are pending.** Saved-report reclassification and source inspection do not replace independent build execution. Storage remains a separate blocker; readiness is not complete. [Survey and repair record](ENVIRONMENT_THIRTY.md)

## Evidence availability

This repository publishes source, tests and written experiment reports. Local `.hx` raw logs, candidate repositories, hidden grading artifacts and image contents are intentionally excluded. Consequently, readers can run the fixture tests and inspect the implementation, but cannot independently reproduce every historical score from this source-only checkout.

Historical documents retain earlier intermediate states and failed attempts. Use this page for the publication summary and the linked experiment documents for scope/version provenance. A later repair never overwrites a historical official outcome.

## Interpretation rules

- Green self-authored/public tests are not an official grader pass.
- `needs_attention` does not negate an independently recorded official pass.
- Patch rejection, missing observations, no candidate and setup failure are distinct from observed behavioral failure.
- Workflow seconds exclude download/preparation/grading stages outside the measured workflow.
- Reported tokens are not monetary cost, and boundary-based limits can overshoot.
- Same-model independent contexts can make correlated errors.
- No full-benchmark result, general advantage or leaderboard claim is established.

## Next development milestones

Restore storage headroom, independently recheck repaired environments, expand version-specific readiness coverage, and measure tool/context/repair costs on fixed scopes before larger model campaigns. Harness search promotion should depend on external executable evidence, followed by separate frozen evaluation.
