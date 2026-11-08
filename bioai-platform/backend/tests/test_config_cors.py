"""CORS configuration: the deployment's CORS_ORIGIN/CORS_ORIGINS must control
the middleware, not the local-default fallback list.

Notes
-----
``Settings`` fields are evaluated at class-definition (import) time from
``os.getenv``, so these tests reload ``app.config`` under controlled
environment variables. The original module state is saved and restored after
each test so other suites keep seeing the real deployment settings.
"""

import importlib
import os

import app.config


def _reload_settings(**env):
    saved = {}
    for key, value in env.items():
        saved[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    importlib.reload(app.config)
    return app.config.settings, saved


def _restore(saved):
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    importlib.reload(app.config)


def test_cors_origin_controls_origins_when_cors_origins_unset():
    settings, saved = _reload_settings(
        CORS_ORIGIN="https://deployed.example.com",
        CORS_ORIGINS=None,
    )
    try:
        assert settings.CORS_ORIGIN == "https://deployed.example.com"
        assert settings.CORS_ORIGINS == ("https://deployed.example.com",)
    finally:
        _restore(saved)


def test_cors_origins_explicit_wins_over_cors_origin():
    settings, saved = _reload_settings(
        CORS_ORIGIN="https://deployed.example.com",
        CORS_ORIGINS="https://a.example.com,https://b.example.com",
    )
    try:
        assert settings.CORS_ORIGINS == ("https://a.example.com", "https://b.example.com")
    finally:
        _restore(saved)


def test_ed25519_keys_default_empty():
    keys = (
        "NGS_CLINICAL_EVIDENCE_ED25519_PRIVATE_KEY",
        "NGS_CLINICAL_EVIDENCE_ED25519_PUBLIC_KEY",
    )
    settings, saved = _reload_settings(**{k: None for k in keys})
    try:
        assert settings.NGS_CLINICAL_EVIDENCE_ED25519_PRIVATE_KEY == ""
        assert settings.NGS_CLINICAL_EVIDENCE_ED25519_PUBLIC_KEY == ""
    finally:
        _restore(saved)
