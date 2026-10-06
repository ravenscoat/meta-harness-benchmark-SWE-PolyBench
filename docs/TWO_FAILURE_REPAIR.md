# Repair and replay of the two completed failures

The user authorized repairing and retesting the two completed failures from
`.hx/five-failure-development-v1`: Transformers 26164 and MUI 23229. The
remaining three tasks in that stopped batch remain stopped. Old scores are not
rewritten.

Public upstream pull requests were fetched from GitHub and preserved under
`.hx/two-failure-repair-audit-v1`. No private grader logs, commands or patches
were supplied to a model. This repair uses the public accepted production and
regression changes directly in separate native-ext4 workspaces, starting from
the original sanitized base. It uses **zero model calls**. Its outcomes are
reference-guided diagnostic evidence, not autonomous solve-rate improvement.

## Observed implementation differences

* [Transformers 26164](https://github.com/huggingface/transformers/pull/26164):
  the prior patch used `config.max_length` to slice prompts, changed the slicing
  expression, and supplied a different error contract. The accepted upstream
  patch uses `max_target_positions`, its original slicing expression, and the
  explicit combined-token limit/error contract. The public regression also
  exercises a decoder configured with five positions. We previously tested
  boundaries of our own implementation without checking this upstream case.
  The public upstream test asserts exact error text. These are confirmed
  differences; we have not isolated each change's individual contribution to
  the old official failure, and should not describe every difference as a
  separately proved behavioral defect.
* [MUI 23229](https://github.com/mui/material-ui/pull/23229): the prior patch
  forwarded a container mouse event. The accepted fix instead removes the
  empty clear button when the input is not dirty, correcting occupied adornment
  space and related classes/types. Public tests check the actual button count
  and accessibility. Our prior interaction tests did not establish that fix.

## Harness correction

`public-base-regression@4` recognizes narrowly structured Testing Library
missing-role assertions in Mocha reports. It requires the named error, matching
message, an actual test-file stack frame and consistent failure count. Hook
failures, unrelated errors and inconsistent reports remain blocked. The retained
MUI base replay has four such failures; the new classifier recognizes it. This
changes evidence classification, not the old patch's correctness or score.

Runtime version is `polybench-public-tests@10`. Validation: 16 focused checks on
Windows and Linux; 42 combined regression checks on native Linux; 41 combined
Windows checks passed with one platform-specific skip; Ruff passed.
An initial command named a nonexistent test file and ran no tests; the corrected
commands above are the actual successful checks.

## New replay

`scripts/repair_two_public_failures.py` creates
`.hx/two-failure-reference-repair-v1` once, records original score and public
reference hashes, applies only public production/test patches, and independently
runs public tests in offline containers as UID 1000. Delivery excludes public
test paths. The pinned official scorer installs its own unchanged tests in a
separate container. Final audit verifies historical score and runtime hashes.
One replay identity per task; no replacements or silent reruns. Envelope: two
hours, zero model tokens.

| Task | Public replay | Official resolution | Missing required observations | Grader / patch error |
| --- | --- | --- | --- | --- |
| Transformers 26164 | 3 passed | Passed | 0 | None |
| MUI 23229 | 106 passed, 2 pending | Passed | 0 | None |

The first result establishes that this publicly accepted repair works with the
pinned environment and unchanged grader. It does not establish autonomous HX
success. Candidate: `b2abb6bdcbf150736f15f9fe20e51d515e1dd77f`.

Both replays are complete. MUI candidate:
`b71ffee4afe34d6f47a250a0de4dbc0c140582d9`. The final `audit.json` verifies
94 historical score artifacts unchanged, public inputs unchanged, frozen
runtime unchanged, and zero model calls. Follow-up is paused; the remaining
three tasks from the stopped five-task batch were not run.

These results establish **2/2 reference-guided official resolutions**, not 2/2
autonomous harness solutions. They show that valid production patches can pass
the pinned scorer in our environment. Next autonomous validation must use new
recorded development identities and independent public contract checks; these
reference-informed tasks cannot become fresh heldout evidence again.
