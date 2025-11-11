#!/usr/bin/env python3
"""
MUTT v2.5 - v1/v2 API Parity Tests (Web UI)

Verifies that v2 aliases return identical payloads as v1 for key endpoints.
These tests monkeypatch DB/Redis to avoid external dependencies.
"""

import pytest


@pytest.fixture(scope="class")
def app(monkeyclass):
    from services import web_ui_service as w

    # Disable DynamicConfig to avoid Redis requirement
    monkeyclass.setattr(w, 'DynamicConfig', None)

    # Bypass Vault/Redis/Postgres initialization
    def fake_fetch_secrets(app):
        app.config['SECRETS'] = {"WEBUI_API_KEY": "test-api-key-123"}
    monkeyclass.setattr(w, 'fetch_secrets', fake_fetch_secrets)
    monkeyclass.setattr(w, 'create_redis_pool', lambda app: None)
    monkeyclass.setattr(w, 'create_postgres_pool', lambda app: app.config.__setitem__('DB_POOL', None))

    # Build app
    app = w.create_app()
    return app

@pytest.mark.usefixtures("app")
@pytest.mark.unit
class TestV2Parity:
    def test_rules_list_parity(self, app):
        # Inject fake DB pool
        app.config['DB_POOL'] = FakePool()
        client = app.test_client()
        headers = {'X-API-KEY': 'test-api-key-123'}

        v1 = client.get('/api/v1/rules', headers=headers)
        v2 = client.get('/api/v2/rules', headers=headers)

        assert v1.status_code == 200
        assert v2.status_code == 200
        assert v1.get_json() == v2.get_json()

    def test_dev_hosts_parity(self, app):
        app.config['DB_POOL'] = FakePool()
        client = app.test_client()
        headers = {'X-API-KEY': 'test-api-key-123'}

        v1 = client.get('/api/v1/dev-hosts', headers=headers)
        v2 = client.get('/api/v2/dev-hosts', headers=headers)

        assert v1.status_code == 200
        assert v2.status_code == 200
        assert v1.get_json() == v2.get_json()

    def test_teams_parity(self, app):
        app.config['DB_POOL'] = FakePool()
        client = app.test_client()
        headers = {'X-API-KEY': 'test-api-key-123'}

        v1 = client.get('/api/v1/teams', headers=headers)
        v2 = client.get('/api/v2/teams', headers=headers)

        assert v1.status_code == 200
        assert v2.status_code == 200
        assert v1.get_json() == v2.get_json()

    def test_metrics_parity(self, app, monkeypatch):
        # Monkeypatch redis client used by web_ui_service
        class DummyRedisModule:
            Redis = FakeRedis
        monkeypatch.setattr(app, 'redis', DummyRedisModule())

        client = app.test_client()
        headers = {'X-API-KEY': 'test-api-key-123'}

        v1 = client.get('/api/v1/metrics', headers=headers)
        v2 = client.get('/api/v2/metrics', headers=headers)

        assert v1.status_code == 200
        assert v2.status_code == 200
        assert v1.get_json() == v2.get_json()

    def test_audit_logs_parity(self, app):
        app.config['DB_POOL'] = FakePool(None)
        client = app.test_client()
        headers = {'X-API-KEY': 'test-api-key-123'}

        v1 = client.get('/api/v1/audit-logs?limit=1', headers=headers)
        v2 = client.get('/api/v2/audit-logs?limit=1', headers=headers)

        assert v1.status_code == 200
        assert v2.status_code == 200
        assert v1.get_json() == v2.get_json()
