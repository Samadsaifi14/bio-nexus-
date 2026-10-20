"""
Shared fixtures for Bio Nexus backend smoke tests.

Mocks heavy/unavailable dependencies (supabase, litellm, Bio, sentry, etc.)
at sys.modules level so routers can import cleanly in a local test env.
"""

import time
import base64
import hashlib
import hmac
import json
import os
import sys
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure the backend app package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Backend pytest runs enforce the same no-skip contract as the full audit.
# Register here so ordinary pytest invocations do not need a special wrapper.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../scripts")))
pytest_plugins = ("audit_pytest_plugin",)

# ---------------------------------------------------------------------------
# Mock out heavy dependencies that aren't installed in the test env
# ---------------------------------------------------------------------------
_MOCK_MODULES = [
    "supabase",
    "supabase._sync.client",
    "litellm",
    "reportlab",
    "reportlab.lib",
    "reportlab.lib.pagesizes",
    "reportlab.lib.styles",
    "reportlab.lib.units",
    "reportlab.lib.colors",
    "reportlab.pdfgen",
    "reportlab.pdfgen.canvas",
    "reportlab.platypus",
    "sentry_sdk",
    "redis",
]

for mod_name in _MOCK_MODULES:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# ---------------------------------------------------------------------------
# Minimal JWT helper
# ---------------------------------------------------------------------------
_SMOKE_JWT_SECRET = "bionexus-smoke-test-only-signing-key-never-use-in-production"


def _make_test_jwt(user_id: str = "test-user-000") -> str:
    # Sign with the standard library so light CI jobs need no JWT package
    # merely to collect unrelated tests. The application still verifies HS256.
    def encode(value):
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    header = encode({"alg": "HS256", "typ": "JWT"})
    payload = encode({"sub": user_id, "exp": int(time.time()) + 3600})
    message = f"{header}.{payload}"
    signature = hmac.new(_SMOKE_JWT_SECRET.encode(), message.encode(), hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"{message}.{encoded_signature}"



TEST_JWT = _make_test_jwt()


# ---------------------------------------------------------------------------
# Lightweight test app — only imports the routers we actually test
# ---------------------------------------------------------------------------
@pytest.fixture()
def client(monkeypatch):
    """Build a minimal FastAPI app with only the 4 routers under test."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", _SMOKE_JWT_SECRET)
    app = FastAPI(title="Bio Nexus Smoke Tests")

    from app.routers import admet, md, function_predict, docking
    app.include_router(admet.router)
    app.include_router(md.router)
    app.include_router(function_predict.router)
    app.include_router(docking.router)

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def auth_headers():
    """Headers dict with a valid Bearer token."""
    return {"Authorization": f"Bearer {TEST_JWT}"}


# ---------------------------------------------------------------------------
# Pre-load OpenMM native libs BEFORE rdkit. OpenMM and RDKit wheels bundle
# conflicting copies of MSVC runtime DLLs (msvcp140/concrt140); importing
# rdkit first makes OpenMM's Context creation crash with an access violation.
# Loading openmm.app first resolves the conflict.
# ---------------------------------------------------------------------------
try:
    import openmm.app  # noqa: F401
except Exception:
    pass

# ---------------------------------------------------------------------------
# Detect rdkit availability (only on HF Spaces Docker, not local dev)
# find_spec avoids actually importing rdkit, which would trigger the
# OpenMM/RDKit runtime conflict above for real-OpenMM tests.
# ---------------------------------------------------------------------------
try:
    import importlib.util
    HAS_RDKIT = importlib.util.find_spec("rdkit.Chem") is not None
except (ImportError, ValueError):
    HAS_RDKIT = False

requires_rdkit = pytest.mark.skipif(not HAS_RDKIT, reason="rdkit not installed locally — run on HF Spaces")

# ---------------------------------------------------------------------------
# Sample molecules
# ---------------------------------------------------------------------------
SAMPLE_MOLECULES = {
    "aspirin": "CC(=O)OC1=CC=CC=C1C(=O)O",
    "caffeine": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
    "ibuprofen": "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
    "paracetamol": "CC(=O)NC1=CC=C(C=C1)O",
    "metformin": "CN(C)C(=N)NC(=O)N",
    "paclitaxel": "CC(=O)OC1C(O)CC2OC3C(O)C(=CC(=O)O3)CC(O)C12C4=CC=CC=C4C(=O)OC5C(O)C(COC(=O)C)OC(O)C5NC(=O)C6=CC=CC=C6",
    "short_pseudo": "C",
}


@pytest.fixture(params=list(SAMPLE_MOLECULES.keys()), ids=list(SAMPLE_MOLECULES.keys()))
def sample_smiles(request):
    name = request.param
    return name, SAMPLE_MOLECULES[name]


@pytest.fixture
def valid_smiles():
    return "CC(=O)OC1=CC=CC=C1C(=O)O"


@pytest.fixture
def invalid_smiles():
    return "NOT_A_SMILES_12345"


@pytest.fixture
def public_upstream_dns(monkeypatch):
    """Public DNS for explicitly opted-in HTTP-mocked tests; SSRF stays active."""
    import socket
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))])
