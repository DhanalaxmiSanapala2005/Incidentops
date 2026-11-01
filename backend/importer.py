"""Optional file import (xlsx / csv / json) with schema detection and row-level validation.
Nothing here is required to use the app: the demo loads bundled samples. Invalid rows are REPORTED, never silently dropped."""
import io, json
from datetime import datetime
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session
import re
from pathlib import Path
from agents import rag, soc
from . import models as m
from .core import audit, ingest_alert
from .redaction import redact
from .config import settings
from .rules import validate_alert
from integrations import client as ic

MAX_BYTES = 15 * 1024 * 1024; MAX_DESC = 1000; EXTS = {".xlsx", ".csv", ".json"}
SVC_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,79}$")
TELEMETRY = ("logs", "metrics", "traces", "deployments")
LOG_LEVELS = {"DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL"}
METRIC_COLS = ["cpu_pct", "memory_pct", "latency_p95_ms", "error_rate_pct", "availability_pct", "request_rate_rps"]
RANGES = {"cpu_pct": (0, 100), "memory_pct": (0, 100), "error_rate_pct": (0, 100), "availability_pct": (0, 100), "latency_p95_ms": (0, 3_600_000), "request_rate_rps": (0, 10_000_000)}
SECTIONS = ["Supported incident types", "Preconditions", "Investigation steps", "Approved remediation", "Required permission", "Risks and side effects", "Rollback procedure", "Verification criteria"]
SOC_REQUIRED = ["alert_id", "timestamp", "product", "alert_category", "title", "severity", "description"]
INFRA_REQUIRED = ["timestamp", "service_name", "metric_value"]
SEV = {"critical": "critical", "high": "high", "medium": "medium", "low": "low", "informational": "low", "info": "low"}
METRIC_ALIASES = {"cpu": "cpu", "high_cpu": "cpu", "cpu_usage": "cpu", "memory": "memory", "high_memory": "memory", "latency": "latency", "high_latency": "latency",
                  "latency_p95": "latency", "latency_p95_ms": "latency", "error_rate": "error_rate", "elevated_error_rate": "error_rate", "downtime": "downtime", "service_down": "downtime"}
REQUIREMENTS = [
    {"feature": "Demo mode (Load Demo Scenario)", "files": "None. Uses bundled synthetic scenarios, runbooks and the sample SOC alerts.", "required": "No"},
    {"feature": "Infrastructure alerts import", "files": "CSV/XLSX/JSON with: " + ", ".join(INFRA_REQUIRED) + ", metric_name or alert_type (cpu, memory, latency, error_rate, downtime)", "required": "Only if you upload"},
    {"feature": "Logs upload", "files": "CSV/XLSX/JSON with: timestamp, service_name, level, message (optional log_id, trace_id)", "required": "Only if you upload"},
    {"feature": "Metrics upload", "files": "CSV/XLSX/JSON with: timestamp, service_name and any of " + ", ".join(METRIC_COLS), "required": "Only if you upload"},
    {"feature": "Traces upload", "files": "CSV/XLSX/JSON with: trace_id, span_id, service_name, operation, start_time, duration_ms, status (optional parent_span_id, error_message)", "required": "Only if you upload"},
    {"feature": "Deployments upload", "files": "CSV/XLSX/JSON with: service_name, version, timestamp (optional change_type deploy|config, change_summary, deployed_by)", "required": "Only if you upload"},
    {"feature": "Runbook upload (admin)", "files": "Markdown (.md) with front matter doc_id, version, access and the standard sections", "required": "Only if you upload"},
    {"feature": "Resolved incidents upload (admin)", "files": "JSON or CSV with: title, symptoms, confirmed_root_cause, resolution (optional incident_id, access)", "required": "Only if you upload"},
    {"feature": "SOC alerts import", "files": "CSV/XLSX/JSON with: " + ", ".join(SOC_REQUIRED), "required": "Only if you upload"},
    {"feature": "SOC triage score", "files": "Optional feature columns (sign-in, IP, sandbox...) from the labelled file. Without them the app says the evidence is insufficient.", "required": "No"},
    {"feature": "Runbooks / RAG", "files": "data/runbooks/*.md (bundled, built from your SOC playbook). Add more .md files with the same front matter.", "required": "Bundled"},
    {"feature": "Dashboard, approvals, governance", "files": "None. Never needs the incident report or an evaluation workbook.", "required": "No"}]


