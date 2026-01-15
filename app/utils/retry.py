# app/utils/retry.py
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests
import redis

def http_retry():
    return retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.3, min=0.3, max=3),
        retry=retry_if_exception_type(requests.RequestException),
    )

def redis_retry():
    return retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.2, min=0.2, max=2),
        retry=retry_if_exception_type(redis.RedisError),
    )
