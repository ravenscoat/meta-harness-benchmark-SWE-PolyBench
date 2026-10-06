# Independent replay uses delivered production source

`blind-public-challenge@4` rebuilds independent verification from the original
repository, applies the exact production patch used for benchmark delivery, and
then applies the frozen independent challenge. Implementer edits to existing
tests, fixtures and test manifests are not inherited. Challenge-path collisions
fail closed. The replay records production and overlay commits, patch hashes,
and selected paths; its version is included in the cached-step identity.

The previous Svelte-only delivery-parity blocking gate was removed. Original
public tests can legitimately expect behavior replaced by a feature, so their
failure alone must not block a correct feature. The diagnostic replay utility
and all previous evidence remain available.

Three separate, model-free official diagnostics informed this decision. The
saved full candidate passed its public checks but the official evaluator rejected
its patch before testing. The pinned reference passed, and the reference with
public test paths filtered also passed. Thus production-only delivery itself is
not sufficient to explain the saved candidate's failure. Full-patch delivery was
rejected as a proposed fix. Reference contents and private grader logs were not
fed into model context. These are post-hoc controls, not replacement task scores.

The corrected independent replay of the saved Svelte candidate passed offline
without inheriting its test edits. All 115 historical score files remain
unchanged. Evidence: `.hx/svelte477-independent-projection-v1/audit.json` and
`independent-delivery.json`; official control summaries are under
`.hx/svelte477-full-delivery-v1`. No new model attempt was run.

The original Svelte official result remains unresolved. This repairs test
isolation, not the candidate's unproven behavior or general benchmark accuracy.
Same-model test authoring can still miss requirements. Public checks passing
must remain distinct from official resolution.

Validation: 27 focused Linux checks, 27 Windows checks, 108 compatibility checks,
the scripted worker fixture, and Ruff passed. Runtime-v14 is archived. The first
Windows run retained a fixture-only CRLF assertion failure; explicit Git newline
configuration corrected it before the passing rerun. The initial diagnostic
launcher import error was corrected with the project import path. Validation
and source hashes are sealed in the evidence root's validation.json.
