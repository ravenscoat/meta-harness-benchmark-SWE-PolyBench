from types import SimpleNamespace

import pytest

from benchmarks.polybench.engine import PolyEngine, VisibleVerifier
from benchmarks.polybench.public_checks import public_test_argv, public_test_execution
from hx.models import Candidate, Check, Settings, WorkerSummary


@pytest.mark.parametrize("argv", [
    ["python3", "-m", "pytest", "tests/test_behavior.py", "-q"],
    ["/usr/bin/python", "-m", "pytest", "tests"],
    ["npm", "test", "--", "--runInBand"],
    ["yarn", "run", "test:unit"],
    ["node", "--test", "tests/example.test.js"],
    ["npm", "run", "test-browser", "--", "--run", "src/example.test.ts"],
    ["npm", "run", "test:unit"],
    ["yarn", "test-browser"],
    ["yarn", "run", "test-browser"],
    ["pnpm", "test:unit"],
    ["pnpm", "run", "test-integration"],
])
def test_public_test_runners(argv):
    assert public_test_argv(argv)


@pytest.mark.parametrize("argv", [[], ["true"], ["sh", "-c", "npm test"],
    ["python", "-c", "print('passed')"], ["npm", "install"], ["npm", "run", "build"],
    ["npm", "run", "test;touch /tmp/marker"], ["yarn", "run", "test:"],
    ["pnpm", "run", "testing"], ["npm", "test-browser"],
    ["npm", "run", "pretest"], ["yarn", "build"]])
def test_non_test_commands_are_not_behavioral_evidence(argv):
    assert not public_test_argv(argv)


def test_summary_rejects_unbounded_or_malformed_test_plan():
    with pytest.raises(ValueError):
        WorkerSummary(summary="done", tests_added=[], limitations=[], verification_commands=[[]])


def test_worker_output_schema_requires_every_property_for_codex():
    schema = WorkerSummary.model_json_schema()
    assert set(schema["required"]) == set(schema["properties"])


@pytest.mark.parametrize("commands,test_passes,expected", [
    ([], True, False),
    ([["python", "-c", "print('passed')"]], True, False),
    ([["pytest", "tests/test_behavior.py"]], False, False),
    ([["pytest", "tests/test_behavior.py"]], True, True),
])
def test_smoke_pass_cannot_hide_missing_or_failed_public_test(
    monkeypatch, tmp_path, commands, test_passes, expected
):
    import benchmarks.polybench.engine as module

    removed = []
    container = SimpleNamespace(id="offline-test", remove=lambda **kw: removed.append(kw))
    monkeypatch.setattr(module, "create", lambda *a, **kw: (container, "/repo"))
    monkeypatch.setattr(module, "populate", lambda *a: None)
    monkeypatch.setattr(module, "assert_clean", lambda *a: None)
    monkeypatch.setattr(module, "regression_check", lambda *a: Check(
        name="public_regression_reproduced", passed=True, evidence="Separate tested replay"))
    monkeypatch.setattr(module, "coverage_check", lambda *a: Check(
        name="public_contract_coverage", passed=True, evidence="Separate coverage tests"))
    executed = []

    def check(name, argv, *args):
        executed.append(argv)
        return Check(name=name, passed=test_passes if name.startswith("public_test_") else True,
                     evidence="Observed subprocess result")

    monkeypatch.setattr(module, "command_check", check)
    candidate = Candidate(base_commit="a", input_commit="a", candidate_commit="b",
        changed_files=["example.js"], workspace=str(tmp_path), diff_sha256="c",
        verification_commands=commands)
    verifier = VisibleVerifier(Settings(), None, {})
    result = verifier.run(candidate, SimpleNamespace(base_commit="a"), tmp_path,
                          lambda: None, lambda *a: None)
    assert result.passed is expected
    assert result.candidate_commit == "b"
    assert removed == [{"force": True}]
    if commands and public_test_argv(commands[0]):
        assert executed[-1][-len(commands[0]):] == commands[0]
        assert "1000:1000" in executed[-1]
        assert "BABEL_DISABLE_CACHE=1" in executed[-1]
        assert not any("CODEX_HOME" in item for item in executed[-1])


def test_empty_consolidation_uses_no_model_and_retains_revision_logic():
    engine = PolyEngine.__new__(PolyEngine)
    events = []
    engine.check_control = lambda *a: None
    engine.store = SimpleNamespace(event=lambda *a, **kw: events.append((a, kw)))
    candidate = SimpleNamespace(candidate_commit="b")
    result = engine._consolidate("r", 0, None, candidate, None, {}, {}, 1)
    assert result.groups == []
    assert result.candidate_commit == "b"
    assert events[0][0][1] == "consolidation.skipped"


def test_environment_prefix_normalization_keeps_argv_and_env_separate(tmp_path):
    argv, env, changes = public_test_execution(["BABEL_DISABLE_CACHE=1", "NODE_ENV=test",
        "./node_modules/.bin/mocha", "public.test.js"], tmp_path)
    assert argv == ["./node_modules/.bin/mocha", "public.test.js", "--exit"]
    assert env == {"BABEL_DISABLE_CACHE": "1", "NODE_ENV": "test"}
    assert changes
    with pytest.raises(ValueError):
        public_test_execution(["NODE_OPTIONS=--require=/private/secret", "npm", "test"], tmp_path)
    with pytest.raises(ValueError):
        public_test_execution(["NODE_ENV=test", "sh", "-c", "npm test"], tmp_path)


