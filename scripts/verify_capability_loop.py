#!/usr/bin/env python3
"""Run acceptance checks and revisit the entire original roadmap after each one.

This is a verification/controller loop, not an AI code generator. Implementation
work is performed by the coding agent; publishing never happens in this script.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / 'bioai-platform/backend'
CATALOG = REPO / 'docs/paper-backed-capabilities/requirements.json'
TEST = 'tests/test_paper_backed_engines.py'
CHECKS = {
 'nextflow':[f'{TEST}::test_trace_keeps_cached_failed_and_unfinished_evidence_distinct',f'{TEST}::test_invalid_trace_never_becomes_success',f'{TEST}::test_trace_path_cannot_escape_owned_output'],
 'counts':[f'{TEST}::test_counts_are_not_satisfied_by_tpm_or_scaled_estimates'],
 'diamond':[f'{TEST}::test_invalid_custom_reference_is_rejected',f'{TEST}::test_diamond_parser_preserves_small_evalues_and_rejects_bad_coordinates',f'{TEST}::test_missing_diamond_is_an_engine_failure',f'{TEST}::test_native_diamond_exact_reference_and_true_no_hit'],
 'pairwise':[f'{TEST}::test_shuffle_test_ties_give_one_and_pvalues_cannot_be_zero',f'{TEST}::test_shuffle_test_limits_fail_before_expensive_work'],
 'ppi_scale':[f'{TEST}::test_string_json_scores_preserve_provider_scale'],
 'rocrate':[f'{TEST}::test_rocrate_preserves_unknown_steps_and_payload_hash',f'{TEST}::test_rocrate_foreign_owner_is_denied_before_provenance_access'],
}


def source_fingerprint():
    digest=hashlib.sha256()
    roots=[BACKEND/'app',BACKEND/'tests',REPO/'bioai-platform/frontend/src',REPO/'scripts']
    files={CATALOG,BACKEND/'requirements.txt',REPO/'bioai-platform/frontend/package.json'}
    for root in roots:
        files.update(path for path in root.rglob('*') if path.is_file() and path.suffix in {'.py','.R','.ts','.tsx','.json'})
    for path in sorted(files):
        digest.update(str(path.relative_to(REPO)).encode())
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):
                digest.update(chunk)
    return digest.hexdigest()


def coverage(catalog, results):
    requirements = []
    for item in catalog['requirements']:
        capabilities = []
        for target in item['required_capabilities']:
            check = item['acceptance_checks'].get(target)
            state = results.get(check, {}).get('state', 'UNVERIFIED') if check else 'UNVERIFIED'
            capabilities.append({'id':target,'check':check,'state':state})
        requirements.append({'id':item['id'],'name':item['name'],'kind':item['kind'],
          'complete':bool(capabilities) and all(c['state']=='PASSED' for c in capabilities),'capabilities':capabilities})
    complete = bool(requirements) and all(item['complete'] for item in requirements)
    return {'requirements':requirements,'scope_complete':complete,'main_release_allowed':complete,
      'unverified_capabilities':sum(c['state']!='PASSED' for item in requirements for c in item['capabilities'])}


def execute_check(identifier, output, environment):
    xml_path = output / f'{identifier}.xml'
    command = [sys.executable,'-m','pytest',*CHECKS[identifier],'-q',f'--junitxml={xml_path}',f'--basetemp={output / (identifier + "-tmp")}']
    result = subprocess.run(command,cwd=BACKEND,env=environment,capture_output=True,text=True,timeout=180)
    (output / f'{identifier}.log').write_text(result.stdout + result.stderr)
    if not xml_path.is_file():
        return {'state':'FAILED','returncode':result.returncode,'reason':'No machine-readable test evidence'}
    root = ET.parse(xml_path).getroot()
    suites = [root] if root.tag=='testsuite' else list(root.iter('testsuite'))
    totals = {key:sum(int(s.get(key,'0')) for s in suites) for key in ('tests','failures','errors','skipped')}
    state = 'FAILED' if result.returncode or totals['errors'] or totals['failures'] or not totals['tests'] else 'BLOCKED' if totals['skipped'] else 'PASSED'
    return {'state':state,'returncode':result.returncode,**totals,'test_report':xml_path.name}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True,help='Run-local directory outside the repository')
    args=parser.parse_args()
    output=args.output.resolve()
    if output.is_relative_to(REPO):
        parser.error('Use an output directory outside the repository so generated reports do not alter source evidence')
    output.mkdir(parents=True,exist_ok=True)
    catalog=json.loads(CATALOG.read_text())
    results={}; iterations=[]
    environment=dict(os.environ)
    for key in ('ALL_PROXY','all_proxy','HTTP_PROXY','HTTPS_PROXY'):
        environment.pop(key,None)  # Offline checks never access public services.
    for identifier in CHECKS:
        before=source_fingerprint()
        results[identifier]=execute_check(identifier,output,environment)
        after=source_fingerprint()
        results[identifier]['source_sha256']=after
        if before!=after:
            results[identifier]['state']='STALE'
            results[identifier]['reason']='Source changed during verification'
        for prior in results.values():
            if prior.get('source_sha256')!=after:
                prior['state']='STALE'
        catalog=json.loads(CATALOG.read_text())
        # Recompare the complete original list after EVERY completed check.
        current=coverage(catalog,results)
        iterations.append({'check':identifier,'state':results[identifier]['state'],
                           'remaining':current['unverified_capabilities']})
        body={'verified_at':datetime.now(timezone.utc).isoformat(),
          'catalog_sha256':hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
          'checks':results,'iterations':iterations,**current}
        temporary=output/'capability-loop.tmp'
        temporary.write_text(json.dumps(body,indent=2)+'\n'); temporary.replace(output/'capability-loop.json')
        print(f"{identifier}: {results[identifier]['state']}; {current['unverified_capabilities']} original/extension capabilities remain unverified",flush=True)
        if results[identifier]['state'] in {'FAILED','STALE'}:
            return 1
    return 0 if current['scope_complete'] else 2

if __name__=='__main__':
    raise SystemExit(main())
