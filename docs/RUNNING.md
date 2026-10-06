# Running HX

## Local workflow

Requirements: Python 3.11+, Git, and an editable checkout. Linux and Windows are supported for the local engine; repository-level Docker experiments were developed under Ubuntu WSL on native Linux storage.

```bash
python -m venv .venv
# Activate .venv for your shell, then:
python -m pip install -e ".[dev]"
python -m hx demo .hx/demo
python -m hx run .hx/demo/tasks/missing-task.json --adapter fake
python -m hx list
```

The fake adapter uses scripted fixtures and makes no model calls. Run `python -m hx --help` for CLI commands. A local handoff records an exact candidate commit; approval does not automatically merge, push or deploy it.

For real model work, install and authenticate Codex separately, run `python -m hx doctor`, review `hx.toml`, and invoke the task without `--adapter fake`. Your provider/account must support the configured model. The checked-in config is an example, not an entitlement to a particular model.

## Tests

```bash
python -m pytest tests/test_environment_thirty.py tests/test_worker_environment.py -q
python -m pytest tests/test_code_search.py tests/test_worker_scaffold.py tests/test_polybench_delivery.py -q
```

These are regression/mechanism checks; passing them is not an official benchmark score. Linux fixtures should use native ext4 temporary storage, especially for subprocess output capture.

## PolyBench requirements

```bash
python -m pip install -e ".[dev,polybench]"
```

Also required:

- Linux Docker and enough host-backed storage for the selected immutable images.
- The pinned upstream evaluator checkout and its own dependencies, installed according to its [documentation](https://github.com/amazon-science/SWE-PolyBench).
- The pinned dataset downloaded separately. Private test/reference columns must not enter worker or proposer context.
- A Linux Codex installation for model trials. A model-free readiness survey needs no model authentication.
- A new experiment manifest recording task identities, source/image/input pins, budgets, selection/exposure history and native-state paths.

The publication snapshot supports overriding the PolyBench transport paths with `HX_CODEX_BINARY` and `HX_CODEX_AUTH`. The latter names a local authentication file; never commit it. Defaults are the historical `/opt/hx-codex/.../codex` binary path and the current user's `~/.codex/auth.json`. Other historical scripts may still contain machine/campaign-specific assumptions and need review.

## Deliberate preparation before execution

This repository includes research controllers, not a turnkey full-benchmark installer. Local `.hx` manifests, datasets, source snapshots, vendor checkouts and credentials are deliberately excluded. Do not run an old campaign controller merely because its file exists.

For a new batch:

1. Pin dataset/evaluator versions and select tasks using metadata before outcomes.
2. Record prior exposure; distinguish fresh cases from deliberate development repeats.
3. Resolve immutable task images and check physical host/Linux storage headroom.
4. Exercise every selected environment in an actual offline UID-1000 worker: source identity, dependency availability, build freshness and runner output.
5. Seal runtime, prompts, scheduler, task inputs and budgets.
6. Start exactly one controller, preserve each consumed identity, and admit model work only after the required gates pass.
7. Independently replay delivered source and public checks, then use the unchanged upstream scorer separately.
8. Audit all outcomes and interruptions, including infrastructure failures and unknown usage.

The `scripts/run_environment_thirty.py` survey depends on a previously prepared pinned dataset, anchor selection and exposure records under `.hx`; it cannot start from this source-only clone alone. Its saved-report validator and build recipes can still be tested using the fixture suite.

## Storage

The research setup retains a 40-GiB host pre-pull guard. This is a configured safety policy, not the total space needed for the full benchmark. Individual image sizes and shared layers vary.

Rotating owned Docker image tags limits the live cache. WSL's backing virtual disk may retain physical allocation after deletion. Check Windows backing-drive space as well as Linux filesystem space; do not solve a storage failure by bypassing admission checks or pruning unrelated images.

## Archived campaigns

Reports describe earlier runs at historical runtime versions. New fixes do not retroactively change their scores. Existing roots may intentionally refuse restart to prevent duplicate or interrupted identities from being silently replaced. Any authorized repair/recheck gets a new record, preserves earlier failure evidence, and respects its locked scope and deadline.