def read_table(data: bytes, filename: str) -> tuple[pd.DataFrame, int]:
    ext = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in EXTS: raise ValueError(f"unsupported file type '{ext}'; use .xlsx, .csv or .json")
    if len(data) > MAX_BYTES: raise ValueError("file larger than 15 MB")
    try:
        if ext == ".csv": raw = pd.read_csv(io.BytesIO(data), header=None, dtype=object)
        elif ext == ".json": return pd.DataFrame(json.loads(data)), 0
        else:
            x = pd.ExcelFile(io.BytesIO(data)); sheet = next((s for s in x.sheet_names if s.lower() in ("alerts", "alert_ingestion_data")), x.sheet_names[0])
            raw = x.parse(sheet, header=None, dtype=object)
    except Exception as e: raise ValueError(f"could not read file: {str(e)[:120]}")
    for i in range(min(3, len(raw))):  # header row may follow a 'required Y/N' marker row
        vals = {str(v).strip() for v in raw.iloc[i].tolist()}
        if vals & {"alert_id", "service_name", "title"}:
            df = raw.iloc[i + 1:].copy(); df.columns = [str(c).strip() for c in raw.iloc[i]]; return df.reset_index(drop=True), i
    raise ValueError("no header row found (expected columns such as alert_id or service_name)")


def detect(df) -> str:
    c = set(df.columns)
    if {"trace_id", "span_id"} <= c: return "traces"
    if {"level", "message", "service_name"} <= c: return "logs"
    if {"version", "service_name", "timestamp"} <= c and "metric_value" not in c: return "deployments"
    if "service_name" in c and c & set(METRIC_COLS) and "metric_value" not in c and "alert_type" not in c: return "metrics"
    if {"title", "product", "alert_category"} <= c: return "soc"
    if "service_name" in c: return "infra"
    raise ValueError("unrecognised schema: need SOC columns (title, product, alert_category ...) or infra columns (service_name, metric_value ...)")


def _ts(v):
    t = pd.to_datetime(v, utc=True, errors="coerce")
    if pd.isna(t): raise ValueError("timestamp is not a valid date")
    return t.tz_convert(None).to_pydatetime()


def _svc(v):
    name = _num(v)
    if name is None: raise ValueError("service_name is required")
    name = str(name).strip()
    if not SVC_RE.match(name): raise ValueError("invalid service name (lowercase letters, digits and hyphens only)")
    return name


def _num(v): return None if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip().lower() in ("", "nan", "none") else v


def parse(df: pd.DataFrame, hdr: int, limit: int):
    kind = detect(df); req = SOC_REQUIRED if kind == "soc" else INFRA_REQUIRED
    missing = [c for c in req if c not in df.columns]
    if kind == "infra" and not ({"metric_name", "alert_type"} & set(df.columns)): missing.append("metric_name or alert_type")
    if missing: raise ValueError(f"missing required columns: {', '.join(missing)}")
    ok, bad = [], []
    for idx, r in df.iterrows():
        n = int(idx) + hdr + 2
        try:
            if kind == "soc":
                aid = str(_num(r["alert_id"]) or "").strip(); title = str(_num(r["title"]) or "").strip(); prod = str(_num(r["product"]) or "").strip()
                if not aid or not title or not prod: raise ValueError("alert_id, title and product are required")
                sev = SEV.get(str(r["severity"]).strip().lower())
                if not sev: raise ValueError(f"severity '{r['severity']}' not one of Critical/High/Medium/Low")
                feats = {}
                for c in soc.FEATURE_COLS:
                    v = _num(r.get(c))
                    if v is not None: feats[c] = str(v) if c in soc.MODEL["categorical"] else float(v)
                ok.append({"row": n, "alert_id": aid, "ts": _ts(r["timestamp"]), "product": prod, "title": title[:200], "category": str(_num(r["alert_category"]) or "")[:60],
                           "severity": sev, "description": str(_num(r["description"]) or "")[:1000], "src_incident": str(_num(r.get("incident_id")) or aid), "mitre": str(_num(r.get("mitre_techniques")) or ""),
                           "state": str(_num(r.get("investigation_state")) or "unknown"), "user": _num(r.get("affected_user")) or _num(r.get("recipient_email")), "device": _num(r.get("affected_device")),
                           "ip": _num(r.get("source_ip")), "features": feats})
            else:
                raw = str(_num(r.get("metric_name")) or _num(r.get("alert_type")) or "").strip().lower().replace(" ", "_")
                metric = METRIC_ALIASES.get(raw)
                if not metric: raise ValueError(f"metric '{raw}' not recognised")
                if "alert_id" in df.columns and not str(_num(r.get("alert_id")) or "").strip(): raise ValueError("alert_id missing")
                if "severity" in df.columns and _num(r.get("severity")) is not None and str(r["severity"]).strip().lower() not in SEV: raise ValueError(f"severity '{r['severity']}' not recognised")
                if len(str(_num(r.get("description")) or "")) > MAX_DESC: raise ValueError(f"description too long (max {MAX_DESC} characters)")
                val = float(r["metric_value"])
                if raw.endswith("_ms"): val /= 1000.0
                p = {"service": _svc(r["service_name"]), "metric": metric, "value": val, "ts": _ts(r["timestamp"]), "external_id": str(_num(r.get("alert_id")) or "") or None,
                     "source": str(_num(r.get("source_id")) or "import")[:40], "message": str(_num(r.get("description")) or "")[:500]}
                validate_alert(p); ok.append({"row": n, **p})
        except (ValueError, TypeError) as e: bad.append({"row": n, "reason": str(e)[:160]})
    if kind == "infra": ok.sort(key=lambda x: x["ts"])
    else:  # keep every alert type represented when limiting: round-robin by title
        groups = {}
        for x in ok: groups.setdefault(x["title"], []).append(x)
        picked = []
        while len(picked) < min(limit, len(ok)):
            for g in groups.values():
                if g and len(picked) < limit: picked.append(g.pop(0))
        ok = picked; return kind, ok, bad
    return kind, ok[:limit], bad


