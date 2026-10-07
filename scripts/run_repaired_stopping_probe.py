"""Three fresh development identities after the sealed second-call repair."""
import json
import os
import shutil
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from filelock import FileLock

from benchmarks.polybench import runner
from benchmarks.polybench.storage_lifecycle import release_images
from hx.agent_search import metrics
from hx.code_search import seal, sha
from hx.models import HXError
from scripts.agent_search_polybench import PolyBenchBackend
from scripts.overnight_limits import account_usage, can_start
from scripts.run_stopping_policy_pilot import ARMS, PROPOSAL, write
from scripts.worker_scaffold_search import exercise_scaffold


def run(root):
    with FileLock('.hx/single-evaluation-controller.lock', timeout=0):
        if root.exists():
            raise HXError('Fresh root required; no consumed identity restart')
        parent = Path('.hx/stopping-policy-pilot-v1')
        old = json.loads((parent/'plan.json').read_text())
        previous = json.loads((parent/'final-audit.json').read_text())['reported_tokens']
        synthetic = sum(json.loads((Path('.hx')/name/file).read_text())['reported_tokens']
                        for name,file in [('live-two-call-validation-v1','failure.json'),
                                          ('live-two-call-validation-v2','result.json')])
        prior_tokens = previous + synthetic
        if time.time() >= old['deadline'] or prior_tokens + 2250000 > old['max_reported_tokens']:
            raise HXError('Original envelope cannot admit three trials')
        for name,digest in json.loads((parent/'runtime-freeze.json').read_text()).items():
            if sha(Path(name).read_bytes()) != digest:
                raise HXError('Parent prepared evidence changed: '+name)
        quota = account_usage(runner.BINARY, runner.AUTH)
        if not can_start(quota):
            raise HXError('Quota blocked before launch')
        root.mkdir()
        started = time.time()
        write(root/'controller.json', {'pid':os.getpid(),'started':started})
        private = Path('/opt/hx-polybench-runtime/v1')/root.name
        prepared = root/'prepared'
        shutil.copytree(parent/'prepared',prepared)
        case = 'serverless__serverless-3457'
        selection=json.loads((prepared/'selection.json').read_text())
        selection['cases']=[c for c in selection['cases'] if c['id']==case]
        write(prepared/'selection.json',selection)
        images=json.loads((prepared/'images.json').read_text())
        images={case:{**images[case],'execution_root':str(private)}}
        write(prepared/'images.json',images)
        storage=json.loads((prepared/'storage.json').read_text())
        storage['execution_root']=str(private)
        write(prepared/'storage.json',storage)
        config=root/'backend-config.json'
        write(config,{'prepared_root':str(prepared.resolve()),'private_root':str(private),
                     'case_provenance':{case:{'reference_informed':False,'previous_coding_exposure':True}}})
        history=old['historical_scores']
        for p in parent.glob('development/*/*/score.json'):
            history[str(p.resolve())]=sha(p.read_bytes())
        paths=[Path(__file__),config,Path('scripts/agent_search_polybench.py'),
               Path('scripts/overnight_limits.py'),Path('scripts/run_agent_search.py'),
               Path('scripts/run_stopping_policy_pilot.py'),Path('scripts/worker_scaffold_search.py'),
               *Path('src/hx').glob('*.py'),*Path('src/hx/prompts').glob('*.md'),
               *Path('src/hx/scaffolds').glob('*.py'),*Path('benchmarks/polybench').glob('*.py'),
               *(runner.VENDOR/'src').rglob('*.py'),runner.BINARY,
               *[p for p in prepared.rglob('*') if p.is_file()],
               *[PROPOSAL/(arm+'.py') for arm in ARMS],
               parent/'plan.json',parent/'final-audit.json',
               Path('.hx/live-two-call-validation-v2/archive-lock.json')]
        plan={ 'development':[case],'heldout':[],'arms':ARMS,'repeats':1,
               'planned_trials':3,'started':started,'deadline':old['deadline'],
               'max_reported_tokens':old['max_reported_tokens'],'prior_reported_tokens':prior_tokens,
               'model':'gpt-6.1-sol','reasoning_effort':'medium','trial_token_headroom':750000,
               'source_locks':{str(p.resolve()):sha(p.read_bytes()) for p in paths},
               'historical_scores':history,'proposal_model_calls':0,
               'classification':'Consumed development comparison; fresh identities, no heldout access or promotion',
               'authorization':'User ok go after fresh live integration pass; inherited original pilot envelope',
               'turn_boundary_overshoot_possible':True }
        write(root/'plan.json',plan)
        write(root/'plan.lock.json',{'sha256':sha((root/'plan.json').read_bytes())})
        tokens=0
        rows={}
        def control(headroom=0):
            if time.time()>=plan['deadline'] or prior_tokens+tokens+headroom>plan['max_reported_tokens']:
                raise HXError('Inherited envelope exhausted')
            for name,digest in {**plan['source_locks'],**history}.items():
                if sha(Path(name).read_bytes())!=digest:
                    raise HXError('Frozen input/runtime/history changed: '+name)
            if sha((root/'plan.json').read_bytes()) != json.loads((root/'plan.lock.json').read_text())['sha256']:
                raise HXError('Plan changed')
            if shutil.disk_usage(Path.cwd()).free<40*1024**3:
                raise HXError('40 GiB storage guard')
        def report(phase):
            write(root/'results.json',{'phase':phase,'planned':3,'reported_tokens':tokens,
                'prior_reported_tokens':prior_tokens,'rows':{a:r.model_dump() for a,r in rows.items()}})
        try:
            backend=PolyBenchBackend(config)
            engine_plan=SimpleNamespace(**plan)
            backend.admit(engine_plan)
            for arm in ARMS:
                if not exercise_scaffold(PROPOSAL/(arm+'.py'),private/('fixture-'+arm)):
                    raise HXError('Scripted policy fixture failed')
            for arm in ARMS:
                control(750000)
                quota=account_usage(runner.BINARY,runner.AUTH)
                write(root/'quota.json',quota)
                if not can_start(quota):
                    raise HXError('Quota blocked; no retry')
                write(root/'phase.json',{'phase':'development','case':case,'arm':arm})
                directory=root/'development'/case/arm
                directory.mkdir(parents=True)
                trial=backend.evaluate(PROPOSAL/(arm+'.py'),case,1,directory,engine_plan,control)
                tokens+=trial.reported_tokens
                rows[arm]=trial
                write(directory/'score.json',trial.model_dump())
                report('development')
                if (not trial.usage_known or trial.infrastructure_error or trial.missing_observations
                        or trial.workflow_error):
                    raise HXError('Operational/unknown-usage trial; preserve partials')
            control()
            write(root/'final-audit.json',{'complete':len(rows)==3,'rows':{a:r.model_dump() for a,r in rows.items()},
                'metrics':{a:metrics([r]) for a,r in rows.items()},'reported_tokens':tokens,
                'prior_reported_tokens':prior_tokens,'historical_scores_verified':len(history),
                'heldout_trials':0,'automatic_promotion':False,'classification':plan['classification']})
            report('completed')
        except BaseException as error:
            write(root/'stop.json',{'error':str(error),'reported_tokens':tokens,'retry_allowed':False,
                'unreturned_usage_may_be_unknown':True})
            report('stopped')
            raise
        finally:
            _,_,client,_=runner.resources(prepared)
            try:
                write(root/'release.json',release_images(client,list(images.values())))
            finally:
                client.close()
                write(root/'controller.exited.json',{'pid':os.getpid(),'time':time.time()})
                write(root/'archive-lock.json',{'files':seal(root)})


if __name__=='__main__':
    run(Path(sys.argv[1]))
