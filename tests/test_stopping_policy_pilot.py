from pathlib import Path

from hx.agent_search import Trial
from hx.worker_scaffold import validate_scaffold
from scripts.run_stopping_policy_pilot import better


def row(case, solved, tokens):
    return Trial(identity=case, case=case, repeat=1, source_sha256='hash', model='fixed',
                 reasoning_effort='medium', official_resolved=solved, public_verified=True,
                 usage_known=True, reported_tokens=tokens, seconds=1,
                 infrastructure_error=None, patch_error=None, missing_observations=0,
                 accepted_candidate=True, reference_informed=False)


def test_candidate_cannot_hide_lost_baseline_solve():
    assert not better([row('a', False, 1), row('b', True, 1)],
                      [row('a', True, 2), row('b', False, 2)])


def test_more_official_solves_with_higher_spend_are_reported_as_accuracy_tradeoff():
    assert better([row('a', True, 20), row('b', True, 20)],
                  [row('a', True, 10), row('b', False, 10)])
    assert not better([row('a', True, 20)], [row('a', True, 10)])


def test_stopping_candidates_only_change_successful_finish_and_are_bounded():
    root = Path('src/hx/scaffolds')
    policies = {}
    for name in ('baseline', 'extra-check', 'compatibility-review'):
        source = (root / ('stopping_' + name.replace('-', '_') + '.py')).read_bytes()
        validate_scaffold(source)
        namespace = {}
        exec(compile(source, str(root / name), 'exec'), namespace)
        policies[name] = namespace['next_action']
    state = {'worker_calls': 1, 'last_summary': {'status': 'complete'}, 'memory': {}}
    assert policies['baseline'](state)['action'] == 'finish'
    assert all(policies[n](state)['action'] == 'delegate' for n in ('extra-check', 'compatibility-review'))
    failing = {**state, 'last_summary': {'status': 'failed'}}
    assert all(p(failing) == policies['baseline'](failing) for p in policies.values())
    assert all(p({**state, 'worker_calls': 2})['action'] == 'finish' for p in policies.values())
