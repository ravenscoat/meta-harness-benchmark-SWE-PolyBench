"""Run a NEW measured search using an explicitly supplied trusted backend.

No default backend, task selection, budget or live-model invocation is implicit.
"""
import argparse
import importlib
from pathlib import Path

from hx.agent_search import SearchPlan, run_search


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--incumbent", type=Path, required=True)
    parser.add_argument("--backend", required=True, help="Trusted Python module exposing create_backend()")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    plan = SearchPlan.model_validate_json(args.plan.read_bytes())
    if args.validate_only:
        from hx.code_search import sha
        from hx.worker_scaffold import validate_scaffold

        validate_scaffold(args.incumbent.read_bytes())
        if plan.source_locks.get(str(args.incumbent.resolve())) != sha(args.incumbent.read_bytes()):
            raise ValueError("Incumbent must be explicitly source-locked")
        for name, expected in plan.source_locks.items():
            if sha(Path(name).read_bytes()) != expected:
                raise ValueError("Source lock changed: " + name)
        print("Plan and source interfaces validated; no models, trials or grading executed.")
        return
    module = importlib.import_module(args.backend)
    if args.root.exists():
        raise ValueError("New root required; consumed search identities cannot restart")
    if not getattr(module, "__file__", None):
        raise ValueError("Backend must have a source file")
    from hx.code_search import sha

    backend_path = Path(module.__file__).resolve()
    if plan.source_locks.get(str(backend_path)) != sha(backend_path.read_bytes()):
        raise ValueError("Trusted backend must be explicitly source-locked")
    run_search(args.root, plan, args.incumbent, module.create_backend())


if __name__ == "__main__":
    main()
