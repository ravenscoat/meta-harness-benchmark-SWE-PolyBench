# Public coding benchmark adapter

HX now has a SWE-PolyBench subset protocol in addition to the existing FastAPI/React synthetic benchmark. This subset tests repository transfer across Python, JavaScript, TypeScript and React projects; it is not a full-stack browser benchmark or a full public leaderboard submission.

## Fixed experiment

The selection contains 35 tasks: 5 setup tasks, 10 development tasks and 20 evaluation tasks. Each partition uses different repositories. Selection uses public metadata and deterministic hash ranking, before inspecting patches or trial outcomes. Dataset revision: `b3fca77b637379f0c01ad86d18753a7ac1998b53`. Evaluator revision: `9c836c5d7f3cb991934132b77d29e6941d912a07`.

The planned 95 task trials are 5 setup runs, 20 development comparisons (Luna alone/current HX), 10 development runs with a fixed Sol proposal, and 60 evaluation runs across all three arms. Evaluation arm order rotates by task. Sol sees development outcomes and public harness artifacts, and proposes one bounded context policy. It receives no evaluation traces, reference patches or hidden-test contents. There is no selection of a winning policy from multiple evaluation attempts.

Luna uses `gpt-6-luna`; Sol uses `gpt-6.1-sol`. The shared limits are recorded in `campaign.toml`: 600 seconds per model attempt, 1,800 seconds per workflow, and 1.2 million observed tokens per task. The serial driver also records a 24-hour/50-million-token campaign envelope. Provider usage limits can still stop execution.

## Execution and grading

The controller uses Linux Docker through Ubuntu WSL. Docker Desktop is independently installed; the current benchmark uses Ubuntu's local Docker socket. The Linux Codex package, including its companion executables, is mounted read-only. Each role gets a fresh dependency container and sanitized Git history. Models run as UID 1000, with all Linux capabilities dropped, no-new-privileges and the inner Codex sandbox. Container seccomp is relaxed only for model containers so nested Bubblewrap can start; default AppArmor remains. The repository extraction root is writable and both actor and controller Git ownership checks are configured explicitly.

The controller transfers the existing Codex login into an ephemeral container. It does not mount the Docker socket, host home, dataset, gold patches or private tests. Workers can inspect source and run installed public tests. Network access from sandboxed tools and web search are disabled. These controls do not constitute a hardened hostile-code security boundary.

VS Code images require an additional public Electron download. Before exposing a
candidate, hidden tests or model credentials, the adapter runs the unchanged
upstream base's `yarn electron` bootstrap with a 300-second infrastructure limit
and checks the expected executable. Its version and download logs are retained.
The grader then disconnects the network before applying patches and running the
unchanged official test command. Models still have no network access from tools.
The initial missing-Electron validation failure is retained separately from the
repaired base/reference evidence; it is not a worker coding result.

Visible verification currently checks patch whitespace and changed Python syntax. It does not claim complete public-test coverage. Independent grading runs the pinned upstream DockerManager, test parser and instance scoring in a fresh container with the official test patch. This adapter does not run the upstream retrieval-metrics pipeline or its full CLI. Official resolution and HX workflow success are reported separately. Missing expected test observations are recorded. The official scorer requires all F2P tests to pass and no observed P2P tests to fail; it does not require every declared P2P test to be present. Setup follows that same definition. Public benchmark training contamination remains possible.

Before scoring each environment, the unchanged base must fail and the reference patch must pass official tests. Infrastructure failures do not become evidence that Luna cannot code. Operational setup pilots, their raw traces and their token usage are preserved under `.hx/polybench-v1/excluded`.

Unchanged baseline symlinks are supported when they resolve inside the workspace.
The index must retain their original Git object IDs. New links, retargeting,
replacement, deletion, link cycles and path escapes remain rejected.
Baseline submodule entries are preserved with their exact Git object IDs and
remain uninitialized and empty. New, changed, removed, replaced or populated
submodules are rejected. Snapshot extraction verifies the complete source-tree
ID against upstream, including these entries. This support was authorized and
tested before development trials; rejected validation records are retained.
Two Transformers snapshots rejected by the previous blanket rule were preserved
with their original source-tree IDs before revalidation; no coding trial ran.

Transformers versions whose public Idefics processor tests reference
`HuggingFaceM4/tiny-random-idefics` warm the public tokenizer/config cache from that
repository before tests or candidate patches. The fetched snapshot revision is
recorded; no weights, private tests or task answers are supplied to workers.
The original missing-fixture reference failure is preserved. Validation must
still pass the original reference patch under the unchanged official scorer.