def parse_telemetry(kind, df, hdr):
    req = {"logs": ["timestamp", "service_name", "level", "message"], "metrics": ["timestamp", "service_name"], "deployments": ["service_name", "version", "timestamp"],
           "traces": ["trace_id", "span_id", "service_name", "operation", "start_time", "duration_ms", "status"]}[kind]
    missing = [c for c in req if c not in df.columns]
    if kind == "metrics" and not set(METRIC_COLS) & set(df.columns): missing.append("at least one metric column")
    if missing: raise ValueError(f"missing required columns: {', '.join(missing)}")
    ok, bad = [], []
    iso = lambda v: _ts(v).isoformat(timespec="seconds") + "Z"
    for idx, r in df.iterrows():
        n = int(idx) + hdr + 2
        try:
            row = {"service_name": _svc(r["service_name"])}
            if kind == "logs":
                lvl = str(_num(r["level"]) or "").upper(); msg = str(_num(r["message"]) or "").strip()
                if lvl not in LOG_LEVELS: raise ValueError(f"level '{r['level']}' not recognised")
                if not msg: raise ValueError("message is required")
                row.update(timestamp=iso(r["timestamp"]), level="WARN" if lvl == "WARNING" else lvl, message=msg[:2000], log_id=str(_num(r.get("log_id")) or f"UP-{n}"), trace_id=str(_num(r.get("trace_id")) or ""))
            elif kind == "metrics":
                row["timestamp"] = iso(r["timestamp"])
                for c in METRIC_COLS:
                    v = _num(r.get(c))
                    if v is None: continue
                    try: f = float(v)
                    except (TypeError, ValueError): raise ValueError(f"{c} must be numeric")
                    if not RANGES[c][0] <= f <= RANGES[c][1]: raise ValueError(f"{c} out of range")
                    row[c] = f
                if len(row) < 3: raise ValueError("row has no metric values")
            elif kind == "traces":
                try: dur = float(r["duration_ms"])
                except (TypeError, ValueError): raise ValueError("duration_ms must be numeric")
                st = str(_num(r["status"]) or "").lower()
                if dur < 0 or st not in ("ok", "error"): raise ValueError("duration_ms must be >= 0 and status ok or error")
                row.update(trace_id=str(r["trace_id"]), span_id=str(r["span_id"]), parent_span_id=str(_num(r.get("parent_span_id")) or ""), operation=str(r["operation"])[:200],
                           start_time=iso(r["start_time"]), duration_ms=dur, status=st, error_message=str(_num(r.get("error_message")) or "")[:300])
            else:
                ver = str(_num(r["version"]) or "").strip(); ct = str(_num(r.get("change_type")) or "deploy").lower()
                if not ver or ct not in ("deploy", "config"): raise ValueError("version is required and change_type must be deploy or config")
                row.update(version=ver, timestamp=iso(r["timestamp"]), change_type=ct, change_summary=str(_num(r.get("change_summary")) or "")[:300], deployed_by=str(_num(r.get("deployed_by")) or "unknown")[:60],
                           deployment_id=str(_num(r.get("deployment_id")) or f"UP-{n}"))
            ok.append(row)
        except (ValueError, TypeError) as e: bad.append({"row": n, "reason": str(e)[:160]})
    return ok, bad


