import json, logging, os, time, uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Literal
from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session
from . import core, importer, pack as pack_mod, models as m, reporting as rp, remediation
from .config import ROOT, settings
from .db import Base, SessionLocal, engine, get_db
from .redaction import redact
from .security import create_token, current_user, require_role, verify_password
from agents import chat as chat_agent, embeddings, llm as llm_mod, rag
from agents.graph import run_workflow
from data.scenarios import BY_ID, SCENARIOS
from integrations import client as ic


@asynccontextmanager
async def lifespan(_):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        core.seed_base(db)
    yield


app = FastAPI(title="IncidentOps AI API", version="1.0.0", lifespan=lifespan,
              description="Autonomous IT incident management: correlation, investigation, approval-gated remediation.")
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("incidentops")


@app.middleware("http")
async def structured_access_log(request: Request, call_next):
    """One JSON line per request with a correlation id. Query strings and bodies are never logged (may contain PII)."""
    rid, t0 = uuid.uuid4().hex[:12], time.time()
    resp = await call_next(request)
    resp.headers["X-Request-ID"] = rid
    log.info(json.dumps({"event": "http", "request_id": rid, "method": request.method, "path": request.url.path, "status": resp.status_code, "ms": int((time.time() - t0) * 1000)}))
    return resp


class Login(BaseModel): username: str; password: str
class AlertIn(BaseModel):
    service: str = Field(min_length=1, max_length=80)
    metric: Literal["cpu", "memory", "latency", "error_rate", "downtime"]
    value: float = Field(ge=0)
    source: str = "monitoring"
    message: str = ""
    ts: datetime | None = None
class Decision(BaseModel): comment: str = ""
class RoleIn(BaseModel): role: Literal["viewer", "engineer", "admin"]
class SettingIn(BaseModel): key: str; value: str


def get_inc(db, id) -> m.Incident:
    inc = db.get(m.Incident, id)
    if not inc: raise HTTPException(404, "incident not found")
    return inc


@app.get("/health")
def health(): return {"status": "ok"}


@app.post("/auth/login")
def login(b: Login, db: Session = Depends(get_db)):
    u = db.query(m.User).filter_by(username=b.username, active=True).first()
    if not u or not verify_password(b.password, u.password_hash):
        core.audit(db, b.username[:60], "login", outcome="denied"); db.commit()
        raise HTTPException(401, "invalid username or password")
    core.audit(db, u.username, "login"); db.commit()
    return {"access_token": create_token(u), "token_type": "bearer", "username": u.username, "role": u.role}


@app.get("/me")
def me(u: m.User = Depends(current_user)): return {"username": u.username, "role": u.role}


# ------------------------------------------------------------------ alerts & incidents
@app.post("/alerts", status_code=201)
def post_alert(a: AlertIn, u: m.User = Depends(require_role("engineer")), db: Session = Depends(get_db)):
    try: alert, inc, created = core.ingest_alert(db, a.model_dump(exclude_none=True), u.username)
    except ValueError as e: raise HTTPException(422, str(e))
    return {"alert_id": alert.id, "incident_id": inc.id, "incident_ref": rp.iid(inc.id), "incident_created": created, "duplicate": alert.is_duplicate, "severity": inc.severity}


