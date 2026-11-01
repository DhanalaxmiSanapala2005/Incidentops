"""HMAC execution tokens. The backend issues one ONLY after a human approval; the sandbox
verifies it. A token is bound to (operation, exact parameters) and expires quickly."""
import base64, hashlib, hmac, json, os, time

KEY = os.getenv("SANDBOX_SIGNING_KEY", "dev-sandbox-signing-key")


def _hash(op: str, params: dict) -> str:
    canon = json.dumps({"op": op, "p": params}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()


def sign(op: str, params: dict, action_id: int, ttl: int = 120) -> str:
    payload = {"h": _hash(op, params), "aid": action_id, "exp": int(time.time()) + ttl}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return f"{body}.{hmac.new(KEY.encode(), body.encode(), hashlib.sha256).hexdigest()}"


def verify(token: str | None, op: str, params: dict) -> dict | None:
    try:
        body, sig = (token or "").split(".")
        good = hmac.new(KEY.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, good):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body))
        if payload["exp"] < time.time() or payload["h"] != _hash(op, params):
            return None
        return payload
    except Exception:
        return None
