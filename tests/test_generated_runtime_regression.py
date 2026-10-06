import json

import pytest

from benchmarks.polybench.regression import classify
from hx.models import Check


def runtime_report():
    message = "Component was created without expected data property 'show'"
    return {'stats': {'tests': 2, 'passes': 1, 'failures': 1, 'pending': 0},
        'failures': [{'fullTitle': 'missing data mounts and updates', 'err': {
            'message': message, 'stack': 'Error: ' + message + '\n'
            '    at new Component (eval at compile (test/runtime/data.test.js:55:3), <anonymous>:39:38)\n'
            '    at Context.<anonymous> (test/runtime/data.test.js:68:18)\n'
            '    at processImmediate (node:internal/timers:466:21)'}}]}


def category(value):
    return classify(Check(name='base', passed=False, evidence=json.dumps(value)))


@pytest.mark.parametrize('error_type', ['Error', 'TypeError', 'RangeError'])
def test_generated_constructor_runtime_error_is_observed_behavior(error_type):
    value = runtime_report()
    value['failures'][0]['err']['stack'] = value['failures'][0]['err']['stack'].replace('Error:', error_type + ':', 1)
    assert category(value) == 'behavioral_failure'


@pytest.mark.parametrize('path', ['test/missing-property-warnings/index.js',
    'tests/runtime/index.js', 'packages/ui/__tests__/index.ts',
    '/testbed/test/runtime/index.js', 'test/runtime/index.cjs', 'data.spec.mjs'])
def test_directory_and_suffix_paths_share_overlay_convention(path):
    value = runtime_report()
    value['failures'][0]['err']['stack'] = value['failures'][0]['err']['stack'].replace('test/runtime/data.test.js', path)
    assert category(value) == 'behavioral_failure'


@pytest.mark.parametrize('path', ['src/component/index.js', 'testify/index.js',
    'test/../src/component.js', 'node_modules/widget/test/index.js',
    'test/runtime/data.json', 'test\\runtime\\index.js'])
def test_non_test_or_unsafe_context_paths_remain_inconclusive(path):
    value = runtime_report()
    value['failures'][0]['err']['stack'] = value['failures'][0]['err']['stack'].replace('test/runtime/data.test.js', path)
    assert category(value) == 'inconclusive'


@pytest.mark.parametrize('mutation', ['hook', 'missing_body', 'compile_failure',
    'test_only_throw', 'message_mismatch', 'failure_count', 'total_count',
    'missing_count', 'boolean_count', 'mixed_unknown', 'module', 'syntax'])
def test_generated_runtime_evidence_fails_closed(mutation):
    value = runtime_report()
    failure = value['failures'][0]
    error = failure['err']
    if mutation == 'hook':
        failure['fullTitle'] = '"before each" hook'
    elif mutation == 'missing_body':
        error['stack'] = error['stack'].replace('Context.<anonymous>', 'Helper.setup')
    elif mutation == 'compile_failure':
        error['stack'] = error['stack'].replace('at new Component', 'at compile')
    elif mutation == 'test_only_throw':
        error['stack'] = error['stack'].splitlines()[0] + '\n    at Context.<anonymous> (test/runtime/data.test.js:68:18)'
    elif mutation == 'message_mismatch':
        error['message'] = 'different error'
    elif mutation == 'failure_count':
        value['stats']['failures'] = 2
    elif mutation == 'total_count':
        value['stats']['tests'] = 3
    elif mutation == 'missing_count':
        del value['stats']['pending']
    elif mutation == 'boolean_count':
        value['stats']['passes'] = True
    elif mutation == 'mixed_unknown':
        value['stats'].update(tests=3, failures=2)
        value['failures'].append({'fullTitle': 'another case', 'err': {'stack': 'TypeError: unknown'}})
    else:
        error['message'] = 'Cannot find module dependency' if mutation == 'module' else 'SyntaxError: invalid source'
        error['stack'] = 'Error: ' + error['message'] + '\n' + '\n'.join(error['stack'].splitlines()[1:])
    assert category(value) in {'inconclusive', 'setup_error'}
