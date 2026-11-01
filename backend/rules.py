"""Deterministic rules: validation, urgency classification, correlation keys, recovery criteria.
Agents and the LLM can read these but can never override them."""
import re
LEVELS = ["low", "medium", "high", "critical"]
METRICS = {"cpu", "memory", "latency", "error_rate", "downtime"}
# metric: (warning threshold, high threshold) — cpu/memory %, latency seconds, error_rate %
THRESHOLDS = {"cpu": (80, 95), "memory": (85, 95), "latency": (1.0, 4.0), "error_rate": (5.0, 10.0)}
CATEGORY_PRIORITY = ["downtime", "error_rate", "latency", "cpu", "memory"]
RECOVERY = {"cpu": 80, "memory": 85, "latency": 1.0, "error_rate": 5.0}
OPEN_STATES = {"open", "investigating", "awaiting_approval", "needs_human", "remediating"}
ALLOWED_OPS = {"restart", "rollback", "scale", "config_change"}
CONFIG_ALLOWLIST = {"feature.new_pricing_engine": bool, "cache.ttl_seconds": int, "db.pool.max_connections": int}
CONFIG_RANGES = {"cache.ttl_seconds": (1, 3600), "db.pool.max_connections": (5, 200)}


SERVICE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def validate_alert(a: dict) -> None:
    svc = str(a.get("service", "")).strip()
    if not svc or svc.lower() in ("nan", "none", "null"):
        raise ValueError("service is required")
    if not SERVICE_RE.match(svc):
        raise ValueError("invalid service name (letters, digits, . _ - only, max 64)")
    if a.get("metric") not in METRICS:
        raise ValueError(f"metric must be one of {sorted(METRICS)}")
    try:
        v = float(a.get("value"))
    except (TypeError, ValueError):
        raise ValueError("value must be numeric")
    if v < 0 or (a["metric"] in ("cpu", "memory", "error_rate") and v > 100):
        raise ValueError("value out of range")


def severity_for(metric: str, value: float) -> str:
    if metric == "downtime":
        return "critical"
    warn, high = THRESHOLDS[metric]
    return "high" if value >= high else "medium" if value >= warn else "low"


def incident_severity(alerts: list[dict]) -> str:
    """Max alert severity; 3+ distinct breaching metrics bump one level (cap: critical)."""
    if not alerts:
        return "low"
    lv = max(LEVELS.index(severity_for(a["metric"], a["value"])) for a in alerts)
    breaching = {a["metric"] for a in alerts if severity_for(a["metric"], a["value"]) != "low"}
    if len(breaching) >= 3:
        lv += 1
    return LEVELS[min(lv, 3)]


def incident_category(alerts: list[dict]) -> str:
    metrics = {a["metric"] for a in alerts}
    return next((c for c in CATEGORY_PRIORITY if c in metrics), "latency")


def verify_recovery(health: dict, metrics: dict) -> tuple[bool, dict]:
    cur = metrics.get("current", {})
    checks = {"health": health.get("status") == "healthy"}
    for m, limit in RECOVERY.items():
        checks[m] = cur.get(m, 999) < limit
    return all(checks.values()), {"checks": checks, "metrics": cur, "health": health.get("status")}


def validate_action(op: str, params: dict, *, services: set[str], versions: list[str] | None = None) -> None:
    """Allowlist + parameter validation. Raises ValueError. Used at plan time AND execution time."""
    if op not in ALLOWED_OPS:
        raise ValueError(f"operation '{op}' is not allowlisted")
    if params.get("service") not in services:
        raise ValueError("unknown or non-sandbox service")
    if op == "rollback":
        if versions is not None and params.get("target_version") not in versions:
            raise ValueError("rollback target is not in the service's deployment history")
    elif op == "scale":
        r = params.get("replicas")
        if not isinstance(r, int) or isinstance(r, bool) or not 1 <= r <= 10:
            raise ValueError("replicas must be an integer between 1 and 10")
    elif op == "config_change":
        key, val = params.get("key"), params.get("value")
        if key not in CONFIG_ALLOWLIST:
            raise ValueError(f"config key '{key}' is not allowlisted")
        typ = CONFIG_ALLOWLIST[key]
        if typ is bool and not isinstance(val, bool):
            raise ValueError("value must be boolean")
        if typ is int:
            lo, hi = CONFIG_RANGES[key]
            if not isinstance(val, int) or isinstance(val, bool) or not lo <= val <= hi:
                raise ValueError(f"value must be an integer in [{lo}, {hi}]")
