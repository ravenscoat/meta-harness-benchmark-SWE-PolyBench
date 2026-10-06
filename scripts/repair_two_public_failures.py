"""Reference-guided repairs of two consumed failures; zero model calls."""
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench import runner
from benchmarks.polybench.containers import create, populate
from benchmarks.polybench.delivery import production_patch
from benchmarks.polybench.dependencies import prepare_dependencies, share_public_fixture
from benchmarks.polybench.grader import grade
from benchmarks.polybench.image_cache import ensure_image
from benchmarks.polybench.prepare import read_rows, sha, write
from benchmarks.polybench.test_environment import docker_environment
from hx.models import Candidate

ROOT = Path('.hx/two-failure-reference-repair-v1')
OLD = Path('.hx/five-failure-development-v1')
AUDIT = Path('.hx/two-failure-repair-audit-v1')
CASES = ['huggingface__transformers-26164', 'mui__material-ui-23229']


def git(workspace, *args):
    return subprocess.check_output(['git', '-C', str(workspace), *args], timeout=120).decode().strip()


def patch_from_files(files):
    pieces = []
    for file in files:
        name = file['filename']
        if not name.startswith(('src/', 'tests/', 'packages/')):
            continue
        if file['status'] != 'modified' or not file.get('patch') or '..' in Path(name).parts:
            raise RuntimeError('Unsupported public patch entry')
        pieces.append(f'diff --git a/{name} b/{name}\n--- a/{name}\n+++ b/{name}\n' + file['patch'] + '\n')
    return ''.join(pieces)


def public_replay(client, case, workspace, argv, directory):
    bootstrap = case['repo'] == 'huggingface/transformers'
    container, workdir = create(client, case, offline=not bootstrap)
    try:
        if bootstrap:
            prepare_dependencies(container, case['repo'], directory / 'dependencies', case['upstream_base'])
            share_public_fixture(container, case['repo'])
            container.reload()
            for network in list(container.attrs['NetworkSettings']['Networks']):
                client.networks.get(network).disconnect(container)
        populate(container, workdir, workspace, case)
        actual = ['docker', 'exec', '-u', '1000:1000', *docker_environment(), '-w', workdir, container.id, *argv]
        directory.mkdir(parents=True, exist_ok=True)
        started = time.time()
        with (directory / 'stdout.txt').open('w') as stdout, (directory / 'stderr.txt').open('w') as stderr:
            result = subprocess.run(actual, stdout=stdout, stderr=stderr, timeout=300)
        record = {'argv': argv, 'exit_code': result.returncode, 'seconds': time.time()-started,
                  'offline': True, 'uid': 1000, 'model_calls': 0}
        write(directory / 'execution.json', record)
        return record
    finally:
        container.remove(force=True)


