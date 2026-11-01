"""Serialisers, timelines, post-incident report (Markdown) and dashboard metrics."""
import math
from collections import Counter
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import models as m


def iso(d): return d.isoformat(timespec="seconds") + "Z" if d else None
def iid(i): return f"INC-{i:04d}"


def pct(vals, p):
    if not vals: return 0.0
    s = sorted(vals); return round(s[max(0, math.ceil(p / 100 * len(s)) - 1)], 3)


def incident_dict(i: m.Incident) -> dict:
    return {"id": i.id, "ref": iid(i.id), "title": i.title, "service": i.service, "category": i.category, "severity": i.severity,
            "status": i.status, "summary": i.summary, "outcome": i.outcome, "flags": i.flags, "opened_at": iso(i.opened_at), "resolved_at": iso(i.resolved_at)}


def action_dict(a: m.Action) -> dict:
    return {"id": a.id, "incident_id": a.incident_id, "incident_ref": iid(a.incident_id), "op": a.op, "params": a.params, "justification": a.justification,
            "risk": a.risk, "side_effects": a.side_effects, "rollback_plan": a.rollback_plan, "evidence_ids": a.evidence_ids, "status": a.status,
            "requested_by": a.requested_by, "created_at": iso(a.created_at), "expires_at": iso(a.expires_at), "executed_at": iso(a.executed_at),
            "result": a.result, "verification": a.verification}


def timeline(db: Session, inc: m.Incident) -> list[dict]:
    ev = [{"ts": iso(a.ts), "kind": "alert", "actor": a.source, "text": f"{a.metric}={a.value}" + (" (duplicate)" if a.is_duplicate else "")}
          for a in db.scalars(select(m.Alert).where(m.Alert.incident_id == inc.id))]
    ev += [{"ts": iso(e.ts), "kind": e.event_type, "actor": e.actor, "text": f"{e.event_type.replace('_', ' ')} [{e.outcome}]"}
           for e in db.scalars(select(m.AuditEvent).where(m.AuditEvent.incident_id == inc.id)) if e.event_type != "alert_ingested"]
    return sorted(ev, key=lambda x: x["ts"])


def incident_detail(db: Session, inc: m.Incident) -> dict:
    inv = db.scalars(select(m.Investigation).where(m.Investigation.incident_id == inc.id).order_by(m.Investigation.id.desc())).first()
    return {**incident_dict(inc),
            "alerts": [{"id": a.id, "metric": a.metric, "value": a.value, "ts": iso(a.ts), "duplicate": a.is_duplicate, "source": a.source}
                       for a in db.scalars(select(m.Alert).where(m.Alert.incident_id == inc.id).order_by(m.Alert.ts))],
            "evidence": [{"id": e.id, "type": e.type, "source_ref": e.source_ref, "ts": iso(e.ts), "content": e.content, "redacted": e.redacted}
                         for e in db.scalars(select(m.Evidence).where(m.Evidence.incident_id == inc.id).order_by(m.Evidence.id))],
            "investigation": None if not inv else {"degraded": inv.degraded, "hypotheses": inv.hypotheses, "runbooks": inv.runbooks, "options": inv.options,
                                                   "narrative": inv.narrative, "notes": inv.notes, "created_at": iso(inv.created_at)},
            "actions": [action_dict(a) for a in db.scalars(select(m.Action).where(m.Action.incident_id == inc.id).order_by(m.Action.id))],
            "timeline": timeline(db, inc)}


