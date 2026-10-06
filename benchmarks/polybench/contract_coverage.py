"""Public requirement inventory and observed test coverage, without model calls.

This enforces traceability and distinct executed witnesses. It cannot prove that
a worker's assertion semantically covers the quoted requirement.
"""
import hashlib
import json
import re
from typing import Literal

from pydantic import Field

from hx.config import digest
from hx.models import Check, Contract, WorkerSummary
from hx.store import atomic_write

VERSION = "public-contract-coverage@4"
LIMITATION = (
    "Requirement extraction covers explicit expected-behavior sections, with a whole-report fallback. "
    "Observed test identities and distinct boundary witnesses establish coverage traceability, "
    "not independent semantic proof, assertion completeness or resistance to fabricated runner output.")
BOUNDARY = re.compile(r"surpass|exceed|overflow|underflow|boundar|\blimits?\b|\bmaximum\b|\bminimum\b|at least|at most|greater than|less than|\b[\w.)]+\s*[<>]=?\s*[\w(]", re.I)


class ContractCase(Contract):
    requirement: str = Field(pattern=r"^r[0-9]{2}$")
    scenario: Literal["behavior", "below", "at", "above"]
    test_id: str = Field(min_length=3, max_length=700)
    assertion: str = Field(min_length=10, max_length=500)


class CoverageSummary(WorkerSummary):
    contract_cases: list[ContractCase] = Field(max_length=24)


def inventory(report):
    """Keep exact public quotes; never let the worker remove obligations."""
    # Hidden GitHub issue-template instructions are not behavioral requirements.
    rendered = re.sub(r"<!--[\s\S]*?(?:-->|$)", "", report)
    lines = rendered.splitlines()
    sections, active, fence, level = [], False, None, 0
    for line in lines:
        delimiter = re.match(r"^\s*(`{3,}|~{3,})(?:\w.*)?\s*$", line)
        single = re.fullmatch(r"\s*`\s*", line)
        if delimiter or single:
            marker = delimiter[1][0] if delimiter else 'single-backtick'
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence:
            continue
        heading = re.match(r"^\s*(#{1,6})\s+(.+?)\s*#*\s*$", line)
        plain_heading = re.fullmatch(r"\s*(?:\*\*)?(Expected (?:behavio[u]?r|results?|output)|Acceptance criteria|Requirements)(?:\*\*)?\s*:?[ \t]*", line, re.I)
        if heading:
            title = heading[2].lower().strip(': ')
            if re.match(r"^(?:expected (?:behavio[u]?r|results?|output)|acceptance criteria|requirements)(?:\s|$)", title):
                active, level = True, len(heading[1])
            elif active and len(heading[1]) <= level:
                active = False
            continue
        if plain_heading:
            active, level = True, 6
            continue
        if active and line.strip():
            text = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", line).strip()
            if re.fullmatch(r"!\[[^\]]*\]\([^)]*\)",text) or re.match(r"^See (?:the )?image(?:s)? below",text,re.I):
                continue
            sections.append(text)
    quotes = list(dict.fromkeys(sections))
    fallback = not quotes
    if fallback:
        quotes = [rendered.strip()]
    errors = []
    if len(quotes) > 8:
        errors.append("Public contract exceeds eight requirements; coverage cannot be certified by this bounded gate.")
    def boundary_text(quote):
        return re.sub(r"```+[\s\S]*?```+|~~~+[\s\S]*?~~~+|<!--[\s\S]*?-->","",quote)
    requirements = [{"id": f"r{i+1:02}", "quote": quote,
                     "scenarios": ["below", "at", "above"] if BOUNDARY.search(boundary_text(quote)) else ["behavior"]}
                    for i, quote in enumerate(quotes[:8])]
    return {"version": VERSION, "report_sha256": hashlib.sha256(report.encode()).hexdigest(),
            "requirements": requirements, "fallback": fallback, "errors": errors}


def evidence_plan(report, cases):
    required = inventory(report)
    return {"inventory_sha256": digest(required),
            "cases": [case.model_dump() for case in cases]}


def structured_reports(text):
    decoder = json.JSONDecoder()
    for match in list(re.finditer(r"\{\s*\"(?:stats|numFailedTestSuites|numFailedTests|numPassedTestSuites|numTotalTestSuites|success|startTime|testResults)\"", text))[:20]:
        try:
            value, _ = decoder.raw_decode(text[match.start():])
        except ValueError:
            continue
        yield value


