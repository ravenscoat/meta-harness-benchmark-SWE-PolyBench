# Architecture

The system separates coding execution, reusable agent-program search and
independent benchmark evaluation. Python owns the control flow and accounting;
models generate code or propose executable workflow changes within that flow.

## Coding execution

1. Load the public issue and pinned repository snapshot.
2. Verify the image, source preparation, dependencies and writable worker workspace.
3. Run the executable agent program in an isolated worker with bounded repository tools.
4. Capture the candidate commit and project its production patch.
5. Independently replay public checks against the delivered source.
6. Apply a bounded public-feedback revision when the configured workflow calls for it.
7. Submit the production patch to the separate official benchmark evaluator.
8. Record the task outcome, usage, runtime and source identities.

## Reusable agent-program search

The incumbent program supplies the baseline. A proposer receives a bounded
archive of public development experience and returns a candidate program.
The candidate uses the same restricted action interface and is evaluated outside
the proposer. Paired development comparisons account for task resolution,
tokens, runtime and preservation of baseline solves. Selection freezes before
reserved-task evaluation. An eligible artifact is separate from runtime installation.

## Implementation map

| Layer | Main modules |
| --- | --- |
| Task contracts and configuration | `src/hx/models.py`, `src/hx/config.py` |
| Workflow and candidate state | `src/hx/engine.py`, `src/hx/single_workflow.py`, `benchmarks/polybench/lean.py` |
| Executable agent interface | `src/hx/worker_scaffold.py`, `src/hx/scaffolds/` |
| Program search and public diagnosis | `src/hx/agent_search.py`, `src/hx/agent_diagnosis.py` |
| Live benchmark search backend | `scripts/agent_search_polybench.py`, `scripts/run_agent_search.py` |
| Repository context | `src/hx/repo_context.py`, `benchmarks/polybench/repo_context.py` |
| Containers and task-local sessions | `benchmarks/polybench/containers.py`, `benchmarks/polybench/sessions.py` |
| Images, dependencies and worker preparation | `benchmarks/polybench/image_cache.py`, `image_transport.py`, `worker_environment.py` |
| Public checks and patch delivery | `benchmarks/polybench/public_checks.py`, `regression.py`, `contract_coverage.py`, `delivery.py` |
| Official evaluation and accounting | `benchmarks/polybench/grader.py`, `metrics.py`, `src/hx/usage.py` |
| State, events and artifacts | `src/hx/store.py`, `benchmarks/polybench/state.py` |

## Execution boundaries

Pinned images and clean source snapshots keep preparation reproducible.
Source-aware builds derive generated artifacts from the candidate under test.
Native worker state supports task-local context, while immutable exported
artifacts support review. Model, runtime and storage budgets bound execution.
Image retention follows the working set and preserves unrelated references.

The worker and proposer receive public issue, repository and execution context.
Private evaluator tests and accepted solutions are kept separate. Official
resolution, public verification and environment readiness are distinct records.
