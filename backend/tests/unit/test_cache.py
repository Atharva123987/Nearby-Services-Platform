import asyncio

from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.cache import get_or_set


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex):
        self.store[key] = value
        self.ttls[key] = ex


class DownRedis:
    async def get(self, key):
        raise RedisConnectionError("down")

    async def set(self, key, value, ex):
        raise RedisConnectionError("down")


def _run(redis, value, calls):
    async def loader():
        calls.append(1)
        return value

    return asyncio.run(get_or_set(redis, "k", loader, ttl=100, empty_ttl=10))


def test_miss_then_hit():
    redis, calls = FakeRedis(), []
    assert _run(redis, {"a": 1}, calls) == ({"a": 1}, False)
    assert _run(redis, {"a": 1}, calls) == ({"a": 1}, True)
    assert len(calls) == 1
    assert 100 <= redis.ttls["k"] <= 110


def test_empty_value_cached_with_short_ttl():
    redis, calls = FakeRedis(), []
    _run(redis, [], calls)
    assert _run(redis, [], calls) == ([], True)
    assert 10 <= redis.ttls["k"] <= 11


def test_redis_down_falls_through_to_loader():
    assert _run(DownRedis(), {"a": 1}, []) == ({"a": 1}, False)
