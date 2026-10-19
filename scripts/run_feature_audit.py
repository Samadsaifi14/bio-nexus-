#!/usr/bin/env python3
"""Execute every collected case; no skip or unfinished case can pass this audit.

Module processes retain flushed phase journals. After a module deadline/crash,
only cases without a terminal teardown report run again, one per process. A
case-level timeout/crash is an explicit failed execution record, never a pass.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import fnmatch
import hashlib
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
PLUGIN = Path(__file__).resolve().parent


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.new')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def execute(target, directory, env, seconds, test_seconds):
    directory.mkdir(parents=True, exist_ok=True)
    events = directory / 'events.jsonl'
    # Every attempt has its own path; an old journal must never satisfy a rerun.
    if events.exists():
        raise ValueError(f'Attempt directory already contains evidence: {directory}')
    command = [sys.executable, '-m', 'pytest', target, '-q', '-p', 'audit_pytest_plugin',
               '--forbid-skips', '--audit-events=' + str(events),
               '--timeout=' + str(test_seconds), '--timeout-method=signal',
               '--junitxml=' + str(directory / 'pytest.xml')]
    started = time.monotonic()
    with (directory / 'process.log').open('w') as log:
        process = subprocess.Popen(command, cwd=BACKEND, env=env, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        deadline = False
        try:
            code = process.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            deadline = True
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                code = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                code = process.wait()
    result = {'target': target, 'exit_code': code, 'deadline_exceeded': deadline,
              'elapsed_seconds': round(time.monotonic() - started, 3),
              'deadline_seconds': seconds, 'command': command,
              'started_at': datetime.now(timezone.utc).isoformat()}
    write_json(directory / 'process.json', result)
    return result


def terminal_cases(directory):
    by_case = {}
    path = directory / 'events.jsonl'
    if not path.exists():
        return {}
    for line in path.read_text().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            # A killed writer's partial final line is incomplete evidence.
            continue
        by_case.setdefault(event['nodeid'], {})[event['phase']] = event
    terminal = {}
    for nodeid, phases in by_case.items():
        if 'teardown' not in phases:
            continue
        problems = [event for event in phases.values() if event['outcome'] != 'passed']
        passed = not problems and phases.get('call', {}).get('outcome') == 'passed'
        terminal[nodeid] = {
            'nodeid': nodeid, 'status': 'passed' if passed else 'failed',
            'duration': sum(event['duration'] for event in phases.values()),
            'reason': '\n'.join(event['reason'] for event in problems) or ('' if passed else 'No completed test call'),
            'evidence': str(directory), 'execution_complete': True,
        }
    return terminal


def write_junit(path, planned, results):
    suite = ET.Element('testsuite', name='complete-feature-audit', tests=str(len(planned)))
    for nodeid in planned:
        row = results[nodeid]
        case = ET.SubElement(suite, 'testcase', classname=nodeid.split('::')[0],
                             name='::'.join(nodeid.split('::')[1:]), time=str(row.get('duration', 0)))
        if row['status'] != 'passed':
            failure = ET.SubElement(case, 'failure', message=row['reason'][:500])
            failure.text = row['reason']
    suite.set('failures', str(sum(row['status'] != 'passed' for row in results.values())))
    suite.set('skipped', '0')
    ET.ElementTree(suite).write(path, encoding='utf-8', xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outdir', type=Path, required=True)
    parser.add_argument('--module-seconds', type=int, default=180)
    parser.add_argument('--case-seconds', type=int, default=120)
    parser.add_argument('--test-root', nargs='+', default=['tests'])
    args = parser.parse_args()
    if min(args.module_seconds, args.case_seconds) < 1:
        parser.error('deadlines must be positive')
    out = args.outdir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'manifest.json').exists():
        parser.error('Use a fresh output directory; previous evidence is immutable')
    env = dict(os.environ, OPENMM_CPU_THREADS='1', OMP_NUM_THREADS='1', PYTHONHASHSEED='0',
               SUPABASE_URL='https://example.supabase.co', SUPABASE_ANON_KEY='test-placeholder',
               SUPABASE_SERVICE_ROLE_KEY='test-placeholder', JWT_SECRET='test-placeholder')
    env['PYTHONPATH'] = str(PLUGIN) + os.pathsep + env.get('PYTHONPATH', '')
    manifest = out / 'manifest.json'
    collect = [sys.executable, '-m', 'pytest', *args.test_root, '--collect-only', '-q',
               '-p', 'audit_pytest_plugin', '--forbid-skips', '--audit-manifest=' + str(manifest)]
    with (out / 'collection.log').open('w') as log:
        collected = subprocess.run(collect, cwd=BACKEND, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    if collected.returncode or not manifest.exists():
        write_json(out / 'summary.json', {'status': 'COLLECTION_FAILED', 'exit_code': collected.returncode,
                                         'complete': False, 'passed': False})
        return 1
    planned = json.loads(manifest.read_text())
    if not planned:
        raise ValueError('Empty collection cannot pass the audit')
    results, attempts = {}, []
    modules = sorted({nodeid.split('::')[0] for nodeid in planned},
                     key=lambda name: (name.endswith('test_blast_comprehensive.py'), name))
    for module in modules:
        directory = out / 'modules' / Path(module).stem
        process = execute(module, directory, env, args.module_seconds, args.case_seconds)
        attempts.append(process)
        results.update(terminal_cases(directory))
        write_json(out / 'cases.json', results)
        print(f'{module}: {len(results)}/{len(planned)} terminal results', flush=True)
    for nodeid in planned:
        if nodeid in results:
            continue
        directory = out / 'recovery' / hashlib.sha256(nodeid.encode()).hexdigest()[:20]
        process = execute(nodeid, directory, env, args.case_seconds + 15, args.case_seconds)
        attempts.append(process)
        recovered = terminal_cases(directory)
        if nodeid in recovered:
            results[nodeid] = recovered[nodeid]
        else:
            results[nodeid] = {
                'nodeid': nodeid, 'status': 'error', 'duration': process['elapsed_seconds'],
                'reason': ('Isolated case exceeded its execution deadline' if process['deadline_exceeded']
                           else f"Isolated case exited {process['exit_code']} without terminal teardown evidence"),
                'evidence': str(directory), 'execution_complete': False,
            }
        write_json(out / 'cases.json', results)
        print(f'Recovered {len(results)}/{len(planned)}: {nodeid} -> {results[nodeid]["status"]}', flush=True)
    counts = Counter(row['status'] for row in results.values())
    summary = {'planned_cases': len(planned), 'recorded_cases': len(results),
               'missing_cases': sorted(set(planned) - set(results)), 'counts': dict(counts),
               'skipped': 0, 'execution_errors': sum(not row['execution_complete'] for row in results.values()),
               'complete': set(results) == set(planned),
               'passed': len(results) == len(planned) and counts.get('passed', 0) == len(planned),
               'scientifically_validated': False}
    write_json(out / 'execution.json', attempts)
    write_json(out / 'summary.json', summary)
    write_junit(out / 'complete.xml', planned, results)
    features = json.loads((ROOT / 'docs/audits/2026-10-18-recheck/feature_manifest.json').read_text())
    for feature in features:
        matching = [row for nodeid, row in results.items()
                    if any(fnmatch.fnmatch(Path(nodeid.split('::')[0]).name, pattern) for pattern in feature['tests'])]
        feature['case_counts'] = dict(Counter(row['status'] for row in matching))
        feature['scientifically_validated'] = False
    write_json(out / 'feature-status.json', features)
    print(json.dumps(summary), flush=True)
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
