"""Telemetry 'worlds' for the mock monitoring service, built from data-pack files (or uploaded rows) instead of code.
One world per service per time window; the sandbox state and the result of every action come from the pack's sandbox files."""
import csv, json
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_CONFIG = {"db.pool.max_connections": 50, "cache.ttl_seconds": 300, "feature.new_pricing_engine": False}
BASE = {"cpu": 35.0, "memory": 55.0, "latency": 0.22, "error_rate": 0.4}
FILES = {"metrics": "telemetry/metrics.csv", "logs": "telemetry/logs.csv", "traces": "telemetry/traces.csv", "deployments": "telemetry/deployments.csv"}


def _dt(s): return datetime.fromisoformat(str(s).replace("Z", "")[:19])
def _iso(d): return d.isoformat(timespec="seconds")
def _f(r, k):
    try: return float(r.get(k) or 0)
    except (TypeError, ValueError): return 0.0
def _units(r): return {"cpu": _f(r, "cpu_pct"), "memory": _f(r, "memory_pct"), "latency": round(_f(r, "latency_p95_ms") / 1000, 3), "error_rate": _f(r, "error_rate_pct")}
def _convert(d): return {"cpu": d.get("cpu_pct", BASE["cpu"]), "memory": d.get("memory_pct", BASE["memory"]), "latency": round(d.get("latency_p95_ms", 220) / 1000, 3), "error_rate": d.get("error_rate_pct", BASE["error_rate"])}
def health_of(cur, avail):
    if avail < 100: return "down"
    return "degraded" if cur["cpu"] >= 80 or cur["memory"] >= 85 or cur["latency"] >= 1.0 or cur["error_rate"] >= 5 else "healthy"


