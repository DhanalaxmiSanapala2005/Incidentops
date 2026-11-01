"""HTTP client for the monitoring + sandbox integrations. GETs retry with bounded backoff;
mutating calls are single-attempt and always carry a signed approval token."""
import time
import httpx
from backend.config import settings
from common.signing import sign

_client: httpx.Client | None = None
LAST_ATTEMPTS = 1


class IntegrationError(Exception):
    pass


def set_client(c): global _client; _client = c


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(base_url=settings.MOCK_BASE_URL, timeout=settings.MOCK_TIMEOUT_S)
    return _client


def get(path: str, retries: int = 3, **params) -> dict:
    global LAST_ATTEMPTS
    last = None
    for i in range(retries):
        LAST_ATTEMPTS = i + 1
        try:
            r = client().get(path, params=params or None, headers={"X-Service-Key": settings.SERVICE_KEY})
            if r.status_code < 500:
                if r.status_code >= 400:
                    raise IntegrationError(f"{path}: HTTP {r.status_code} {r.text[:120]}")
                return r.json()
            last = f"HTTP {r.status_code}"
        except httpx.HTTPError as e:
            last = str(e)
        time.sleep(settings.RETRY_BACKOFF_S * (2 ** i))
    raise IntegrationError(f"{path} unavailable after {retries} attempts ({last})")


def admin(path: str, method="post", **kw) -> dict:
    r = client().request(method, path, headers={"X-Service-Key": settings.SERVICE_KEY}, **kw)
    r.raise_for_status(); return r.json()


def mutate(path: str, body: dict, op: str, params: dict, action_id: int) -> tuple[int, dict]:
    """Single attempt; token binds op + exact params."""
    try:
        r = client().post(path, json=body, headers={"X-Service-Key": settings.SERVICE_KEY,
                                                    "X-Exec-Token": sign(op, params, action_id)})
    except httpx.HTTPError as e:
        raise IntegrationError(f"sandbox unreachable: {e}")
    try: data = r.json()
    except Exception: data = {"raw": r.text[:200]}
    return r.status_code, data
