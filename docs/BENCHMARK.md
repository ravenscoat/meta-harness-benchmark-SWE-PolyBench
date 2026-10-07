# SWE-PolyBench integration

The project tests coding-agent workflows against **SWE-PolyBench** using selected
tasks from **Material UI, Svelte and Serverless**.

The adapter connects pinned task metadata and repository snapshots to Docker
workers, offline environment preparation, independent public verification,
production-patch delivery and the upstream official evaluator.

Reusable-agent experiments compare incumbent and candidate programs on a fixed
development set, then evaluate a frozen selected program on separate reserved
tasks. Model settings, task identities, execution budgets and evaluator inputs
are recorded for each experiment. Official resolution, public checks, token
usage and workflow duration are recorded separately.

[SWE-PolyBench upstream](https://github.com/amazon-science/SWE-PolyBench)
