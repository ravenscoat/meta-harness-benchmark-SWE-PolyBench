"""Independent public-test replay on original production source.

This checks differential behavior, not whether worker-authored tests cover an issue.
No evaluator data or model credentials enter the disposable replay container.
"""
import hashlib
import re
import subprocess
from pathlib import Path, PurePosixPath

from benchmarks.polybench.containers import archive, command, create, populate
from benchmarks.polybench.contract_coverage import observed_tests, structured_reports
from benchmarks.polybench.delivery import is_test_path
from benchmarks.polybench.dependencies import prepare_dependencies, share_public_fixture
from benchmarks.polybench.prepare import write
from benchmarks.polybench.public_checks import public_test_execution
from benchmarks.polybench.report_capture import capture_argv
from benchmarks.polybench.test_environment import docker_environment
from benchmarks.polybench.worker_environment import build_check
from hx.check_execution import command_check
from hx.models import Check
from hx.process import clean_env

VERSION = "public-base-regression@11"
SVELTE_RUNNER_SHA256 = "8174388346cfb3b8a2d9edab9747d32a775fd50aaa60c46ed6f9b1de5e65b340"
LIMITATION = (
    "Base red / candidate green is differential test evidence, not proof of issue relevance or "
    "completeness. Worker tests and runner output remain untrusted; unrelated or fabricated "
    "assertions can pass this gate. Independent task evaluation remains separate."
)


def test_projection(candidate):
    """Generate a bounded regular-file test patch using public path conventions."""
    def git(*args):
        return subprocess.run(["git", "-C", candidate.workspace, *args], check=True,
            capture_output=True, timeout=60).stdout

    names = git("diff", "--name-only", "-z", "--no-renames",
        candidate.base_commit, candidate.candidate_commit).decode().split("\0")
    paths = [p for p in names if p and is_test_path(p)]
    if len(paths) > 50:
        raise ValueError("Public regression overlay exceeds 50 files")
    for p in paths:
        if "\n" in p or "\r" in p or "\\" in p or p.startswith("/") or ".." in Path(p).parts:
            raise ValueError("Unsafe public regression path")
    specs = [":(literal)" + p for p in paths]
    if not specs:
        return b"", paths
    for revision in (candidate.base_commit, candidate.candidate_commit):
        entries = git("ls-tree", "-r", "-z", revision, "--", *specs).split(b"\0")
        if any(row and row.split(b" ", 1)[0] not in {b"100644", b"100755"} for row in entries):
            raise ValueError("Public regression overlay must contain regular files, not links")
    patch = git("diff", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames",
        candidate.base_commit, candidate.candidate_commit, "--", *specs)
    if len(patch) > 2_000_000:
        raise ValueError("Public regression overlay exceeds two MB")
    return patch, paths


def svelte_followup_policy(container, workdir, case, base_commit):
    """Attest the unchanged public runner before interpreting its skip errors."""
    if case.get("repo") != "sveltejs/svelte":
        return None
    path = "test/runtime/index.js"
    # This optional exception policy only applies to the attested legacy JS
    # runner. Newer Svelte versions use a TS runner; absence is not setup failure.
    # Keep genuine Git/container errors visible instead of catching all failures.
    entry = command(container, ["git", "ls-tree", "-z", base_commit, "--", path], workdir)
    fields = entry.removesuffix(b"\0").split(b"\t")
    if (len(fields) != 2 or fields[1] != path.encode()
            or not fields[0].startswith((b"100644 blob ", b"100755 blob "))):
        return None
    original = command(container, ["git", "show", base_commit + ":" + path], workdir)
    if hashlib.sha256(original).hexdigest() != SVELTE_RUNNER_SHA256:
        return None
    active = command(container, ["cat", path], workdir)
    if active != original:
        return None
    return {"version": "svelte-followup-errors@1", "runner": path,
            "sha256": SVELTE_RUNNER_SHA256, "line": 64}


def mocha_test_body_frame(line):
    """Use the same test-path conventions as the independently replayed overlay."""
    match = re.fullmatch(r'\s*at Context\.[^\n]+ \(([^\n()]+):\d+:\d+\)', line)
    if not match:
        return False
    path = match[1]
    parts = PurePosixPath(path).parts
    return (bool(re.search(r'\.[cm]?[jt]sx?$', path))
            and '\\' not in path and not any(p in {'..', 'node_modules'} for p in parts)
            and is_test_path(path))


