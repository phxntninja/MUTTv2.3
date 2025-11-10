import pytest


pytestmark = pytest.mark.unit


class FakeRedisClient:
    def __init__(self, pool):
        # Simulate auth failure by inspecting pool password
        if getattr(pool, 'password', None) == 'bad':
            raise Exception('auth failed')
    def ping(self):
        return True


def test_redis_uses_current_when_valid(monkeypatch):
    import services.redis_connector as rc

    class FakePool:
        def __init__(self, **kwargs):
            self.password = kwargs.get('password')

    import redis
    monkeypatch.setattr(redis, 'ConnectionPool', lambda **kwargs: FakePool(**kwargs))
    monkeypatch.setattr(redis, 'Redis', lambda connection_pool: FakeRedisClient(connection_pool))

    pool = rc.get_redis_pool(
        host='h', port=6379,
        password_current='cur', password_next='next',
        tls_enabled=False
    )
    assert getattr(pool, 'password') == 'cur'


def test_redis_falls_back_to_next(monkeypatch):
    import services.redis_connector as rc

    class FakePool:
        def __init__(self, **kwargs):
            self.password = kwargs.get('password')

    import redis
    monkeypatch.setattr(redis, 'ConnectionPool', lambda **kwargs: FakePool(**kwargs))

    # Fail on 'cur' by raising in FakeRedisClient init
    def fake_redis_ctor(connection_pool):
        if getattr(connection_pool, 'password') == 'cur':
            raise Exception('auth failed')
        return FakeRedisClient(connection_pool)

    monkeypatch.setattr(redis, 'Redis', fake_redis_ctor)

    pool = rc.get_redis_pool(
        host='h', port=6379,
        password_current='cur', password_next='next',
        tls_enabled=False
    )
    assert getattr(pool, 'password') == 'next'


def test_redis_both_passwords_fail(monkeypatch):
    import services.redis_connector as rc

    class FakePool:
        def __init__(self, **kwargs):
            self.password = kwargs.get('password')

    import redis
    monkeypatch.setattr(redis, 'ConnectionPool', lambda **kwargs: FakePool(**kwargs))

    def fake_redis_ctor(connection_pool):
        raise Exception('auth failed')

    monkeypatch.setattr(redis, 'Redis', fake_redis_ctor)

    with pytest.raises(Exception):
        rc.get_redis_pool(
            host='h', port=6379,
            password_current='cur', password_next='next',
            tls_enabled=False
        )

