"""Run every backend test module with an OS deadline and retained JUnit evidence.

Module isolation is an audit diagnostic, not a replacement for the monolithic CI gate.
An unfinished module is explicitly blocked and is never counted as passed.
"""
from pathlib import Path
import datetime
import json
import os
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / 'bioai-platform/backend'
RETRY = '--retry' in sys.argv
OUT = Path(__file__).resolve().parent / ('backend-retry' if RETRY else 'backend')
OUT.mkdir(exist_ok=True)
(OUT / "work").mkdir(exist_ok=True)
env = dict(os.environ, SUPABASE_URL='https://example.supabase.co',
           SUPABASE_ANON_KEY='test-placeholder', SUPABASE_SERVICE_ROLE_KEY='test-placeholder',
           JWT_SECRET='test-placeholder', PYTHONHASHSEED='0', BIONEXUS_AUDIT_SEED='20260916')
records = []
files = sorted((BACKEND / 'tests').glob('test_*.py'))
if RETRY:
    prior = json.loads((OUT.parent / 'backend/execution.json').read_text())
    failed = {row['module'] for row in prior if row['exit_code'] != 0}
    files = [path for path in files if path.name in failed]
# Keep the provider-availability module last, matching the existing CI order.
files.sort(key=lambda p: (p.name == 'test_blast_comprehensive.py', p.name))
for path in files:
    budget = 900 if path.name == 'test_blast_comprehensive.py' else 300 if path.name == 'test_feature_validation.py' else 120
    log = OUT / (path.stem + '.log')
    xml = OUT / (path.stem + '.xml')
    command = [sys.executable, '-m', 'pytest', str(path.relative_to(BACKEND)),
               '-vv', '--disable-warnings', '--timeout=90', '--timeout-method=signal',
               '--junitxml=' + str(xml), '--basetemp=' + str(OUT / 'work' / path.stem)]
    started = time.monotonic()
    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with log.open('w') as handle:
        process = subprocess.Popen(command, cwd=BACKEND, env=env,
                                   stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
        blocked = False
        try:
            code = process.wait(timeout=budget)
        except subprocess.TimeoutExpired:
            blocked = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                code = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                code = process.wait()
    entry = dict(module=path.name, started_at=stamp, elapsed_seconds=round(time.monotonic()-started, 2),
                 exit_code=code, deadline_seconds=budget, deadline_exceeded=blocked,
                 junit=xml.name if xml.exists() else None, log=log.name,
                 command=command)
    records.append(entry)
    (OUT / 'execution.json').write_text(json.dumps(records, indent=2) + '\n')
    print(json.dumps({k:entry[k] for k in ('module','exit_code','elapsed_seconds','deadline_exceeded')}), flush=True)
print('Completed module attempts:', len(records), 'of', len(files), flush=True)
