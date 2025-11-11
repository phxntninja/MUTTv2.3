#!/usr/bin/env python3
"""
MUTT v2.5 - v1/v2 API Parity Tests (Web UI)

Verifies that v2 aliases return identical payloads as v1 for key endpoints.
These tests monkeypatch DB/Redis to avoid external dependencies.
"""

import pytest


def _make_app(monkeypatch):
    from services import web_ui_service as w

    # Disable DynamicConfig to avoid Redis requirement
    monkeypatch.setattr(w, 'DynamicConfig', None)

    # Bypass Vault/Redis/Postgres initialization
    def fake_fetch_secrets(app):
        app.config['SECRETS'] = {"WEBUI_API_KEY": "test-api-key-123"}
    monkeypatch.setattr(w, 'fetch_secrets', fake_fetch_secrets)
    monkeypatch.setattr(w, 'create_redis_pool', lambda app: None)
    monkeypatch.setattr(w, 'create_postgres_pool', lambda app: app.config.__setitem__('DB_POOL', None))

    # Build app
    app = w.create_app()
    return app, w


class FakeCursor:
    def __init__(self, data):
        self._data = data
        self._rows = []
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        q = ' '.join(query.split()).lower()
        if 'from alert_rules' in q:
            self._rows = [
                {
                    'id': 1,
                    'match_string': 'ERROR',
                    'trap_oid': None,
                    'syslog_severity': None,
                    'match_type': 'contains',
                    'priority': 100,
                    'prod_handling': 'Page_and_ticket',
                    'dev_handling': 'Ticket_only',
                    'team_assignment': 'NETO',
                    'is_active': True,
                }
            ]
        elif 'from development_hosts' in q:
            self._rows = [{'hostname': 'dev-host-1'}, {'hostname': 'dev-host-2'}]
        elif 'from device_teams' in q:
            self._rows = [
                {'hostname': 'host-a', 'team_assignment': 'NetOps'},
                {'hostname': 'host-b', 'team_assignment': 'SRE'},
            ]
        elif 'from event_audit_log' in q:
            # Provide a minimal rowset for audit logs
            self._rows = [
                {
                    'id': 1,
                    'event_timestamp': '2025-11-10T00:00:00Z',
                    'hostname': 'host-a',
                    'matched_rule_id': 1,
                    'handling_decision': 'Page_and_ticket',
                    'forwarded_to_moog': True,
                    'raw_message': '{"message": "foo"}'
                }
            ]
        elif 'count(*)' in q:
            # For audit-logs count path when exercised
            self._rows = [(0,)]
        else:
            self._rows = []
        self.rowcount = len(self._rows)

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeConn:
    def cursor(self, cursor_factory=None):
        return FakeCursor(data=None)


class FakePool:
    def getconn(self):
        return FakeConn()

    def putconn(self, conn):
        pass


class FakeRedis:
    def __init__(self, *args, **kwargs):
        pass

    def ping(self):
        return True

    def scan_iter(self, match=None):
        # Return 5 recent 1m keys and 24h keys
        if match and ':1m:' in match:
            # Simulate 60 minutes worth
            for i in range(60):
                yield f"mutt:metrics:1m:{i:02d}"
        elif match and ':24h:' in match:
            for i in range(24):
                yield f"mutt:metrics:24h:{i:02d}"
        else:
            return []

    def mget(self, keys):
        # Provide simple ascending values for determinism
        return list(range(len(keys)))

    def get(self, key):
        # Provide fixed counters for current minute/hour/day
        if 'current:1m' in key:
            return 100
        if 'current:1h' in key:
            return 6000
        if 'current:24h' in key:
            return 144000
        return 0


@pytest.mark.unit
class TestV2Parity:
    def test_rules_list_parity(self, monkeypatch):
        app, w = _make_app(monkeypatch)
        # Inject fake DB pool
        app.config['DB_POOL'] = FakePool()
        client = app.test_client()
        headers = {'X-API-KEY': 'test-api-key-123'}

        v1 = client.get('/api/v1/rules', headers=headers)
        v2 = client.get('/api/v2/rules', headers=headers)

        assert v1.status_code == 200
        assert v2.status_code == 200
        assert v1.get_json() == v2.get_json()

    def test_dev_hosts_parity(self, monkeypatch):
        app, w = _make_app(monkeypatch)
        app.config['DB_POOL'] = FakePool()
        client = app.test_client()
        headers = {'X-API-KEY': 'test-api-key-123'}

        v1 = client.get('/api/v1/dev-hosts', headers=headers)
        v2 = client.get('/api/v2/dev-hosts', headers=headers)

        assert v1.status_code == 200
        assert v2.status_code == 200
        assert v1.get_json() == v2.get_json()

    def test_teams_parity(self, monkeypatch):
        app, w = _make_app(monkeypatch)
        app.config['DB_POOL'] = FakePool()
        client = app.test_client()
        headers = {'X-API-KEY': 'test-api-key-123'}

        v1 = client.get('/api/v1/teams', headers=headers)
        v2 = client.get('/api/v2/teams', headers=headers)

        assert v1.status_code == 200
        assert v2.status_code == 200
        assert v1.get_json() == v2.get_json()

    def test_metrics_parity(self, monkeypatch):
        app, w = _make_app(monkeypatch)
        # Monkeypatch redis client used by web_ui_service
        class DummyRedisModule:
            Redis = FakeRedis
        monkeypatch.setattr(w, 'redis', DummyRedisModule())

        client = app.test_client()
        headers = {'X-API-KEY': 'test-api-key-123'}

        v1 = client.get('/api/v1/metrics', headers=headers)
        v2 = client.get('/api/v2/metrics', headers=headers)

        assert v1.status_code == 200
        assert v2.status_code == 200
        assert v1.get_json() == v2.get_json()

    def test_audit_logs_parity(self, monkeypatch):
        app, w = _make_app(monkeypatch)
        app.config['DB_POOL'] = FakePool(None)
        client = app.test_client()
        headers = {'X-API-KEY': 'test-api-key-123'}

        v1 = client.get('/api/v1/audit-logs?limit=1', headers=headers)
        v2 = client.get('/api/v2/audit-logs?limit=1', headers=headers)

        assert v1.status_code == 200
        assert v2.status_code == 200
        assert v1.get_json() == v2.get_json()
