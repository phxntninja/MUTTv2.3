#!/usr/bin/env python3
"""
MUTT v2.5 — Smoke Tests

These are light, environment-driven smoke tests that validate basic service health and
API responsiveness in the docker-compose test stack. They are skipped unless
E2E_COMPOSE=true is set in the environment.

Environment variables (with sensible defaults for docker-compose.test.yml):
- E2E_COMPOSE=true            # enable these tests
- E2E_INGESTOR_BASE=http://localhost:8080
- E2E_WEBUI_BASE=http://localhost:8090
- E2E_WEBUI_API_KEY=test-webui

Run locally (compose stack):
  bash scripts/run_e2e.sh
"""

import os
import time
import json
import pytest
import requests


E2E_ENABLED = os.getenv("E2E_COMPOSE", "false").lower() == "true"


def _base(name: str, default: str) -> str:
    return os.getenv(name, default).rstrip("/")


@pytest.mark.smoke
def test_health_endpoints_up():
    if not E2E_ENABLED:
        pytest.skip("E2E_COMPOSE not enabled")

    ingestor = _base("E2E_INGESTOR_BASE", "http://localhost:8080")
    webui = _base("E2E_WEBUI_BASE", "http://localhost:8090")
    forwarder_health = os.getenv("E2E_FORWARDER_HEALTH", "http://localhost:8084/health")

    for url in [f"{ingestor}/health", f"{webui}/health", forwarder_health]:
        r = requests.get(url, timeout=5)
        assert r.status_code == 200, f"health failed for {url}: {r.status_code} {r.text}"
        data = r.json()
        assert data.get("status") == "healthy"


@pytest.mark.smoke
def test_webui_metrics_secured_and_returns_json():
    if not E2E_ENABLED:
        pytest.skip("E2E_COMPOSE not enabled")

    webui = _base("E2E_WEBUI_BASE", "http://localhost:8090")
    api_key = os.getenv("E2E_WEBUI_API_KEY", "test-webui")

    # Without API key should 401
    r_noauth = requests.get(f"{webui}/api/v2/metrics", timeout=5)
    assert r_noauth.status_code in (401, 403), f"expected 401/403, got {r_noauth.status_code}"

    # With API key should 200 and JSON payload
    r = requests.get(f"{webui}/api/v2/metrics", headers={"X-API-KEY": api_key}, timeout=5)
    assert r.status_code == 200, f"metrics failed: {r.status_code} {r.text}"
    data = r.json()
    assert "summary" in data and "chart_24h" in data


@pytest.mark.smoke
def test_webui_rules_list_accessible():
    if not E2E_ENABLED:
        pytest.skip("E2E_COMPOSE not enabled")

    webui = _base("E2E_WEBUI_BASE", "http://localhost:8090")
    api_key = os.getenv("E2E_WEBUI_API_KEY", "test-webui")

    r = requests.get(f"{webui}/api/v2/rules", headers={"X-API-KEY": api_key}, timeout=5)
    assert r.status_code == 200, f"rules list failed: {r.status_code} {r.text}"
    data = r.json()
    assert "rules" in data and isinstance(data["rules"], list)


@pytest.mark.smoke
def test_config_audit_list_accessible():
    if not E2E_ENABLED:
        pytest.skip("E2E_COMPOSE not enabled")

    webui = _base("E2E_WEBUI_BASE", "http://localhost:8090")
    api_key = os.getenv("E2E_WEBUI_API_KEY", "test-webui")

    r = requests.get(
        f"{webui}/api/v2/config-audit?limit=1",
        headers={"X-API-KEY": api_key},
        timeout=5,
    )
    assert r.status_code == 200, f"config audit failed: {r.status_code} {r.text}"
    data = r.json()
    assert "changes" in data and "pagination" in data