def test_mocha_script_is_discovered_from_public_manifest_without_running_it(tmp_path):
    (tmp_path / "package.json").write_text('{"scripts":{"test:unit":"cross-env NODE_ENV=test mocha tests/*.js"}}')
    command = ["npm", "run", "test:unit", "--", "--grep", "behavior"]
    actual, _, changes = public_test_execution(command, tmp_path)
    assert actual == [*command, "--exit"]
    assert changes
    assert public_test_execution(["yarn", "test:unit"], tmp_path)[0] == ["yarn", "test:unit", "--exit"]
    (tmp_path / "package.json").write_text('{"scripts":{"test:unit":"jest"}}')
    assert public_test_execution(command, tmp_path)[0] == command
    assert public_test_execution(["mocha", "--no-exit", "public.test.js"], tmp_path)[0] == ["mocha", "--no-exit", "public.test.js"]


@pytest.mark.parametrize("manager,arguments", [
    ("yarn", ["test:unit", "--grep", "behavior"]),
    ("pnpm", ["run", "test:unit", "--grep", "behavior"]),
    ("npm", ["run", "test:unit", "--", "--grep", "behavior"]),
    ("npm", ["run", "test:unit", "--grep", "behavior"]),
    ("yarn", ["mocha", "tests/public.test.js"]),
])
def test_absolute_package_manager_gets_same_mocha_handling(tmp_path, manager, arguments):
    (tmp_path / "package.json").write_text('{"scripts":{"test:unit":"cross-env NODE_ENV=test mocha tests/*.js"}}')
    relative = [manager, *arguments]
    absolute = ["/usr/local/nvm/versions/node/v16.20.2/bin/" + manager, *arguments]
    relative_actual, relative_env, relative_changes = public_test_execution(relative, tmp_path)
    actual, env, changes = public_test_execution(absolute, tmp_path)
    assert actual == [absolute[0], *relative_actual[1:]]
    assert actual[-1] == "--exit"
    assert (env, changes) == (relative_env, relative_changes)
    assert absolute == ["/usr/local/nvm/versions/node/v16.20.2/bin/" + manager, *arguments]


def test_absolute_runner_preserves_explicit_no_exit_and_non_mocha(tmp_path):
    yarn = "/usr/local/nvm/versions/node/v16.20.2/bin/yarn"
    (tmp_path / "package.json").write_text('{"scripts":{"test:unit":"mocha tests/*.js"}}')
    command = [yarn, "test:unit", "--no-exit"]
    assert public_test_execution(command, tmp_path)[0] == command
    (tmp_path / "package.json").write_text('{"scripts":{"test:unit":"jest tests/*.js"}}')
    command = [yarn, "test:unit"]
    assert public_test_execution(command, tmp_path)[0] == command


@pytest.mark.parametrize("entry", ["node_modules/mocha/bin/mocha", "./node_modules/mocha/bin/mocha.js"])
def test_known_node_mocha_entrypoint_replays_without_mutating_plan(tmp_path, entry):
    command = ["node", entry, "--reporter", "json", "lib/utils/config/config.test.js",
               "lib/utils/config/symlink.regression.test.js"]
    original = list(command)
    assert public_test_argv(command)
    actual, env, changes = public_test_execution(command, tmp_path)
    assert actual == [*original, "--exit"]
    assert env == {}
    assert changes
    assert command == original
    assert public_test_execution([*command, "--no-exit"], tmp_path)[0][-1] == "--no-exit"


def test_saved_mui_cross_env_shape_uses_container_environment(tmp_path):
    command = ["node", "node_modules/cross-env/src/bin/cross-env.js", "NODE_ENV=test",
               "BABEL_ENV=test", "BABEL_DISABLE_CACHE=1", "node", "node_modules/mocha/bin/mocha",
               "--exit", "--reporter", "json", "packages/mui-material/src/Autocomplete/Autocomplete.test.js"]
    assert public_test_argv(command)
    actual, env, changes = public_test_execution(command, tmp_path)
    assert actual == command[5:]
    assert env == {"NODE_ENV": "test", "BABEL_ENV": "test", "BABEL_DISABLE_CACHE": "1"}
    assert len(changes) == 4


@pytest.mark.parametrize("command", [
    ["node", "--require", "evil.js", "node_modules/mocha/bin/mocha"],
    ["node", "-e", "console.log('passed')"],
    ["node", "/private/node_modules/mocha/bin/mocha"],
    ["node", "../node_modules/mocha/bin/mocha"],
    ["node", "tools/mocha.js"],
    ["node", "node_modules/cross-env/src/bin/cross-env.js", "NODE_OPTIONS=--require=evil", "mocha"],
    ["node", "node_modules/cross-env/src/bin/cross-env.js", "NODE_ENV=production", "mocha"],
    ["node", "node_modules/cross-env/src/bin/cross-env.js", "NODE_ENV=test", "node", "evil.js"],
    ["node", "node_modules/cross-env/src/bin/cross-env.js", "mocha"],
])
def test_node_wrapper_support_does_not_accept_arbitrary_programs(tmp_path, command):
    assert not public_test_argv(command)
    with pytest.raises(ValueError):
        public_test_execution(command, tmp_path)


def test_author_contract_examples_are_accepted_by_the_replay_runner(tmp_path):
    from benchmarks.polybench.public_checks import public_test_contract
    for command in public_test_contract()["examples"]:
        assert public_test_argv(command)
        public_test_execution(command, tmp_path)
