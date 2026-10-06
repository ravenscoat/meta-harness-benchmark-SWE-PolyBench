# Svelte477 readiness checks

Subsequent aggregate-only [official classification](SVELTE477_FAILURE_CLASSIFICATION.md)
found 2/4 required new-behavior tests pass and 556/556 required existing-behavior
tests pass. Parser results match the independently decoded saved report. The
public probe suite does not yet detect the failed new-behavior acceptance.

Completed public-only, model-free diagnostics before another coding attempt.
No benchmark identity was resumed or replaced, and no private evaluator material
or accepted solution was used to design these probes.

1. Independent verification reconstructs original source plus the exact delivered
   production patch and frozen public tests. The saved receipt records delivery
   SHA256 `7f722c7ab0c436e692531d45e183f6008ff5669095057b5a284c0ef59b2b7962`.
   Implementer test edits are excluded. This is `blind-public-challenge@4`.
2. Extended the saved public regression with omitted conditional rendering and
   updates, independent attribute/text updates, and retained target validation.
   Both inline and shared-helper variants run. The corrected suite passed all
   30 tests on the saved production patch. No concrete missing behavior was found
   in these probes; the official failure remains unexplained by public evidence.
3. A disposable production-source mutation changed the warning text to
   `HX_SOURCE_MARKER`. A separate offline replay rebuilt successfully and failed
   the public assertions. This demonstrates sensitivity to current generated
   source rather than silently passing against the cached compiler. It does not
   prove that every future build environment is reliable.

The initial expanded probe expected empty innerHTML for an inactive conditional.
Svelte legitimately emits a comment anchor; both initial failures were probe
assertion errors, not candidate bugs. Version 1 evidence is preserved. Version 2
checks absence of the rendered element instead and passes. Do not report version
1's raw `concrete_candidate_gap_found` flag as a confirmed behavior gap.

Build/report/delivery regression checks passed: 111 Linux tests, 108 Windows
tests with three Linux-only skips. Linux includes forced-exit capture of a 6 MB
JSON report, oversized-report rejection, setup/timeout rejection, and source
build failures blocking model launch or functional-test success. Those checks
exercise the existing mechanisms; no additional runtime change was needed.

Evidence roots: `.hx/svelte477-readiness-v1` and `-v2`; version 2 retains the
expanded public tests, candidate replay, mutation replay, plan and audit. All
115 historical score hashes were verified unchanged. Zero model calls and zero
official grader calls were made in this readiness work. The original saved
Svelte official result is still unresolved. Public coverage is stronger but
does not establish official correctness or a benchmark improvement.
