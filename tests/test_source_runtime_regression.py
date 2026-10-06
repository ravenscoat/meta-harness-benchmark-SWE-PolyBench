import copy
import json

import pytest

from benchmarks.polybench.regression import classify
from hx.models import Check


def report():
    message = "Cannot read properties of undefined (reading 'fontSize')"
    return {
        "stats": {"tests": 2, "passes": 1, "failures": 1, "pending": 0},
        "failures": [
            {
                "fullTitle": "disabled variant retains enabled behavior",
                "file": "/testbed/packages/styles/font.test.js",
                "err": {
                    "message": message,
                    "stack": "TypeError: " + message + "\n"
                    "    at forEach (packages/styles/font.js:37:50)\n"
                    "    at Array.forEach (<anonymous>)\n"
                    "    at Context.<anonymous> (packages/styles/font.test.js:8:39)\n",
                },
            }
        ],
    }


def category(value):
    return classify(Check(name="base", passed=False, evidence=json.dumps(value)))


def test_counted_source_runtime_exception_is_behavioral_execution_failure():
    assert category(report()) == "behavioral_failure"


@pytest.mark.parametrize(
    "mutation",
    [
        "count",
        "message",
        "hook",
        "test_throw",
        "dependency",
        "missing_file",
        "other_file",
        "missing_body",
        "loader",
        "escape",
        "mixed_unknown",
    ],
)
def test_source_exception_does_not_admit_setup_or_ambiguous_evidence(mutation):
    value = report()
    failure = value["failures"][0]
    error = failure["err"]
    if mutation == "count":
        value["stats"]["passes"] = True
    elif mutation == "message":
        error["message"] = "different"
    elif mutation == "hook":
        failure["fullTitle"] = "before all hook"
    elif mutation == "test_throw":
        error["stack"] = error["stack"].replace(
            "packages/styles/font.js:", "packages/styles/font.test.js:"
        )
    elif mutation == "dependency":
        error["stack"] = error["stack"].replace(
            "packages/styles/font.js:", "node_modules/dep/index.js:"
        )
    elif mutation == "missing_file":
        del failure["file"]
    elif mutation == "other_file":
        failure["file"] = "/testbed/other.test.js"
    elif mutation == "missing_body":
        error["stack"] = error["stack"].replace("Context.<anonymous>", "Helper.call")
    elif mutation == "loader":
        error["stack"] += "    at Module._compile (node:internal/modules/cjs/loader:1:1)\n"
    elif mutation == "escape":
        error["stack"] = error["stack"].replace(
            "packages/styles/font.js:", "packages/../outside.js:"
        )
    else:
        value["stats"].update(tests=3, failures=2)
        value["failures"].append(copy.deepcopy(failure))
        value["failures"][1]["err"]["stack"] = "Error: unknown"
    assert category(value) != "behavioral_failure"