def observed_tests(logs):
    """Recognize named passes, never summary counts or skip/xfail statuses."""
    text = re.sub(r"\x1b\[[0-9;]*m", "", logs)
    passed, conflicted = set(), set()
    for line in text.splitlines():
        match = re.match(r"^\s*(\S+::\S+)\s+(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\b", line)
        if match:
            identity = "pytest:" + match[1]
            (passed if match[2] == "PASSED" else conflicted).add(identity)
    # Built-in Mocha JSON and Jest/Vitest JSON reporters need no extra packages.
    for value in structured_reports(text):
        if isinstance(value.get("stats"), dict) and isinstance(value.get("passes"), list):
            for status in ("passes", "failures", "pending"):
                rows = value.get(status, [])
                for row in rows if isinstance(rows, list) else []:
                    if isinstance(row, dict) and isinstance(row.get("fullTitle"), str):
                        identity = "mocha:" + row["fullTitle"]
                        (passed if status == "passes" else conflicted).add(identity)
        if isinstance(value.get("testResults"), list):
            for suite in value["testResults"]:
                if not isinstance(suite, dict):
                    continue
                rows = suite.get("assertionResults", [])
                for row in rows if isinstance(rows, list) else []:
                    if isinstance(row, dict) and isinstance(row.get("fullName"), str):
                        identity = "js:" + row["fullName"]
                        (passed if row.get("status") == "passed" else conflicted).add(identity)
    return passed - conflicted


def coverage_check(candidate, task, directory, public_checks, emit):
    required = inventory(task.report)
    problems = list(required["errors"])
    plan = getattr(candidate, "public_contract", None)
    bindings = []
    if not isinstance(plan, dict) or plan.get("inventory_sha256") != digest(required):
        problems.append("Missing or stale public contract evidence; return contract_cases for the current public requirement inventory.")
    else:
        try:
            if set(plan) != {"inventory_sha256", "cases"} or len(plan["cases"]) > 24:
                raise ValueError("invalid plan shape")
            bindings = [ContractCase.model_validate(row) for row in plan["cases"]]
        except (ValueError, TypeError, KeyError):
            problems.append("Invalid public contract evidence shape.")
    observed = set()
    for index, check in enumerate(public_checks, 1):
        if not check.passed:
            continue
        chunks = []
        for name in ("stdout.txt", "stderr.txt"):
            path = directory / f"public_test_{index}" / name
            if path.is_file():
                if path.stat().st_size > 2_000_000:
                    problems.append(f"public_test_{index} report exceeds bounded coverage parsing; select focused tests.")
                    continue
                chunks.append(path.read_text("utf-8", errors="replace"))
        observed.update(observed_tests("\n".join(chunks)))
    expected = {(req["id"], scenario) for req in required["requirements"] for scenario in req["scenarios"]}
    covered, used_tests = set(), set()
    for binding in bindings:
        key = (binding.requirement, binding.scenario)
        if key not in expected:
            problems.append(f"Unknown obligation {key}; worker cannot remove or redefine the public contract.")
        elif binding.test_id in used_tests:
            problems.append(f"Duplicate evidence for {binding.requirement}/{binding.scenario}; use distinct executed tests for distinct obligations.")
        elif binding.test_id not in observed:
            problems.append(f"Unobserved passing test {binding.test_id}; use pytest -vv or built-in Mocha/Jest/Vitest JSON output. Skips and summary counts do not qualify.")
        else:
            covered.add(key)
            used_tests.add(binding.test_id)
    for req, scenario in sorted(expected - covered):
        quote = next(r["quote"] for r in required["requirements"] if r["id"] == req)
        problems.append(f"Missing {req}/{scenario}: {quote[:500]}")
    passed = not problems and bool(expected)
    artifact = {"version": VERSION, "candidate_commit": candidate.candidate_commit,
                "inventory": required, "bindings": [b.model_dump() for b in bindings],
                "observed_passing_tests": sorted(observed), "covered": sorted(covered),
                "passed": passed, "problems": problems, "limitation": LIMITATION}
    atomic_write(directory / "contract_coverage.json", json.dumps(artifact, indent=2).encode())
    emit("verification.contract_coverage", {"passed": passed, "covered": len(covered),
         "required": len(expected), "problems": problems[:8]})
    return Check(name="public_contract_coverage", passed=passed,
                 evidence="Distinct executed tests cover the recorded public contract. " + LIMITATION if passed
                 else "\n".join(problems)[:12000])
