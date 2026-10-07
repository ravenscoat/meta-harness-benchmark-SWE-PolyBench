"""One authorized synthetic live two-call check; never a benchmark score."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import docker
from filelock import FileLock

from benchmarks.polybench.containers import ContainerAdapter
from benchmarks.polybench.runner import AUTH, BINARY
from benchmarks.polybench.sessions import TaskSessions, workspace_tree
from hx.code_search import sha
from hx.config import canonical
from hx.git import git
from hx.models import HXError, Settings, Task, WorkerSummary
from hx.store import atomic_write
from hx.worker_scaffold import WorkerScaffoldAdapter
from scripts.overnight_limits import account_usage, can_start


def run(root):
    with FileLock('.hx/single-evaluation-controller.lock', timeout=0):
        if root.exists():
            raise HXError('Consumed validation root; never restart')
        root.mkdir()
        def write(name, value):
            atomic_write(root/name,canonical(value))
        started=time.time()
        write('controller.json',{'pid':os.getpid(),'started':started})
        native=Path('/opt/hx-polybench-runtime/v1')/root.name
        native.mkdir(exist_ok=False)
        workspace=native/'workspace'
        workspace.mkdir()
        (workspace/'clamp.py').write_text('def clamp(value, low, high):\n    return value\n')
        (workspace/'.gitignore').write_text('__pycache__/\n')
        (workspace/'tests').mkdir()
        (workspace/'tests/test_clamp.py').write_text('''import unittest
from clamp import clamp
class ClampTests(unittest.TestCase):
    def test_inside(self): self.assertEqual(clamp(3, 1, 5), 3)
    def test_below(self): self.assertEqual(clamp(-2, 1, 5), 1)
    def test_above(self): self.assertEqual(clamp(8, 1, 5), 5)
''')
        git(workspace,'init')
        git(workspace,'-c','user.name=HX','-c','user.email=hx@local','add','--all')
        git(workspace,'-c','user.name=HX','-c','user.email=hx@local','commit','-qm','Synthetic original base')
        base=git(workspace,'rev-parse','HEAD')
        client=docker.from_env()
        image=client.images.get('hx-two-call-fixture:v1')
        upstream=client.containers.run(image.id,['git','rev-parse','HEAD'],remove=True).decode().strip()
        scaffold=root/'scaffold.py'
        scaffold.write_text('''def next_action(state):
    guidance = "Implement clamp bounds in clamp.py; run the existing unittest suite. Do not modify tests."
    if state['worker_calls'] == 1:
        guidance = "Review the existing delivered implementation, add a concise clamp function docstring, and run unchanged unittest tests. Preserve behavior and test files."
    return {'action': 'delegate' if state['worker_calls'] < 2 else 'finish', 'query': '', 'guidance': guidance, 'memory': {}, 'context': {}, 'omit_optional_context': []}
''')
        paths=[Path(__file__),scaffold,*Path('src/hx').glob('*.py'),*Path('benchmarks/polybench').glob('*.py'),BINARY]
        locks={str(p.resolve()):sha(p.read_bytes()) for p in paths}
        original_test=(workspace/'tests/test_clamp.py').read_bytes()
        history=json.loads(Path('.hx/stopping-policy-pilot-v1/plan.json').read_text())['historical_scores']
        write('plan.json',{'started':started,'deadline':started+900,'max_reported_tokens':100000,
              'shared_model_seconds':180,'max_calls':2,'model':'gpt-6.1-sol','effort':'medium',
              'image_id':image.id,'source_locks':locks,'historical_scores':history,
              'classification':'Synthetic integration validation; no benchmark or official grader',
              'turn_boundary_overshoot_possible':True})
        write('plan.lock.json',{'sha256':sha((root/'plan.json').read_bytes())})
        tokens=0
        events=[]
        def control():
            if time.time()>=started+900:
                raise HXError('Original validation deadline exhausted')
            if shutil.disk_usage(Path.cwd()).free<40*1024**3:
                raise HXError('40 GiB storage guard')
            if any(sha(Path(p).read_bytes())!=h for p,h in locks.items()):
                raise HXError('Frozen runtime changed')
        def emit(kind,data):
            nonlocal tokens
            if kind=='worker.usage':
                tokens+=int(data['tokens'])
            events.append({'kind':kind,'data':data})
            write('events.json',events)
        class Admitted(ContainerAdapter):
            calls=0
            def run(self,*args,**kwargs):
                control()
                q=account_usage(BINARY,AUTH)
                write('quota.json',q)
                if not can_start(q):
                    raise HXError('Ordinary quota blocked; no retry')
                self.calls+=1
                if self.calls>2:
                    raise HXError('Two-call cap')
                return super().run(*args,**kwargs)
        settings=Settings(adapter='codex',workflow='single',worker_model='gpt-6.1-sol',
            reasoning_effort='medium',max_observed_tokens=100000,repair_token_reserve=10000)
        delegate=Admitted(settings,client,{'repo':'hx/synthetic','repo_path':str(workspace),
            'upstream_base':upstream,'image_id':image.id},BINARY,AUTH)
        delegate.sessions=TaskSessions()
        wrapped=WorkerScaffoldAdapter(delegate,scaffold,settings)
        wrapped.headroom=lambda:100000-tokens
        task=Task(id='synthetic-two-call',repo=str(workspace),report='Clamp numeric value to inclusive low/high bounds; review afterward.',
                  base_commit=base,allowed_paths=['clamp.py'],protected_paths=['tests/**'])
        try:
            control()
            result=wrapped.run('implementer',task,workspace,{'native_session_scope':root.name},
                'Use only public fixture code. Obey executable_scaffold.guidance. Return WorkerSummary. Do not change Git history or test files.',
                WorkerSummary,native/'logs',control,emit,180)
            execution=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],
                cwd=workspace,capture_output=True,text=True,timeout=30)
            atomic_write(root/'verification.txt',(execution.stdout+execution.stderr).encode())
            sessions=[e['data'] for e in events if e['kind']=='worker.session']
            saves=[e['data'] for e in events if e['kind']=='worker.session_saved']
            good=(delegate.calls==2 and len(sessions)==2 and not sessions[0]['resumed']
                and sessions[1]['resumed'] and len(saves)==2 and execution.returncode==0
                and (workspace/'tests/test_clamp.py').read_bytes()==original_test
                and workspace_tree(workspace)==saves[-1]['source_tree'])
            write('result.json',{'passed':good,'delegate_calls':delegate.calls,'reported_tokens':tokens,
                'sessions':sessions,'source_tree':workspace_tree(workspace),'worker_result':result,
                'verification_exit':execution.returncode,'official_grader_calls':0,'historical_scores_verified':len(history),
                'history_intact':all(sha(Path(p).read_bytes())==h for p,h in history.items()),
                'classification':'Synthetic live integration only; no benchmark performance claim'})
            atomic_write(root/'delivered-clamp.py',(workspace/'clamp.py').read_bytes())
            if not good:
                raise HXError('Live two-call integration did not satisfy receipts')
        except BaseException as error:
            write('failure.json',{'error':str(error),'reported_tokens':tokens,'delegate_calls':delegate.calls,'retry':False})
            raise
        finally:
            client.close()
            write('controller.exited.json',{'pid':os.getpid(),'time':time.time()})
        print((root/'result.json').read_text())


if __name__=='__main__':
    run(Path(sys.argv[1]))
