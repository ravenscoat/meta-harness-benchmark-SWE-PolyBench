# Appended to the existing evaluator's helper program; never copied to workers.
def sync(operations, tenant='a'):
    return client.post('/sync',json={'operations':operations},headers={'X-Tenant':tenant})
def operation(id, key, title='updated', version=1):
    return {'mutation_id':key,'item_id':id,'expected_version':version,'title':title}
def test_delta():
    id=create(title='original').json()['id']
    op=operation(id,'once')
    reply=sync([op]); assert reply.status_code==200
    result=reply.json()['results'][0]; assert result['status']==200 and result['item']['version']==2
    assert sync([op]).json()==reply.json() and audit(id)==2
    reused=sync([operation(id,'once','different')]).json()['results'][0]
    assert reused['mutation_id']=='once' and reused['status']==409 and 'item' not in reused
    conflict=sync([operation(id,'conflict','bad',1)]).json()['results'][0]
    assert conflict['status']==412 and conflict['item']['title']=='updated'
    assert get(id).json()['version']==2 and audit(id)==2
    foreign=sync([operation(id,'foreign')],'b').json()['results'][0]
    assert foreign['mutation_id']=='foreign' and foreign['status']==404 and 'item' not in foreign
    assert sync([]).status_code==422 and sync([op,op]).status_code==422
    assert sync([operation(id,'blank',' ')]).status_code==422
    assert sync([operation(id,'long','x'*121)]).status_code==422
    missing=client.post('/sync',json={'operations':[op]}); assert missing.status_code==401
    restart=subprocess.run([sys.executable,'-c',"import json; from fastapi.testclient import TestClient; from backend.app import app; c=TestClient(app); print(json.dumps(c.post('/sync',json={'operations':"+repr([op])+"},headers={'X-Tenant':'a'}).json()))"],capture_output=True,text=True,env=os.environ.copy(),timeout=20)
    assert restart.returncode==0 and json.loads(restart.stdout)==reply.json()
def test_delta_concurrent():
    id=create(title='CAS sync').json()['id']
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        replies=list(pool.map(lambda n:sync([operation(id,f'writer-{n}',f'title-{n}')]),range(8)))
    statuses=[r.json()['results'][0]['status'] for r in replies]
    assert sorted(statuses)==[200]+[412]*7
    assert get(id).json()['version']==2 and audit(id)==2
    id2=create(title='same operation').json()['id']; op=operation(id2,'parallel-replay')
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        replies=list(pool.map(lambda _:sync([op]),range(12)))
    assert all(r.status_code==200 for r in replies)
    assert len({json.dumps(r.json(),sort_keys=True) for r in replies})==1
    assert get(id2).json()['version']==2 and audit(id2)==2
    a=create(title='a').json()['id']; b=create(title='b').json()['id']
    reply=sync([operation(a,'first'),operation(b,'second'),operation(999999,'missing')]).json()['results']
    assert [r['mutation_id'] for r in reply]==['first','second','missing']
    assert [r['status'] for r in reply]==[200,200,404]
    assert get(a).json()['version']==2 and get(b).json()['version']==2
    # Request validation precedes every mutation, including invalid late entries.
    id3=create(title='untouched').json()['id']
    assert sync([operation(id3,'valid'),operation(id3,'invalid',' ')]).status_code==422
    assert get(id3).json()['version']==1 and audit(id3)==1
