import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('capability_loop', ROOT / 'scripts/verify_capability_loop.py')
loop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loop)


def test_all_original_tools_remain_in_completion_gate():
    catalog = json.loads(loop.CATALOG.read_text())
    original = [row for row in catalog['requirements'] if row['kind'] == 'original_tool']
    assert [row['id'] for row in original] == [f'tool-{i:02}' for i in range(1,26)]
    assert all(row['required_capabilities'] for row in original)
    verified = {key:{'state':'PASSED'} for key in loop.CHECKS}
    report = loop.coverage(catalog, verified)
    assert not report['scope_complete'] and not report['main_release_allowed']
    assert report['unverified_capabilities'] > 0
    assert all(not row['complete'] for row in report['requirements'] if row['kind']=='original_tool')


def test_skipped_or_failed_native_evidence_cannot_mark_capability_complete():
    catalog = {'requirements':[{'id':'blast','name':'Custom DB','kind':'tool',
                'required_capabilities':['diamond'],'acceptance_checks':{'diamond':'diamond'}}]}
    for state in ('UNVERIFIED','FAILED','BLOCKED'):
        assert not loop.coverage(catalog, {'diamond':{'state':state}})['main_release_allowed']
    assert loop.coverage(catalog, {'diamond':{'state':'PASSED'}})['main_release_allowed']
