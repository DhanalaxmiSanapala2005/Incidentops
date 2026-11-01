"""Deterministic evidence -> hypothesis extraction. Every hypothesis cites evidence ids;
uncertainty is explicit. (Traditional-ML hook: replace/augment `detect` with a classifier.)"""
import re
from datetime import datetime

PAT = {
    "db_conn": re.compile(r"connection (pool|timeout)|pool=exhausted|too many connections|waiting", re.I),
    "oom": re.compile(r"OutOfMemory|\bOOM\b|heap usage|memory leak|GC overhead", re.I),
    "service_down": re.compile(r"process exited|liveness probe failed|CrashLoopBackOff|no space left", re.I),
    "cpu_sat": re.compile(r"saturated|queue depth|queue growing|cpu throttl", re.I),
    "cache_miss": re.compile(r"cache miss", re.I),
    "upstream": re.compile(r"upstream|bad gateway|\b50[23]\b", re.I),
    "cert": re.compile(r"certificate (has )?expired|x509|tls handshake failed", re.I),
    "errors_after_deploy": re.compile(r"error|exception|timeout|mismatch|failed|exhausted", re.I),
}
FLAG = re.compile(r"feature\.[a-z_]+")
CFGD = re.compile(r"(\S+) changed from (\S+) to (\S+)")
PRIORITY = ["deploy_regression", "config_flag", "oom", "cert_expiry", "service_down", "transient", "cpu_saturation", "cache_miss", "db_connection", "upstream_dependency"]


def _conf(n: int, base=0.55, step=0.1, cap=0.3) -> float:
    return round(min(base + min(n * step, cap), 0.95), 2)


