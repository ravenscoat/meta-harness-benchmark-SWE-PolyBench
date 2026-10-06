import ast,csv,hashlib,html,json
from collections import Counter
from pathlib import Path
from urllib.parse import quote
csv.field_size_limit(100000000)
source=Path('.hx/polybench-v1/dataset.csv')
selection=json.loads(Path('.hx/polybench-v1/selection.json').read_text())
assert hashlib.sha256(source.read_bytes()).hexdigest()==selection['dataset_sha256']
selected={r['id']:r['split'] for r in selection['cases']}
records=[]
for row in csv.DictReader(source.open(encoding='utf-8')):
    numbers=list(dict.fromkeys(str(n) for n in ast.literal_eval(row['issue_numbers'])))
    pr=int(float(row['pull_number']))
    records.append({'id':row['instance_id'],'repository':row['repo'],'language':row['language'],'category':row['task_category'],'selected_split':selected.get(row['instance_id'],''),'issues':[f"https://github.com/{row['repo']}/issues/{n}" for n in numbers],'fix_pr':f"https://github.com/{row['repo']}/pull/{pr}"})
repos=[]
for repo,count in sorted(Counter(r['repository'] for r in records).items()):
    base='https://github.com/'+repo
    repos.append({'repository':repo,'tasks':count,'all_issues':base+'/issues?q='+quote('is:issue'),'closed_issues':base+'/issues?q='+quote('is:issue is:closed'),'open_issues':base+'/issues?q='+quote('is:issue is:open'),'merged_prs':base+'/pulls?q='+quote('is:pr is:merged')})
out=Path('docs/benchmark-issues')
(out/'index.json').write_text(json.dumps({'dataset':selection['dataset'],'revision':selection['dataset_revision'],'task_count':len(records),'repository_count':len(repos),'repositories':repos,'tasks':records,'note':'Metadata links only; issue status is shown live on GitHub. Reference PRs are solutions: inspected tasks become development material.'},indent=2),encoding='utf-8')
with (out/'tasks.csv').open('w',newline='',encoding='utf-8') as f:
    writer=csv.DictWriter(f,fieldnames=['id','repository','language','category','selected_split','issues','fix_pr']);writer.writeheader()
    writer.writerows({**r,'issues':' | '.join(r['issues'])} for r in records)
def link(url,label):return '<a target="_blank" rel="noopener" href="'+html.escape(url,quote=True)+'">'+html.escape(label)+'</a>'
repo_rows=''.join('<tr><td>'+html.escape(r['repository'])+'</td><td>'+str(r['tasks'])+'</td><td>'+ ' · '.join(link(r[k],label) for k,label in [('all_issues','All'),('closed_issues','Closed'),('open_issues','Open'),('merged_prs','Merged fixes')])+'</td></tr>' for r in repos)
task_rows=''.join('<tr data-search="'+html.escape(' '.join(str(r[k]) for k in ['id','repository','language','category','selected_split']).lower(),quote=True)+'"><td>'+html.escape(r['id'])+'</td><td>'+html.escape(r['language'])+'</td><td>'+html.escape(r['category'])+'</td><td>'+html.escape(r['selected_split'] or 'Outside HX selection')+'</td><td>'+(' · '.join(link(url,'Issue #'+url.rsplit('/',1)[1]) for url in r['issues']) or 'No linked issue')+'</td><td>'+link(r['fix_pr'],'PR #'+r['fix_pr'].rsplit('/',1)[1])+'</td></tr>' for r in records)
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SWE-PolyBench issue explorer</title><style>body{font:16px system-ui;margin:32px auto;max-width:1200px;padding:0 22px;background:#f5f7fa;color:#172337}h1{font-size:30px}p{line-height:1.55}table{width:100%;border-collapse:collapse;background:white;margin:20px 0}td,th{text-align:left;padding:12px;border-bottom:1px solid #dbe1ea}a{color:#145ec5}input{padding:12px;width:min(600px,90%);font:inherit;border:1px solid #aab8c9;border-radius:6px}.scroll{overflow:auto}.note{padding:16px;background:#e8eef8;border-radius:8px}th{background:#eaf0f7}small{color:#526176}</style><h1>SWE-PolyBench Verified: repository issues</h1><p>382 pinned benchmark tasks across 20 repositories. Browse all issues, closed discussions and merged fixes. GitHub shows their live status.</p><p class="note">Reading a fix PR reveals a reference solution. Use inspected tasks for development; reserve untouched tasks for later evaluation. This index contains metadata links, not solution patches or evaluator tests.</p><h2>Repositories</h2><div class="scroll"><table><thead><tr><th>Repository</th><th>Benchmark tasks</th><th>Browse GitHub</th></tr></thead><tbody>'''+repo_rows+'''</tbody></table></div><h2>All benchmark tasks</h2><input id="search" aria-label="Filter tasks" placeholder="Search repository, task number, language or HX split"><p id="count">382 tasks shown</p><div class="scroll"><table><thead><tr><th>Task</th><th>Language</th><th>Category</th><th>HX selection</th><th>Reported issue</th><th>Reference fix</th></tr></thead><tbody id="tasks">'''+task_rows+'''</tbody></table></div><small>Pinned dataset revision: '''+html.escape(selection['dataset_revision'])+'''</small><script>const rows=[...document.querySelectorAll('#tasks tr')];document.querySelector('#search').addEventListener('input',e=>{const q=e.target.value.toLowerCase().trim();let n=0;for(const row of rows){const show=row.dataset.search.includes(q);row.hidden=!show;if(show)n++;}document.querySelector('#count').textContent=n+' tasks shown';});</script></html>'''
(out/'index.html').write_text(page,encoding='utf-8')
assert len(records)==382 and len(repos)==20 and len(selected)==35
print(json.dumps({'tasks':len(records),'repositories':len(repos),'selected':len(selected),'artifacts':str(out)}))
