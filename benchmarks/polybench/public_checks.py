"""Replay worker-selected public tests; never consume benchmark-private commands."""
import json
import re
import shlex
from pathlib import PurePosixPath

VERSION = "public-runner-contract@2"
TEST_ENVIRONMENT = {"BABEL_DISABLE_CACHE": "1", "NODE_ENV": "test", "BABEL_ENV": "test"}
MOCHA_ENTRYPOINTS = {"node_modules/mocha/bin/mocha", "node_modules/mocha/bin/mocha.js"}
CROSS_ENV_ENTRYPOINT = "node_modules/cross-env/src/bin/cross-env.js"


def _known_node_entrypoint(argv, paths):
    return (len(argv) >= 2 and PurePosixPath(argv[0]).name == "node"
            and argv[1] in paths | {"./" + p for p in paths})


def _test_prefix(argv):
    """Unwrap only the known cross-env entrypoint and fixed test assignments.

    Never accept arbitrary Node programs, Node options, environment variables,
    shell wrappers, or paths merely sharing a basename with the allowed ones.
    """
    command, environment, changes = list(argv), {}, []
    if _known_node_entrypoint(command, {CROSS_ENV_ENTRYPOINT}):
        command = command[2:]
        if not command or "=" not in command[0]:
            raise ValueError("cross-env test wrapper requires known test assignments")
        changes.append("Unwrapped known cross-env test entrypoint")
    while command and "=" in command[0]:
        key, value = command[0].split("=", 1)
        if TEST_ENVIRONMENT.get(key) != value:
            raise ValueError("Unsupported test environment assignment")
        environment[key] = value
        command.pop(0)
        changes.append("Moved known test environment assignment into Docker environment")
    return command, environment, changes


def public_test_contract():
    """The same bounded runner contract used by authoring and independent replay."""
    return {
        "version": VERSION,
        "examples": [
            ["python", "-m", "pytest", "-vv", "tests/test_behavior.py"],
            ["./node_modules/.bin/mocha", "--reporter", "json", "tests/behavior.test.js"],
            ["node", "node_modules/mocha/bin/mocha", "--reporter", "json", "tests/behavior.test.js"],
            ["npm", "run", "test:unit", "--", "--reporter", "json"],
        ],
        "instructions": (
            "Return argv, not shell text. Replay supports pytest, Mocha/Jest/Vitest executable "
            "aliases, conventional package test scripts, node --test, and these exact local "
            "Node Mocha entrypoints: node_modules/mocha/bin/mocha or mocha.js (optional ./). "
            "The exact Node cross-env entrypoint node_modules/cross-env/src/bin/cross-env.js "
            "may precede only NODE_ENV=test, BABEL_ENV=test, BABEL_DISABLE_CACHE=1 and a supported "
            "test command. Arbitrary Node scripts, -e/-r/--require/--import options, shell "
            "wrappers and other environment assignments are unsupported. Discovery or command "
            "acceptance is not execution evidence. Use installed public tooling and inspect "
            "real named test output."
        ),
    }


def test_script(name):
    return bool(re.fullmatch(r"test(?:[:-][A-Za-z0-9][A-Za-z0-9:_-]*)?", name))


def public_test_argv(argv: list[str]) -> bool:
    """Accept common test runners, not arbitrary shell or interpreter programs.

    This validates command shape, not test relevance or test honesty. Execution
    stays in an offline disposable container without model credentials.
    """
    try:
        argv, _, _ = _test_prefix(argv)
    except ValueError:
        return False
    if not argv:
        return False
    executable = PurePosixPath(argv[0]).name
    runners = {"mocha", "jest", "vitest"}
    if argv[0] in runners or argv[0] in {"./node_modules/.bin/" + r for r in runners}:
        return True
    if executable in {"python", "python3"}:
        return len(argv) >= 3 and argv[1:3] == ["-m", "pytest"]
    if executable == "pytest":
        return True
    if executable in {"npm", "yarn", "pnpm"}:
        args = argv[1:]
        if executable in {"yarn", "pnpm"} and args and args[0] in runners:
            return True
        return bool(args) and (
            args[0] == "test" or
            executable in {"yarn", "pnpm"} and test_script(args[0]) or
            len(args) >= 2 and args[0] == "run" and
            test_script(args[1])
        )
    return (executable == "node" and len(argv) > 1 and argv[1] == "--test"
            or _known_node_entrypoint(argv, MOCHA_ENTRYPOINTS))


def public_test_execution(argv, workspace):
    """Normalize known environment prefixes and Mocha lifecycle from public metadata.

    This changes execution only, preserving the original candidate/test plan.
    Mocha --exit runs after its assertions; it does not verify resource cleanup.
    """
    command, environment, changes = _test_prefix(argv)
    if not public_test_argv(command):
        raise ValueError("Unsupported public test runner")
    executable = PurePosixPath(command[0]).name
    mocha = executable == "mocha" or _known_node_entrypoint(command, MOCHA_ENTRYPOINTS)
    if executable in {"npm", "yarn", "pnpm"}:
        script = command[2] if len(command) > 2 and command[1] == "run" else command[1]
        mocha = executable in {"yarn", "pnpm"} and command[1] == "mocha"
        manifest = workspace / "package.json"
        if manifest.is_file() and manifest.resolve().is_relative_to(workspace.resolve()) and manifest.stat().st_size <= 100000:
            try:
                script_text = json.loads(manifest.read_text()).get("scripts", {}).get(script, "")
                tokens = shlex.split(script_text)
                if tokens and tokens[0] == "cross-env":
                    tokens.pop(0)
                    while tokens and "=" in tokens[0]:
                        tokens.pop(0)
                mocha = mocha or bool(tokens) and PurePosixPath(tokens[0]).name == "mocha"
            except (ValueError, AttributeError, TypeError):
                pass
    if mocha and "--exit" not in command and "--no-exit" not in command:
        if executable == "npm" and "--" not in command:
            command.append("--")
        command.append("--exit")
        changes.append("Explicit Mocha exit after completed tests; dangling resource cleanup remains unverified")
    return command, environment, changes
