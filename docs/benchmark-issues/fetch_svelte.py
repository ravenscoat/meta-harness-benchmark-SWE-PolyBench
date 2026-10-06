import json,urllib.request
from pathlib import Path
root=Path('docs/benchmark-issues/svelte-728');root.mkdir(exist_ok=True)
for name,url in [('issue','https://api.github.com/repos/sveltejs/svelte/issues/721'),('fix-pr','https://api.github.com/repos/sveltejs/svelte/pulls/728'),('comments','https://api.github.com/repos/sveltejs/svelte/issues/721/comments?per_page=100')]:
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'HX-public-issue-review','Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(request,timeout=30) as response: data=json.load(response)
        (root/(name+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
        if isinstance(data,dict):print(json.dumps({'kind':name,'url':data.get('html_url'),'title':data.get('title'),'state':data.get('state'),'merged':data.get('merged'),'body':data.get('body','')[:2200]}))
        else: print(json.dumps({'kind':name,'comments':[{'url':r['html_url'],'body':r.get('body','')[:1200]} for r in data]}))
    except Exception as error:
        (root/(name+'-error.json')).write_text(json.dumps({'url':url,'error':str(error)}))
        print(name,str(error))
