"""Observed Nextflow process evidence; never infer an unobserved task count."""
from __future__ import annotations
import csv
import hashlib
import io
from pathlib import Path

MAX_TRACE_BYTES = 5 * 1024 * 1024
REQUIRED = {'task_id', 'name', 'status', 'exit'}


def parse_trace(body: bytes) -> dict:
    if len(body) > MAX_TRACE_BYTES:
        raise ValueError('Nextflow trace exceeds the 5 MB monitoring limit; no partial summary was produced')
    text = body.decode('utf-8-sig')
    # The worker may be appending a record. A partial last row is not evidence.
    complete = text[:text.rfind('\n') + 1] if text else ''
    reader = csv.DictReader(io.StringIO(complete), delimiter='\t')
    if not REQUIRED.issubset(reader.fieldnames or []):
        raise ValueError('Nextflow trace is missing task_id, name, status or exit')
    tasks = []
    for row in reader:
        if None in row or any(row.get(key) is None for key in REQUIRED):
            raise ValueError('Malformed complete Nextflow trace row')
        raw = row['status'].upper()
        exit_value = row['exit'].strip()
        try:
            exit_code = int(exit_value) if exit_value not in {'', '-'} else None
        except ValueError as exc:
            raise ValueError('Invalid Nextflow process exit code') from exc
        state = raw if raw in {'COMPLETED', 'CACHED', 'FAILED', 'ABORTED', 'RUNNING', 'SUBMITTED'} else 'UNKNOWN'
        if state == 'COMPLETED' and exit_code != 0:
            state = 'FAILED' if exit_code is not None else 'UNKNOWN'
        tasks.append({'task_id': row['task_id'], 'name': row['name'], 'recorded_status': raw,
                      'state': state, 'exit_code': exit_code,
                      **{key: row[key] for key in ('hash', 'duration', 'realtime', 'peak_rss', '%cpu') if row.get(key)}})
    states = {state: sum(t['state'] == state for t in tasks) for state in
              ('COMPLETED', 'CACHED', 'FAILED', 'ABORTED', 'RUNNING', 'SUBMITTED', 'UNKNOWN')}
    return {'state': 'OBSERVED', 'observed_process_records': len(tasks), 'states': states,
            'tasks': tasks, 'trace_sha256': hashlib.sha256(body).hexdigest(),
            'incomplete_last_record': bool(text and not text.endswith('\n')),
            'claim': 'Only emitted trace records are counted. Cached tasks are separate from fresh execution. No total-task percentage or scientific validity is inferred.'}


def observe_trace(outdir: str) -> dict:
    if outdir.startswith('s3://'):
        return {'state': 'UNAVAILABLE', 'message': 'Remote trace monitoring is not configured; use the retained S3 execution artifacts.'}
    root = Path(outdir).resolve()
    folder = root / 'pipeline_info'
    candidates = []
    if folder.is_dir():
        for path in folder.glob('execution_trace*.txt'):
            resolved = path.resolve()
            if resolved.is_relative_to(root) and resolved.is_file():
                candidates.append(resolved)
    if not candidates:
        return {'state': 'NOT_EMITTED', 'message': 'No Nextflow trace has been emitted for this run yet.'}
    # Multiple traces can belong to separate launches: do not concatenate them.
    path = max(candidates, key=lambda item: (item.stat().st_mtime_ns, item.name))
    try:
        with path.open('rb') as stream:
            body = stream.read(MAX_TRACE_BYTES + 1)
        return {**parse_trace(body), 'trace_filename': path.name,
                'trace_selection': 'Most recently modified execution trace in this owned output directory'}
    except (OSError, UnicodeError, ValueError) as exc:
        return {'state': 'INVALID', 'message': str(exc)[:300]}
