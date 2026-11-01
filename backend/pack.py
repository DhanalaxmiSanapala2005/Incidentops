"""Load the bundled incident data pack: services, runbook rows, mock telemetry, alerts (correlated into incidents) and the RAG index."""
import csv
from sqlalchemy import select
from sqlalchemy.orm import Session
from agents import embeddings, rag
from . import importer, models as m
from .config import ROOT
from .core import audit
from integrations import client as ic

PACK = ROOT / "data" / "pack"


def available() -> bool: return (PACK / "alerts" / "alerts.csv").exists()


def loaded(db: Session) -> list[int]:
    ids = db.scalars(select(m.Alert.incident_id).where(m.Alert.external_id.like("AL-%")).distinct()).all()
    return sorted(i for i in ids if i)


def load_pack(db: Session, actor: str) -> dict:
    if not available(): raise FileNotFoundError("data/pack is missing; copy the incident data pack to data/pack")
    existing = loaded(db)
    for r in csv.DictReader(open(PACK / "reference" / "services.csv", encoding="utf-8")):
        if not db.scalar(select(m.Service).where(m.Service.name == r["service_name"])): db.add(m.Service(name=r["service_name"], environment="sandbox", owner=r["owner_team"]))
    for p in sorted((PACK / "knowledge" / "runbooks").glob("*.md")):
        meta = dict(l.split(": ", 1) for l in p.read_text(encoding="utf-8").split("---")[1].strip().splitlines() if ": " in l)
        if not db.scalar(select(m.Runbook).where(m.Runbook.doc_id == meta["doc_id"], m.Runbook.version == int(meta["version"]))):
            db.add(m.Runbook(doc_id=meta["doc_id"], version=int(meta["version"]), title=meta.get("title", meta["doc_id"])[:160], category=meta.get("category", "general")[:24],
                             access=meta.get("access", "engineer"), path=str(p.relative_to(ROOT))))
    db.commit()
    mock = ic.admin("/admin/pack/load")
    res = {"already_loaded": bool(existing), "incident_ids": existing, "alerts_imported": 0, "rejected": 0, "mock": mock}
    if not existing:
        r = importer.run_import(db, (PACK / "alerts" / "alerts.csv").read_bytes(), "alerts.csv", actor, limit=500)
        res.update(alerts_imported=r["imported"], incident_ids=r["incident_ids"], rejected=r["rejected_count"])
    try: res["rag"] = rag.reindex(db) if embeddings.enabled() else "embeddings off; keyword retrieval"
    except embeddings.EmbeddingUnavailable as e: res["rag"] = f"embedding failed; keyword retrieval used ({e})"
    audit(db, actor, "pack_loaded", "data/pack", detail={"alerts": res["alerts_imported"], "incidents": len(res["incident_ids"])}); db.commit()
    return res
