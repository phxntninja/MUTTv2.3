#!/usr/bin/env python3
import pytest


def _make_app(monkeypatch):
    from services import web_ui_service as w

    # Bypass external dependencies
    monkeypatch.setattr(w, 'DynamicConfig', None)
    def fake_fetch_secrets(app):
        app.config['SECRETS'] = {"WEBUI_API_KEY": "test-api-key-123"}
    monkeypatch.setattr(w, 'fetch_secrets', fake_fetch_secrets)
    monkeypatch.setattr(w, 'create_redis_pool', lambda app: None)
    monkeypatch.setattr(w, 'create_postgres_pool', lambda app: app.config.__setitem__('DB_POOL', None))

    return w.create_app(), w


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self._result = []
        self.rowcount = 0
        self._count_mode = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        q = ' '.join(query.split()).lower()
        if q.startswith('select count(*)'):
            self._result = [(len(self._rows),)]
        else:
            self._result = self._rows
        self.rowcount = len(self._result)

    def fetchall(self):
        return list(self._result)

    def fetchone(self):
        return self._result[0] if self._result else None


class FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self, cursor_factory=None):
        return FakeCursor(self._rows)


class FakePool:
    def __init__(self, rows):
        self._rows = rows

    def getconn(self):
        return FakeConn(self._rows)

    def putconn(self, conn):
        pass


@pytest.mark.unit
def test_config_audit_list_and_pagination(monkeypatch):
    app, w = _make_app(monkeypatch)
    rows = [
        {
            'id': 1,
            'changed_at': '2025-11-10T10:00:00Z',
            'changed_by': 'admin_api_key',
            'operation': 'CREATE',
            'table_name': 'alert_rules',
            'record_id': 42,
            'reason': 'initial rule',
            'correlation_id': 'abc'
        }
    ]
    app.config['DB_POOL'] = FakePool(rows)
    client = app.test_client()
    headers = {'X-API-KEY': 'test-api-key-123'}

    resp = client.get('/api/v2/config-audit?limit=1', headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'changes' in data and isinstance(data['changes'], list)
    assert data['pagination']['limit'] == 1
    assert data['pagination']['total'] == 1


@pytest.mark.unit
def test_config_audit_filters(monkeypatch):
    app, w = _make_app(monkeypatch)
    # We only validate that endpoint responds; FakeCursor returns same rows irrespective of filters
    rows = [
        {
            'id': 2,
            'changed_at': '2025-11-10T11:00:00Z',
            'changed_by': 'user_alice',
            'operation': 'UPDATE',
            'table_name': 'alert_rules',
            'record_id': 99,
            'reason': 'tuning',
            'correlation_id': 'def'
        }
    ]
    app.config['DB_POOL'] = FakePool(rows)
    client = app.test_client()
    headers = {'X-API-KEY': 'test-api-key-123'}

    url = '/api/v2/config-audit?changed_by=user_alice&table_name=alert_rules&record_id=99&operation=update&start_date=2025-11-01&end_date=2025-11-30'
    resp = client.get(url, headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['changes'][0]['changed_by'] == 'user_alice'
