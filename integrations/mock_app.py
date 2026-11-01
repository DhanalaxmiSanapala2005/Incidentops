"""Mock monitoring + sandbox remediation service (runs as its own process on :8001).
Read endpoints need X-Service-Key. Mutating endpoints additionally need a signed
X-Exec-Token (issued by the backend only after human approval), bound to exact params."""
import os, time
from datetime import datetime, timedelta
from typing import Any
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel
from common.signing import verify
from data.scenarios import BASELINE, SCENARIOS, BY_ID
from integrations import pack_world
from pathlib import Path

SERVICE_KEY = os.getenv("MOCK_SERVICE_KEY", "mock-monitoring-key")
ALLOWED_CONFIG = {"feature.new_pricing_engine", "cache.ttl_seconds", "db.pool.max_connections"}
app = FastAPI(title="Mock Monitoring & Sandbox API", version="1.0")
WORLD: dict[str, dict] = {}
PACK = pack_world.PackStore()
PACK_DIR = Path(os.getenv("MOCK_PACK_DIR", str(Path(__file__).resolve().parents[1] / "data" / "pack")))


def load_pack():
    PACK.reset(); PACK.load_dir(PACK_DIR); PACK.build(); return PACK.counts()


def _now(): return datetime.utcnow()
def _iso(dt): return dt.isoformat(timespec="seconds")


def _series(base, cur):
    ramp = [0, 0, .05, .1, .4, .8, .95, 1]
    now = _now()
    return [{"ts": _iso(now - timedelta(minutes=2 * (7 - i))),
             **{k: round(base[k] + (cur[k] - base[k]) * r, 2) for k in base}} for i, r in enumerate(ramp)]


def build_world(sc):
    now = _now()
    return {"service": sc["service"], "environment": "sandbox", "version": sc["version"], "replicas": sc["replicas"],
            "config": dict(sc["config"]), "health": sc["health"], "metrics": dict(sc["metrics"]),
            "series": _series(BASELINE, sc["metrics"]), "fix": sc["fix"], "scenario": sc["id"],
            "logs": [{"ts": _iso(now - timedelta(minutes=m)), "level": l, "msg": t} for m, l, t in sc["logs"]],
            "deployments": [{"version": d["version"], "ts": _iso(now - timedelta(minutes=d["minutes_ago"])),
                             "status": d["status"], "by": "ci-bot"} for d in sc["deployments"]],
            "outage_calls": sc["chaos"].get("logs_outage_calls", 0), "actions": []}


def reset(service: str | None = None):
    for sc in SCENARIOS:
        if service is None or sc["service"] == service:
            WORLD[sc["service"]] = build_world(sc)


reset()
load_pack()


def key(x_service_key: str = Header(None)):
    if x_service_key != SERVICE_KEY:
        raise HTTPException(401, "invalid service key")


def svc(sid: str, at: str | None = None) -> dict:
    if at and PACK.worlds:
        w = PACK.pick(sid, at)
        if w: return w
    if sid not in WORLD:
        raise HTTPException(404, f"unknown service {sid}")
    return WORLD[sid]


@app.get("/healthz")
def healthz(): return {"ok": True}


@app.get("/services", dependencies=[Depends(key)])
def services(): return [{"id": k, "environment": v["environment"], "health": v["health"]} for k, v in WORLD.items()]


@app.get("/services/{sid}/metrics", dependencies=[Depends(key)])
def metrics(sid: str, at: str | None = None): w = svc(sid, at); return {"service": sid, "current": w["metrics"], "series": w["series"]}


@app.get("/services/{sid}/health", dependencies=[Depends(key)])
def health(sid: str, at: str | None = None): w = svc(sid, at); return {"service": sid, "status": w["health"], "checked_at": _iso(_now())}


@app.get("/services/{sid}/logs", dependencies=[Depends(key)])
def logs(sid: str, limit: int = 50, at: str | None = None):
    w = svc(sid, at)
    if w.get("pack") and "logs" in w["unavailable"]:
        raise HTTPException(503, "log backend unavailable")
    if w.get("outage_calls", 0) > 0:
        w["outage_calls"] -= 1
        raise HTTPException(503, "log backend temporarily unavailable")
    return {"service": sid, "logs": w["logs"][-limit:]}


@app.get("/services/{sid}/deployments", dependencies=[Depends(key)])
def deployments(sid: str, at: str | None = None): return {"service": sid, "deployments": svc(sid, at)["deployments"]}


@app.get("/services/{sid}/traces", dependencies=[Depends(key)])
def traces(sid: str, at: str | None = None):
    w = svc(sid, at)
    if w.get("pack"):
        if "traces" in w["unavailable"]: raise HTTPException(503, "trace backend unavailable")
        return {"service": sid, "traces": w["traces"]}
    slow = w["metrics"]["latency"] > 1
    return {"service": sid, "traces": [{"trace_id": f"tr-{i}", "root": "GET /api", "duration_ms": int(w["metrics"]["latency"] * 1000 * (1 + i / 10)),
                                         "slowest_span": "db.query" if slow else "handler"} for i in range(3)]}


@app.get("/services/{sid}/state", dependencies=[Depends(key)])
def state(sid: str, at: str | None = None):
    w = svc(sid, at)
    return {"service": sid, "version": w["version"], "replicas": w["replicas"], "config": w["config"], "environment": w["environment"]}


