# Single repaired Svelte7422 development attempt

Authorized after the model-free worker/parser repairs. New root
`.hx/lean-svelte-repair-v1` preserves the previous zero-token setup failure and
all historical scores. This is selected development evidence, not a fresh
heldout comparison or leaderboard result.

One gpt-6.1-sol medium implementer, no separate test author, at most one
task-local repair. Original pinned inputs, image and official scorer retained.
Workflow target 300,000 reported tokens, repair reserve 60,000, batch allowance
600,000 at turn boundaries (overshoot possible). Three-hour deadline includes
quota waiting; 600-second calls and 1,200-second workflow. Primary usage must
be below 80%, weekly below 90%, with ordinary usage allowed. No purchases or
reset-credit redemption. Insufficient remaining time or unknown quota blocks.

Runner `scripts.run_lean_svelte_repair` refuses any existing root. It locks
source, scheduler and inputs before waiting, checks the actual offline UID1000
worker build before coding, and replays the production patch independently
before unchanged official grading. No old identity is resumed or replaced.
Runtime must remain frozen while waiting and running.

Validation: 17 admission/native-session/delivery checks passed on Linux and
permitted Windows execution, plus Ruff. The first sandboxed Windows delivery
check hit the retained Git shared-memory permission failure; its permitted
rerun passed. Earlier repair checks and real 118-test model-free public probe
remain documented in WORKER_PARSER_REPAIR.md.

Completed after the natural quota reset. **Svelte7422 officially resolved**:
the delivered candidate passed the unchanged official scorer, all required tests
were observed, and there was no patch rejection or grader infrastructure error.
Candidate: `38694adcdf68d20f0edfce6e7749a8d1b9c5940f`.

Independent candidate replay used the exact production patch (only KeyBlock.ts)
plus five new public regression files; original test edits were not inherited.
The key-block command passed 36/36 and component-slot command passed 189/189.
These public checks are separate from official acceptance.

Workflow status remains **failed**, visible verification false. Base-regression
replay stopped before execution because the legacy Svelte followup helper tried
`git show <base>:test/runtime/index.js`, absent in this Svelte3 snapshot. Thus no
independent base behavioral reproduction is established. This is an HX verifier
compatibility failure, not an observed official candidate failure. No scored
rerun or runtime modification was made; the next source change should make the
optional legacy helper check applicability before reading a version-specific
path, with a regression test for the absent-file case.

One implementer call, 14 completed command executions, no repair: 352,624
reported tokens (350,030 input, of which 315,520 cached; 2,594 output), 169.58
workflow seconds. Usage known. The 300,000 target overshot by 52,624 at a turn
boundary; the 600,000 batch allowance was not exceeded. Workflow seconds exclude
quota waiting, downloads and grading; reported tokens are not monetary cost.

`final-audit.json` verifies all 127 historical score-file hashes, frozen source,
plan, scheduler, inputs and new score seal. Previous zero-token setup failure is
unchanged. Controller exited and monitoring ended. This selected development
pass does not establish causal improvement or leaderboard performance.
