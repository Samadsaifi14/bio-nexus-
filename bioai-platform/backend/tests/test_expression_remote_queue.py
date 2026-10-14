import copy
import hashlib
import json
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
import pytest
from app.rnaseq import durable, remote_queue as remote
from app.rnaseq.expression import ExpressionParameters, RnaSeqExpressionError


class Query:
    def __init__(self, sb, table):
        self.sb,self.name=sb,table; self.filters=[]; self.operation='select'; self.payload=None; self.count=None
    def select(self,*_): return self
    def insert(self,body): self.operation='insert'; self.payload=body; return self
    def upsert(self,body): self.operation='upsert'; self.payload=body; return self
    def update(self,body): self.operation='update'; self.payload=body; return self
    def eq(self,key,value): self.filters.append(lambda r:r.get(key)==value); return self
    def gt(self,key,value): self.filters.append(lambda r:r.get(key,0)>value); return self
    def order(self,*_,**__): return self
    def limit(self,value): self.count=value; return self
    def execute(self):
        with self.sb.lock:
            data=self.sb.tables.setdefault(self.name,[])
            if self.operation in ('insert','upsert'):
                body=copy.deepcopy(self.payload)
                if self.name==remote.TABLE:
                    body={'attempts':0,'heartbeat':None,'lease':None,'result':None,'error':None,'progress':[],**body}
                old=next((r for r in data if r['id']==body['id']),None)
                if old and self.operation=='upsert': old.update(body); found=[old]
                else: data.append(body); found=[body]
            else:
                found=[r for r in data if all(f(r) for f in self.filters)]
                if self.count is not None: found=found[:self.count]
                if self.operation=='update':
                    for row in found: row.update(copy.deepcopy(self.payload))
            return SimpleNamespace(data=copy.deepcopy(found))


class Storage:
    def __init__(self): self.objects={}; self.public=False
    def list_buckets(self): return [{'name':remote.BUCKET,'public':self.public}]
    def from_(self,_): return self
    def download(self,key): return self.objects[key]
    def upload(self,key,body,_): self.objects[key]=body
    def remove(self,keys):
        for key in keys:self.objects.pop(key,None)


class Client:
    def __init__(self): self.tables={};self.storage=Storage();self.lock=threading.Lock()
    def table(self,name): return Query(self,name)


@pytest.fixture
def sb(monkeypatch):
    client=Client()
    monkeypatch.setattr(remote,'get_supabase',lambda:client)
    monkeypatch.setattr(remote,'_upload_bytes',lambda path,body,_:client.storage.upload(path,body,{}))
    monkeypatch.setattr(remote,'expression_readiness',lambda *_:{'available':True,'missing':[],'rscript_available':True})
    return client


@pytest.fixture
def job(sb,tmp_path,monkeypatch):
    monkeypatch.setattr(remote,'readiness',lambda *_:{'available':True,'missing':[]})
    counts=tmp_path/'counts.tsv'; counts.write_bytes(b'gene\ts1\ts2\ng1\t1\t2\n')
    meta=tmp_path/'meta.tsv'; meta.write_bytes(b'sample\tcondition\ns1\ta\ns2\tb\n')
    job_id=remote.enqueue('alice',counts,meta,ExpressionParameters(),{'fixture':True})['job_id']
    row=sb.tables[remote.TABLE][0];row.update(state='RUNNING',phase='qc',lease=str(uuid.uuid4()),attempts=1,heartbeat=time.time())
    return copy.deepcopy(row)


def test_auto_selects_remote_only_without_explicit_local_root(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings,'SUPABASE_URL','https://project.supabase.co')
    monkeypatch.setattr(settings,'SUPABASE_SERVICE_ROLE_KEY','fixture-not-a-key')
    monkeypatch.delenv('BIONEXUS_EXPRESSION_ROOT',raising=False);monkeypatch.delenv('BIONEXUS_EXPRESSION_BACKEND',raising=False)
    assert durable.storage_backend()=='supabase'
    monkeypatch.setenv('BIONEXUS_EXPRESSION_ROOT','/data/expression')
    assert durable.storage_backend()=='local'
    monkeypatch.setenv('BIONEXUS_EXPRESSION_BACKEND','unknown')
    with pytest.raises(RnaSeqExpressionError):durable.storage_backend()