def generated_constructor_failure(error, stats, failures):
    """Recognize a generated application constructor throwing in a Mocha body.

    This is observed runtime behavior, not proof of issue relevance. Do not
    infer reproduction from arbitrary exceptions, compile/loader failures,
    or a test frame mentioned only inside an eval origin.
    """
    counts = [stats.get(k) for k in ('tests', 'passes', 'failures', 'pending')]
    if (any(type(n) is not int or n < 0 for n in counts)
            or counts[2] != len(failures) or counts[0] != sum(counts[1:])):
        return False
    message, stack = error.get('message'), error.get('stack')
    if not isinstance(message, str) or not message or not isinstance(stack, str):
        return False
    lines = stack.splitlines()
    if len(lines) < 3 or lines[0] not in {name + ': ' + message
            for name in ('Error', 'TypeError', 'RangeError')}:
        return False
    # Require the top throw frame to be a generated constructor, followed by
    # an actual Context call from a conventional test file. Setup remains
    # rejected by classify() before this path is considered.
    constructor = re.fullmatch(
        r'\s*at new [A-Za-z_$][\w$]* \(eval at [^\n]+, <anonymous>:\d+:\d+\)', lines[1])
    body = any(mocha_test_body_frame(line) for line in lines[2:])
    return bool(constructor and body)


def source_runtime_failure(failure, stats, failures):
    """A counted TypeError/RangeError thrown by source called from a test body.

    This records execution failure, not issue relevance. Test-only throws,
    loader/hook errors, ambiguous frames and inconsistent counts fail closed.
    """
    counts = [stats.get(k) for k in ('tests', 'passes', 'failures', 'pending')]
    if (any(type(n) is not int or n < 0 for n in counts)
            or counts[2] != len(failures) or counts[0] != sum(counts[1:])):
        return False
    error = failure.get('err', {})
    message, stack = error.get('message'), error.get('stack')
    if not isinstance(message, str) or not message or not isinstance(stack, str):
        return False
    lines = stack.splitlines()
    if len(lines) < 3 or lines[0] not in {'TypeError: ' + message, 'RangeError: ' + message}:
        return False
    top = re.fullmatch(r'\s*at [\w.$<>]+ \(([^\n()]+):\d+:\d+\)', lines[1])
    if not top:
        return False
    path = top[1]
    parts = PurePosixPath(path).parts
    if ('\\' in path or any(p in {'..', 'node_modules'} for p in parts)
            or not re.search(r'\.[cm]?[jt]sx?$', path) or is_test_path(path)):
        return False
    # A require/import stack is setup, even if a Context frame follows it.
    if any(re.search(r'\bat (?:Module\.|require\b|.*(?:Hook|\.setup)\b)', line) for line in lines[2:]):
        return False
    test_file = failure.get('file')
    if not isinstance(test_file, str) or not is_test_path(test_file):
        return False
    for line in lines[2:]:
        frame = re.fullmatch(r'\s*at Context\.[^\n]+ \(([^\n()]+):\d+:\d+\)', line)
        if frame and mocha_test_body_frame(line):
            # Mocha's file is absolute; transpiled stack paths can be relative.
            return test_file == frame[1] or test_file.endswith('/' + frame[1])
    return False


def mocha_behavioral_failures(report, policy=None):
    failures = report.get("failures")
    if not isinstance(failures, list) or not failures:
        return False
    asserted = set()
    assertions = 0
    stats = report.get("stats", {})
    if not isinstance(stats, dict):
        stats = {}
    for failure in failures:
        if not isinstance(failure, dict):
            return False
        error, title = failure.get("err", {}), failure.get("fullTitle", "")
        if not isinstance(error, dict) or not isinstance(title, str) or not title or re.search(r"\bhook\b", title, re.I):
            return False
        family = re.fullmatch(r"(runtime [^()\n]+) \((?:shared|inline) helpers\)", title)
        stack = str(error.get("stack", ""))
        message = str(error.get("message", ""))
        label_assertion = (
            message.startswith("Found a label with the text of: ")
            and 'however no form control was found associated to that label.' in message.split('\n', 1)[0]
            and stack.startswith(('Error: ' + message.split('\n', 1)[0],
                                  'TestingLibraryElementError: ' + message.split('\n', 1)[0]))
            and bool(re.search(r"\b(?:get|find)ByLabelText\b", stack))
        )
        # Testing Library's getBy* queries assert DOM presence by throwing a
        # named error, rather than an AssertionError. Require a real test frame
        # and matching structured counts; setup/hooks still fail closed.
        dom_assertion = (
            (label_assertion or (
                stack.startswith("TestingLibraryElementError: Unable to find an element with the role ")
                and message.startswith("Unable to find an element with the role ")))
            and bool(re.search(r"\.(?:test|spec)\.[jt]sx?:\d+:\d+", stack))
            and stats.get("failures") == len(failures)
        )
        if (error.get("code") == "ERR_ASSERTION" or "AssertionError" in stack or dom_assertion
                or generated_constructor_failure(error, stats, failures)
                or source_runtime_failure(failure, stats, failures)):
            assertions += 1
            if family:
                asserted.add(family[1])
            continue
        # Only this attested runner deliberately throws these follow-up errors.
        # Orphan skips, unrelated errors and skipped tests never prove behavior.
        if (not policy or policy.get("sha256") != SVELTE_RUNNER_SHA256
                or not family or family[1] not in asserted
                or error.get("message") != "skipping test, already failed"
                or not str(error.get("stack", "")).startswith("Error: skipping test, already failed\n")
                or not re.search(r"\(test/runtime/index\.js:64:11\)", str(error.get("stack", "")))
                or stats.get("failures") != len(failures)):
            return False
    return assertions > 0