class Chaos(BaseModel):
    service: str
    outage_calls: int = 0


@app.post("/admin/reset", dependencies=[Depends(key)])
def admin_reset(service: str | None = None):
    reset(service)
    if service is None: load_pack()  # full reset also drops uploaded telemetry and restores the bundled pack
    return {"reset": service or "all"}


class Upload(BaseModel):
    kind: str
    rows: list[dict] = []
    data: Any = None


@app.post("/admin/pack/load", dependencies=[Depends(key)])
def admin_pack_load(): return load_pack()


@app.get("/admin/pack/status", dependencies=[Depends(key)])
def admin_pack_status(): return {**PACK.counts(), "windows": [{"service": w["service"], "start": w["start"].isoformat(), "scenario": w["scenario"]} for w in PACK.worlds]}


@app.post("/admin/pack/upload", dependencies=[Depends(key)])
def admin_pack_upload(u: Upload):
    if u.kind in pack_world.FILES: PACK.add(u.kind, u.rows)
    elif u.kind in ("state", "outcomes"): setattr(PACK, u.kind, u.data or {})
    elif u.kind == "catalog": PACK.catalog = u.data or []
    else: raise HTTPException(422, "unknown kind")
    PACK.build(); return PACK.counts()


@app.post("/admin/chaos", dependencies=[Depends(key)])
def admin_chaos(c: Chaos): svc(c.service)["outage_calls"] = c.outage_calls; return {"ok": True}


# ---------------------------------------------------------------- sandbox (mutating)
class Empty(BaseModel): pass
class Rollback(BaseModel): service: str; target_version: str
class Scale(BaseModel): replicas: int
class Config(BaseModel): key: str; value: bool | int | str


def _heal(w):
    w["metrics"] = dict(BASELINE); w["health"] = "healthy"
    w["series"] += [{"ts": _iso(_now() + timedelta(minutes=i)), **BASELINE} for i in range(1, 3)]
    w["logs"].append({"ts": _iso(_now()), "level": "INFO", "msg": "service recovered, health checks passing"})


def _guard(op, params, token):
    p = verify(token, op, params)
    if not p:
        raise HTTPException(403, "missing, expired or mismatched approval token")
    return p


def _record(w, op, params, p, effective):
    if w.get("pack"):
        res, outcome = pack_world.result_of(w, op, params); pack_world.apply(w, res, outcome)
        w["actions"].append({"op": op, "params": params, "action_id": p["aid"], "ts": _iso(_now()), "effective": res == "success", "result": res}); return
    w["actions"].append({"op": op, "params": params, "action_id": p["aid"], "ts": _iso(_now()), "effective": effective})
    if effective:
        _heal(w)


@app.post("/sandbox/services/{sid}/restart", dependencies=[Depends(key)])
def restart(sid: str, x_exec_token: str = Header(None), at: str | None = None):
    w = svc(sid, at); params = {"service": sid}; p = _guard("restart", params, x_exec_token)
    eff = not w.get("pack") and w["fix"]["op"] == "restart" and w["fix"]["effective"]
    _record(w, "restart", params, p, eff); return {"status": "restarted", "service": sid}


@app.post("/sandbox/deployments/rollback", dependencies=[Depends(key)])
def rollback(b: Rollback, x_exec_token: str = Header(None), at: str | None = None):
    w = svc(b.service, at); params = b.model_dump(); p = _guard("rollback", params, x_exec_token)
    if b.target_version not in {d["version"] for d in w["deployments"]}:
        raise HTTPException(422, "unknown target version")
    w["version"] = b.target_version
    w["deployments"].insert(0, {"version": b.target_version, "ts": _iso(_now()), "status": "success", "by": "rollback"})
    _record(w, "rollback", params, p, not w.get("pack") and w["fix"]["op"] == "rollback" and w["fix"]["effective"])
    return {"status": "rolled_back", "version": b.target_version}


@app.post("/sandbox/services/{sid}/scale", dependencies=[Depends(key)])
def scale(sid: str, b: Scale, x_exec_token: str = Header(None), at: str | None = None):
    w = svc(sid, at); params = {"service": sid, **b.model_dump()}; p = _guard("scale", params, x_exec_token)
    if not 1 <= b.replicas <= 10:
        raise HTTPException(422, "replicas out of range")
    w["replicas"] = b.replicas
    _record(w, "scale", params, p, not w.get("pack") and w["fix"]["op"] == "scale" and w["fix"]["effective"] and b.replicas > 2)
    return {"status": "scaled", "replicas": b.replicas}


@app.post("/sandbox/services/{sid}/config", dependencies=[Depends(key)])
def config(sid: str, b: Config, x_exec_token: str = Header(None), at: str | None = None):
    w = svc(sid, at); params = {"service": sid, **b.model_dump()}; p = _guard("config_change", params, x_exec_token)
    if b.key not in ALLOWED_CONFIG:
        raise HTTPException(422, "config key not allowlisted")
    prev = w["config"].get(b.key); w["config"][b.key] = b.value
    _record(w, "config_change", params, p, not w.get("pack") and w["fix"]["op"] == "config_change" and w["fix"]["effective"] and b.value != prev)
    return {"status": "configured", "key": b.key, "value": b.value}