def run_import(db: Session, data: bytes, filename: str, actor: str, limit: int = 100, dry_run: bool = False) -> dict:
    df, hdr = read_table(data, filename); kind = detect(df)
    if kind in TELEMETRY:
        rows, bad = parse_telemetry(kind, df, hdr)
        res = {"schema": kind, "rows_in_file": len(df), "valid": len(rows), "rejected": bad[:50], "rejected_count": len(bad), "dry_run": dry_run, "imported": 0, "skipped_existing": 0, "incident_ids": []}
        if dry_run or not rows: return res
        try: ic.admin("/admin/pack/upload", json={"kind": kind, "rows": rows}); res["imported"] = len(rows)
        except Exception as e: raise ValueError(f"monitoring service unreachable: {str(e)[:100]}")
        audit(db, actor, "data_imported", filename[:60], detail={"schema": kind, "imported": len(rows), "rejected_count": len(bad)}); db.commit(); return res
    kind, rows, bad = parse(df, hdr, limit)
    res = {"schema": kind, "rows_in_file": len(df), "valid": len(rows), "rejected": bad[:50], "rejected_count": len(bad), "dry_run": dry_run,
           "imported": 0, "skipped_existing": 0, "incident_ids": []}
    if dry_run: return res
    ids = set()
    if kind == "infra":
        for r in rows:
            _, inc, _ = ingest_alert(db, {k: r[k] for k in ("service", "metric", "value", "ts", "source", "message", "external_id")}, actor)
            inc.flags = {**(inc.flags or {}), "source": "import"}  # incidents from files use the imported/pack knowledge corpus
            ids.add(inc.id); res["imported"] += 1
    else:
        existing = set(db.scalars(select(m.Alert.fingerprint).where(m.Alert.source == "soc_import")))
        by_src = {}
        for r in rows:
            fp = f"soc:{r['alert_id']}"
            if fp in existing: res["skipped_existing"] += 1; continue
            inj = False
            desc, f1 = rag.sanitize(r["description"]); inj |= f1
            if r["src_incident"] in by_src: inc = by_src[r["src_incident"]]
            else:
                flags = {"soc": {**r["features"], "title": r["title"], "alert_id": r["alert_id"], "product": r["product"]}, "import": "soc", "injection_flagged": inj}
                inc = m.Incident(title=r["title"], service=r["product"], category="security", severity=r["severity"], status="open", summary=redact(desc)[0][:300],
                                 flags=flags, opened_at=r["ts"]); db.add(inc); db.flush(); by_src[r["src_incident"]] = inc
                ev = [("alert", f"siem:{r['alert_id']}", f"[{r['severity']}] {r['title']} ({r['product']} / {r['category']}). {desc} MITRE: {r['mitre'] or 'n/a'}. SIEM state: {r['state']}."),
                      ("identity", f"siem:{r['alert_id']}#identity", f"user={r['user']} device={r['device']} source_ip={r['ip']} role={r['features'].get('user_role', 'unknown')}")]
                if r["features"]: ev.append(("indicator", f"siem:{r['alert_id']}#indicators", json.dumps({k: v for k, v in r["features"].items()}, sort_keys=True)))
                for t, ref, txt in ev:
                    c, red = redact(txt); db.add(m.Evidence(incident_id=inc.id, type=t, source_ref=ref, ts=r["ts"], content=c, redacted=red))
            db.add(m.Alert(service=r["product"], metric="security", value=0.0, source="soc_import", message=redact(desc)[0], fingerprint=fp, is_duplicate=False, ts=r["ts"], incident_id=inc.id))
            res["imported"] += 1; ids.add(inc.id)
    res["incident_ids"] = sorted(ids)
    audit(db, actor, "data_imported", filename[:60], detail={k: res[k] for k in ("schema", "imported", "skipped_existing", "rejected_count")})
    db.commit(); return res


