"""Audit trail, runtime settings, alert ingestion/correlation, seeding."""
import re
from datetime import datetime, timedelta
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from . import models as m
from .config import ROOT, settings
from .rules import OPEN_STATES, incident_category, incident_severity, validate_alert
from .security import hash_password
from data.scenarios import BY_ID, SERVICES

DEFAULT_SETTINGS = {"approval_ttl_min": str(settings.DEFAULT_APPROVAL_TTL_MIN), "require_separation_of_duties": "false"}
SEED_USERS = [("admin", "admin123", "admin"), ("engineer", "engineer123", "engineer"),
              ("engineer2", "engineer123", "engineer"), ("viewer", "viewer123", "viewer")]


def audit(db: Session, actor: str, event_type: str, target: str = "", outcome: str = "ok",
          incident_id: int | None = None, detail: dict | None = None):
    db.add(m.AuditEvent(actor=actor, event_type=event_type, target=target, outcome=outcome,
                        incident_id=incident_id, detail=detail or {}))


def get_setting(db: Session, key: str) -> str:
    row = db.get(m.Setting, key)
    return row.value if row else DEFAULT_SETTINGS[key]


def set_setting(db: Session, key: str, value: str):
    if key not in DEFAULT_SETTINGS:
        raise ValueError(f"unknown setting {key}")
    row = db.get(m.Setting, key)
    if row: row.value = value
    else: db.add(m.Setting(key=key, value=value))


def seed_base(db: Session):
    if not db.query(m.User).count():
        for u, p, r in SEED_USERS:
            db.add(m.User(username=u, password_hash=hash_password(p), role=r))
    for s in SERVICES:
        if not db.query(m.Service).filter_by(name=s).first():
            db.add(m.Service(name=s, environment="sandbox"))
    db.flush()
    have = {(r.doc_id, r.version) for r in db.query(m.Runbook)}
    if True:
        for p in sorted((ROOT / "data" / "runbooks").glob("*.md")):
            meta = dict(l.split(": ", 1) for l in p.read_text(encoding="utf-8").split("---")[1].strip().splitlines())
            if (meta["doc_id"], int(meta["version"])) in have: continue
            title = re.search(r"^# (.+)$", p.read_text(encoding="utf-8"), re.M).group(1)
            db.add(m.Runbook(doc_id=meta["doc_id"], version=int(meta["version"]), title=title,
                             category=meta["category"], access=meta["access"], path=str(p.relative_to(ROOT))))
    db.commit()


OPERATIONAL = [m.ChatMessage, m.AuditEvent, m.WorkflowRun, m.Approval, m.Action, m.Investigation, m.Evidence, m.Alert, m.Incident]


def reset_operational(db: Session):
    for model in OPERATIONAL:
        db.execute(delete(model))
    db.commit()


def _alert_dict(a: m.Alert) -> dict:
    return {"metric": a.metric, "value": a.value}


def refresh_incident(db: Session, inc: m.Incident):
    alerts = db.scalars(select(m.Alert).where(m.Alert.incident_id == inc.id)).all()
    ad = [_alert_dict(a) for a in alerts]
    inc.severity, inc.category = incident_severity(ad), incident_category(ad)
    inc.opened_at = min(a.ts for a in alerts)
    uniq = sorted({a.metric for a in alerts})
    inc.title = f"{inc.service}: {', '.join(uniq)} alert{'s' if len(uniq) > 1 else ''}"
    dups = sum(a.is_duplicate for a in alerts)
    inc.summary = (f"{len(alerts)} alerts ({dups} duplicates) on {inc.service}; metrics: {', '.join(uniq)}; "
                   f"severity {inc.severity} by documented rules.")


def ingest_alert(db: Session, payload: dict, actor: str) -> tuple[m.Alert, m.Incident, bool]:
    """Validate -> fingerprint -> correlate into an open incident (same service, within window) or open one.
    Every source alert is preserved; duplicates are flagged, never dropped."""
    validate_alert(payload)
    ts = payload.get("ts") or datetime.utcnow()
    fp = f"{payload['service']}:{payload['metric']}"
    window = ts - timedelta(minutes=settings.CORRELATION_WINDOW_MIN)
    inc = db.scalars(select(m.Incident).where(m.Incident.service == payload["service"], m.Incident.status.in_(OPEN_STATES),
                                              m.Incident.opened_at >= window).order_by(m.Incident.id.desc())).first()
    created = inc is None
    if created:
        inc = m.Incident(title="pending", service=payload["service"], category="latency", severity="low",
                         status="open", opened_at=ts)
        db.add(inc); db.flush()
    dup = db.scalars(select(m.Alert.id).where(m.Alert.incident_id == inc.id, m.Alert.fingerprint == fp)).first() is not None
    alert = m.Alert(service=payload["service"], metric=payload["metric"], value=float(payload["value"]),
                    source=payload.get("source", "monitoring"), message=payload.get("message", ""),
                    fingerprint=fp, is_duplicate=dup, ts=ts, incident_id=inc.id, external_id=payload.get("external_id"))
    db.add(alert); db.flush()
    refresh_incident(db, inc)
    audit(db, actor, "alert_ingested", f"alert:{alert.id}", incident_id=inc.id,
          detail={"metric": alert.metric, "value": alert.value, "duplicate": dup, "incident_created": created})
    db.commit()
    return alert, inc, created


def inject_scenario(db: Session, sid: str, actor: str) -> m.Incident:
    sc = BY_ID[sid]
    now = datetime.utcnow()
    inc = None
    for a in sc["alerts"]:
        _, inc, _ = ingest_alert(db, {"service": sc["service"], "metric": a["metric"], "value": a["value"],
                                      "ts": now - timedelta(minutes=a["minutes_ago"]), "source": f"scenario:{sid}",
                                      "message": sc["name"]}, actor)
    inc.flags = dict(sc["flags"], scenario=sid)
    db.commit()
    return inc
