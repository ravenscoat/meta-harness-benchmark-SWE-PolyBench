# Synchronization feature challenges

Four original feature tasks extend the transactional workspace with a new delta
synchronization API and a durable React outbox. They require new implementations,
not restoring disabled conditionals. Search uses API and outbox tasks separately;
reserved tasks require both and emphasize recovery/concurrency. Each starts from
the same working baseline and is reset independently.

The server must provide durable per-mutation replay, payload conflict detection,
atomic compare-and-swap updates, per-tenant isolation, ordered independent results,
full-request validation before mutation, and exactly-once audit effects under
concurrent retries. The outbox must handle durable enqueue, corrupt storage,
storage failure, single-flight flush, enqueue during flush, same-item version
rebasing, malformed acknowledgements, conflicts, explicit retry/discard, tenant
switches, unmount, reload and React StrictMode.

```powershell
.\.venv\Scripts\python.exe -m benchmarks.advanced.runner build .hx/sync-features-v1
.\.venv\Scripts\python.exe -m benchmarks.advanced.runner validate .hx/sync-validation-v1 --manifest .hx/sync-features-v1/manifest.json
.\.venv\Scripts\python.exe -m benchmarks.advanced.runner run .hx/sync-experiments-v1 --manifest .hx/sync-features-v1/manifest.json --config benchmarks/advanced/campaign.toml --iterations 2 --repeats 2
```

This trusted, locally written extension reuses the same campaign engine and Codex
adapter. Extension code, reference programs, frontend assets and task specifications
are hashed before a run. The extension is not model-generated executable code.
Sol still proposes only declarative context policies and never receives reserved
task results. Both arms use the same resource ceilings within this collection;
ceilings differ from the smaller repair collection because these are new features.

Reference programs and acceptance checks are AI-authored and mechanically
validated. Scores measure the API and React hook contracts; they do not establish
a complete browser UI or generalize to arbitrary repositories. The API exposes
typed per-operation results rather than treating an HTTP200 batch as proof that
every operation succeeded. See the parent benchmark README for the remaining
evaluation limitations and trace layout.

This extension also turns a bounded visible-test timeout into a failed verification
check, allowing review and revision to repair a hanging test. User cancellation,
overall run-budget exhaustion and integrity errors still abort the run. The frozen
repair campaign retains its original behavior for a reproducible comparison;
this recovery change is recorded in the advanced extension fingerprint.