@app.get("/alerts")
def list_alerts(service: str | None = None, metric: str | None = None, limit: int = 200, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(m.Alert).order_by(m.Alert.ts.desc()).limit(limit)
    if service: q = q.where(m.Alert.service == service)
    if metric: q = q.where(m.Alert.metric == metric)
    return [{"id": a.id, "service": a.service, "metric": a.metric, "value": a.value, "ts": rp.iso(a.ts), "incident": rp.iid(a.incident_id) if a.incident_id else None,
             "duplicate": a.is_duplicate, "source": a.source, "external_id": a.external_id, "incident_id": a.incident_id} for a in db.scalars(q)]


@app.get("/incidents")
def list_incidents(status: str | None = None, severity: str | None = None, service: str | None = None, q: str | None = None,
                   _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    st = select(m.Incident).order_by(m.Incident.id.desc())
    if status: st = st.where(m.Incident.status == status)
    if severity: st = st.where(m.Incident.severity == severity)
    if service: st = st.where(m.Incident.service == service)
    if q: st = st.where(m.Incident.title.ilike(f"%{q}%") | m.Incident.summary.ilike(f"%{q}%"))
    return [rp.incident_dict(i) for i in db.scalars(st)]


@app.get("/incidents/{id}")
def incident(id: int, _: m.User = Depends(current_user), db: Session = Depends(get_db)): return rp.incident_detail(db, get_inc(db, id))


@app.get("/incidents/{id}/metrics")
def incident_metrics(id: int, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    inc = get_inc(db, id)
    if inc.category == "security": raise HTTPException(404, "no infrastructure metrics for security alerts")
    try: return ic.get(f"/services/{inc.service}/metrics")
    except ic.IntegrationError as e: raise HTTPException(502, str(e))


@app.post("/incidents/{id}/investigate")
def investigate(id: int, u: m.User = Depends(require_role("engineer")), db: Session = Depends(get_db)):
    inc = get_inc(db, id)
    if inc.status in ("resolved", "remediating"): raise HTTPException(409, f"incident is {inc.status}")
    return run_workflow(db, inc, u)


def _background_investigation(incident_id: int, username: str):
    """In-process worker: own DB session, state persisted in workflow_runs, failures end as needs_human (see run_workflow)."""
    db = SessionLocal()
    try:
        inc, user = db.get(m.Incident, incident_id), db.scalars(select(m.User).where(m.User.username == username)).first()
        if inc and user: run_workflow(db, inc, user)
    except Exception as e:
        log.error(json.dumps({"event": "background_investigation_failed", "incident_id": incident_id, "error": str(e)[:200]}))
    finally: db.close()


@app.post("/incidents/{id}/investigate/async", status_code=202)
def investigate_async(id: int, bg: BackgroundTasks, u: m.User = Depends(require_role("engineer")), db: Session = Depends(get_db)):
    inc = get_inc(db, id)
    if inc.status in ("resolved", "remediating"): raise HTTPException(409, f"incident is {inc.status}")
    busy = db.scalars(select(m.WorkflowRun).where(m.WorkflowRun.incident_id == id, m.WorkflowRun.status == "running",
                                                   m.WorkflowRun.started_at > datetime.utcnow() - timedelta(minutes=10))).first()
    if busy: raise HTTPException(409, "an investigation is already running for this incident")
    core.audit(db, u.username, "investigation_queued", f"incident:{id}", incident_id=id); db.commit()
    bg.add_task(_background_investigation, id, u.username)
    return {"queued": True, "incident_id": id, "poll": f"/incidents/{id}/run"}


@app.get("/incidents/{id}/run")
def latest_run(id: int, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    get_inc(db, id)
    r = db.scalars(select(m.WorkflowRun).where(m.WorkflowRun.incident_id == id).order_by(m.WorkflowRun.id.desc())).first()
    if not r: return {"status": "none"}
    return {"status": r.status, "duration_s": r.duration_s, "error": r.error, "steps": (r.state or {}).get("steps", []), "tokens_in": r.tokens_in, "tokens_out": r.tokens_out, "cost_usd": r.cost_usd}


@app.get("/incidents/{id}/report", response_class=PlainTextResponse)
def report(id: int, u: m.User = Depends(current_user), db: Session = Depends(get_db)):
    inc = get_inc(db, id); core.audit(db, u.username, "report_exported", f"incident:{id}", incident_id=id); db.commit()
    return rp.build_report(db, inc)


# ------------------------------------------------------------------ approvals & actions
@app.get("/actions")
def list_actions(status: str | None = None, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    db.execute(update(m.Action).where(m.Action.status == "pending", m.Action.expires_at <= now).values(status="expired")); db.commit()
    st = select(m.Action).order_by(m.Action.id.desc())
    if status: st = st.where(m.Action.status == status)
    return [rp.action_dict(a) for a in db.scalars(st)]


def _decide(id: int, decision: str, body: Decision, u: m.User, db: Session):
    act = db.get(m.Action, id)
    if not act: raise HTTPException(404, "action not found")
    if core.get_setting(db, "require_separation_of_duties") == "true" and act.requested_by == u.username:
        raise HTTPException(403, "separation of duties: the requester cannot decide their own action")
    claim = db.execute(update(m.Action).where(m.Action.id == id, m.Action.status == "pending", m.Action.expires_at > datetime.utcnow())
                       .values(status="approved" if decision == "approved" else "rejected"))
    db.commit()
    if claim.rowcount != 1:
        db.refresh(act)
        if act.status == "pending": act.status = "expired"; db.commit()
        raise HTTPException(409, f"action is '{act.status}' and can no longer be decided")
    db.add(m.Approval(action_id=id, approver=u.username, decision=decision, comment=body.comment))
    core.audit(db, u.username, f"action_{decision}", f"action:{id}", incident_id=act.incident_id, detail={"op": act.op, "params": act.params, "comment": body.comment})
    if decision == "rejected":
        inc = db.get(m.Incident, act.incident_id); inc.status = "open"; inc.outcome = "rejected_by_engineer"
    db.commit()
    if decision == "approved":
        try: remediation.execute_action(db, id, u.username)
        except remediation.ExecutionError as e: raise HTTPException(409, str(e))
    db.refresh(act)
    return rp.action_dict(act)


@app.post("/actions/{id}/approve")
def approve(id: int, b: Decision = Decision(), u: m.User = Depends(require_role("engineer")), db: Session = Depends(get_db)): return _decide(id, "approved", b, u, db)


@app.post("/actions/{id}/reject")
def reject(id: int, b: Decision = Decision(), u: m.User = Depends(require_role("engineer")), db: Session = Depends(get_db)): return _decide(id, "rejected", b, u, db)


# ------------------------------------------------------------------ reference data, dashboard, scenarios
@app.get("/services")
def services(_: m.User = Depends(current_user), db: Session = Depends(get_db)):
    open_ = {i.service for i in db.scalars(select(m.Incident).where(m.Incident.status.not_in(["resolved"])))}
    return [{"name": s.name, "environment": s.environment, "owner": s.owner, "open_incident": s.name in open_} for s in db.scalars(select(m.Service))]


@app.get("/runbooks")
def runbooks(u: m.User = Depends(current_user), db: Session = Depends(get_db)):
    from .security import RANK
    return [{"doc_id": r.doc_id, "version": r.version, "title": r.title, "category": r.category, "access": r.access}
            for r in db.scalars(select(m.Runbook)) if RANK[u.role] >= RANK[r.access]]


@app.get("/dashboard")
def dashboard(_: m.User = Depends(current_user), db: Session = Depends(get_db)): return rp.dashboard(db)


SAMPLES = {"soc_real": ("real_alerts.xlsx", 17), "soc_labelled": ("synthetic_labelled_sample.csv", 34), "infra_template": ("../templates/alerts_infra_template.csv", 100)}


@app.get("/import/requirements")
def import_requirements(_: m.User = Depends(current_user)): return importer.REQUIREMENTS


@app.post("/import/alerts")
def import_alerts(file: UploadFile = File(...), limit: int = 100, dry_run: bool = False, u: m.User = Depends(require_role("engineer")), db: Session = Depends(get_db)):
    if not 1 <= limit <= 500: raise HTTPException(422, "limit must be between 1 and 500")
    data = file.file.read(importer.MAX_BYTES + 1)
    try: return importer.run_import(db, data, file.filename or "upload", u.username, limit, dry_run)
    except ValueError as e: raise HTTPException(422, str(e))


@app.post("/import/file")
def import_file(file: UploadFile = File(...), limit: int = 100, dry_run: bool = False, u: m.User = Depends(require_role("engineer")), db: Session = Depends(get_db)):
    return import_alerts(file, limit, dry_run, u, db)


def _try_reindex(db):
    if not embeddings.enabled(): return "embeddings off; keyword retrieval only"
    try: return f"indexed {rag.reindex(db)['embedded_now']} new chunks"
    except embeddings.EmbeddingUnavailable as e: return f"embedding failed; keyword retrieval used ({str(e)[:100]})"


@app.post("/import/runbook")
def upload_runbook(file: UploadFile = File(...), u: m.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    try: res = importer.import_runbook(db, file.file.read(300_000), file.filename or "upload.md", u.username)
    except ValueError as e: raise HTTPException(422, str(e))
    return {**res, "index": _try_reindex(db)}


@app.post("/import/resolved")
def upload_resolved(file: UploadFile = File(...), u: m.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    try: res = importer.import_resolved(db, file.file.read(importer.MAX_BYTES + 1), file.filename or "upload.json", u.username)
    except ValueError as e: raise HTTPException(422, str(e))
    return {**res, "index": _try_reindex(db) if res["imported"] else "nothing imported"}


@app.post("/pack/load")
def pack_load(reset: bool = False, u: m.User = Depends(require_role("engineer")), db: Session = Depends(get_db)):
    """Load the bundled demo pack (12 scenarios as files). reset=true (admin) clears operational data first."""
    if reset:
        if u.role != "admin": raise HTTPException(403, "only an admin can reset before loading")
        core.reset_operational(db)
    try: return pack_mod.load_pack(db, u.username)
    except FileNotFoundError as e: raise HTTPException(404, str(e))
    except ic.IntegrationError as e: raise HTTPException(502, str(e))
    except Exception as e:
        if "ConnectError" in type(e).__name__ or "HTTPStatus" in type(e).__name__: raise HTTPException(502, f"monitoring service unreachable: {str(e)[:100]}")
        raise


@app.get("/pack/status")
def pack_status(_: m.User = Depends(current_user), db: Session = Depends(get_db)):
    return {"available": pack_mod.available(), "incidents_loaded": len(pack_mod.loaded(db))}


@app.get("/admin/rag/status")
def rag_status(_: m.User = Depends(require_role("admin")), db: Session = Depends(get_db)): return rag.status(db)


@app.post("/admin/rag/reindex")
def rag_reindex(_: m.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    try: return rag.reindex(db)
    except embeddings.EmbeddingUnavailable as e: raise HTTPException(503, f"embeddings unavailable: {e}")


@app.get("/admin/llm/status")
def llm_status(_: m.User = Depends(require_role("admin"))): return llm_mod.status()


@app.post("/admin/llm/test")
def llm_test(_: m.User = Depends(require_role("admin"))):
    out = {}
    try: _, meta = llm_mod.complete_json('Reply only with JSON {"ok": true}', "ping"); out["chat"] = {"ok": True, "latency_s": meta.get("latency_s"), "tokens": meta.get("tokens_in", 0) + meta.get("tokens_out", 0), "provider": meta["provider"]}
    except llm_mod.LLMUnavailable as e: out["chat"] = {"ok": False, "error": str(e)[:160]}
    try: out["embeddings"] = {"ok": True, "dims": len(embeddings.embed(["ping"])[0]), "model": settings.EMBED_MODEL}
    except embeddings.EmbeddingUnavailable as e: out["embeddings"] = {"ok": False, "error": str(e)[:160]}
    return out


@app.post("/import/sample/{name}")
def import_sample(name: str, limit: int | None = None, u: m.User = Depends(require_role("engineer")), db: Session = Depends(get_db)):
    if name not in SAMPLES: raise HTTPException(404, f"unknown sample; choose one of {sorted(SAMPLES)}")
    fn, default = SAMPLES[name]; path = ROOT / "data" / "samples" / fn
    return importer.run_import(db, path.read_bytes(), path.name, u.username, limit or default)


@app.get("/scenarios")
def scenarios(_: m.User = Depends(current_user)):
    return [{k: s[k] for k in ("id", "name", "service", "category", "description", "expect")} for s in SCENARIOS]


@app.post("/scenarios/{sid}/inject")
def inject(sid: str, u: m.User = Depends(require_role("engineer")), db: Session = Depends(get_db)):
    if sid not in BY_ID: raise HTTPException(404, "unknown scenario")
    ic.admin(f"/admin/reset?service={BY_ID[sid]['service']}")  # reproducible: re-seed this service's world
    inc = core.inject_scenario(db, sid, u.username)
    return rp.incident_dict(inc)


# ------------------------------------------------------------------ admin
@app.get("/admin/audit")
def audit_log(event_type: str | None = None, limit: int = 300, _: m.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    q = select(m.AuditEvent).order_by(m.AuditEvent.id.desc()).limit(limit)
    if event_type: q = q.where(m.AuditEvent.event_type == event_type)
    return [{"id": e.id, "ts": rp.iso(e.ts), "actor": e.actor, "event": e.event_type, "target": e.target, "outcome": e.outcome,
             "incident": rp.iid(e.incident_id) if e.incident_id else None, "detail": e.detail} for e in db.scalars(q)]


@app.get("/admin/users")
def users(_: m.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return [{"id": u.id, "username": u.username, "role": u.role, "active": u.active} for u in db.scalars(select(m.User))]


@app.put("/admin/users/{id}/role")
def set_role(id: int, b: RoleIn, a: m.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    u = db.get(m.User, id)
    if not u: raise HTTPException(404, "user not found")
    if u.id == a.id: raise HTTPException(409, "you cannot change your own role")
    old, u.role = u.role, b.role
    core.audit(db, a.username, "role_changed", f"user:{u.username}", detail={"from": old, "to": b.role}); db.commit()
    return {"id": u.id, "username": u.username, "role": u.role}


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    incident_id: int | None = None


@app.post("/chat")
def chat(body: ChatIn, u: m.User = Depends(current_user), db: Session = Depends(get_db)):
    """Read-only incident assistant. Any signed-in role may ask; answers never trigger changes."""
    text = body.message.strip()
    if not text: raise HTTPException(422, "message is empty")
    recent = db.scalar(select(func.count()).select_from(m.ChatMessage).where(m.ChatMessage.user_id == u.id, m.ChatMessage.role == "user",
                                                                           m.ChatMessage.created_at > m.utcnow() - timedelta(minutes=1)))
    if recent >= 20: raise HTTPException(429, "too many messages; wait a minute and try again")
    res = chat_agent.answer(db, u, text, body.incident_id)
    iid = res["incident_id"]
    db.add(m.ChatMessage(user_id=u.id, incident_id=iid, role="user", content=redact(text)[0][:500], meta={}))
    db.add(m.ChatMessage(user_id=u.id, incident_id=iid, role="assistant", content=res["text"], meta={k: res[k] for k in ("intent", "citations", "suggestions", "source")}))
    lm = res["llm_meta"]
    core.audit(db, u.username, "chat_query", f"incident:{iid}" if iid else "portfolio", outcome="blocked" if res["intent"] == "refused" else "ok", incident_id=iid,
               detail={"intent": res["intent"], "source": res["source"], "tokens_in": lm.get("tokens_in", 0), "tokens_out": lm.get("tokens_out", 0)})
    db.commit()
    return {"answer": res["text"], **{k: res[k] for k in ("intent", "citations", "suggestions", "source", "incident_id")}}


@app.get("/chat/history")
def chat_history(incident_id: int | None = None, limit: int = Query(50, ge=1, le=200), u: m.User = Depends(current_user), db: Session = Depends(get_db)):
    """Only the caller's own messages, for one incident (or the no-incident conversation)."""
    q = select(m.ChatMessage).where(m.ChatMessage.user_id == u.id, m.ChatMessage.incident_id == incident_id if incident_id else m.ChatMessage.incident_id.is_(None))
    rows = list(reversed(db.scalars(q.order_by(m.ChatMessage.id.desc()).limit(limit)).all()))
    return [{"id": r.id, "role": r.role, "content": r.content, "meta": r.meta, "created_at": r.created_at.isoformat()} for r in rows]


@app.delete("/chat/history")
def clear_chat_history(u: m.User = Depends(current_user), db: Session = Depends(get_db)):
    n = db.execute(delete(m.ChatMessage).where(m.ChatMessage.user_id == u.id)).rowcount; db.commit()
    return {"deleted": n}


@app.get("/admin/settings")
def get_settings(_: m.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return {**{k: core.get_setting(db, k) for k in core.DEFAULT_SETTINGS}, "llm_provider": settings.LLM_PROVIDER, "database": engine.url.get_backend_name(),
            "tracing": "langsmith" if os.getenv("LANGSMITH_TRACING", "").lower() == "true" and os.getenv("LANGSMITH_API_KEY") else "disabled",
            "trace_inputs_hidden": os.getenv("LANGSMITH_HIDE_INPUTS", "true").lower() == "true"}


@app.put("/admin/settings")
def put_settings(b: SettingIn, a: m.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    try: core.set_setting(db, b.key, b.value)
    except ValueError as e: raise HTTPException(422, str(e))
    core.audit(db, a.username, "setting_changed", b.key, detail={"value": b.value}); db.commit()
    return {b.key: b.value}


@app.post("/admin/reset")
def reset(a: m.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    core.reset_operational(db); ic.admin("/admin/reset")
    core.audit(db, a.username, "environment_reset"); db.commit()
    return {"status": "reset"}
