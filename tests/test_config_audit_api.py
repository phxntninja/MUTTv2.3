#!/usr/bin/env python3
import pytest


@pytest.fixture(scope="module")
def app(monkeymodule):
    from services import web_ui_service as w

    # Bypass external dependencies
    monkeymodule.setattr(w, 'DynamicConfig', None)
    def fake_fetch_secrets(app):
        app.config['SECRETS'] = {"WEBUI_API_KEY": "test-api-key-123"}
    monkeymodule.setattr(w, 'fetch_secrets', fake_fetch_secrets)
    monkeymodule.setattr(w, 'create_redis_pool', lambda app: None)
    monkeymodule.setattr(w, 'create_postgres_pool', lambda app: app.config.__setitem__('DB_POOL', None))

    return w.create_app()

@pytest.mark.unit
def test_config_audit_list_and_pagination(app):
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
def test_config_audit_filters(app):
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
