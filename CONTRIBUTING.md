# Contributing

Contributions should improve an executable mechanism and include evidence of its behavior.

## Development

Use Python 3.11+, install `python -m pip install -e ".[dev,polybench]"`, and run the relevant tests from the checkout. Fixture tests do not require model calls. Keep tests meaningful: validate incorrect-output rejection and transitions, not merely copies of implementation details.

For public-check or environment changes, add a regression for the observed failure and confirm neighboring supported cases still work. A fixture pass does not replace a real offline container probe when build, ownership, dependency or capture behavior changed.

## Experiment integrity

Record selection, exposure, runtime/input/image pins, budget and scorer version before model work. Use a separate identity for a deliberate new attempt. Preserve failed, interrupted and unknown-usage outcomes. Never replace an existing score to improve an apparent success rate.

Only public issue/source/workflow evidence belongs in worker or proposer context. Official evaluator artifacts and accepted reference solutions stay separate. Avoid tuning from reserved outcomes. Distinguish operational repair validation from task correctness.

## Pull requests

Explain the observed failure, final behavior, relevant validation and limits. State whether real container or model validation occurred. Do not claim improved benchmark accuracy from a synthetic test, consumed repeat or unpaired small sample.

Do not commit credentials, `.hx` raw runs, virtual environments, downloaded datasets, evaluator checkouts, image archives or private grading outputs. Check licensing and attribution before adding third-party code.
