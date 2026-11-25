import asyncio

from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.cache import get_or_set, get_version, invalidate


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex):
        self.store[key] = value
        self.ttls[key] = ex

    async def eval(self, script, numkeys, version_key, key, version, value, ttl):
        if self.store.get(version_key, "0") == str(version):
            await self.set(key, value, ex=ttl)

    async def incr(self, key):
        self.store[key] = str(int(self.store.get(key, 0)) + 1)

    async def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)


class DownRedis:
    async def get(self, key):
        raise RedisConnectionError("down")

    async def set(self, key, value, ex):
        raise RedisConnectionError("down")

    async def incr(self, key):
        raise RedisConnectionError("down")

    async def delete(self, *keys):
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


def test_invalidate_bumps_version_and_deletes_keys():
    redis = FakeRedis()
    redis.store["service:1"] = "{}"
    asyncio.run(invalidate(redis, "v", "service:1"))
    assert asyncio.run(get_version(redis, "v")) == 1
    assert "service:1" not in redis.store


def test_version_helpers_tolerate_redis_down():
    assert asyncio.run(get_version(DownRedis(), "v")) is None
    asyncio.run(invalidate(DownRedis(), "v", "k"))


def test_malformed_json_is_replaced():
    redis, calls = FakeRedis(), []
    redis.store["k"] = "{broken"
    assert _run(redis, {"a": 1}, calls) == ({"a": 1}, False)
    assert _run(redis, {"a": 1}, calls) == ({"a": 1}, True)
    assert len(calls) == 1


def test_zero_ttl_skips_existing_entry_and_does_not_write():
    redis = FakeRedis()
    redis.store["k"] = '"old"'

    async def load():
        return "new"

    assert asyncio.run(get_or_set(redis, "k", load, ttl=0, empty_ttl=10)) == ("new", False)
    assert redis.store["k"] == '"old"'

    async def load_empty():
        return []

    assert asyncio.run(get_or_set(redis, "empty", load_empty, ttl=10, empty_ttl=0)) == ([], False)
    assert "empty" not in redis.store


def test_detail_cache_miss_does_not_restore_value_after_invalidation():
    redis = FakeRedis()

    async def load_before_update():
        await invalidate(redis, "v", "k")
        return {"name": "old"}

    result = asyncio.run(
        get_or_set(redis, "k", load_before_update, ttl=100, empty_ttl=10, version_key="v")
    )
    assert result == ({"name": "old"}, False)
    assert "k" not in redis.store
