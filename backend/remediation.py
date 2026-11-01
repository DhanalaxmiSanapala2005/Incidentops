"""Approval-gated execution: atomic claim -> re-validate -> signed sandbox call -> verify -> recover/escalate."""
import time
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from . import models as m
from .core import audit
from .rules import validate_action, verify_recovery
from integrations import client as ic

RECOVERY = {"restart": "escalate", "rollback": "escalate", "scale": "revert", "config_change": "revert"}


class ExecutionError(Exception): ...


def _route(op: str, p: dict) -> tuple[str, dict]:
    s = p["service"]
    return {"restart": (f"/sandbox/services/{s}/restart", {}),
            "rollback": ("/sandbox/deployments/rollback", {"service": s, "target_version": p.get("target_version")}),
            "scale": (f"/sandbox/services/{s}/scale", {"replicas": p.get("replicas")}),
            "config_change": (f"/sandbox/services/{s}/config", {"key": p.get("key"), "value": p.get("value")})}[op]


def _call(db, act, op, params, label="sandbox_call", at=None):
    path, body = _route(op, params)
    code, data = ic.mutate(path + (f"?at={at}" if at else ""), body, op, params, act.id)
    audit(db, "system:executor", label, f"action:{act.id}", "ok" if code < 300 else "error", act.incident_id,
          {"op": op, "params": params, "http_status": code, "response": data})
    db.commit()
    return code, data


def verify(svc: str, at: str | None = None) -> tuple[bool, dict]:
    last = {}
    for i in range(3):
        try:
            ok, last = verify_recovery(ic.get(f"/services/{svc}/health", at=at), ic.get(f"/services/{svc}/metrics", at=at))
        except ic.IntegrationError as e:
            ok, last = False, {"error": str(e)}
        if ok: return True, last
        time.sleep(0.05)
    return False, last


def execute_action(db: Session, action_id: int, actor: str) -> m.Action:
    claim = db.execute(update(m.Action).where(m.Action.id == action_id, m.Action.status == "approved").values(status="executing"))
    db.commit()
    if claim.rowcount != 1:
        raise ExecutionError("action is not in 'approved' state (already executed or never approved)")
    act = db.get(m.Action, action_id); inc = db.get(m.Incident, act.incident_id)
    inc.status = "remediating"; db.commit()
    at = inc.opened_at.isoformat()
    result = {"calls": [], "recovery": None}

    def finish(ok: bool, verification: dict, error: str = ""):
        act.status = "verified" if ok else "failed_escalated"
        act.executed_at = datetime.utcnow(); act.verification = verification
        if error: result["error"] = error
        act.result = result
        if ok: inc.status, inc.outcome, inc.resolved_at = "resolved", "auto_verified", datetime.utcnow()
        else: inc.status, inc.outcome = "escalated", "remediation_failed"
        audit(db, "system:executor", "action_verified" if ok else "action_failed_escalated", f"action:{act.id}", "ok" if ok else "failed", inc.id,
              {"verification": verification, "error": error})
        db.commit(); return act

    if not db.scalar(select(m.Approval).where(m.Approval.action_id == act.id, m.Approval.decision == "approved")):
        return finish(False, {}, "no approval record; refusing to execute")
    try:
        services = {s.name for s in db.scalars(select(m.Service)).all() if s.environment == "sandbox"}
        deps = ic.get(f"/services/{act.params.get('service')}/deployments", at=at)["deployments"]
        validate_action(act.op, act.params, services=services, versions=[d["version"] for d in deps])
        prev = ic.get(f"/services/{act.params['service']}/state", at=at)
    except (ValueError, ic.IntegrationError) as e:
        return finish(False, {}, f"pre-execution validation failed: {e}")
    try:
        code, data = _call(db, act, act.op, act.params, at=at)
        result["calls"].append({"op": act.op, "http_status": code, "response": data})
        if code >= 300: return finish(False, {}, f"sandbox rejected call (HTTP {code}): {data}")
    except ic.IntegrationError as e:
        return finish(False, {}, str(e))
    ok, v = verify(act.params["service"], at)
    if ok: return finish(True, v)
    if RECOVERY[act.op] == "revert":  # documented recovery: restore the previous value, then escalate
        back = dict(act.params)
        if act.op == "scale": back["replicas"] = prev["replicas"]
        else: back["value"] = prev["config"].get(act.params["key"], act.params["value"])
        try:
            code, data = _call(db, act, act.op, back, "sandbox_recovery_call", at)
            result["recovery"] = {"strategy": "revert", "params": back, "http_status": code}
        except ic.IntegrationError as e:
            result["recovery"] = {"strategy": "revert", "error": str(e)}
    else:
        result["recovery"] = {"strategy": "escalate", "note": f"{act.op} cannot be safely undone automatically; further mutations stopped"}
    return finish(False, v, "post-action verification failed")
