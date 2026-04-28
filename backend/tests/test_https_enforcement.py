"""HTTPS enforcement middleware: production redirect + HSTS header.

Tested in isolation against a small ad-hoc FastAPI app so we don't have to
re-import main.py with a mutated ENV (the import has heavy side effects).
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from middleware import HSTS_VALUE, HTTPSEnforcementMiddleware


def _build_app(enabled: bool) -> TestClient:
    app = FastAPI()
    app.add_middleware(HTTPSEnforcementMiddleware, enabled=enabled)

    @app.get("/")
    def root():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return TestClient(app)


def test_disabled_passes_traffic_unchanged():
    """Dev/test mode: middleware is a no-op — no redirect, no HSTS."""
    client = _build_app(enabled=False)
    r = client.get("/", headers={"x-forwarded-proto": "http"})
    assert r.status_code == 200
    assert "strict-transport-security" not in {k.lower() for k in r.headers}


def test_enabled_redirects_plain_http_to_https():
    """Production: HTTP request gets a 301 to the HTTPS equivalent."""
    client = _build_app(enabled=True)
    r = client.get(
        "/some/path?x=1",
        headers={"x-forwarded-proto": "http"},
        follow_redirects=False,
    )
    assert r.status_code == 301
    location = r.headers["location"]
    assert location.startswith("https://")
    assert "/some/path" in location
    assert "x=1" in location


def test_enabled_emits_hsts_on_https_response():
    """Production: HTTPS request flows through and gains HSTS header."""
    client = _build_app(enabled=True)
    r = client.get("/", headers={"x-forwarded-proto": "https"})
    assert r.status_code == 200
    assert r.headers["strict-transport-security"] == HSTS_VALUE


def test_health_path_is_not_redirected():
    """LB probes hit /health over plain HTTP; redirecting them would flip
    the load balancer status to unhealthy. Skip the redirect for that path."""
    client = _build_app(enabled=True)
    r = client.get(
        "/health",
        headers={"x-forwarded-proto": "http"},
        follow_redirects=False,
    )
    assert r.status_code == 200
    # HSTS still attaches even on the skip path so plain probes get the hint.
    assert r.headers["strict-transport-security"] == HSTS_VALUE


def test_multi_hop_xff_proto_uses_leftmost_value():
    """Behind several proxies X-Forwarded-Proto can be a comma list. The
    leftmost entry is what the original client spoke — that's what we
    redirect on."""
    client = _build_app(enabled=True)
    r = client.get(
        "/",
        headers={"x-forwarded-proto": "http, https"},
        follow_redirects=False,
    )
    assert r.status_code == 301


def test_no_xff_falls_back_to_request_scheme():
    """Without X-Forwarded-Proto the request URL scheme decides. TestClient
    speaks http://, so without the header we redirect."""
    client = _build_app(enabled=True)
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"].startswith("https://")


# ---------------------------------------------------------------------------
# Startup assertions: ENV=production must reject http:// config.
# ---------------------------------------------------------------------------


import importlib  # noqa: E402
import sys  # noqa: E402

import pytest  # noqa: E402


def _reload_main(monkeypatch, env):
    """Re-import main.py with a fresh env. Drops all cached modules that
    capture IS_PRODUCTION at import time so the new env actually takes."""
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    for mod in ("main", "auth", "auth_routes", "billing_routes", "middleware"):
        sys.modules.pop(mod, None)
    return importlib.import_module("main")


def test_production_rejects_http_app_url(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "x" * 80)
    with pytest.raises(RuntimeError, match="APP_URL must use https"):
        _reload_main(
            monkeypatch,
            {
                "ENV": "production",
                "ALLOWED_ORIGINS": "https://app.example.com",
                "APP_URL": "http://app.example.com",
            },
        )


def test_production_rejects_http_origin(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "x" * 80)
    with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS must use https"):
        _reload_main(
            monkeypatch,
            {
                "ENV": "production",
                "ALLOWED_ORIGINS": "http://app.example.com,https://other.example.com",
                "APP_URL": "https://app.example.com",
            },
        )
