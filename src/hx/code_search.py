"""Paper-inspired code search over a pure evidence tool, with immutable experience.

This is a mechanism search, not an end-to-end coding benchmark. Evaluation is
outside the proposer and candidate code never receives authentication.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from pydantic import Field

from hx.config import canonical
from hx.models import Contract, HXError
from hx.store import atomic_write

TARGET = "src/hx/failure_evidence.py"


class CodeProposal(Contract):
    diagnosis: str = Field(min_length=20, max_length=3000)
    inspected_files: list[str] = Field(min_length=1, max_length=30)
    change: str = Field(min_length=20, max_length=3000)
    limitations: list[str] = Field(min_length=1, max_length=8)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def seal(root: Path) -> dict:
    """No links or hidden extra artifacts can masquerade as archived experience."""
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise HXError("Experience contains a symlink")
        if path.is_file():
            files[path.relative_to(root).as_posix()] = sha(path.read_bytes())
    return files


def copy_experience(destination: Path, sources: dict[str, Path]) -> dict:
    """Caller explicitly names public files; never recursively import run roots."""
    destination.mkdir(parents=True, exist_ok=False)
    for name, source in sources.items():
        relative = Path(name)
        if relative.is_absolute() or any(p in {"..", "."} for p in relative.parts):
            raise HXError("Invalid experience path")
        if source.is_symlink() or not source.is_file():
            raise HXError("Public experience must be a regular file")
        data = source.read_bytes()
        if len(data) > 20_000_000:
            raise HXError("Public experience file exceeds archive limit; not silently truncated")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(target, data)
    return seal(destination)


def validate_source(data: bytes, interface="focused_output", parameters=("output", "limit")):
    """Deliberately narrow pure-code surface, not a general Python sandbox."""
    if len(data) > 32_000:
        raise HXError("Candidate code too large")
    tree = ast.parse(data)
    forbidden = {"open", "eval", "exec", "compile", "globals", "locals", "vars",
        "getattr", "setattr", "delattr", "__import__", "input", "breakpoint"}
    allowed_attributes = {"compile", "search", "match", "finditer", "findall", "split",
        "sub", "escape", "I", "IGNORECASE", "M", "MULTILINE", "S", "DOTALL",
        "splitlines", "join", "strip", "lstrip", "rstrip", "lower", "upper", "casefold",
        "startswith", "endswith", "replace", "find", "rfind", "count", "append", "extend",
        "add", "items", "keys", "values", "get", "pop", "index", "sort", "group", "span",
        "start", "end", "fromkeys", "isalnum", "isspace", "isalpha", "isdigit"}
    found = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if not isinstance(node, ast.Import) or any(a.name != "re" or a.asname for a in node.names):
                raise HXError("Only direct import re is permitted in this pure tool")
        if isinstance(node, ast.Name) and (node.id in forbidden or "__" in node.id):
            raise HXError("Forbidden capability in candidate")
        if isinstance(node, ast.Attribute) and node.attr not in allowed_attributes:
            raise HXError("Unsupported attribute in pure candidate: " + node.attr)
        if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef, ast.With, ast.AsyncWith)):
            raise HXError("Unsupported candidate construct")
        if isinstance(node, ast.FunctionDef) and node.decorator_list:
            raise HXError("Candidate decorators are unsupported")
        if isinstance(node, ast.FunctionDef) and node.name == interface:
            found = True
            if ([arg.arg for arg in node.args.args] != list(parameters)
                    or node.args.posonlyargs or node.args.kwonlyargs or node.args.vararg or node.args.kwarg):
                raise HXError(interface + " interface changed")
    if not found:
        raise HXError("Missing " + interface + " interface")
    return tree


def search_cases() -> list[dict]:
    noise = "WARNING: deprecated option in compatibility layer\n" * 100
    return [
        {"id": "warning-before-error", "output": noise + "AssertionError: expected missing task to return 404\n" + noise,
            "needles": ["expected missing task to return 404"], "limit": 800},
        {"id": "late-cause", "output": "Traceback (most recent call last):\n" +
            "  compatibility diagnostic context\n" * 90 + "ValueError: unsupported structured input\n" + noise,
            "needles": ["unsupported structured input"], "limit": 800},
        {"id": "two-causes", "output": "ERROR " + "transient setup warning " * 90 + "\n" +
            "FAILED tests/test_status.py - AssertionError: response status mismatch\n" + noise,
            "needles": ["response status mismatch"], "limit": 1000},
        {"id": "short", "output": "1 passed", "needles": ["1 passed"], "limit": 800},
    ]


def validation_cases() -> list[dict]:
    # These are not exported to the proposer. A failed validation is not fed back
    # during this attempt; a subsequent new search must use a new validation set.
    padding = "notice: optional renderer extension unavailable\n" * 130
    return [
        {"id": "validation-terminal-cause", "output": "Traceback\n" + "  execution frame\n" * 110 +
            "RuntimeError: transaction was rolled back unexpectedly\n" + padding,
            "needles": ["transaction was rolled back unexpectedly"], "limit": 900},
        {"id": "validation-failed-summary", "output": "ERROR " + "loader details " * 150 +
            "\nFAILED test_navigation - AssertionError: route changed after redirect\n" + padding,
            "needles": ["route changed after redirect"], "limit": 900},
        {"id": "validation-no-error", "output": padding, "needles": [], "limit": 900},
    ]


def evaluate(source: Path, cases: list[dict], directory: Path) -> dict:
    validate_source(source.read_bytes())
    directory.mkdir(parents=True, exist_ok=False)
    atomic_write(directory / "cases.json", canonical(cases))
    # Isolated interpreter, no Codex auth env or model call. Imports use stdlib only.
    driver = """import json,runpy,sys
try:
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU,(4,4))
except ImportError:
    pass
function=runpy.run_path(sys.argv[1])['focused_output']
cases=json.load(open(sys.argv[2]))
rows=[]
for case in cases:
    text=function(case['output'],case['limit'])
    if not isinstance(text,str) or len(text)>case['limit']:
        raise ValueError('invalid or oversized output')
    rows.append({'id':case['id'],'passed':all(n in text for n in case['needles']),
                 'characters':len(text),'excerpt':text})
print(json.dumps(rows))
"""
    result = subprocess.run([sys.executable, "-I", "-c", driver, str(source.resolve()),
        str((directory / "cases.json").resolve())], capture_output=True, timeout=8,
        env={"SYSTEMROOT": os.environ["SYSTEMROOT"]} if sys.platform == "win32" else {})
    atomic_write(directory / "stdout.json", result.stdout)
    atomic_write(directory / "stderr.txt", result.stderr)
    if result.returncode or len(result.stdout) > 40_000:
        raise HXError("Candidate mechanism evaluation failed; raw output retained")
    rows = json.loads(result.stdout)
    score = {"quality": sum(r["passed"] for r in rows), "count": len(rows),
        "context_characters": sum(r["characters"] for r in rows), "rows": rows,
        "metric": "Diagnostic retention and excerpt size; not coding accuracy or model tokens"}
    atomic_write(directory / "score.json", canonical(score))
    return score


def dominates(candidate: dict, incumbent: dict) -> bool:
    return (candidate["quality"] >= incumbent["quality"] and
        candidate["context_characters"] <= incumbent["context_characters"] and
        (candidate["quality"] > incumbent["quality"] or
         candidate["context_characters"] < incumbent["context_characters"]))


def frontier(scores: dict[str, dict]) -> list[str]:
    return sorted(name for name, score in scores.items()
        if not any(dominates(other, score) for key, other in scores.items() if key != name))
