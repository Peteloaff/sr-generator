"""Per-IP daily generation rate limit (stopgap before accounts/login)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from sr.config import get_settings
from sr.services import ratelimit


class _FakeClient:
    host = "1.2.3.4"


class _FakeRequest:
    def __init__(self, ip: str = "1.2.3.4", forwarded: str | None = None):
        self.client = _FakeClient()
        self.client.host = ip
        self.headers = {"x-forwarded-for": forwarded} if forwarded else {}


def _set_limit(monkeypatch, n: int):
    monkeypatch.setenv("SR_MAX_GENERATIONS_PER_IP_PER_DAY", str(n))
    get_settings.cache_clear()


def test_client_ip_prefers_forwarded_for():
    req = _FakeRequest(ip="10.0.0.1", forwarded="203.0.113.5, 10.0.0.1")
    assert ratelimit.client_ip(req) == "203.0.113.5"


def test_client_ip_falls_back_to_request_client():
    req = _FakeRequest(ip="203.0.113.9")
    assert ratelimit.client_ip(req) == "203.0.113.9"


def test_allows_up_to_the_limit_then_blocks(client, monkeypatch):
    _set_limit(monkeypatch, 2)
    from sr.db import SessionLocal

    db = SessionLocal()
    req = _FakeRequest(ip="9.9.9.9")
    try:
        ratelimit.enforce_daily_limit(db, req)
        ratelimit.enforce_daily_limit(db, req)
        with pytest.raises(HTTPException) as exc:
            ratelimit.enforce_daily_limit(db, req)
        assert exc.value.status_code == 429
    finally:
        db.close()
    monkeypatch.delenv("SR_MAX_GENERATIONS_PER_IP_PER_DAY", raising=False)
    get_settings.cache_clear()


def test_different_ips_are_independent(client, monkeypatch):
    _set_limit(monkeypatch, 1)
    from sr.db import SessionLocal

    db = SessionLocal()
    try:
        ratelimit.enforce_daily_limit(db, _FakeRequest(ip="1.1.1.1"))
        ratelimit.enforce_daily_limit(db, _FakeRequest(ip="2.2.2.2"))  # different IP, not blocked
        with pytest.raises(HTTPException):
            ratelimit.enforce_daily_limit(db, _FakeRequest(ip="1.1.1.1"))
    finally:
        db.close()
    monkeypatch.delenv("SR_MAX_GENERATIONS_PER_IP_PER_DAY", raising=False)
    get_settings.cache_clear()


def test_zero_disables_the_limit(client, monkeypatch):
    _set_limit(monkeypatch, 0)
    from sr.db import SessionLocal

    db = SessionLocal()
    req = _FakeRequest(ip="5.5.5.5")
    try:
        for _ in range(50):
            ratelimit.enforce_daily_limit(db, req)
    finally:
        db.close()
    monkeypatch.delenv("SR_MAX_GENERATIONS_PER_IP_PER_DAY", raising=False)
    get_settings.cache_clear()


def test_generate_full_song_endpoint_enforces_the_limit(client, monkeypatch):
    _set_limit(monkeypatch, 1)
    song = client.post("/songs", json={"title": "Rate Limit Test"}).json()

    r1 = client.post(f"/songs/{song['id']}/generate", json={})
    assert r1.status_code == 201

    r2 = client.post(f"/songs/{song['id']}/generate", json={})
    assert r2.status_code == 429

    monkeypatch.delenv("SR_MAX_GENERATIONS_PER_IP_PER_DAY", raising=False)
    get_settings.cache_clear()
