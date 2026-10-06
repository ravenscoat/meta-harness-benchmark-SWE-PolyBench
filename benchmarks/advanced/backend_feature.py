"""Append to the reference app for evaluator-only delta synchronization."""
from pydantic import Field


class Operation(BaseModel):
    mutation_id: str = Field(min_length=1, max_length=80)
    item_id: int = Field(ge=1)
    expected_version: int = Field(ge=1)
    title: str


class SyncBatch(BaseModel):
    operations: list[Operation] = Field(min_length=1, max_length=50)


@app.post('/sync')
def synchronize(body: SyncBatch, x_tenant: str | None = Header(None)):
    tenant = tenant_value(x_tenant)
    for operation in body.operations:
        valid_title(operation.title)
    if len({op.mutation_id for op in body.operations}) != len(body.operations):
        raise HTTPException(422, 'duplicate mutation identifiers')
    results = []
    with connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS mutations(tenant TEXT NOT NULL, key TEXT NOT NULL, digest TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(tenant,key))')
        db.execute('BEGIN IMMEDIATE')
        for op in body.operations:
            digest = hashlib.sha256(json.dumps(op.model_dump(),sort_keys=True).encode()).hexdigest()
            saved = db.execute('SELECT * FROM mutations WHERE tenant=? AND key=?',(tenant,op.mutation_id)).fetchone()
            if saved:
                result = json.loads(saved['result']) if saved['digest']==digest else {'mutation_id':op.mutation_id,'status':409}
                results.append(result)
                continue
            row = db.execute('SELECT * FROM items WHERE tenant=? AND id=?',(tenant,op.item_id)).fetchone()
            result = {'mutation_id':op.mutation_id}
            if row is None:
                result['status'] = 404
            elif row['version'] != op.expected_version:
                result.update(status=412, item=dict(row))
            else:
                db.execute('UPDATE items SET title=?,version=version+1,updated=updated+1 WHERE tenant=? AND id=? AND version=?',(op.title,tenant,op.item_id,op.expected_version))
                db.execute('INSERT INTO audit(tenant,item_id,kind) VALUES(?,?,?)',(tenant,op.item_id,'sync'))
                result.update(status=200,item=lookup(db,tenant,op.item_id))
            db.execute('INSERT INTO mutations VALUES(?,?,?,?)',(tenant,op.mutation_id,digest,json.dumps(result)))
            results.append(result)
    return {'results':results}