class PackStore:
    def __init__(self): self.reset()

    def reset(self):
        self.rows = {k: [] for k in FILES}; self.state, self.outcomes, self.catalog, self.worlds = {}, {}, [], []

    def add(self, kind, rows): self.rows[kind].extend(rows)

    def load_dir(self, path):
        p = Path(path)
        for kind, rel in FILES.items():
            if (p / rel).exists():
                with open(p / rel, newline="", encoding="utf-8") as f: self.rows[kind].extend(csv.DictReader(f))
        for attr, rel in (("state", "sandbox/sandbox_state.json"), ("outcomes", "sandbox/remediation_outcomes.json")):
            if (p / rel).exists(): setattr(self, attr, json.loads((p / rel).read_text(encoding="utf-8")))
        if (p / "scenarios/scenario_catalog.json").exists(): self.catalog = json.loads((p / "scenarios/scenario_catalog.json").read_text(encoding="utf-8"))

    def counts(self): return {**{k: len(v) for k, v in self.rows.items()}, "worlds": len(self.worlds)}

    def build(self):
        self.worlds = []; by = {}
        for r in self.rows["metrics"]: by.setdefault(r["service_name"], []).append(r)
        for svc, rows in by.items():
            rows.sort(key=lambda r: str(r["timestamp"])); win, prev = [], None
            for r in rows:
                t = _dt(r["timestamp"])
                if prev and t - prev > timedelta(hours=2): self._make(svc, win); win = []
                win.append(r); prev = t
            if win: self._make(svc, win)

    def _make(self, svc, rows):
        start, end = _dt(rows[0]["timestamp"]), _dt(rows[-1]["timestamp"])
        sid = next((c["scenario_id"] for c in self.catalog if c["service"] == svc and abs((_dt(c["window_start"]) - start).total_seconds()) < 600), None)
        st = self.state.get(sid, {}); cur = _units(rows[-1]); avail = _f(rows[-1], "availability_pct") if rows[-1].get("availability_pct") not in (None, "") else 100.0
        series = [{"ts": _iso(_dt(r["timestamp"])), **_units(r)} for r in rows[::4]] + ([{"ts": _iso(end), **cur}] if (len(rows) - 1) % 4 else [])
        lo, hi = start - timedelta(minutes=5), end + timedelta(minutes=5)
        logs = sorted(({"ts": _iso(_dt(l["timestamp"])), "level": "WARN" if str(l["level"]).upper() == "WARNING" else str(l["level"]).upper(), "msg": str(l["message"]),
                        "id": l.get("log_id") or None, "trace_id": l.get("trace_id") or None}
                       for l in self.rows["logs"] if l["service_name"] == svc and lo <= _dt(l["timestamp"]) <= hi), key=lambda x: x["ts"])
        deps = sorted(({"version": str(d["version"]).lstrip("v"), "ts": _iso(_dt(d["timestamp"])), "status": "success" if str(d.get("change_type", "deploy")) == "deploy" else "config",
                        "by": d.get("deployed_by") or "unknown", "id": d.get("deployment_id"), "summary": d.get("change_summary", ""), "change_type": d.get("change_type", "deploy")}
                       for d in self.rows["deployments"] if d["service_name"] == svc and _dt(d["timestamp"]) <= end), key=lambda x: x["ts"], reverse=True)
        real = [d for d in deps if d["status"] == "success"]
        ver = str(st.get("version") or (real[0]["version"] if real else "1.0.0")).lstrip("v"); prev = str(st.get("previous_version") or (real[1]["version"] if len(real) > 1 else ver)).lstrip("v")
        by = {}
        for s in self.rows["traces"]: by.setdefault(s["trace_id"], []).append(s)
        traces = []
        for tid, spans in by.items():
            root = next((s for s in spans if not s.get("parent_span_id") or str(s.get("parent_span_id")) in ("", "nan")), None)
            if not root or root["service_name"] != svc or not lo <= _dt(root["start_time"]) <= hi: continue
            slow = max(spans, key=lambda s: _f(s, "duration_ms")); err = next((s for s in spans if s.get("status") == "error"), None)
            traces.append({"trace_id": tid, "root": root["operation"], "duration_ms": int(_f(root, "duration_ms")), "slowest_span": slow["operation"], "slowest_service": slow["service_name"],
                           "error": err.get("error_message") if err else None, "error_service": err["service_name"] if err else None, "start": _iso(_dt(root["start_time"]))})
        traces.sort(key=lambda t: t["start"], reverse=True)
        outs = self.outcomes.get(sid, []); good = next((o for o in outs if o["result"] == "success"), None)
        self.worlds.append({"pack": True, "service": svc, "environment": "sandbox", "scenario": sid, "start": start, "end": end, "version": ver, "prev_version": prev,
                            "replicas": st.get("replicas", 3), "base_replicas": st.get("replicas", 3), "config": {**DEFAULT_CONFIG, **st.get("config", {})},
                            "health": health_of(cur, avail), "metrics": cur, "series": series, "logs": logs, "deployments": deps, "traces": traces[:8],
                            "unavailable": set(st.get("unavailable", [])), "outcomes": outs, "healthy": _convert(good["health_after"]) if good else dict(BASE), "actions": []})

    def pick(self, service, at):
        try: t = _dt(at)
        except Exception: return None
        return next((w for w in self.worlds if w["service"] == service and w["start"] - timedelta(hours=1) <= t <= w["end"] + timedelta(hours=1)), None)


def result_of(w, op, params):
    """What the pack says this exact action does: success | partial | no_effect | fails_verification."""
    for o in w["outcomes"]:
        if o["operation"] != op: continue
        p = o.get("parameters", {})
        if op == "rollback" and str(params.get("target_version", "")).lstrip("v") != str(p.get("target_version", "")).lstrip("v"): continue
        if op == "config_change" and (params.get("key"), params.get("value")) != (p.get("key"), p.get("value")): continue
        if op == "scale" and int(params.get("replicas", 0)) < w["base_replicas"] + 2: continue
        return o["result"], o
    return "no_effect", None


def apply(w, res, outcome):
    if res == "success":
        w["metrics"] = dict(w["healthy"]); w["health"] = "healthy"
    elif res == "partial" and outcome: w["metrics"] = _convert(outcome["health_after"]); w["health"] = "degraded"
    w["logs"].append({"ts": _iso(datetime.utcnow()), "level": "INFO", "msg": "service recovered, health checks passing" if res == "success" else f"action result: {res}", "id": None, "trace_id": None})
