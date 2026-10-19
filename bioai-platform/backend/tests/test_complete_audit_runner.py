"""Process-level checks: a crash or deadline cannot erase collected case results."""
import importlib.util
import os
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('complete_runner', ROOT / 'scripts/run_feature_audit.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_journal_keeps_pass_and_reports_skip_as_failure(tmp_path, monkeypatch):
    test = tmp_path / 'test_phase_contract.py'
    test.write_text('import pytest\ndef test_pass(): assert 2+2 == 4\ndef test_skip(): pytest.skip("runtime absent")\n')
    monkeypatch.setattr(runner, 'BACKEND', tmp_path)
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'scripts'))
    process = runner.execute(str(test), tmp_path / 'attempt', env, 20, 10)
    cases = runner.terminal_cases(tmp_path / 'attempt')
    assert process['exit_code'] == 1
    assert len(cases) == 2
    assert sorted(row['status'] for row in cases.values()) == ['failed', 'passed']
    assert 'Audit forbids skipped tests' in next(row['reason'] for row in cases.values() if row['status'] == 'failed')
    assert not list(ET.parse(tmp_path / 'attempt/pytest.xml').iter('skipped'))


def test_completed_phase_survives_abrupt_process_exit(tmp_path, monkeypatch):
    test = tmp_path / 'test_crash_contract.py'
    test.write_text('import os\ndef test_pass(): assert True\ndef test_crash(): os._exit(7)\n')
    monkeypatch.setattr(runner, 'BACKEND', tmp_path)
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'scripts'))
    process = runner.execute(str(test), tmp_path / 'attempt', env, 20, 10)
    cases = runner.terminal_cases(tmp_path / 'attempt')
    assert process['exit_code'] == 7
    assert len(cases) == 1
    assert next(iter(cases.values()))['status'] == 'passed'
    assert not any('test_crash' == key.split('::')[-1] for key in cases)


def test_deadline_retains_earlier_terminal_case(tmp_path, monkeypatch):
    test = tmp_path / 'test_deadline_contract.py'
    test.write_text('import time\ndef test_pass(): assert True\ndef test_slow(): time.sleep(60)\n')
    monkeypatch.setattr(runner, 'BACKEND', tmp_path)
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'scripts'))
    process = runner.execute(str(test), tmp_path / 'attempt', env, 2, 60)
    cases = runner.terminal_cases(tmp_path / 'attempt')
    assert process['deadline_exceeded'] is True
    assert len(cases) == 1
    assert next(iter(cases.values()))['status'] == 'passed'
