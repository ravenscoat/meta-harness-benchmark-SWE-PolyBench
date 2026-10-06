"""Exactly three untouched public benchmark bugs with blind challenge checks."""
import argparse
import json
import os
import shutil
import time
from pathlib import Path

from filelock import FileLock

from benchmarks.polybench import runner
from benchmarks.polybench.independent import VERSION, IndependentEngine
from benchmarks.polybench.prepare import sha, write
from scripts.overnight_limits import account_usage, can_start

CASES=['serverless__serverless-7374','serverless__serverless-7277','mui__material-ui-28190']


def prepare(root):
    if root.exists():
        raise RuntimeError('New three-task root required')
    source=Path('.hx/polybench-v1')
    history={str(p.resolve()):sha(p) for p in Path('.hx').glob('*/experiments/*/*/score.json')}
    used={json.loads(Path(p).read_text()).get('case') for p in history}
    # Also exclude coding identities that were started but never scored.
    for state in Path('.hx').glob('*/experiments/*/*/state'):
        snapshots=sorted(state.glob('console-snapshot.*.json'))
        if snapshots:
            saved=json.loads(snapshots[-1].read_text())
            for run in saved if isinstance(saved,list) else []:
                task=run.get('task',{})
                if isinstance(task,dict):
                    used.add(task.get('id'))
    if used & set(CASES):
        raise RuntimeError('Selected task already has a recorded coding score')
    root.mkdir()
    for name in ('dataset.csv','storage.json'):
        shutil.copyfile(source/name,root/name)
    text=Path('.hx/worker-environment-development-v2/settings.toml').read_text()
    text=text.replace('repair_token_reserve = 60000','repair_token_reserve = 150000')
    text=text.replace('max_observed_tokens = 400000','max_observed_tokens = 700000')
    text=text.replace('run_timeout_seconds = 1800','run_timeout_seconds = 2400')
    import tomllib

    from hx.models import Settings
    Settings.model_validate(tomllib.loads(text))
    (root/'settings.toml').write_text(text)
    selection=json.loads((source/'selection.json').read_text())
    selection['cases']=[c for c in selection['cases'] if c['id'] in CASES]
    selection['planned']={'evaluation':3}
    images=json.loads((source/'images.json').read_text())
    write(root/'selection.json',selection)
    write(root/'images.json',{key:images[key] for key in CASES})
    for key in CASES:
        gate=json.loads((source/'preflight'/key/'validation.json').read_text())
        if not gate['valid'] or gate['image_id']!=images[key]['image_id']:
            raise RuntimeError('Pinned environment invalid')
        for directory,name in [('public',key+'.json'),('preflight/'+key,'validation.json')]:
            target=root/directory
            target.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source/directory/name,target/name)
    (root/'experiments').mkdir()
    now=time.time()
    prior=Path('.hx/independent-three-v1')
    parent=None
    if root.name=='independent-three-v2' and prior.exists():
        previous=json.loads((prior/'results.json').read_text())
        if previous['scored'] or previous['reported_tokens'] or previous['retained_unscored_runs'] or not (prior/'controller.exited.json').exists():
            raise RuntimeError('Prior startup has coding consumption; no replacement allowed')
        old_plan=json.loads((prior/'plan.json').read_text())
        now=old_plan['started']
        parent={str(p.resolve()):sha(p) for p in [prior/'plan.json',prior/'plan.lock.json',prior/'stop.json',prior/'results.json']}
    plan={'cases':CASES,'started':now,'deadline':now+14400,'max_reported_tokens':2600000,
          'planned_trials':3,'worker':'gpt-6.1-sol','protocol':VERSION,
          'selection':'First two unused original Serverless bugs and first unused MUI bug in original metadata order. No solution/score content used for ranking.',
          'historical_scores':history,'startup_failure_preserved':parent,'scheduler':{str(p.resolve()):sha(p) for p in
            [Path(__file__),Path('scripts/overnight_limits.py'),Path('scripts/run_five_failure_development.py')]},
          'limitations':'Three tasks, no paired baseline; no causal gain or leaderboard claim. Same model in separate blind test-author and implementer contexts; correlated errors remain. At most one repair per task. 700000 tokens per workflow at model turn boundaries, may overshoot; 2.6M batch allowance. No credit purchases/reset redemption. Existing public issue only; no solutions or private grader content enter model context.'}
    write(root/'plan.json',plan)
    write(root/'plan.lock.json',{'sha256':sha(root/'plan.json')})
    runner.lock_sources(root)


