"""Regression coverage for backend worker startup.

BLAST/pipeline jobs are persisted as ``queued`` and depend on the durable
worker to claim them. FastAPI applications configured with an explicit
lifespan must initialize those services from that lifespan rather than from a
legacy startup-event hook.
"""

from __future__ import annotations

import ast
from pathlib import Path


MAIN_PATH = Path(__file__).resolve().parents[1] / "app" / "main.py"


def _async_function(tree: ast.AST, name: str) -> ast.AsyncFunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name:
            return node
    raise AssertionError(f"async function {name!r} not found in app/main.py")


def _uses_legacy_startup_event(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            if not (isinstance(func, ast.Attribute) and func.attr == "on_event"):
                continue
            if decorator.args and isinstance(decorator.args[0], ast.Constant):
                if decorator.args[0].value == "startup":
                    return True
    return False


def test_lifespan_explicitly_initializes_backend_services():
    source = MAIN_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lifespan = _async_function(tree, "lifespan")

    awaited_calls = {
        node.value.func.id
        for node in ast.walk(lifespan)
        if isinstance(node, ast.Await)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
    }

    assert "_startup_services" in awaited_calls, (
        "FastAPI lifespan must await _startup_services(); otherwise the durable "
        "worker may never start and queued BLAST jobs can remain stuck forever."
    )


def test_worker_startup_does_not_depend_on_legacy_startup_event():
    source = MAIN_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert not _uses_legacy_startup_event(tree)

    startup = _async_function(tree, "_startup_services")
    start_worker_calls = [
        node
        for node in ast.walk(startup)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "start_worker"
    ]
    assert start_worker_calls, "_startup_services must retain durable worker startup"
