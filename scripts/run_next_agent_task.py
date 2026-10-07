"""User-authorized task6, one fresh baseline identity with inherited pilot limits."""
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
from benchmarks.polybench.worker_environment import worker_environment_check
from hx.code_search import seal, sha
from hx.models import HXError
from scripts.agent_search_polybench import PolyBenchBackend
from scripts.overnight_limits import account_usage, can_start
from scripts.run_stopping_policy_pilot import PROPOSAL, write
from scripts.worker_scaffold_search import exercise_scaffold

KEY='serverless__serverless-7102'


def run(root):
    with FileLock('.hx/single-evaluation-controller.lock',timeout=0):
        if root.exists():
            raise HXError('Consumed root; never restart')
        parent=Path('.hx/repaired-stopping-probe-v1')
        inherited=json.loads((parent/'plan.json').read_text())
        previous=inherited['prior_reported_tokens']+json.loads((parent/'results.json').read_text())['reported_tokens']
        if time.time()>=inherited['deadline'] or previous+750000>inherited['max_reported_tokens']:
            raise HXError('Inherited allowance/deadline cannot admit task')
        quota=account_usage(runner.BINARY,runner.AUTH)
        if not can_start(quota):
            raise HXError('Quota blocked; no launch')
        root.mkdir()
        write(root/'controller.json',{'pid':os.getpid(),'started':time.time()})
        source=Path('.hx/coding-seventeen-v1/tasks')/KEY
        prepared=root/'prepared'
        prepared.mkdir()
        for name in ('dataset.csv','selection.json','images.json','storage.json'):
            shutil.copyfile(source/name,prepared/name)
        shutil.copyfile(parent/'prepared/settings.toml',prepared/'settings.toml')
        for name in ('public','preflight'):
            shutil.copytree(source/name,prepared/name)
        private=Path('/opt/hx-polybench-runtime/v1')/root.name
        images=json.loads((prepared/'images.json').read_text())
        images[KEY]['execution_root']=str(private)
        write(prepared/'images.json',images)
        storage=json.loads((prepared/'storage.json').read_text())
        storage['execution_root']=str(private)
        write(prepared/'storage.json',storage)
        config=root/'backend-config.json'
        write(config,{'prepared_root':str(prepared.resolve()),'private_root':str(private),
              'case_provenance':{KEY:{'reference_informed':False,'previous_coding_exposure':True}}})
        history=dict(inherited['historical_scores'])
        history.update({str(p.resolve()):sha(p.read_bytes()) for p in parent.glob('development/*/*/score.json')})
        paths=[Path(__file__),config,Path('scripts/agent_search_polybench.py'),
               Path('scripts/overnight_limits.py'),Path('scripts/run_agent_search.py'),
               Path('scripts/run_stopping_policy_pilot.py'),Path('scripts/worker_scaffold_search.py'),
               *Path('src/hx').glob('*.py'),*Path('src/hx/prompts').glob('*.md'),
               *Path('src/hx/scaffolds').glob('*.py'),*Path('benchmarks/polybench').glob('*.py'),
               *(runner.VENDOR/'src').rglob('*.py'),runner.BINARY,
               *[p for p in prepared.rglob('*') if p.is_file()],PROPOSAL/'baseline.py',
               source/'plan.lock.json' if (source/'plan.lock.json').exists() else source/'selection.json',
               parent/'archive-lock.json']
        plan={'development':[KEY],'heldout':[],'task_number':6,'coding_trials':1,
              'model':'gpt-6.1-sol','reasoning_effort':'medium','trial_token_headroom':750000,
              'deadline':inherited['deadline'],'max_reported_tokens':inherited['max_reported_tokens'],
              'prior_reported_tokens':previous,'source_locks':{str(p.resolve()):sha(p.read_bytes()) for p in paths},
              'historical_scores':history,'authorization':'User explicitly requested next problem after development comparison',
              'classification':'Consumed development; fresh unseeded baseline identity; no heldout/promotion',
              'proposal_model_calls':0,'turn_boundary_overshoot_possible':True}
        write(root/'plan.json',plan)
        write(root/'plan.lock.json',{'sha256':sha((root/'plan.json').read_bytes())})
        tokens=0
        def control(headroom=0):
            if time.time()>=plan['deadline'] or previous+tokens+headroom>plan['max_reported_tokens']:
                raise HXError('Inherited envelope exhausted')
            for name,digest in {**plan['source_locks'],**history}.items():
                if sha(Path(name).read_bytes())!=digest:
                    raise HXError('Source/input/history changed: '+name)
            if sha((root/'plan.json').read_bytes())!=json.loads((root/'plan.lock.json').read_text())['sha256']:
                raise HXError('Plan changed')
            if shutil.disk_usage(Path.cwd()).free<40*1024**3:
                raise HXError('40 GiB storage guard')
        try:
            control(750000)
            write(root/'phase.json',{'phase':'pinned_image_worker_preflight','case':KEY})
            _,_,client,settings=runner.resources(prepared)
            try:
                runner.ensure_image(client,prepared,images[KEY])
                receipt=worker_environment_check(client,images[KEY],Path(images[KEY]['repo_path']),
                    root/'worker-preflight',settings,control,lambda *args:None)
                write(root/'worker-receipt.json',receipt)
            finally:
                client.close()
            backend=PolyBenchBackend(config)
            engine_plan=SimpleNamespace(**plan)
            backend.admit(engine_plan)
            if not exercise_scaffold(PROPOSAL/'baseline.py',private/'fixture-baseline'):
                raise HXError('Scripted policy fixture failed')
            write(root/'phase.json',{'phase':'coding','case':KEY,'arm':'baseline'})
            directory=root/'development'/KEY/'baseline'
            directory.mkdir(parents=True)
            trial=backend.evaluate(PROPOSAL/'baseline.py',KEY,1,directory,engine_plan,control)
            tokens=trial.reported_tokens
            write(directory/'score.json',trial.model_dump())
            write(root/'results.json',{'planned':1,'reported_tokens':tokens,'trial':trial.model_dump()})
            control()
            write(root/'final-audit.json',{'complete':True,'trial':trial.model_dump(),
                'reported_tokens':tokens,'prior_reported_tokens':previous,'historical_scores_verified':len(history),
                'classification':plan['classification'],'no_next_task':True})
        except BaseException as error:
            write(root/'stop.json',{'error':str(error),'reported_tokens':tokens,'retry_allowed':False,
                                  'unreturned_usage_may_be_unknown':True})
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
