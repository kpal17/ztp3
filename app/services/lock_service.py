import redis
from redis.exceptions import RedisError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.utils.settings import REDIS_URL
from app.utils.logging import get_logger

logger = get_logger(__name__)

#LUA porownaj i usun, atomicity
_RELEASE_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
"""

#redis wykonuje atomowo przez lua,s krypt dziala jako jedna nieprzerywalna operacja
#lua jest single threaded wiec tlko jedna operacja na raz
#nie mozna wcisnac sie miedzy GET a DEL, wiec tu jest get + porownanie + del wszystko naraz

#tenacity retry
def redis_retry():
    return retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.2, min=0.2, max=2),
        retry=retry_if_exception_type(RedisError),
    )

class LockService:
    """
    -rezerwacja produktu (lock)
    -zwalnianie locka
    -atomowosc przy pomocy lua
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
        #SET product:1:lock "123" NX EX 900
        return self.redis.set(
            name=key, #kllucz
            value=str(cart_id),
            nx=True, #not eXists, jesli nie istnieje to True, jak jest to nic nie rob i False
            ex=ttl, #Expire (wygasa po uplywie ttl), nie trzeba recznie czyscic (!!!)
        )

    @redis_retry()
    def release_product_lock(self, product_id: int, cart_id: int) -> bool:
        key = f"product:{product_id}:lock"
        logger.info(f"Release lock {key} for cart {cart_id}")
        res = self.redis.eval(_RELEASE_LUA, 1, key, str(cart_id))
        return bool(res)