def validate(root,plan):
    assert sha(root/'plan.json')==json.loads((root/'plan.lock.json').read_text())['sha256']
    for name,value in {**plan['historical_scores'],**plan['scheduler'],**(plan.get('startup_failure_preserved') or {})}.items():
        if sha(Path(name))!=value:
            raise RuntimeError('Sealed input changed: '+name)
    runner.lock_sources(root)


def usage_all(root):
    # The shared helper addresses development scores only; selected tasks retain
    # their original evaluation split. Count both scores and native unscored runs.
    from benchmarks.polybench.state import trial_store
    rows=[json.loads(p.read_text()) for p in (root/'experiments/heldout-results').glob('*/score.json')]
    tokens=sum(r['observed_tokens'] for r in rows)
    incomplete=[]
    for p in (root/'experiments/heldout-results').glob('*/state/native-state.json'):
        trial=p.parent.parent
        if not (trial/'score.json').exists():
            runs=trial_store(root,trial).list()
            tokens+=sum(r['observed_tokens'] for r in runs)
            incomplete.extend(r['id'] for r in runs)
    return rows,tokens,incomplete


def report(root,plan):
    rows,tokens,incomplete=usage_all(root)
    value={'planned_trials':3,'scored':len(rows),'complete':len(rows)==3,'rows':rows,
           'reported_tokens':tokens,'retained_unscored_runs':incomplete,
           'official_resolved':sum(bool(r['official_resolved']) for r in rows),
           'wall_seconds':time.time()-plan['started'],'limitations':plan['limitations']}
    write(root/'results.json',value)
    write(root/'experiments/report.json',value)
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('--prepare',action='store_true')
    args=parser.parse_args()
    os.environ['PATH']='/opt/hx-codex/node_modules/.bin:'+os.environ['PATH']
    root=args.root.resolve()
    if args.prepare:
        prepare(root)
    plan=json.loads((root/'plan.json').read_text())
    original=runner.PolyEngine
    def guard(step=None):
        validate(root,plan)
        _,tokens,_=usage_all(root)
        reserve=850000 if step is None else 150000
        if tokens+reserve>plan['max_reported_tokens'] or time.time()+ (2430 if step is None else 630)>=plan['deadline']:
            raise RuntimeError('Fixed three-task envelope lacks another execution window')
        quota=account_usage(runner.BINARY,runner.AUTH)
        write(root/'quota.json',quota)
        if not can_start(quota):
            raise RuntimeError('Account quota stop; wait natural reset, no credits used')
    class Guarded(IndependentEngine):
        def _worker(self,*args,**kwargs):
            guard(args[1])
            reserve=350000 if args[1]=='implement' else self.settings.repair_token_reserve
            if self.model_headroom(args[0])<reserve:
                raise RuntimeError('Implementation/repair reserve unavailable')
            return super()._worker(*args,**kwargs)
    with FileLock('.hx/single-evaluation-controller.lock').acquire(timeout=0):
        write(root/'controller.json',{'pid':os.getpid(),'started':time.time()})
        runner.PolyEngine=Guarded
        try:
            for key in CASES:
                rows,_,incomplete=usage_all(root)
                if any(r['case']==key for r in rows):
                    continue
                if incomplete or any(r.get('usage_known') is False for r in rows):
                    raise RuntimeError('Interrupted/unknown coding consumption; no silent retry')
                guard()
                runner.run_case(root,key,'full',start_guard=lambda:guard('before-worker'))
                print(json.dumps(report(root,plan)),flush=True)
            validate(root,plan)
            write(root/'audit.json',{'completed':True,'historical_scores_unchanged':len(plan['historical_scores']),
                'score_hashes':{str(p.relative_to(root)):sha(p) for p in (root/'experiments/heldout-results').glob('*/score.json')}})
        except BaseException as exc:
            write(root/'stop.json',{'error':str(exc),'type':type(exc).__name__,'time':time.time()})
            raise
        finally:
            report(root,plan)
            write(root/'controller.exited.json',{'pid':os.getpid(),'time':time.time()})
            runner.PolyEngine=original


if __name__=='__main__':
    main()
