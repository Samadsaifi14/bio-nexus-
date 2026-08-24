"""Auth verification tests — forged JWTs must never yield a user_id."""

import asyncio
import time

import jwt as pyjwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.services import auth

SECRET = "unit-test-secret-0123456789abcdef-0123456789"
SUB = "11111111-2222-3333-4444-555555555555"


def _make_token(sub=SUB, secret=SECRET, expires_delta=3600, headers=None):
    payload = {
        "sub": sub,
        "role": "authenticated",
        "exp": int(time.time()) + expires_delta,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256", headers=headers or {})


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    auth._verified_cache.clear()
    yield
    auth._verified_cache.clear()


class TestLocalVerification:
    def test_valid_signed_token_returns_sub(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
        assert auth._verify_locally(_make_token()) == SUB

    def test_forged_signature_rejected(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
        forged = _make_token(secret="attacker-key-0123456789abcdef-0123456789")
        assert auth._verify_locally(forged) is None

    def test_expired_token_rejected(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
        expired = _make_token(expires_delta=-10)
        assert auth._verify_locally(expired) is None

    def test_missing_claims_rejected(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
        token = pyjwt.encode({"role": "authenticated"}, SECRET, algorithm="HS256")
        assert auth._verify_locally(token) is None


class TestGetUserId:
    def test_anonymous_when_no_credentials(self):
        assert asyncio.run(auth.get_user_id(None)) is None

    @pytest.mark.parametrize("bad", ["", "not-a-jwt", "a.b", "...."])
    def test_malformed_tokens_rejected_without_network(self, bad):
        # No SUPABASE_JWT_SECRET set -> would hit network path if it got there;
        # malformed shapes must short-circuit to None.
        assert asyncio.run(auth.get_user_id(_creds(bad))) is None

    def test_forged_token_rejected_with_secret_configured(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
        forged = f"{_make_token().split('.')[0]}.{_make_token().split('.')[1]}.garbage"
        assert asyncio.run(auth.get_user_id(_creds(forged))) is None

    def test_delegates_to_supabase_path_without_secret(self, monkeypatch):
        seen = {}

        async def fake_verify(token: str):
            seen["token"] = token
            return SUB

        monkeypatch.setattr(auth, "_verify_via_supabase", fake_verify)
        result = asyncio.run(auth.get_user_id(_creds("aaa.bbb.ccc")))
        assert result == SUB
        assert seen["token"] == "aaa.bbb.ccc"


class TestRequireUserId:
    def test_raises_401_on_unverifiable_token(self, monkeypatch):
        async def fake_verify(token: str):
            return None

        monkeypatch.setattr(auth, "_verify_via_supabase", fake_verify)
        with pytest.raises(HTTPException) as exc:
            asyncio.run(auth.require_user_id(_creds("x.y.z")))
        assert exc.value.status_code == 401

    def test_passes_through_verified_sub(self, monkeypatch):
        async def fake_verify(token: str):
            return SUB

        monkeypatch.setattr(auth, "_verify_via_supabase", fake_verify)
        assert asyncio.run(auth.require_user_id(_creds("x.y.z"))) == SUB