def build_report(db: Session, inc: m.Incident) -> str:
    d = incident_detail(db, inc); inv = d["investigation"] or {}
    mttr = f"{(inc.resolved_at - inc.opened_at).total_seconds() / 60:.1f} min" if inc.resolved_at else "n/a (unresolved)"
    L = [f"# Post-incident report: {d['ref']} {d['title']}", "",
         f"- **Service:** {inc.service}  \n- **Severity:** {inc.severity}  \n- **Status:** {inc.status}  \n- **Outcome:** {inc.outcome or 'open'}  \n- **MTTR:** {mttr}", "",
         "## Summary", inv.get("narrative", {}).get("summary", inc.summary), "", "## Alerts"]
    L += [f"- {a['ts']} {a['metric']}={a['value']} ({a['source']}){' duplicate' if a['duplicate'] else ''}" for a in d["alerts"]]
    L += ["", "## Root-cause hypotheses (evidence-backed)"]
    for h in inv.get("hypotheses", []):
        L.append(f"- **{h['id']} {h['title']}** (confidence {h['confidence']}{', UNCERTAIN' if h['uncertain'] else ''}); evidence ids {h['evidence_ids']}. {h['explanation']}")
    L += ["", "## Runbooks used"] + [f"- {r['doc_id']}@v{r['version']} {r['section']} (score {r['score']})" for r in inv.get("runbooks", [])]
    L += ["", "## Actions"]
    for a in d["actions"]:
        L.append(f"- Action #{a['id']} `{a['op']}` {a['params']} -> **{a['status']}**; risk {a['risk']}; verification: {a['verification'].get('checks', a['verification'])}")
        if a["result"].get("recovery"): L.append(f"  - recovery: {a['result']['recovery']}")
    L += ["", "## Approvals"]
    for ap in db.scalars(select(m.Approval).join(m.Action, m.Action.id == m.Approval.action_id).where(m.Action.incident_id == inc.id)):
        L.append(f"- {iso(ap.decided_at)} {ap.approver}: {ap.decision} {('- ' + ap.comment) if ap.comment else ''}")
    L += ["", "## Timeline"] + [f"- {t['ts']} [{t['actor']}] {t['text']}" for t in d["timeline"]]
    if inv.get("notes"): L += ["", "## Limitations / notes"] + [f"- {n}" for n in inv["notes"]]
    return "\n".join(L) + "\n"


def dashboard(db: Session) -> dict:
    incs = db.scalars(select(m.Incident)).all(); runs = db.scalars(select(m.WorkflowRun)).all()
    res = [i for i in incs if i.resolved_at]
    mttr = round(sum((i.resolved_at - i.opened_at).total_seconds() for i in res) / len(res) / 60, 2) if res else 0.0
    done = [r.duration_s for r in runs if r.status != "running"]
    fp = Counter(a.fingerprint for a in db.scalars(select(m.Alert)))
    acts = Counter(a.status for a in db.scalars(select(m.Action)))
    return {"total_incidents": len(incs), "open": sum(i.status not in ("resolved",) for i in incs),
            "awaiting_approval": sum(i.status == "awaiting_approval" for i in incs), "resolved": len(res), "escalated": sum(i.status in ("escalated", "needs_human") for i in incs),
            "mttr_min": mttr, "by_severity": dict(Counter(i.severity for i in incs)), "by_status": dict(Counter(i.status for i in incs)),
            "repeated_alerts": [{"fingerprint": k, "count": v} for k, v in fp.most_common(8) if v > 1], "action_outcomes": dict(acts),
            "workflow": {"runs": len(runs), "p50_s": pct(done, 50), "p95_s": pct(done, 95),
                         "error_rate": round(sum(r.status == "failed" for r in runs) / len(runs), 3) if runs else 0.0,
                         "degraded_rate": round(sum(r.status == "degraded" for r in runs) / len(runs), 3) if runs else 0.0,
                         "tokens_in": sum(r.tokens_in for r in runs), "tokens_out": sum(r.tokens_out for r in runs),
                         "avg_cost_usd": round(sum(r.cost_usd for r in runs) / len(runs), 5) if runs else 0.0,
                         "recent": [{"id": r.id, "incident": iid(r.incident_id), "status": r.status, "duration_s": r.duration_s, "tokens": r.tokens_in + r.tokens_out}
                                    for r in sorted(runs, key=lambda r: -r.id)[:15]]}}
