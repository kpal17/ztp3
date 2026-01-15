# app/services/lock_service.py
import redis
from redis.exceptions import RedisError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.utils.settings import REDIS_URL
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Lua: compare-and-delete (atomic)
_RELEASE_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
"""

def redis_retry():
    return retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.2, min=0.2, max=2),
        retry=retry_if_exception_type(RedisError),
    )

class LockService:
    """
    Odpowiada za:
    - rezerwację produktu (lock)
    - zwalnianie locka
    - pełną atomowość (Lua)
    """

    def __init__(self, url: str | None = None):
        self.redis = redis.Redis.from_url(
            url or REDIS_URL,
            decode_responses=True,
        )

    @redis_retry()
    def acquire_product_lock(self, product_id: int, cart_id: int, ttl: int) -> bool:
        key = f"product:{product_id}:lock"
        logger.info(f"Acquire lock {key} for cart {cart_id}")
        return self.redis.set(
            name=key,
            value=str(cart_id),
            nx=True,
            ex=ttl,
        )

    @redis_retry()
    def release_product_lock(self, product_id: int, cart_id: int) -> bool:
        key = f"product:{product_id}:lock"
        logger.info(f"Release lock {key} for cart {cart_id}")
        res = self.redis.eval(_RELEASE_LUA, 1, key, str(cart_id))
        return bool(res)
