# Public contract coverage gate

The development runtime `polybench-public-tests@7` adds an executable coverage
gate to the existing public red/green reproduction check. It addresses the
observed failure where a partial Whisper fix passed its own regression and was
marked ready despite failing official evaluation.

Before implementation, HX extracts exact public text from explicit expected
behavior or acceptance sections. Without such a section it uses the whole issue
as one obligation. A bounded keyword heuristic adds below/at/above scenarios for
limit-related requirements. More than eight extracted requirements fails closed.
This is a heuristic inventory, not complete natural-language understanding.

The same implementation response must include `contract_cases`: requirement ID,
scenario, named test ID and assertion description. No extra model call is added.
HX independently runs the public commands and parses named passing tests from
pytest verbose output or built-in Mocha/Jest/Vitest JSON reports. Summary counts,
skips, stale inventories and reused identities cannot satisfy distinct obligations.
Missing evidence blocks readiness and enters the existing bounded repair loop.
An evidence-only correction retains the exact candidate commit and diff, and is
verified again. Empty initial implementations and unchanged no-op revisions remain
rejected. Native FastAPI workflows retain their existing default contracts.

## Development evidence

Two preserved candidates were replayed in actual containers with no model calls
and no official regrading:

| Saved candidate | Public reproduction | New coverage gate |
| --- | --- | --- |
| Transformers 26164 incomplete fix | Base red, candidate green | Blocked: three length-limit scenarios missing |
| LangChain 6765 successful fix | Base red, candidate green | Passed: recorded behavior has a named passing witness |

The root agent backfilled the diagnostic mappings to existing public tests and
enabled verbose output. These probes do not demonstrate that Luna can produce
good mappings autonomously. The source patches and original scores were unchanged.
An actual pinned React-task Mocha installation also correctly distinguished a
passing test, assertion failure and pending test using its JSON reporter.

The scripted workflow regression confirms that missing coverage reaches repair,
an evidence-only correction preserves the candidate commit, and verification runs
again. Scripted responses are mechanism tests, not coding-capability evidence.

Evidence is stored under `.hx/contract-coverage-runtime-v1/probes`; its completion
record verifies all 87 indexed prior score files and the replayed source hashes.

Final related suites passed 142 tests on native Linux and 141 on Windows, with
one Windows symlink skip covered on Linux. Ruff passed. The first sandboxed
Windows run retained 29 fixture failures caused by Git shared-memory access
denial (112 passed, one skipped); the same suite passed outside that sandbox.
`validation.json`, the source snapshot and Windows XML record the final checks.

## Limits and next evaluation

Passing this gate establishes traceability to observed test identities. It does
not independently prove assertion semantics, full issue coverage, or resistance
to fabricated runner output. The worker still describes the mapping. Heuristic
boundary detection can over-require or miss cases; unsupported output formats
fail closed, including pytest parameter identities containing whitespace.

The official Transformers failure remains a failure. No fresh task has yet run
under version 7 and no benchmark improvement is claimed. The next capability
check should use one unused pinned official task in a new versioned experiment,
with account/budget checks, preserved scores and private grader isolation.
