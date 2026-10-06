# Fresh-domain harness comparison

This is a fixed prospective comparison of one-shot Luna, archived core HX and the
improved core HX, with two repeats of four new full-stack task specifications:
seat booking, stock transfer, invoice allocation and inbox acknowledgement.
The app repositories have domain-specific backend contracts but share a SQLite
scaffold and React editor contract. They are original synthetic tasks, not four
independently reviewed real-world projects. AI-authored tests/references are
mechanically validated, not independent human ground truth.

All tasks are reserved for this comparison. There is no search, proposer or
retuning during these trials. Sol still consolidates Luna correctness/security
reviews in both full-workflow arms. The bundle comparison cannot attribute an
outcome change to a particular prompt or runtime change.

## Final frozen campaign

- Collection: `.hx/fresh-domains-v1/manifest.json`.
- Validation: `.hx/fresh-validation-v4/validation.json` (all four seeds fail both
  backend and browser acceptance; all references pass both and visible checks).
- Campaign: `.hx/fresh-experiments-v3`; **24/24 completed trials**.
- Raw scores: one-shot 7/8, archived HX 8/8, improved HX 8/8; no updated-runtime
  success gain. The sole failure concerns ambiguous replay/validation precedence.
  See [results and limitations](../../docs/FRESH_BENCHMARK_RESULTS.md).
- `single`: one-shot implementation/visible checks using archived core code/prompts.
- `full`: archived core HX from `.hx/experiments-v1/runtime-source`.
- `improved`: current core HX copied before evaluating these tasks.
- Prior advanced extension/policy settings are not used in the archived core arm.
- Medium reasoning, Luna workers and Sol consolidation; one revision/attempt,
  300-second model-attempt limit, 90-second verification limit, 1,200-second run
  limit and 800,000 observed task tokens. Per-task ceilings match across arms;
  actual compute differs. Aggregate envelope: 15 million observed tokens/four hours.
- Task/arm scheduling rotates deterministically; no valid model campaigns overlap.
- Source, prompts, protocol, evaluators, settings and plan are fingerprinted before
  model runs. Each runtime has an offline npm cache and dependency preflight.
- A completed score is reused only through its matching frozen trial identity.
  Incomplete one-shot model work cannot be silently rerun in the same campaign.

## Browser checks

Private acceptance launches a real localhost FastAPI server, a Vite frontend and
an isolated headless Edge browser using the bundled Playwright library. Network
requests are restricted to loopback. Browser scenarios cover typing while a real
API response is delayed, coalescing repeated submissions, and owner A/B/A switching
while older work completes after a newer request. Reference browser runs retain
screenshots/traces. This coverage does not exhaust every requested error/unmount
scenario or establish broad browser compatibility.

Backend checks exercise boolean/integer validation, durable immutable replay,
process restart, owner isolation, rounding, transactional rollback and concurrent
writes. Visible checks remain separate from private grading. Success requires
private backend and browser acceptance plus successful visible verification/handoff.
Approval readiness alone is not success; no candidate is approved automatically.

## Watch or resume

```powershell
.\.venv\Scripts\python.exe scripts\hx_console.py --campaign .hx\fresh-experiments-v3
```

Run the controller with network permission for the Codex CLI transport; model-tool
sandbox networking stays disabled:

```powershell
.\.venv\Scripts\python.exe scripts\run_campaign.py --timeout 14400 .hx/fresh-experiments-v3 -- -m benchmarks.fresh.runner run .hx/fresh-experiments-v3 --max-tokens 15000000 --max-seconds 14400
```

The supervisor stops after a scored quota failure or `stop-after-case` request.
Original clock and saved outcomes persist. No reset credits are consumed. Reports
update after grading; the console can show an active trial before it is scored.

## Excluded setup attempts

`fresh-experiments-v1` retains 13 dependency failures caused by an incorrect
frozen-runtime npm-cache location. SQLite confirms zero instantiated model sessions.
`fresh-experiments-v2` retains a cancelled model transport attempt denied by
Windows socket permissions in restricted execution; it produced no completed
model turn. Neither is part of the final 24 trials. Earlier browser-discovery
validation attempts are also retained; v4 is the final validated collection.
Zero observed tokens during a failed process is not a general proof of zero cost.

Runner checks cover paired plan generation and rejection of mismatched validation,
modified archives and frozen-source tampering. The prior core suite passed 73
checks; three new campaign tests and the four console checks passed separately.
[Playwright launch documentation](https://playwright.dev/docs/api/class-browsertype#browser-type-launch)
was consulted for the browser setup; executable selection was validated locally.