def test_private_storage_and_worker_heartbeat_required(sb):
    assert 'worker heartbeat' in ','.join(remote.readiness()['missing'])
    remote.tick('worker')
    assert remote.readiness()['available']
    sb.storage.public=True
    assert not remote.readiness()['available']


def test_inputs_survive_local_directory_loss_and_owner_isolation(job,sb,tmp_path):
    assert remote._download(remote._prefix('alice',job['id']),'counts.tsv',job['payload']['checksums']['counts.tsv'])==b'gene\ts1\ts2\ng1\t1\t2\n'
    with pytest.raises(FileNotFoundError): remote.status(job['id'],'bob')
    assert remote.list_jobs('bob')['jobs']==[]
    assert remote.list_jobs('alice')['jobs'][0]['job_id']==job['id']
    assert not any('bionexus-expression-' in key for key in sb.storage.objects)


def test_qc_checkpoint_is_uploaded_before_review_and_approval_restores_it(job,sb,monkeypatch):
    calls=[]
    def execute(**kwargs):
        calls.append(kwargs)
        kwargs['checkpoint_path'].write_bytes(b'retained-qc')
        return {'run_id':'qc-run','state':'QC_READY'}
    monkeypatch.setattr(remote,'execute_expression_analysis',execute)
    monkeypatch.setattr(remote,'load_manifest',lambda *_:{'run_id':'qc-run','state':'QC_READY'})
    remote.run_job(job)
    row=sb.tables[remote.TABLE][0]
    assert row['state']=='QC_REVIEW'
    checkpoint=row['result']['checkpoint_file']; prefix=remote._prefix('alice',job['id'])
    assert sb.storage.objects[f'{prefix}/{checkpoint}']==b'retained-qc'
    assert not calls[0]['counts_path'].exists()  # disposable cache removed
    digest=row['result']['checkpoint_sha256']
    with pytest.raises(RnaSeqExpressionError):remote.approve(job['id'],'alice','wrong')
    remote.approve(job['id'],'alice',digest)
    assert row['state']=='QUEUED' and row['phase']=='infer'
    assert row['payload']['qc_review']['checkpoint_sha256']==hashlib.sha256(b'retained-qc').hexdigest()


def test_changed_retained_input_never_executes(job,sb,monkeypatch):
    sb.storage.objects[f"{remote._prefix('alice',job['id'])}/counts.tsv"]=b'changed'
    monkeypatch.setattr(remote,'execute_expression_analysis',lambda **_:pytest.fail('changed input executed'))
    remote.run_job(job)
    row=sb.tables[remote.TABLE][0]
    assert row['state']=='FAILED' and 'checksum' in row['error']


def test_lost_lease_cannot_publish_success(job,sb,monkeypatch):
    def execute(**kwargs):
        kwargs['checkpoint_path'].write_bytes(b'checkpoint')
        sb.tables[remote.TABLE][0]['lease']=str(uuid.uuid4())
        return {'run_id':'old-lease'}
    monkeypatch.setattr(remote,'execute_expression_analysis',execute)
    remote.run_job(job)
    assert sb.tables[remote.TABLE][0]['state']=='RUNNING' and sb.tables[remote.TABLE][0]['result'] is None


def test_cancel_checks_state_and_owner(job,sb):
    with pytest.raises(FileNotFoundError):remote.cancel(job['id'],'bob')
    with pytest.raises(RnaSeqExpressionError):remote.cancel(job['id'],'alice')
    sb.tables[remote.TABLE][0]['state']='QUEUED'
    assert remote.cancel(job['id'],'alice')['state']=='CANCELLED'
    assert remote.cancel(job['id'],'alice')['state']=='CANCELLED'


def test_local_worker_has_explicit_stop(monkeypatch):
    monkeypatch.setattr(durable,'tick',lambda *_:None)
    monkeypatch.setattr(durable,'claim',lambda *_:None)
    stop,thread=durable.start_expression_worker();stop.set();thread.join(timeout=1)
    assert not thread.is_alive()


def test_remote_paths_and_checksum_reject_traversal(sb):
    for name in ('../file','/absolute','C:\\file','..'):
        with pytest.raises(RnaSeqExpressionError):remote._name(name)
    with pytest.raises(FileNotFoundError):remote._prefix('alice','../foreign')
