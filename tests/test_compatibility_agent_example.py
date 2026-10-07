"""Exercise bounded compatibility decisions without a model or evaluator."""
import importlib.util
from pathlib import Path

from hx.worker_scaffold import validate_scaffold


def load_example():
    path = Path(__file__).resolve().parents[1] / 'examples/agents/compatibility_guard.py'
    validate_scaffold(path.read_bytes())
    spec = importlib.util.spec_from_file_location('compatibility_example', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_excluded_checks_trigger_bounded_public_revision():
    action = load_example().next_action({'worker_calls': 1, 'last_summary': {
        'summary': 'Targeted checks passed.',
        'verification_commands': [['mocha', 'affected.js', '--grep', 'compatibility', '--invert']]}})
    assert action['action'] == 'delegate'
    assert action['context']['unresolved_items']
    assert 'unfiltered' in action['guidance']


def test_current_compatibility_failure_is_not_erased_by_passed_clause():
    action = load_example().next_action({'worker_calls': 1, 'last_summary': {
        'summary': 'Targeted checks passed; one existing compatibility test still fails.'}})
    assert action['action'] == 'delegate'


def test_resolved_baseline_reproduction_does_not_trigger_extra_revision():
    action = load_example().next_action({'worker_calls': 1, 'last_summary': {
        'summary': 'Original source tests failed before the fix. Afterward all checks passed.'}})
    assert action['action'] == 'finish'


def test_revision_cap_remains_bounded():
    assert load_example().next_action({'worker_calls': 2, 'last_summary': {
        'summary': 'Existing compatibility test still fails.'}})['action'] == 'finish'