def detect(service, logs, metrics, deployments, health, state, first_alert_ts, traces=None, evid=None) -> list[dict]:
    """logs: [{ts(datetime), level, msg, ev_id}]; deployments: [{version, ts(datetime), status, ev_id}] newest first."""
    out = []
    traces = traces or []; evid = evid or {}
    ext = [t for t in traces if t.get("error_service") and t["error_service"] != service]  # failing span owned by another service

    def hyp(signal, title, conf, ev, expl, op=None, params=None, uncertain=None):
        unc = uncertain if uncertain is not None else (conf < 0.7 or len(ev) < 2)
        out.append({"id": f"H{len(out) + 1}", "signal": signal, "title": title, "confidence": conf, "uncertain": unc,
                    "evidence_ids": ev, "explanation": expl, "op": op, "params": params})

    ok = [d for d in deployments if d["status"] == "success"]
    if ok and first_alert_ts:
        latest = ok[0]; gap = (first_alert_ts - latest["ts"]).total_seconds() / 60
        after = [l for l in logs if l["ts"] >= latest["ts"] and PAT["errors_after_deploy"].search(l["msg"]) and l["level"] != "INFO"]
        if 0 <= gap <= 90 and after and len(ok) > 1:
            hyp("deploy_regression", f"Deployment v{latest['version']} likely introduced the fault", _conf(len(after), 0.6),
                [latest["ev_id"]] + [l["ev_id"] for l in after[:4]],
                f"v{latest['version']} was deployed {int(gap)} min before the first alert and {len(after)} error/warn log lines follow it. "
                "Correlation, not proven causation: confirm after rollback." + (f" However a failing span belongs to {ext[0]['error_service']}, so the deployment may be coincidental; no rollback is recommended." if ext else ""),
                None if ext else "rollback", None if ext else {"service": service, "target_version": ok[1]["version"]}, uncertain=True if ext else None)
    recent_deploy = bool(out)
    flags = {}
    for l in logs:
        if l["level"] == "ERROR":
            for k in FLAG.findall(l["msg"]):
                flags.setdefault(k, []).append(l["ev_id"])
    for k, ev in flags.items():
        if k in state.get("config", {}) and len(ev) >= 2:
            hyp("config_flag", f"Feature flag {k} correlates with errors", _conf(len(ev), 0.6), ev,
                f"{len(ev)} error lines mention {k}=true. Disabling the flag is a reversible mitigation.",
                "config_change", {"service": service, "key": k, "value": False})
    def lines(key): return [l["ev_id"] for l in logs if PAT[key].search(l["msg"])]
    n = lines("oom")
    if n: hyp("oom", "Memory exhaustion / leak", _conf(len(n)), n, f"{len(n)} log lines show memory pressure; memory is at {metrics.get('memory')}%.", "restart", {"service": service})
    n = lines("service_down")
    if n or health.get("status") == "down":
        hyp("service_down", "Service process is down", _conf(len(n)), n or ([evid["health"]] if evid.get("health") else []),
            f"{len(n)} log lines show crash/health failures. Restart may not help if the cause is environmental (e.g. disk full).",
            "restart", {"service": service}, uncertain=any("no space left" in l["msg"] for l in logs))
    n = lines("cpu_sat")
    if n and metrics.get("cpu", 0) >= 90 and not recent_deploy:
        hyp("cpu_saturation", "CPU saturation from queue backlog", _conf(len(n)), n,
            f"CPU {metrics.get('cpu')}% with {len(n)} saturation log lines and no recent deployment.",
            "scale", {"service": service, "replicas": min(state.get("replicas", 2) + 2, 10)})
    n = lines("cache_miss")
    if n and not recent_deploy:
        cfgd = next(((d, m_) for d in deployments if d.get("status") == "config" and (m_ := CFGD.search(d.get("summary", ""))) and m_.group(1) == "cache.ttl_seconds"), None)
        old = int(cfgd[1].group(2)) if cfgd and cfgd[1].group(2).isdigit() else 600
        hyp("cache_miss", "Cache miss storm driving latency", _conf(len(n) + (1 if cfgd else 0)), n + ([cfgd[0]["ev_id"]] if cfgd else []),
            f"{len(n)} log lines show high cache miss ratio." + (f" A configuration change set cache.ttl_seconds from {cfgd[1].group(2)} to {cfgd[1].group(3)} just before; reverting restores {old}." if cfgd else ""),
            "config_change", {"service": service, "key": "cache.ttl_seconds", "value": old})
    n = lines("cert")
    if n: hyp("cert_expiry", "TLS certificate or secret expired", _conf(len(n), 0.7), n, "Logs show an expired certificate or handshake failure. A restart will not fix this; rotating certificates needs an administrator (runbook RB-010).", uncertain=False)
    n = lines("db_conn")
    pool = state.get("config", {}).get("db.pool.max_connections")
    if n and not recent_deploy and isinstance(pool, int) and 0 < pool < 200 and any("pool" in l["msg"].lower() for l in logs):
        hyp("db_connection", "Database connection pool exhaustion", _conf(len(n)), n, f"{len(n)} log lines show pool timeouts with no recent deployment. Raising the pool from {pool} to {min(pool * 3, 200)} is reversible.",
            "config_change", {"service": service, "key": "db.pool.max_connections", "value": min(pool * 3, 200)})
    elif n: hyp("db_connection", "Database connection pool exhaustion", _conf(len(n)), n, f"{len(n)} log lines show pool timeouts/exhaustion; this is a symptom that supports the primary hypothesis.")
    n = lines("upstream")
    if n or ext:
        dep = ext[0]["error_service"] if ext else None
        hyp("upstream_dependency", f"Dependency {dep} is failing or slow" if dep else "Upstream dependency failure (outside observable scope)", _conf(len(n) + len(ext)), n + [t["ev_id"] for t in ext if t.get("ev_id")],
            (f"Traces show failing spans inside {dep}. " if dep else "Errors point to an upstream dependency. ") + "No allowlisted remediation applies; verify with the dependency owner or provider.", uncertain=True)
    if not out and health.get("status") == "healthy" and metrics and metrics.get("cpu", 0) < 80 and metrics.get("memory", 0) < 85 and metrics.get("latency", 0) < 1.0 and metrics.get("error_rate", 0) < 5:
        hyp("transient", "Alert condition has already cleared (transient or flapping)", 0.5, [evid["metric"]] if evid.get("metric") else [],
            "Current metrics are back below every alert threshold and no log, deployment or trace evidence explains the alerts. Treat as transient or flapping; take no action and observe.", uncertain=True)
    out.sort(key=lambda h: PRIORITY.index(h["signal"]))
    for i, h in enumerate(out, 1):
        h["id"] = f"H{i}"
    return out
