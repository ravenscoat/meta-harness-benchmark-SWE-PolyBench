"""Zero-model execution smoke check for retained public test-author commands.

This never submits an implementation to an official grader or rewrites a score.
Previously evaluated tasks are consumed development diagnostics here.
"""
import json
import time
from pathlib import Path

from benchmarks.polybench.independent import validate_challenge
from benchmarks.polybench.prepare import sha, write
from benchmarks.polybench.public_checks import public_test_contract
from benchmarks.polybench.regression import regression_check
from hx.config import load_settings
from hx.models import Candidate, Task


def main():
    import docker

    source = Path('.hx/independent-three-v2').resolve()
    root = Path('.hx/meta-harness-adaptation-v1/probes').resolve()
    if root.exists():
        raise RuntimeError('Diagnostic identity exists; retain previous evidence')
    root.mkdir(parents=True)
    audit = json.loads((source / 'audit.json').read_text())
    plan = json.loads((source / 'plan.json').read_text())
    sealed = {**plan['historical_scores'], **plan['scheduler'],
              **(plan.get('startup_failure_preserved') or {}),
              **{str(source / p): h for p, h in audit['score_hashes'].items()}}
    # Old input locks are retained; executable changes have a separate version.
    frozen = {str(p.resolve()): sha(p) for p in Path('benchmarks/polybench').glob('*.py')}
    frozen[str(Path(__file__).resolve())] = sha(Path(__file__))
    write(root / 'freeze.json', {'source_sha256': frozen, 'sealed_evidence': sealed,
          'contract': public_test_contract(), 'model_calls': 0,
          'official_grader_calls': 0, 'classification': 'Consumed public development diagnostics'})
    images = json.loads((source / 'images.json').read_text())
    settings = load_settings(source / 'settings.toml')
    client = docker.from_env(timeout=180)
    results = {}
    try:
        for key in plan['cases']:
            trial = source / 'experiments/heldout-results' / ('full-' + key + '-1')
            files = list((trial / 'state/runs').glob('*/artifacts/independent_challenge.json'))
            if len(files) != 1:
                raise RuntimeError('Exactly one retained challenge expected')
            candidate = Candidate.model_validate_json(files[0].read_text())
            task = Task(id=key, repo=images[key]['repo_path'], report='Retained public command smoke check',
                        base_commit=candidate.base_commit, kind='bug', allowed_paths=['**'])
            events = []
            started = time.monotonic()
            record = {'challenge_sha256': sha(files[0]), 'commands': candidate.verification_commands}
            try:
                # No image pulls, dependency installation, or model access.
                client.images.get(images[key]['image_id'])
                validate_challenge(candidate, task)
                result = regression_check(candidate, task, root / key, settings, client,
                    images[key], lambda: None,
                    lambda event, data, events=events: events.append({'event': event, 'data': data}))
                record.update(check=result.model_dump())
            except Exception as error:
                record.update(operational_error=type(error).__name__ + ': ' + str(error))
            record['seconds'] = time.monotonic() - started
            results[key] = record
            write(root / key / 'events.json', events)
            write(root / 'results.json', results)
            print(json.dumps({'case': key, 'check': record.get('check'),
                              'operational_error': record.get('operational_error')}), flush=True)
        if not all(sha(Path(p)) == h for p, h in {**sealed, **frozen}.items()):
            raise RuntimeError('Sealed evidence or diagnostic executable changed')
        write(root / 'complete.json', {'model_calls': 0, 'official_grader_calls': 0,
              'historical_score_files_unchanged': len(plan['historical_scores']),
              'new_score_files_unchanged': len(audit['score_hashes']),
              'limitations': 'Reproduction is not a coding win or proof of complete issue coverage. '
                             'Setup errors remain failures; scores are not replaced.'})
    finally:
        client.close()


if __name__ == '__main__':
    main()
