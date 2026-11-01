"""Measures document retrieval on the pack's 41 test questions: keyword-only, and hybrid (keyword + Ollama embeddings) when Ollama is reachable.
Usage (project root, PYTHONPATH set):  python scripts/run_rag_eval.py      Writes docs/rag_eval_report.md. Nothing is guessed: if Ollama is not reachable, hybrid is reported as not run."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from backend.config import settings
from backend.db import Base, SessionLocal, engine
from agents import embeddings, rag
Base.metadata.create_all(engine)
Q = json.loads((ROOT / "data/pack/evaluation/rag_eval_queries.json").read_text(encoding="utf-8"))


def run(db):
    r = dict(n=0, r1=0, r3=0, r5=0, mrr=0.0, kb_n=0, kb3=0, leak=0, ver_n=0, ver_ok=0, abstain_top=[], inscope_top=[])
    for x in Q:
        res = rag.search(x["query"], x["role"], k=40, db=db, corpus={"pack"}, per_doc=1)
        docs = [(h["doc_id"], h["version"]) for h in res]; rbs = [d for d, _ in docs if d.startswith("RB-")]; kb = [d for d, _ in docs if d.startswith("HIST-")]
        r["leak"] += sum(1 for d, _ in docs[:5] if d in x.get("forbidden_runbooks", []) + x.get("forbidden_incidents", []))
        if x.get("expected_runbooks"):
            r["n"] += 1; pos = next((k for k, d in enumerate(rbs) if d in x["expected_runbooks"]), None)
            r["r1"] += pos == 0; r["r3"] += pos is not None and pos < 3; r["r5"] += pos is not None and pos < 5; r["mrr"] += 1 / (pos + 1) if pos is not None else 0
            r["inscope_top"].append(res[0]["score"] if res else 0)
        if x.get("expected_incidents"): r["kb_n"] += 1; r["kb3"] += any(d in x["expected_incidents"] for d in kb[:3])
        if x.get("expected_version"): r["ver_n"] += 1; r["ver_ok"] += any(d == "RB-001" and v == 2 for d, v in docs[:1] + [p for p in docs if p[0] == "RB-001"][:1])
        if x.get("expect_abstain") and x["kind"] != "injection": r["abstain_top"].append(res[0]["score"] if res else 0)
    return r


def row(name, r):
    lo = lambda v: f"{min(v):.2f}" if v else "n/a"; hi = lambda v: f"{max(v):.2f}" if v else "n/a"
    return (f"| {name} | {r['r1']}/{r['n']} ({r['r1'] / r['n']:.0%}) | {r['r3']}/{r['n']} ({r['r3'] / r['n']:.0%}) | {r['r5']}/{r['n']} ({r['r5'] / r['n']:.0%}) | {r['mrr'] / r['n']:.2f} | {r['kb3']}/{r['kb_n']} | "
            f"{r['leak']} | {r['ver_ok']}/{r['ver_n']} | lowest in-scope {lo(r['inscope_top'])}, highest out-of-scope {hi(r['abstain_top'])} |")


with SessionLocal() as db:
    kw = run(None); lines = [row("Keyword only (TF-IDF)", kw)]; note = ""
    if embeddings.enabled():
        try:
            rag.reindex(db); lines.append(row(f"Hybrid (keyword + {settings.EMBED_MODEL})", run(db)))
        except embeddings.EmbeddingUnavailable as e: note = f"\nHybrid not run: Ollama embeddings unavailable ({str(e)[:120]}).\n"
    else: note = "\nHybrid not run: EMBED_PROVIDER is not 'ollama'. Set it and start Ollama (see README), then run this script again.\n"
body = ("# RAG retrieval evaluation (measured, synthetic data)\n\nTest set: `data/pack/evaluation/rag_eval_queries.json` (41 queries; 35 with an expected runbook, 34 with an expected past incident). "
        "Runbook hit = any expected runbook within the top K documents. Leakage = admin-only documents returned to a lower role in the top 5 (must be 0). Last column: if the lowest best-score of real questions is above the highest best-score of out-of-scope questions, a score cutoff could refuse out-of-scope questions; set RAG_MIN_DENSE only after checking this on your own data.\n\n"
        "| Method | Runbook @1 | Runbook @3 | Runbook @5 | MRR | Past incident @3 | Leakage | Current version first | Top score |\n|---|---|---|---|---|---|---|---|---|\n" + "\n".join(lines) + "\n" + note +
        "\nLimits: 41 questions written by the project author on synthetic documents; one run.\n")
(ROOT / "docs/rag_eval_report.md").write_text(body, encoding="utf-8"); print(body)
