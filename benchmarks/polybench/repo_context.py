"""Read-only, bounded repository orientation prototype; not in the live runtime.

Uses tracked public source only. Does not run repository code or test commands.
"""
import argparse
import ast
import json
import math
import re
import subprocess
from pathlib import Path

MAX_READ = 96_000
MAX_TOTAL_READ = 16_000_000
MAX_SOURCE_FILES = 2_000
PRIVATE_NAMES = {"auth.json", ".env", "patch_code.diff", "patch_test.diff", "eval.sh"}
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".svelte"}


def tracked_files(root):
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--stage", "-z"],
        check=True, capture_output=True, timeout=15,
    )
    files = []
    for entry in result.stdout.split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, _, stage = metadata.split()
        if mode not in {b"100644", b"100755"} or stage != b"0":
            continue
        name = raw_path.decode("utf-8", errors="replace")
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or path.name in PRIVATE_NAMES:
            continue
        if any(part.startswith(".env") or part in {".git", ".hx", "node_modules"}
               for part in path.parts):
            continue
        candidate = root / path
        # Reject links at every level, including links escaping through a parent.
        if any(parent.is_symlink() for parent in [candidate, *candidate.parents]
               if parent != root.parent):
            continue
        if candidate.is_file() and root in candidate.resolve().parents:
            files.append(name)
    return sorted(set(files))


def bounded_read(root, name):
    with (root / name).open("rb") as stream:
        data = stream.read(MAX_READ + 1)
    if len(data) > MAX_READ or b"\0" in data:
        return None
    return data.decode("utf-8", errors="replace")


def outline(content, suffix):
    if suffix == ".py":
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return {"status": "parse_error", "symbols": []}
        symbols = [{"name": node.name, "line": node.lineno,
                    "kind": "class" if isinstance(node, ast.ClassDef) else "function"}
                   for node in tree.body
                   if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
        segment = getattr(ast, "get_source_segment", None)
        lines = content.splitlines()
        imports = [segment(content, node) if segment else lines[node.lineno - 1] for node in tree.body
                   if isinstance(node, (ast.Import, ast.ImportFrom))]
        return {"status": "python_ast", "symbols": symbols[:30],
                "imports": [item[:180] for item in imports[:12] if item]}
    symbols = []
    pattern = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?"
                         r"(?:function|class|const|let)\s+([A-Za-z_$][\w$]*)")
    for number, line in enumerate(content.splitlines(), 1):
        match = pattern.match(line)
        if match:
            symbols.append({"name": match.group(1), "line": number})
    return {"status": "lexical_only", "symbols": symbols[:30]}


def inspect(root, query, limit=12):
    root = root.resolve(strict=True)
    files = tracked_files(root)
    terms = list(dict.fromkeys(re.findall(r"[a-zA-Z_][a-zA-Z_0-9]{2,}", query.lower())))[:20]
    # Rare path anchors (e.g. summary) deserve more attention than model-wide words.
    weights = {term: 4 * math.log1p(len(files) / (1 + sum(term in name.lower() for name in files)))
               for term in terms}
    ranked = []
    tests = []
    manifests = []
    source_files = []
    for name in files:
        path = Path(name)
        lower = name.lower()
        is_test = bool(re.search(r"(^|/)(tests?|__tests__)(/|$)|test_|[._]test[.]|[._]spec[.]", lower))
        if is_test and path.suffix in SOURCE_SUFFIXES:
            tests.append(name)
        if path.name in {"package.json", "pyproject.toml", "pytest.ini", "tox.ini"}:
            manifests.append(name)
        if path.suffix not in SOURCE_SUFFIXES:
            continue
        path_score = sum(weights[term] for term in terms if term in lower)
        source_files.append((path_score, name, is_test))
    source_files.sort(key=lambda item: (-item[0], item[1]))
    scanned = 0
    read_bytes = 0
    for path_score, name, is_test in source_files[:MAX_SOURCE_FILES]:
        if read_bytes + MAX_READ > MAX_TOTAL_READ:
            break
        scanned += 1
        read_bytes += min((root / name).stat().st_size, MAX_READ + 1)
        content = bounded_read(root, name)
        if content is None:
            continue
        # Bound search influence: large/generated files cannot dominate by repetition.
        body_score = sum(min(3, content.lower().count(term)) for term in terms)
        score = round(path_score + body_score, 3)
        if score:
            ranked.append((score, name, content, is_test))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    relevance = {name: score for score, name, _, _ in ranked}
    tests.sort(key=lambda name: (-relevance.get(name, 0), name))
    selected = [{"path": name, "score": score, "is_test": is_test,
                 "outline": outline(content, Path(name).suffix)}
                for score, name, content, is_test in ranked[:max(1, min(limit, 20))]]
    scripts = []
    for name in manifests[:20]:
        content = bounded_read(root, name)
        if content is None or Path(name).name != "package.json":
            continue
        try:
            data = json.loads(content)
        except (ValueError, TypeError):
            continue
        if not isinstance(data, dict) or not isinstance(data.get("scripts", {}), dict):
            continue
        for key, value in data.get("scripts", {}).items():
            if isinstance(key, str) and isinstance(value, str) and "test" in key.lower():
                scripts.append({"manifest": name, "script": key[:100], "command": value[:200]})
    return {"version": "orientation-prototype-1", "tracked_file_count": len(files),
            "source_files_scanned": scanned,
            "source_scan_truncated": scanned < len(source_files),
            "query_terms": terms, "matches": selected, "test_files": tests[:40],
            "test_file_count": len(tests), "manifests": manifests[:20],
            "declared_test_scripts": scripts[:20],
            "limitations": ["Lexical relevance is a hint, not dependency analysis.",
                            "Declared scripts and test filenames do not prove tests pass.",
                            "Oversized files, symlinks, gitlinks and private artifacts are omitted."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()
    print(json.dumps(inspect(args.repo, args.query, args.limit), ensure_ascii=True))
