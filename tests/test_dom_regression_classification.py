import json

import pytest

from benchmarks.polybench.regression import classify, mocha_behavioral_failures
from hx.models import Check


def report(stack=None, message=None, title="Autocomplete opens listbox"):
    return {"stats": {"failures": 1}, "failures": [{"fullTitle": title,
        "err": {"message": message or 'Unable to find an element with the role "listbox"',
            "stack": stack or ('TestingLibraryElementError: Unable to find an element with the role "listbox"\n'
                ' at Context.<anonymous> (/testbed/Autocomplete.test.js:51:13)')}}]}


def test_missing_role_in_test_is_behavioral_assertion():
    assert mocha_behavioral_failures(report())


def test_hook_missing_role_does_not_prove_regression():
    assert not mocha_behavioral_failures(report(title='"before each" hook'))


def test_missing_test_frame_and_mismatched_message_fail_closed():
    assert not mocha_behavioral_failures(report(stack='TestingLibraryElementError: Unable to find an element with the role "listbox"'))
    assert not mocha_behavioral_failures(report(message="Cannot find module"))


def test_inconsistent_counts_or_mixed_unknown_failure_fail_closed():
    value = report()
    value["stats"]["failures"] = 2
    assert not mocha_behavioral_failures(value)


def label_report():
    message = 'Found a label with the text of: Currency, however no form control was found associated to that label. Make sure you\'re using the "for" attribute or "aria-labelledby" attribute correctly.'
    return report(message=message, stack='Error: ' + message + '\n    at Context.getByLabelText (packages/TextField/TextField.select-id.test.js:64:12)',
                  title='TextField retains label association')


def test_missing_label_target_is_observed_behavior():
    value = label_report()
    assert mocha_behavioral_failures(value)
    assert classify(Check(name='base', passed=False, evidence=json.dumps(value))) == 'behavioral_failure'


@pytest.mark.parametrize('mutation', ['hook', 'no_test_frame', 'no_query_frame', 'wrong_message', 'counts', 'mixed_setup'])
def test_label_classifier_rejects_incomplete_or_setup_evidence(mutation):
    value = label_report()
    failure = value['failures'][0]
    if mutation == 'hook':
        failure['fullTitle'] = '"before each" hook'
    elif mutation == 'no_test_frame':
        failure['err']['stack'] = failure['err']['stack'].replace('.test.js', '.js')
    elif mutation == 'no_query_frame':
        failure['err']['stack'] = failure['err']['stack'].replace('getByLabelText', 'setup')
    elif mutation == 'wrong_message':
        failure['err']['message'] = 'Cannot find module'
    elif mutation == 'counts':
        value['stats']['failures'] = 2
    else:
        value['stats']['failures'] = 2
        value['failures'].append({'fullTitle': 'loads dependency', 'err': {'stack': 'Error: Cannot find module'}})
    assert not mocha_behavioral_failures(value)
    value["failures"].append({"fullTitle": "another test", "err": {"stack": "TypeError: unknown"}})
    assert not mocha_behavioral_failures(value)