def main():
    if ROOT.exists():
        raise RuntimeError('New identity only; never rerun this root')
    with FileLock('.hx/single-evaluation-controller.lock').acquire(timeout=0):
        ROOT.mkdir()
        for name in ('dataset.csv', 'storage.json', 'settings.toml', 'selection.json', 'images.json'):
            shutil.copyfile(OLD / name, ROOT / name)
        (ROOT / 'experiments').mkdir()
        history = {str(p.resolve()): sha(p) for p in Path('.hx').glob('*/experiments/*/*/score.json')}
        public_inputs = {str(p.resolve()): sha(p) for p in AUDIT.glob('*public-*.json')}
        plan = {'cases': CASES, 'started': time.time(), 'deadline': time.time()+7200,
                'model_calls': 0, 'reported_tokens': 0, 'historical_scores': history,
                'public_inputs': public_inputs, 'scheduler_sha256': sha(Path(__file__)),
                'limitations': 'Public accepted solutions explicitly inspected and used to repair consumed tasks. Reference-guided diagnostic, not autonomous HX success, fresh evaluation, or improvement measurement.'}
        write(ROOT / 'plan.json', plan)
        write(ROOT / 'plan.lock.json', {'sha256': sha(ROOT / 'plan.json')})
        write(ROOT / 'controller.json', {'pid': os.getpid(), 'started': time.time()})
        runner.lock_sources(ROOT)
        selection, images, client, _ = runner.resources(ROOT)
        outcomes = []
        try:
            for key in CASES:
                assert time.time() < plan['deadline']
                runner.lock_sources(ROOT)
                write(ROOT / 'phase.json', {'case': key, 'stage': 'public-reference-repair'})
                number = key.rsplit('-', 1)[1]
                files = json.loads((AUDIT / (number+'-public-files.json')).read_text())
                pr = json.loads((AUDIT / (number+'-public-pr.json')).read_text())
                old_trial = OLD / 'experiments/search-history' / ('full-'+key+'-1')
                previous = json.loads((old_trial / 'score.json').read_text())
                artifact = json.loads((old_trial / 'state/runs' / previous['run_id'] / 'artifacts/implement.json').read_text())
                workspace = Path('/opt/hx-polybench-runtime/v1/repairs/two-failure-v1') / key
                workspace.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(['git', 'clone', '--no-hardlinks', artifact['workspace'], str(workspace)], check=True, capture_output=True, timeout=120)
                git(workspace, 'checkout', '--detach', artifact['base_commit'])
                directory = ROOT / 'experiments/repairs' / key
                directory.mkdir(parents=True)
                patch = patch_from_files(files)
                (directory / 'public-upstream.patch').write_text(patch)
                subprocess.run(['git', '-C', str(workspace), 'apply', '--check', str((directory/'public-upstream.patch').resolve())], check=True, capture_output=True)
                subprocess.run(['git', '-C', str(workspace), 'apply', str((directory/'public-upstream.patch').resolve())], check=True, capture_output=True)
                git(workspace, 'add', '--all')
                git(workspace, '-c', 'user.name=HX', '-c', 'user.email=hx@localhost', 'commit', '-m', 'Public reference-guided development repair')
                commit = git(workspace, 'rev-parse', 'HEAD')
                changed = git(workspace, 'diff', '--name-only', artifact['base_commit'], commit).splitlines()
                candidate = Candidate(workspace=str(workspace), base_commit=artifact['base_commit'], input_commit=artifact['base_commit'], candidate_commit=commit,
                    changed_files=changed, diff_sha256=hashlib.sha256(git(workspace,'diff',artifact['base_commit'],commit).encode()).hexdigest(),
                    verification_commands=[])
                delivered, delivery = production_patch(candidate)
                write(directory/'delivery.json', delivery)
                write(directory/'candidate.json', candidate.model_dump())
                write(directory/'prediction.json', {'instance_id': key, 'model_patch': delivered})
                case = images[key]
                ensure_image(client, ROOT, case)
                argv = (['python','-m','pytest','-vv','tests/models/whisper/test_modeling_whisper.py::WhisperModelTest::test_generate_with_prompt_ids_max_length',
                         'tests/models/whisper/test_modeling_whisper.py::WhisperModelTest::test_generate_with_prompt_ids_and_task_and_language',
                         'tests/models/whisper/test_modeling_whisper.py::WhisperModelTest::test_generate_with_prompt_ids_and_forced_decoder_ids']
                    if number=='26164' else ['npm','run','test:unit','--','--reporter','json','--grep','(<Autocomplete />|createFilterOptions)','--exit'])
                public = public_replay(client, case, workspace, argv, directory/'public-candidate')
                if public['exit_code'] != 0:
                    raise RuntimeError('Public repaired candidate tests failed; retain evidence')
                row = next(r for r in read_rows(ROOT/'dataset.csv') if r['instance_id']==key)
                accepted = grade(row, delivered, ROOT/'experiments/private-evaluation'/key, client)
                outcome = {'case':key,'candidate_commit':commit,'public_tests_passed':True,
                    'official_resolved':accepted['resolved'], 'unobserved_acceptance_tests':len(accepted['expected_tests_unobserved']),
                    'grader_error':accepted['infrastructure_error'],'candidate_patch_error':accepted['candidate_patch_error'],
                    'public_reference':pr['html_url'],'public_reference_commit':pr['head']['sha'],
                    'model_calls':0,'reported_tokens':0,'limitations':plan['limitations']}
                write(directory/'score.json', outcome)
                outcomes.append(outcome)
                write(ROOT/'results.json', {'rows':outcomes,'complete':len(outcomes)==2,'official_resolved':sum(bool(x['official_resolved']) for x in outcomes)})
                print(json.dumps(outcome),flush=True)
            for name, expected in {**history, **public_inputs}.items():
                assert sha(Path(name))==expected, name
            runner.lock_sources(ROOT)
            write(ROOT/'audit.json', {'historical_scores_unchanged':len(history),'public_inputs_unchanged':True,
                'model_calls':0,'complete':True,'rows':outcomes})
        except BaseException as exc:
            write(ROOT/'stop.json', {'error':str(exc),'type':type(exc).__name__,'time':time.time()})
            raise
        finally:
            write(ROOT/'controller.exited.json', {'pid':os.getpid(),'time':time.time()})


if __name__ == '__main__':
    main()
