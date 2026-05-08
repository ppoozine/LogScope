from redis.asyncio import Redis, from_url


class CacheManager:
    def __init__(self, url: str) -> None:
        self._url = url
        self._client: Redis | None = None

    async def connect(self) -> None:
        if self._client is not None:
            return
        self._client = from_url(self._url, decode_responses=True)
        await self._client.ping()  # type: ignore[misc]

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> Redis:
        if self._client is None:
            raise RuntimeError("CacheManager not connected")
        return self._client


_cache: CacheManager | None = None


def init_cache(url: str) -> CacheManager:
    global _cache
    _cache = CacheManager(url)
    return _cache


def get_cache() -> CacheManager:
    if _cache is None:
        raise RuntimeError("Cache not initialized")
    return _cache


async def get_redis() -> Redis:
    """FastAPI Depends: return active Redis client."""
    return get_cache().client
