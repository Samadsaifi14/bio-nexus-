"""
Shared fixtures for Bio Nexus backend smoke tests.

Mocks heavy/unavailable dependencies (supabase, litellm, Bio, sentry, etc.)
at sys.modules level so routers can import cleanly in a local test env.
"""

import base64
import json
import os
import sys
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure the backend app package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Mock out heavy dependencies that aren't installed in the test env
# ---------------------------------------------------------------------------
_MOCK_MODULES = [
    "supabase",
    "supabase._sync.client",
    "litellm",
    "Bio",
    "Bio.SeqIO",
    "Bio.Seq",
    "Bio.Blast",
    "Bio.Blast.Applications",
    "reportlab",
    "reportlab.lib",
    "reportlab.lib.pagesizes",
    "reportlab.pdfgen",
    "reportlab.pdfgen.canvas",
    "sentry_sdk",
    "aiohttp",
    "redis",
]

for mod_name in _MOCK_MODULES:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# ---------------------------------------------------------------------------
# Minimal JWT helper
# ---------------------------------------------------------------------------
def _make_test_jwt(user_id: str = "test-user-000") -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"sub": user_id}).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.sig"


TEST_JWT = _make_test_jwt()


# ---------------------------------------------------------------------------
# Lightweight test app — only imports the routers we actually test
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def client():
    """Build a minimal FastAPI app with only the 4 routers under test."""
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
# Detect rdkit availability (only on HF Spaces Docker, not local dev)
# ---------------------------------------------------------------------------
try:
    from rdkit import Chem
    HAS_RDKIT = True
except ImportError:
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
