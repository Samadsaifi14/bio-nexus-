#!/usr/bin/env python3
"""Run every backend module in isolation and retain failures, skips and deadlines.

A successful process is a regression result, never independent scientific validation.
Module isolation avoids losing the entire report to native-library memory growth.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import fnmatch
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'bioai-platform/backend'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outdir', type=Path, required=True)
    parser.add_argument('--module-seconds', type=int, default=120)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    out = args.outdir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    index = out / 'execution.json'
    records = json.loads(index.read_text()) if args.resume and index.exists() else []
    for row in records:
        counts = row['counts']
        if row['exit_code'] == 0 and counts.get('skipped'):
            row['status'] = 'PASSED_WITH_SKIPS' if counts.get('passed') else 'SKIPPED'
    done = {r['module'] for r in records}
    env = dict(os.environ, OPENMM_CPU_THREADS='1', OMP_NUM_THREADS='1', PYTHONHASHSEED='0',
               SUPABASE_URL='https://example.supabase.co', SUPABASE_ANON_KEY='test-placeholder',
               SUPABASE_SERVICE_ROLE_KEY='test-placeholder', JWT_SECRET='test-placeholder')
    files = sorted((BACKEND / 'tests').glob('test_*.py'), key=lambda p: (p.name == 'test_blast_comprehensive.py', p.name))
    for path in files:
        if path.name in done:
            continue
        log, xml = out / (path.stem + '.log'), out / (path.stem + '.xml')
        command = [sys.executable, '-m', 'pytest', 'tests/' + path.name, '-q', '--timeout=90',
                   '--junitxml=' + str(xml), '--basetemp=' + str(out / 'work' / path.stem)]
        (out / 'work').mkdir(exist_ok=True)
        started = time.monotonic()
        row = {'module': path.name, 'started_at': datetime.now(timezone.utc).isoformat(),
               'deadline_seconds': args.module_seconds, 'junit': xml.name, 'log': log.name}
        with log.open('w') as handle:
            process = subprocess.Popen(command, cwd=BACKEND, env=env, stdout=handle,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = process.wait(timeout=args.module_seconds)
                row['deadline_exceeded'] = False
            except subprocess.TimeoutExpired:
                row['deadline_exceeded'] = True
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    code = process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    code = process.wait()
        row.update(exit_code=code, elapsed_seconds=round(time.monotonic() - started, 2))
        if code < 0:
            row['termination_signal'] = signal.Signals(-code).name
        counts, problems = Counter(), []
        if xml.exists():
            for case in ET.parse(xml).iter('testcase'):
                outcome = next((tag for tag in ('failure', 'error', 'skipped') if case.find(tag) is not None), 'passed')
                counts[outcome] += 1
                if outcome != 'passed':
                    child = case.find(outcome)
                    problems.append({'test': case.get('classname', '') + '::' + case.get('name', ''),
                                     'outcome': outcome, 'reason': child.get('message') or (child.text or '')[:2000]})
        if row['deadline_exceeded']:
            status = 'TIMED_OUT'
        elif code != 0:
            status = 'FAILED'
        elif counts.get('skipped'):
            status = 'PASSED_WITH_SKIPS' if counts.get('passed') else 'SKIPPED'
        else:
            status = 'PASSED'
        row.update(counts=dict(counts), problems=problems, status=status)
        if not xml.exists():
            row['junit'] = None
        records.append(row)
        index.write_text(json.dumps(records, indent=2) + '\n')
        print(f"{len(records)}/{len(files)} {path.name}: {row['status']} {dict(counts)}", flush=True)
    manifest = json.loads((ROOT / 'docs/audits/2026-10-18-recheck/feature_manifest.json').read_text())
    features = []
    for feature in manifest:
        matched = [r for r in records if any(fnmatch.fnmatch(r['module'], pattern) for pattern in feature['tests'])]
        counts = Counter()
        for row in matched:
            counts.update(row['counts'])
        features.append({**feature, 'counts': dict(counts), 'module_status': {r['module']: r['status'] for r in matched},
                         'scientifically_validated': False,
                         'note': 'Shared-module counts overlap; do not add feature rows. Original scientific gaps remain open.'})
    summary = {'attempted_modules': len(records),
               'modules_with_complete_junit': sum(bool(r['counts']) and not r['deadline_exceeded'] for r in records), 'planned_modules': len(files),
               'all_modules_attempted': len(records) == len(files), 'features': features,
               'passed_modules': sum(r['status'] == 'PASSED' for r in records),
               'skipped_tests': sum(r['counts'].get('skipped', 0) for r in records),
               'failed_or_timed_out_modules': [r['module'] for r in records if r['status'] in {'FAILED', 'TIMED_OUT'}]}
    (out / 'feature-status.json').write_text(json.dumps(summary, indent=2) + '\n')
    return 0 if summary['all_modules_attempted'] and not summary['failed_or_timed_out_modules'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
