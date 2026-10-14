"""Postgres-leased expression queue with private durable inputs/checkpoints.

Local directories are disposable caches. A claim can run after an API/Space
restart because all authoritative inputs and QC checkpoints are remote.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import logging
import re
import shutil
import tempfile
import threading
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from app.rnaseq.expression import (BUCKET, R_SCRIPT, ExpressionParameters,
    RnaSeqExpressionError, _ensure_bucket, _safe_user_key, _upload_bytes,
    execute_expression_analysis, expression_readiness, get_supabase, load_manifest, sha256_file)

logger = logging.getLogger(__name__)
TABLE = 'rnaseq_expression_queue'
WORKERS = 'rnaseq_expression_workers'
MAX_ATTEMPTS = 3
LEASE_SECONDS = 120


def _owner(user: str) -> str:
    return hashlib.sha256(user.encode()).hexdigest()


def _id(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise FileNotFoundError('Expression job not found') from exc


def _name(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,150}', value) or value in ('.','..'):
        raise RnaSeqExpressionError('Invalid retained input filename')
    return value


def _prefix(user: str, job_id: str) -> str:
    return f'{_safe_user_key(user)}/queued/{_id(job_id)}'


def _rows(query) -> list[dict]:
    result = query.execute()
    if not isinstance(result.data, list):
        raise RnaSeqExpressionError('Durable expression database returned an invalid response')
    return result.data


def _owned(job_id: str, user: str) -> dict:
    rows = _rows(get_supabase().table(TABLE).select('*').eq('id', _id(job_id)).eq('owner', _owner(user)).limit(1))
    if not rows:
        raise FileNotFoundError('Expression job not found')
    return rows[0]


def _download(prefix: str, name: str, expected: str) -> bytes:
    body = get_supabase().storage.from_(BUCKET).download(f'{prefix}/{_name(name)}')
    if not isinstance(body, bytes) or hashlib.sha256(body).hexdigest() != expected:
        raise RnaSeqExpressionError('Retained input/checkpoint checksum mismatch')
    return body


def storage_ready() -> None:
    _rows(get_supabase().table(TABLE).select('id').limit(1))
    buckets = get_supabase().storage.list_buckets() or []
    bucket = next((b for b in buckets if (b.get('name') if isinstance(b, dict) else getattr(b,'name',None)) == BUCKET), None)
    if bucket is None:
        _ensure_bucket()
        buckets = get_supabase().storage.list_buckets() or []
        bucket = next((b for b in buckets if (b.get('name') if isinstance(b, dict) else getattr(b,'name',None)) == BUCKET), None)
        if bucket is None:
            raise RnaSeqExpressionError('Private RNA-seq artifact bucket is unavailable')
    public = bucket.get('public') if isinstance(bucket, dict) else getattr(bucket,'public',None)
    if public is not False:
        raise RnaSeqExpressionError('RNA-seq artifact bucket must be confirmed private')


def readiness(salmon: bool = False) -> dict:
    result = expression_readiness(salmon)
    result['storage_backend'] = 'supabase'
    try:
        storage_ready()
        active = _rows(get_supabase().table(WORKERS).select('id').gt('heartbeat',time.time()-30).limit(1))
        if not active:
            result['missing'].append('dedicated expression worker heartbeat')
    except Exception as exc:
        result['missing'].append(f'Durable expression database/private storage unavailable ({type(exc).__name__}); apply the expression queue migration')
    result['available'] = not result['missing']
    return result


def enqueue(user: str, counts: Path, metadata: Path, params: ExpressionParameters,
            source: dict, *, input_kind: str = 'raw_counts', extras: dict[str,bytes] | None = None,
            full_analysis: bool = False) -> dict:
    ready = readiness(input_kind == 'salmon')
    if not ready['available']:
        raise RnaSeqExpressionError('Durable execution unavailable: ' + ', '.join(ready['missing']))
    params.validate()
    job_id = str(uuid.uuid4()); prefix = _prefix(user,job_id)
    files = {'counts.tsv':counts.read_bytes(), 'metadata.tsv':metadata.read_bytes()}
    for name, body in (extras or {}).items():
        _name(name)
        if name in files:
            raise RnaSeqExpressionError('Extra inputs cannot replace the count or metadata matrix')
        files[name] = body
    uploaded = []
    try:
        for name, body in files.items():
            path = f'{prefix}/{name}'; _upload_bytes(path,body,'application/octet-stream'); uploaded.append(path)
        payload = {'params':asdict(params),'source':source,'input_kind':input_kind,
                   'checksums':{n:hashlib.sha256(b).hexdigest() for n,b in files.items()},
                   'engine_sha256':sha256_file(R_SCRIPT)}
        now=time.time()
        _rows(get_supabase().table(TABLE).insert({'id':job_id,'owner':_owner(user),'user_id':user,
            'state':'QUEUED','phase':'full' if full_analysis else 'qc','payload':payload,
            'created':now,'updated':now}))
    except Exception:
        # Unique new job prefix only; no existing user results can be removed here.
        if uploaded:
            try: get_supabase().storage.from_(BUCKET).remove(uploaded)
            except Exception: logger.warning('Unpublished expression inputs could not be cleaned up')
        raise
    return {'job_id':job_id,'state':'QUEUED'}


def _monitor(row: dict) -> dict:
    from app.rnaseq.durable import _monitor as monitor
    return monitor(row)


def status(job_id: str, user: str) -> dict:
    row=_owned(job_id,user); result=row.get('result')
    if result:
        result={**load_manifest(user,result['run_id']),
                **({'checkpoint_sha256':result['checkpoint_sha256']} if result.get('checkpoint_sha256') else {})}
    return {'job_id':row['id'],'state':row['state'],'phase':row['phase'],'attempts':row['attempts'],
            'error':row.get('error'),'result':result,'progress':row.get('progress') or [],**_monitor(row)}


def list_jobs(user: str, limit: int = 50) -> dict:
    if not 1 <= limit <= 100:
        raise RnaSeqExpressionError('Job list limit must be between 1 and 100')
    rows=_rows(get_supabase().table(TABLE).select('*').eq('owner',_owner(user)).order('created',desc=True).limit(limit))
    return {'jobs':[{'job_id':r['id'],'state':r['state'],'phase':r['phase'],'attempts':r['attempts'],
                     'error':r.get('error'),**_monitor(r)} for r in rows]}


def cancel(job_id: str, user: str) -> dict:
    row=_owned(job_id,user)
    if row['state']=='CANCELLED': return {'job_id':row['id'],'state':'CANCELLED'}
    if row['state'] not in ('QUEUED','QC_REVIEW'):
        raise RnaSeqExpressionError('Only queued jobs or jobs awaiting QC review can be cancelled; running process termination is unavailable')
    changed=_rows(get_supabase().table(TABLE).update({'state':'CANCELLED','lease':None,'updated':time.time()}).eq('id',row['id']).eq('owner',_owner(user)).eq('state',row['state']))
    if not changed: raise RnaSeqExpressionError('Job state changed; reload before cancelling')
    return {'job_id':row['id'],'state':'CANCELLED'}


def approve(job_id: str, user: str, checkpoint_sha256: str) -> dict:
    row=_owned(job_id,user)
    if row['state']!='QC_REVIEW': raise RnaSeqExpressionError('This job is not awaiting QC review')
    result=row['result']; recorded=result['checkpoint_sha256']
    if checkpoint_sha256!=recorded: raise RnaSeqExpressionError('QC checkpoint changed; inference cannot proceed')
    _download(_prefix(user,row['id']),result['checkpoint_file'],recorded)
    payload={**row['payload'],'qc_review':{'checkpoint_sha256':recorded,'checkpoint_file':result['checkpoint_file'],
              'qc_run_id':result['run_id'],'reviewed_at':time.time()}}
    changed=_rows(get_supabase().table(TABLE).update({'state':'QUEUED','phase':'infer','attempts':0,
        'payload':payload,'updated':time.time(),'progress':[]}).eq('id',row['id']).eq('owner',_owner(user)).eq('state','QC_REVIEW').eq('updated',row['updated']))
    if not changed: raise RnaSeqExpressionError('QC review changed; reload before approval')
    return {'job_id':row['id'],'state':'QUEUED'}


def claim(worker_id: str) -> dict | None:
    rows=_rows(get_supabase().rpc('claim_rnaseq_expression_job',{'worker_id':worker_id}))
    return rows[0] if rows else None


def tick(worker_id: str, job: dict | None = None) -> None:
    sb=get_supabase(); now=time.time()
    _rows(sb.table(WORKERS).upsert({'id':worker_id,'heartbeat':now}))
    if job:
        _rows(sb.table(TABLE).update({'heartbeat':now}).eq('id',job['id']).eq('lease',job['lease']).eq('state','RUNNING'))


def run_job(job: dict) -> None:
    payload=job['payload']; prefix=_prefix(job['user_id'],job['id'])
    result=None; state='FAILED'; error=None
    with tempfile.TemporaryDirectory(prefix='bionexus-expression-') as scratch:
        folder=Path(scratch); progress=folder/'progress.jsonl'
        done=threading.Event()
        def heartbeat():
            from app.rnaseq.durable import read_progress
            while not done.wait(5):
                try:
                    tick('expression-'+job['lease'],job)
                    _rows(get_supabase().table(TABLE).update({'progress':read_progress(progress)}).eq('id',job['id']).eq('lease',job['lease']).eq('state','RUNNING'))
                except Exception: logger.warning('Expression heartbeat/progress update unavailable')
        thread=threading.Thread(target=heartbeat,daemon=True); thread.start()
        try:
            if sha256_file(R_SCRIPT)!=payload['engine_sha256']:
                raise RnaSeqExpressionError('Statistical implementation changed; submit a new reviewed run')
            for name,digest in payload['checksums'].items():
                (folder/_name(name)).write_bytes(_download(prefix,name,digest))
            checkpoint=None
            if job['phase']=='qc': checkpoint=folder/f"qc_{job['lease']}.rds"
            elif job['phase']=='infer':
                reviewed=payload['qc_review']; checkpoint=folder/_name(reviewed['checkpoint_file'])
                checkpoint.write_bytes(_download(prefix,checkpoint.name,reviewed['checkpoint_sha256']))
            if payload['input_kind']=='salmon':
                rows=list(csv.DictReader(io.StringIO((folder/'counts.tsv').read_text()),delimiter='\t'))
                out=io.StringIO(); writer=csv.writer(out,delimiter='\t',lineterminator='\n'); writer.writerow(['sample','quant_file'])
                for row in rows:
                    name=_name(row['quant_file'])
                    if name not in payload['checksums']: raise RnaSeqExpressionError('Unretained Salmon quantification input')
                    writer.writerow([row['sample'],str(folder/name)])
                (folder/'counts.tsv').write_text(out.getvalue())
            result=execute_expression_analysis(user_id=job['user_id'],counts_path=folder/'counts.tsv',metadata_path=folder/'metadata.tsv',
                params=ExpressionParameters(**payload['params']),source_label='reviewed-recovery',
                source_metadata={**payload['source'],'input_checksums':payload['checksums'],'qc_review':payload.get('qc_review')},
                stage=job['phase'],checkpoint_path=checkpoint,input_kind=payload['input_kind'],
                tx2gene_path=folder/'tx2gene.tsv' if payload['input_kind']=='salmon' else None,progress_path=progress)
            if job['phase']=='qc':
                digest=sha256_file(checkpoint)
                _upload_bytes(f'{prefix}/{checkpoint.name}',checkpoint.read_bytes(),'application/octet-stream')
                result={**result,'checkpoint_sha256':digest,'checkpoint_file':checkpoint.name}; state='QC_REVIEW'
            else: state='SUCCEEDED'
        except Exception as exc:
            error=str(exc)[:1000]
            if not isinstance(exc,RnaSeqExpressionError) and job['attempts']<MAX_ATTEMPTS: state='QUEUED'
        finally:
            done.set(); thread.join()
        from app.rnaseq.durable import read_progress
        _rows(get_supabase().table(TABLE).update({'state':state,'result':result,'error':error,'updated':time.time(),
              'lease':None,'progress':read_progress(progress)}).eq('id',job['id']).eq('lease',job['lease']).eq('state','RUNNING'))