def import_runbook(db: Session, data: bytes, filename: str, actor: str) -> dict:
    """Admin upload of a versioned runbook (.md). Newer versions supersede older ones at retrieval time."""
    if not filename.lower().endswith(".md"): raise ValueError("runbooks must be .md files")
    if len(data) > 200_000: raise ValueError("runbook larger than 200 KB")
    try: text = data.decode("utf-8")
    except UnicodeDecodeError: raise ValueError("file is not UTF-8 text")
    parts = text.split("---", 2)
    if len(parts) < 3 or parts[0].strip(): raise ValueError("missing front matter (--- ... ---) with doc_id and version")
    meta = dict(l.split(": ", 1) for l in parts[1].strip().splitlines() if ": " in l)
    doc_id = meta.get("doc_id", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_\-]{0,39}", doc_id): raise ValueError("doc_id must be 1-40 letters, digits, - or _")
    try: version = int(meta.get("version", "")); assert version >= 1
    except Exception: raise ValueError("version must be a positive integer")
    access = meta.get("access", "engineer").strip()
    if access not in ("viewer", "engineer", "admin"): raise ValueError("access must be viewer, engineer or admin")
    body = parts[2].strip(); title = re.search(r"^# (.+)$", body, re.M)
    if not title: raise ValueError("runbook body needs a '# Title' heading")
    warnings = [f"missing section: {s}" for s in SECTIONS if f"## {s}" not in body]
    _, flagged = rag.sanitize(body)
    d = settings.UPLOAD_DIR / "runbooks"; d.mkdir(parents=True, exist_ok=True); path = d / f"{doc_id}_v{version}.md"; path.write_text(text, encoding="utf-8")
    if not db.scalar(select(m.Runbook).where(m.Runbook.doc_id == doc_id, m.Runbook.version == version)):
        db.add(m.Runbook(doc_id=doc_id, version=version, title=title.group(1)[:160], category=meta.get("category", "general")[:24], access=access, path=str(path)))
    audit(db, actor, "runbook_uploaded", f"{doc_id}@v{version}", detail={"access": access, "warnings": len(warnings), "injection_flagged": flagged}); db.commit()
    return {"doc_id": doc_id, "version": version, "access": access, "title": title.group(1), "warnings": warnings, "injection_flagged": flagged}


def import_resolved(db: Session, data: bytes, filename: str, actor: str) -> dict:
    """Admin upload of resolved incidents (.json list or .csv) used for similar-incident retrieval."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext not in ("json", "csv"): raise ValueError("resolved incidents must be .json or .csv")
    if len(data) > MAX_BYTES: raise ValueError("file larger than 15 MB")
    try: df = pd.DataFrame(json.loads(data)) if ext == "json" else pd.read_csv(io.BytesIO(data), dtype=object)
    except Exception as e: raise ValueError(f"could not read file: {str(e)[:100]}")
    need = ["title", "symptoms", "confirmed_root_cause", "resolution"]
    if [c for c in need if c not in df.columns]: raise ValueError(f"missing required columns: {', '.join(c for c in need if c not in df.columns)}")
    ok, bad = [], []
    for i, r in df.iterrows():
        try:
            vals = {c: str(_num(r[c]) or "").strip() for c in need}
            if not all(vals.values()): raise ValueError("title, symptoms, confirmed_root_cause and resolution are all required")
            iid = str(_num(r.get("incident_id")) or f"UP-{Path(filename).stem[:20]}-{i + 1}")
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_\-]{0,59}", iid): raise ValueError("incident_id has invalid characters")
            access = str(_num(r.get("access")) or "engineer")
            if access not in ("viewer", "engineer", "admin"): raise ValueError("access must be viewer, engineer or admin")
            ok.append({"incident_id": iid, "title": vals["title"][:160], **{k: vals[k][:600] for k in need[1:]}, "access": access, "version": 1})
        except ValueError as e: bad.append({"row": int(i) + 2, "reason": str(e)})
    if ok:
        d = settings.UPLOAD_DIR / "resolved"; d.mkdir(parents=True, exist_ok=True)
        (d / (re.sub(r"[^A-Za-z0-9_\-]", "_", Path(filename).stem)[:40] + ".json")).write_text(json.dumps(ok), encoding="utf-8")
        audit(db, actor, "resolved_incidents_uploaded", filename[:60], detail={"imported": len(ok), "rejected": len(bad)}); db.commit()
    return {"imported": len(ok), "rejected": bad[:50], "rejected_count": len(bad)}