def classify(check, followup_policy=None):
    """Conservative common-runner output classifier; uncertainty fails closed."""
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", check.evidence)
    if "Child tree terminated" in text:
        return "timeout"
    if re.search(r"ModuleNotFoundError|ImportError|Cannot find module|ERR_MODULE_NOT_FOUND|"
        r"ERROR collecting|ERROR at setup of|ERROR at teardown of|"
        r"^ERROR .+::|\b[1-9]\d* errors?\b|error during collection|errors during collection|"
        r"(?:before|after) (?:all|each)[\"']? hook|Missing script|command not found|"
        r"No such file or directory|SyntaxError|no test files found", text, re.I | re.M):
        return "setup_error"
    if re.search(r"no tests (?:ran|collected|found)|0 passing\b", text, re.I) and not re.search(
        r"[1-9]\d* (?:failed|failing)\b", text):
        return "no_tests"
    if check.passed:
        if observed_tests(text):
            return "baseline_passed"
        if re.search(r"\b[1-9]\d* (?:passed|passing)\b|Tests:\s+.*[1-9]\d* passed|"
            r"# pass [1-9]\d*", text):
            return "baseline_passed"
        return "inconclusive"
    # A nonzero exit is insufficient: require a test-runner failure summary
    # together with test-case failure evidence, not a collection/hook failure.
    pytest = re.search(r"\b[1-9]\d* failed\b", text) and re.search(r"(?m)^FAILED .+::", text)
    mocha = re.search(r"(?m)^\s*[1-9]\d* failing\s*$", text) and "AssertionError" in text
    javascript = re.search(r"Tests:\s+.*[1-9]\d* failed", text) and re.search(
        r"AssertionError|Expected:|Expected |Received:", text)
    node = re.search(r"# fail [1-9]\d*", text) and "ERR_ASSERTION" in text
    for report in structured_reports(text):
        failures = report.get("failures")
        if isinstance(failures, list) and failures:
            return "behavioral_failure" if mocha_behavioral_failures(report, followup_policy) else "inconclusive"
        suites = report.get("testResults", [])
        if isinstance(suites, list):
            failed = [row for suite in suites if isinstance(suite, dict)
                      and isinstance(suite.get("assertionResults"), list)
                      for row in (suite.get("assertionResults") or []) if isinstance(row, dict)
                      and row.get("status") == "failed"]
            if failed and all(re.search(r"AssertionError|Expected:|Expected |Received:",
                                       str(row.get("failureMessages", ""))) for row in failed):
                return "behavioral_failure"
    return "behavioral_failure" if pytest or mocha or javascript or node else "inconclusive"


def classify_public_logs(check, logs, settings, policy=None):
    """Classify complete bounded output, never silently drop a large stream."""
    limit = min(settings.max_log_bytes, 20_000_000)
    chunks, sizes = [], {}
    for name in ('stdout.txt', 'stderr.txt'):
        path = logs / name
        if not path.is_file():
            continue
        with path.open('rb') as stream:
            data = stream.read(limit - sum(sizes.values()) + 1)
        sizes[name] = len(data)
        if sum(sizes.values()) > limit:
            return 'report_oversized', {'limit_bytes': limit, 'bytes_read': sizes,
                'error': 'Complete public output exceeds classification budget; no stream was ignored.'}
        chunks.append(data.decode('utf-8', errors='replace'))
    text = '\n'.join(chunks) if chunks else check.evidence
    if 'Child tree terminated' in check.evidence:
        return 'timeout', {'limit_bytes': limit, 'bytes_read': sizes}
    summaries = []
    for report in structured_reports(text):
        stats = report.get('stats')
        if isinstance(stats, dict):
            failures = report.get('failures')
            failures = failures if isinstance(failures, list) else []
            summaries.append({'stats': {k: stats.get(k) for k in ('tests', 'passes', 'failures', 'pending')},
                'failures': [{'title': str(f.get('fullTitle', ''))[:500],
                    'message': str(f.get('err', {}).get('message', ''))[:500]}
                    for f in failures[:100] if isinstance(f, dict)
                    and isinstance(f.get('err', {}), dict)]})
    category = classify(check.model_copy(update={'evidence': text}), policy)
    return category, {'limit_bytes': limit, 'bytes_read': sizes, 'reports': summaries}


