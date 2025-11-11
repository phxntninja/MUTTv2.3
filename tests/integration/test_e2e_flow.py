#!/usr/bin/env python3
"""
End-to-end smoke test for docker-compose harness.

This test requires the docker-compose.test.yml environment to be running.
It is skipped unless E2E_COMPOSE=true is set in the environment.
"""

import os
import time
import json
import pytest
import requests


E2E_ENABLED = os.getenv('E2E_COMPOSE', 'false').lower() == 'true'


@pytest.mark.integration
def test_ingest_to_mock_moog_smoke():
    if not E2E_ENABLED:
        pytest.skip('E2E_COMPOSE not enabled')

    ingestor = os.getenv('E2E_INGESTOR_URL', 'http://localhost:8080/api/v2/ingest')
    api_key = os.getenv('E2E_API_KEY', 'test-ingest')
    mock_moog_stats = os.getenv('E2E_MOCK_MOOG_STATS', 'http://localhost:18083/stats')

    # Baseline stats
    before = requests.get(mock_moog_stats, timeout=5).json()
    start_count = before.get('count', 0)

    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "message": "E2E test message",
        "hostname": "e2e-host",
        "syslog_severity": 3
    }

    r = requests.post(ingestor, json=payload, headers={"X-API-KEY": api_key}, timeout=5)
    assert r.status_code in (200, 202), r.text

    # Poll mock-moog stats for up to 30s to see count increment
    deadline = time.time() + 30
    while time.time() < deadline:
        current = requests.get(mock_moog_stats, timeout=5).json()
        if current.get('count', 0) > start_count:
            break
        time.sleep(1)
    else:
        pytest.fail("mock-moog did not receive an event within 30s")

