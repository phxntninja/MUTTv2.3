import pytest
from unittest.mock import MagicMock


pytestmark = pytest.mark.unit


def make_pool_mock(fail_on_password=None):
    import types
    class FakeConn:
        def cursor(self):
            class Ctx:
                def __enter__(self):
                    return self
                def __exit__(self, exc_type, exc, tb):
                    return False
                def execute(self, _):
                    return None
            return Ctx()
    class FakePool:
        def __init__(self, password):
            if fail_on_password and password == fail_on_password:
                raise Exception("auth failed")
            self.password = password
        def getconn(self):
            return FakeConn()
        def putconn(self, _):
            return None
    return FakePool


def test_postgres_uses_current_when_valid(monkeypatch):
    import services.postgres_connector as pc
    # Patch psycopg2.pool.ThreadedConnectionPool to our fake
    FakePool = make_pool_mock()
    class FakePsyPool:
        ThreadedConnectionPool = None
    import psycopg2.pool as real_pool
    monkeypatch.setattr(real_pool, "ThreadedConnectionPool", lambda **kwargs: FakePool(kwargs['password']))

    pool = pc.get_postgres_pool(
        host='h', port=5432, dbname='d', user='u',
        password_current='cur', password_next='next',
        minconn=1, maxconn=2
    )
    assert getattr(pool, 'password') == 'cur'


def test_postgres_falls_back_to_next(monkeypatch):
    import services.postgres_connector as pc
    # Fail on current, succeed on next
    FakePool = make_pool_mock(fail_on_password='cur')
    import psycopg2.pool as real_pool
    monkeypatch.setattr(real_pool, "ThreadedConnectionPool", lambda **kwargs: FakePool(kwargs['password']))

    pool = pc.get_postgres_pool(
        host='h', port=5432, dbname='d', user='u',
        password_current='cur', password_next='next',
        minconn=1, maxconn=2
    )
    assert getattr(pool, 'password') == 'next'


def test_postgres_both_passwords_fail(monkeypatch):
    import services.postgres_connector as pc
    # Fail on both
    def fail_pool(**kwargs):
        raise Exception("auth failed")
    import psycopg2.pool as real_pool
    monkeypatch.setattr(real_pool, "ThreadedConnectionPool", fail_pool)

    with pytest.raises(Exception):
        pc.get_postgres_pool(
            host='h', port=5432, dbname='d', user='u',
            password_current='cur', password_next='next',
            minconn=1, maxconn=2
        )

