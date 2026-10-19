"""Durable per-phase test events and strict skip handling for the audit runner."""
from __future__ import annotations
import json
from pathlib import Path
import time
import pytest


def pytest_addoption(parser):
    group = parser.getgroup('complete-audit')
    group.addoption('--audit-events')
    group.addoption('--audit-manifest')
    group.addoption('--forbid-skips', action='store_true')


def _event(config, **payload):
    filename = config.getoption('--audit-events')
    if filename:
        with Path(filename).open('a', encoding='utf-8') as handle:
            handle.write(json.dumps({'time': time.time(), **payload}) + '\n')
            handle.flush()


def pytest_collection_finish(session):
    filename = session.config.getoption('--audit-manifest')
    if filename:
        Path(filename).write_text(json.dumps([item.nodeid for item in session.items], indent=2) + '\n')


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):
    result = yield
    report = result.get_result()
    if report.skipped and collector.config.getoption('--forbid-skips'):
        report.outcome = 'failed'
        report.longrepr = 'Audit forbids collection skips: ' + str(report.longrepr)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    result = yield
    report = result.get_result()
    if report.skipped and item.config.getoption('--forbid-skips'):
        report.outcome = 'failed'
        report.longrepr = 'Audit forbids skipped tests: ' + str(report.longrepr)
    _event(item.config, nodeid=item.nodeid, phase=report.when,
           outcome=report.outcome, duration=report.duration,
           reason=str(report.longrepr)[:8000] if report.failed or report.skipped else '')