def regression_check(candidate, task, directory, settings, client, case, control, emit):
    evidence = {"version": VERSION, "base_commit": task.base_commit,
        "candidate_commit": candidate.candidate_commit, "model_calls": 0,
        "limitation": LIMITATION, "commands": []}

    def finish(passed, category, message):
        evidence.update(passed=passed, category=category)
        write(directory / "regression.json", evidence)
        emit("verification.regression", evidence)
        return Check(name="public_regression_reproduced", passed=passed, evidence=message)

    control()
    emit("verification.regression.started", {"version": VERSION, "base_commit": task.base_commit})
    if task.base_commit != candidate.base_commit:
        return finish(False, "projection_error", "Task and candidate base commits differ")
    if not 1 <= len(candidate.verification_commands) <= 3:
        return finish(False, "missing_test_plan", "Supply one to three focused functional commands")
    try:
        patch, paths = test_projection(candidate)
    except (ValueError, subprocess.CalledProcessError) as exc:
        return finish(False, "projection_error", str(exc))
    evidence.update(test_paths=paths, test_overlay_sha256=hashlib.sha256(patch).hexdigest())
    bootstrap = case.get("repo") in {"huggingface/transformers", "microsoft/vscode"}
    container, workdir = create(client, case, offline=not bootstrap)
    try:
        if bootstrap:
            prepare_dependencies(container, case["repo"], directory / "dependencies", case["upstream_base"])
            share_public_fixture(container, case["repo"])
            container.reload()
            for network in list(container.attrs["NetworkSettings"]["Networks"]):
                client.networks.get(network).disconnect(container)
            container.reload()
            if container.attrs["NetworkSettings"]["Networks"]:
                raise RuntimeError("Base regression container did not become offline")
        populate(container, workdir, Path(candidate.workspace), case)
        control()
        command(container, ["git", "reset", "--hard", task.base_commit], workdir, "1000:1000")
        command(container, ["git", "clean", "-fd"], workdir, "1000:1000")
        if patch:
            if not container.put_archive("/tmp", archive({"hx-public-regression.patch": patch}, uid=1000)):
                raise RuntimeError("Public regression overlay transfer failed")
            command(container, ["git", "apply", "--binary", "--whitespace=nowarn",
                "/tmp/hx-public-regression.patch"], workdir, "1000:1000")
        command(container, ["git", "add", "--all"], workdir, "1000:1000")
        changed = command(container, ["git", "diff", "--cached", "--name-only", "-z",
            task.base_commit], workdir, "1000:1000").decode().split("\0")
        if set(filter(None, changed)) - set(paths):
            return finish(False, "projection_error", "Non-test source entered base replay")
        before = command(container, ["git", "write-tree"], workdir, "1000:1000")
        followups = svelte_followup_policy(container, workdir, case, task.base_commit)
        evidence["followup_policy"] = followups
        build = build_check(container, workdir, Path(candidate.workspace), case,
            directory / "public-build", settings, control, emit)
        if build and not build.passed:
            return finish(False, "setup_error", "Base public build prerequisite failed: " + build.evidence)
        for index, argv in enumerate(candidate.verification_commands):
            control()
            # Same normalized argv as the candidate replay. A new package script
            # absent from the original manifest remains a setup error, never red.
            actual, environment, adaptations = public_test_execution(argv, Path(candidate.workspace))
            logs = directory / f"base_test_{index + 1}"
            check = command_check(f"base_test_{index + 1}", ["docker", "exec", "-u", "1000:1000",
                *docker_environment(), *[v for k, value in environment.items() for v in ("-e", k + "=" + value)],
                "-w", workdir, container.id, *capture_argv(actual, settings.max_log_bytes)], directory, clean_env(), logs, settings, control, emit)
            category, ingestion = classify_public_logs(check, logs, settings, followups)
            evidence["commands"].append({"original_argv": argv, "executed_argv": actual,
                "adaptations": adaptations, "category": category, "ingestion": ingestion, "logs": str(logs),
                "check": check.model_dump()})
        command(container, ["git", "add", "--all"], workdir, "1000:1000")
        if command(container, ["git", "write-tree"], workdir, "1000:1000") != before:
            return finish(False, "mutated_source", "Tests changed the base replay source; reproduction is untrusted")
        categories = [c["category"] for c in evidence["commands"]]
        reproduced = "behavioral_failure" in categories and all(
            c in {"behavioral_failure", "baseline_passed"} for c in categories)
        return finish(reproduced, "reproduced" if reproduced else "not_reproduced",
            "Base replay: " + ", ".join(categories) + ". " + (
                "Observed test failure on original production code; candidate checks passed separately. "
                if reproduced else "Need a focused regression that fails behaviorally on the original code. "
                "Timeouts, import/setup errors, empty runs and unknown output do not establish reproduction. ") + LIMITATION)
    finally:
        container.remove(force=True)
