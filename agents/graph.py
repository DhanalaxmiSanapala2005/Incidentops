"""LangGraph workflow: triage -> investigate -> (retrieve -> plan -> verify -> propose | escalate) -> audit.
State is persisted to workflow_runs.state after every node; retries/timeouts are bounded."""
import json, logging, time
from datetime import datetime, timedelta
from typing import TypedDict
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select, update
from backend import models as m
from backend.core import audit, get_setting
from backend.redaction import redact
from backend.rules import incident_category, incident_severity, validate_action
from integrations import client as ic
from . import planner, rag, signals, soc


class WF(TypedDict, total=False):
    incident_id: int; service: str; severity: str; category: str; evidence: list; hypotheses: list
    runbooks: list; options: list; narrative: dict; notes: list; degraded: bool; no_evidence: bool
    metrics: dict; svc_state: dict; health: dict; primary: dict | None; llm_meta: dict


def run_workflow(db, inc: m.Incident, user: m.User) -> dict:
    run = m.WorkflowRun(incident_id=inc.id); db.add(run)
    audit(db, user.username, "investigation_started", f"incident:{inc.id}", incident_id=inc.id)
    db.commit()
    t0, steps = time.time(), []
    simulate = bool(inc.flags.get("simulate_llm_timeout"))

    def wrap(name, fn):
        def inner(state):
            s0 = time.time(); upd = fn(state)
            steps.append({"node": name, "ms": int((time.time() - s0) * 1000)})
            logging.getLogger("incidentops.agent").info(json.dumps({"event": "agent_node", "incident_id": inc.id, "node": name, "ms": steps[-1]["ms"]}))
            merged = {**state, **upd}
            run.state = {"steps": steps, "summary": {k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in merged.items()
                                                     if k in ("severity", "category", "evidence", "hypotheses", "runbooks", "options", "degraded", "no_evidence")}}
            db.commit(); return upd
        return inner

    # ---------------------------------------------------------------- nodes
    def triage(s):  # deterministic rules only
        if inc.category == "security":  # severity comes from the SIEM; deterministic infra thresholds do not apply
            inc.status = "investigating"
            audit(db, "agent:triage", "triaged", f"incident:{inc.id}", incident_id=inc.id, detail={"severity": inc.severity, "kind": "security"})
            return {"severity": inc.severity, "category": inc.category, "notes": [], "degraded": False}
        alerts = db.scalars(select(m.Alert).where(m.Alert.incident_id == inc.id)).all()
        ad = [{"metric": a.metric, "value": a.value} for a in alerts]
        inc.severity, inc.category, inc.status = incident_severity(ad), incident_category(ad), "investigating"
        notes = [] if alerts else ["no alerts attached to incident"]
        audit(db, "agent:triage", "triaged", f"incident:{inc.id}", incident_id=inc.id, detail={"severity": inc.severity, "alerts": len(alerts)})
        return {"severity": inc.severity, "category": inc.category, "notes": notes, "degraded": False}

    def investigate(s):  # read-only integration calls
        if inc.category == "security":  # evidence was stored at import; read it, never call infra telemetry
            ev = [{"id": r.id, "type": r.type, "source_ref": r.source_ref, "content": r.content, "redacted": r.redacted}
                  for r in db.scalars(select(m.Evidence).where(m.Evidence.incident_id == inc.id).order_by(m.Evidence.id))]
            hyps = soc.detect(inc.flags.get("soc", {}), ev)
            audit(db, "agent:log_investigation", "evidence_collected", f"incident:{inc.id}", incident_id=inc.id, detail={"evidence": len(ev), "hypotheses": len(hyps), "kind": "security"})
            return {"evidence": ev, "hypotheses": hyps, "notes": [], "degraded": False, "no_evidence": not ev, "metrics": {}, "svc_state": {}, "health": {}}
        svc, notes, got, degraded = inc.service, list(s["notes"]), {}, False
        at = inc.opened_at.isoformat()  # lets the monitoring service pick the matching time window
        for name, path in [("metrics", "metrics"), ("health", "health"), ("logs", "logs"), ("deployments", "deployments"), ("traces", "traces"), ("state", "state")]:
            try:
                got[name] = ic.get(f"/services/{svc}/{path}", at=at)
                if ic.LAST_ATTEMPTS > 1:
                    degraded = True; notes.append(f"{name} API needed {ic.LAST_ATTEMPTS} attempts (transient failure, retried)")
            except ic.IntegrationError as e:
                degraded = True; notes.append(f"{name} unavailable: {e}")
        ev, now = [], datetime.utcnow()

        def add(type_, ref, ts, content):
            text, red = redact(content)
            row = m.Evidence(incident_id=inc.id, type=type_, source_ref=ref, ts=ts, content=text, redacted=red)
            db.add(row); db.flush(); ev.append({"id": row.id, "type": type_, "source_ref": ref, "content": text, "redacted": red}); return row.id

        cur = got.get("metrics", {}).get("current", {})
        evid = {}
        if cur: evid["metric"] = add("metric", f"monitoring:/services/{svc}/metrics", now, json.dumps(cur))
        if got.get("health"): evid["health"] = add("health", f"monitoring:/services/{svc}/health", now, json.dumps({"status": got["health"]["status"]}))
        trs = []
        for t in got.get("traces", {}).get("traces", [])[:2]:
            eid = add("trace", f"monitoring:/services/{svc}/traces#{t['trace_id']}", now, json.dumps(t)); trs.append({**t, "ev_id": eid})
        deps = []
        for d in got.get("deployments", {}).get("deployments", [])[:3]:
            ts = datetime.fromisoformat(d["ts"])
            eid = add("deployment", f"deployments:{svc}@{d['version']}", ts, f"deployment v{d['version']} status={d['status']} by={d['by']}" + (f" summary={d['summary']}" if d.get("summary") else ""))
            deps.append({**d, "ts": ts, "ev_id": eid})
        logs = []
        for i, l in enumerate(got.get("logs", {}).get("logs", [])[-15:]):
            ts = datetime.fromisoformat(l["ts"])
            eid = add("log", f"logs:{svc}#{l.get('id') or 'L%d' % i}", ts, f"[{l['level']}] {l['msg']}")
            logs.append({"ts": ts, "level": l["level"], "msg": ev[-1]["content"], "ev_id": eid})
        no_ev = not cur and not logs
        hyps = [] if no_ev else signals.detect(svc, logs, cur, deps, got.get("health", {}), got.get("state", {}), inc.opened_at, trs, evid)
        if no_ev: notes.append("no metrics or logs retrievable: escalating without a diagnosis")
        audit(db, "agent:log_investigation", "evidence_collected", f"incident:{inc.id}", "degraded" if degraded else "ok", inc.id,
              {"evidence": len(ev), "hypotheses": len(hyps)})
        return {"evidence": ev, "hypotheses": hyps, "notes": notes, "degraded": degraded or s.get("degraded", False),
                "no_evidence": no_ev, "metrics": cur, "svc_state": got.get("state", {}), "health": got.get("health", {})}

    def retrieve(s):  # role-filtered RAG
        top_logs = " ".join(e["content"] for e in s["evidence"] if e["type"] == "log")[:400]
        terms = {"upstream_dependency": "third party dependency outage escalate", "transient": "flapping noisy alerts self resolving", "deploy_regression": "elevated error rate after a deployment",
                 "cert_expiry": "certificate expiry downtime", "config_flag": "configuration change feature flag", "cache_miss": "configuration change cache", "db_connection": "database connection pool exhaustion",
                 "oom": "memory exhaustion leak", "service_down": "service downtime crash loop", "cpu_saturation": "cpu saturation scale"}
        q = (f"{inc.title} {s['category']} {s['service']} " + " ".join(h["title"] + " " + h["signal"] + " " + terms.get(h["signal"], "") for h in s["hypotheses"]) + " " + top_logs
             + " " + " ".join(n_ for n_ in s["notes"] if "unavailable" in n_))
        pack_side = (inc.flags or {}).get("source") in ("import", "pack")
        res = rag.search(q, user.role, k=5, db=db, corpus={"pack"} if pack_side else {"legacy", "soc"})
        notes = list(s["notes"]) + [f"retrieved passage from {r['doc_id']} sanitised (possible prompt injection)" for r in res if r["injection_flagged"]]
        audit(db, "agent:runbook_retrieval", "runbooks_retrieved", f"incident:{inc.id}", incident_id=inc.id, detail={"docs": [f"{r['doc_id']}@v{r['version']}" for r in res]})
        return {"runbooks": res, "notes": notes}

    def plan(s):
        opts = planner.build_options(s["hypotheses"], s["runbooks"])
        blob = " ".join(e["content"] for e in s["evidence"])
        nar, meta, deg, note = planner.narrate(inc.summary, s["hypotheses"], s["runbooks"], blob, simulate)
        notes = list(s["notes"]) + ([note] if note else [])
        audit(db, "agent:remediation_planner", "plan_built", f"incident:{inc.id}", "degraded" if deg else "ok", inc.id, {"options": len(opts), "narrative": nar["source"]})
        return {"options": opts, "narrative": nar, "llm_meta": meta, "degraded": s.get("degraded", False) or deg, "notes": notes}

    def verify(s):  # deterministic gate: allowlist, params, evidence grounding
        notes, ids = list(s["notes"]), {e["id"] for e in s["evidence"]}
        for h in s["hypotheses"]:
            h["evidence_ids"] = [i for i in h["evidence_ids"] if i in ids]
            if not h["evidence_ids"]: h["uncertain"] = True; notes.append(f"{h['id']} has no supporting evidence; marked uncertain")
        services = {r.name for r in db.scalars(select(m.Service)).all() if r.environment == "sandbox"}
        versions = [e["source_ref"].split("@")[1] for e in s["evidence"] if e["type"] == "deployment"]
        primary = next((o for o in s["options"] if o["recommended"] and o["op"]), None)
        if primary:
            try: validate_action(primary["op"], primary["params"], services=services, versions=versions)
            except ValueError as e:
                notes.append(f"proposed action rejected by validation: {e}"); primary = None
        return {"primary": primary, "notes": notes}

    def propose(s):
        p = s["primary"]
        db.execute(update(m.Action).where(m.Action.incident_id == inc.id, m.Action.status == "pending").values(status="superseded"))
        ttl = int(get_setting(db, "approval_ttl_min"))
        h = next((x for x in s["hypotheses"] if x["id"] == p["hypothesis_id"]), {})
        just = f"{h.get('title', '')}. {s['narrative']['hypothesis_notes'].get(p['hypothesis_id'], '')} {s['narrative']['justification']} Runbook: {p['runbook']}."
        act = m.Action(incident_id=inc.id, op=p["op"], params=p["params"], justification=just.strip(), risk=p["risk"],
                       side_effects=p["side_effects"], rollback_plan=p["rollback_plan"], evidence_ids=p["evidence_ids"],
                       requested_by=user.username, expires_at=datetime.utcnow() + timedelta(minutes=ttl))
        db.add(act); db.flush(); inc.status = "awaiting_approval"
        audit(db, "agent:remediation_planner", "action_proposed", f"action:{act.id}", incident_id=inc.id, detail={"op": p["op"], "params": p["params"]})
        return {}

    def escalate(s):
        inc.status = "needs_human"
        audit(db, "agent:remediation_planner", "escalated_to_human", f"incident:{inc.id}", "needs_human", inc.id, {"notes": s["notes"]})
        return {"options": s.get("options") or planner.build_options([], []), "narrative": s.get("narrative") or {"source": "none", "summary": inc.summary, "hypothesis_notes": {}, "justification": "No safe automated action; engineer must investigate."}}

    def finish(s):
        inv = m.Investigation(incident_id=inc.id, degraded=s.get("degraded", False), hypotheses=s["hypotheses"], runbooks=s.get("runbooks", []),
                              options=s["options"], narrative=s["narrative"], notes=s["notes"])
        db.add(inv)
        meta = s.get("llm_meta") or {}
        run.tokens_in, run.tokens_out, run.cost_usd = meta.get("tokens_in", 0), meta.get("tokens_out", 0), meta.get("cost_usd", 0.0)
        audit(db, "agent:orchestrator", "investigation_completed", f"incident:{inc.id}", "degraded" if s.get("degraded") else "ok", inc.id, {"status": inc.status})
        return {}

    # ---------------------------------------------------------------- graph
    g = StateGraph(WF)
    for n, f in [("triage", triage), ("investigate", investigate), ("retrieve", retrieve), ("plan", plan), ("verify", verify),
                 ("propose", propose), ("escalate", escalate), ("audit", finish)]:
        g.add_node(n, wrap(n, f))
    g.add_edge(START, "triage"); g.add_edge("triage", "investigate")
    g.add_conditional_edges("investigate", lambda s: "escalate" if s.get("no_evidence") else "retrieve", {"escalate": "escalate", "retrieve": "retrieve"})
    g.add_edge("retrieve", "plan"); g.add_edge("plan", "verify")
    g.add_conditional_edges("verify", lambda s: "propose" if s.get("primary") else "escalate", {"propose": "propose", "escalate": "escalate"})
    g.add_edge("propose", "audit"); g.add_edge("escalate", "audit"); g.add_edge("audit", END)
    app = g.compile()
    try:
        final = app.invoke({"incident_id": inc.id, "service": inc.service, "notes": [], "evidence": [], "hypotheses": [], "runbooks": [], "options": []})
        run.status = "degraded" if final.get("degraded") else "completed"
    except Exception as e:  # never leave the incident in limbo
        db.rollback(); run = db.merge(run); inc = db.merge(inc)
        run.status, run.error, inc.status = "failed", str(e)[:400], "needs_human"
        audit(db, "agent:orchestrator", "investigation_failed", f"incident:{inc.id}", "failed", inc.id, {"error": str(e)[:400]})
        run.duration_s = round(time.time() - t0, 3); db.commit()
        return {"status": "failed", "error": str(e), "incident_status": inc.status}
    run.duration_s = round(time.time() - t0, 3); db.commit()
    return {"status": run.status, "incident_status": inc.status, "degraded": final.get("degraded", False), "notes": final.get("notes", []),
            "steps": steps, "hypotheses": final.get("hypotheses", []), "duration_s": run.duration_s}