## Current status

The 35-task selection is saved under `.hx/polybench-v1/selection.json`; agent-safe issues are under `public`. The first yt-dlp environment passed unchanged-base/reference validation. Four operational worker pilots were excluded (182,019 total observed tokens); their tools did not successfully perform the coding task. A model-free check now passes worker Git access, workspace directory creation, staging and nested Bubblewrap execution.

The corrected first setup trial completed with 191,448 observed tokens. Luna inspected source, edited implementation and public tests, and ran tests. Visible whitespace/syntax verification passed. The official grader rejected the submitted patch after applying its test patch, so official resolution is false. A model-free re-grade of the identical prediction confirmed candidate patch rejection, with no infrastructure error. The original score, worker fingerprint and re-grade provenance remain saved. An explicit sealed-setup manifest retains this coding outcome across setup infrastructure repairs; it does not authorize a worker rerun or apply to development/evaluation trials. Consult `experiments/report.json` and the saved prediction for exact evidence.

Docker storage was verified on D: on 2026-10-02: Ubuntu's registered backing disk is `D:\WSL\Ubuntu\ext4.vhdx`, and Docker's `/var/lib/docker` is inside that ext4 filesystem. Docker Desktop's WSL registration is also under `D:\docker\DockerDesktopWSL\main`. No disk relocation was necessary. The earlier C: capacity warning was based on an incorrect assumption about the WSL disk location.

Preflight now reads the verified `.hx/polybench-v1/storage.json`, checks the active WSL distribution and Docker data root, and checks the actual physical backing drive as well as Linux filesystem free space. It stops before new pulls below 40 GiB; D: had approximately 148 GiB free at verification. Reverify that file if WSL storage is relocated again. Setup downloads/validation have resumed.

A large three.js snapshot previously hit the 30-second host Git initialization limit on the Windows-mounted filesystem. Its validation and partial snapshot were retained under `excluded/threejs-14836-preflight-timeout`; the revised setup attempt passed unchanged-base/reference grading. Git initialization has a 300-second infrastructure limit. Validated snapshots, fresh attempt workspaces and SQLite databases now live under `/opt/hx-polybench-runtime/v1` on Ubuntu's native ext4 filesystem, backed by D:. Logs, predictions, atomic console snapshots and reports remain in this project. Worker and workflow budgets remain unchanged.

A subsequent three.js setup attempt stopped with SQLite disk I/O before CLI execution while Windows monitored the Linux writer's database on the Windows mount. Its recovered database passed integrity checking and recorded zero model usage; evidence is retained under `excluded/threejs-14836-sqlite-io`. The console now reads exported JSON snapshots instead of opening native benchmark databases across operating systems. This infrastructure exclusion does not change the task selection or consume a scored coding attempt.

The controller retains the previous image while pulling a replacement to reuse shared dependency layers, then releases its recorded benchmark tags. Missing validated images are rehydrated by immutable registry digest. Images with unrelated tags or attached containers are preserved; there is no Docker-wide prune. This limits cache growth while retaining validated image identities.

All five setup reference environments passed the official gate. The tailwindcss-853 reference patch has 13 declared regression tests unobserved; tailwindcss-116 has three. Original strict-coverage rejections and corrected gate results are saved; these limitations are not hidden or counted as worker failures. The reference gate was aligned with upstream scoring before any development/evaluation model comparison. The live counts and current phase are in `.hx/polybench-v1/experiments/report.json` and `phase.json`. No improvement is inferred from setup outcomes.

## Commands

Run from the repository root in Ubuntu WSL, using the installed benchmark environment:

```sh
/opt/hx-polybench-venv/bin/python -m benchmarks.polybench.runner report .hx/polybench-v1
/opt/hx-polybench-venv/bin/python -m benchmarks.polybench.runner trial .hx/polybench-v1 --case yt-dlp__yt-dlp-9862 --arm single
/opt/hx-polybench-venv/bin/python -m scripts.run_polybench .hx/polybench-v1
```

The full campaign requires storage and all environment/reference gates to pass first. It will stop on an operational failure and preserve evidence. Do not delete failed trials or quietly rerun scored coding failures. Setup infrastructure repairs must retain excluded attempts and their usage. Source hashes freeze before development models start. Logs and official prediction exports remain on disk for review; `scripts/hx_console.py` displays atomic benchmark state snapshots.
