# app/services/product_client.py
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from requests import RequestException

from app.utils.settings import PRODUCT_SERVICE_URL
from app.utils.logging import get_logger

logger = get_logger(__name__)


def http_retry():
    return retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.3, min=0.3, max=3),
        retry=retry_if_exception_type(RequestException),
    )

class ProductClient:
    def __init__(self, base_url: str | None = None, timeout: int = 2):
        self.base_url = (base_url or PRODUCT_SERVICE_URL).rstrip("/")
        self.timeout = timeout

    @http_retry()
    def fetch_product(self, product_id: int) -> dict:
        url = f"{self.base_url}/products/{product_id}"
        logger.info(f"ProductClient GET {url}")

        resp = requests.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()
