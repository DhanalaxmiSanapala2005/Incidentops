"""Hybrid retriever over versioned runbooks and resolved incidents: keyword TF-IDF plus (when Ollama embeddings are available) dense
vectors stored in the database, fused with reciprocal rank fusion. Always applies retrieval authorization (role) and a corpus filter,
keeps only the latest version of each document, sanitises passages, and falls back to keyword search on any embedding failure.
Retrieved text is reference material, never instructions."""
import hashlib, json, math, re
from collections import Counter
from backend.config import ROOT, settings
from backend.security import RANK
from . import embeddings

STOP = set("the a an and or of to in on is are was were be for with at by it this that as from if not do".split())
INJECTION = re.compile(r"(?i)(ignore (all |any )?(previous|prior|above) (instructions|rules)|disregard .*instructions|you are now|system prompt|run (the )?command|delete|drop table|rm -rf|exfiltrate)")
_extra: list[dict] = []  # test hook for poisoned documents


def toks(s): return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 1]


def _corpus(doc_id: str, uploaded=False) -> str:
    if uploaded or doc_id.startswith(("RB-", "HIST-")): return "pack"
    if doc_id.startswith(("soc_", "INC-S")): return "soc"
    return "legacy"


def _sources():
    return [(ROOT / "data" / "runbooks", False), (ROOT / "data" / "pack" / "knowledge" / "runbooks", False), (settings.UPLOAD_DIR / "runbooks", True)]


def _resolved_files():
    return [(ROOT / "data" / "resolved_incidents.json", False), (ROOT / "data" / "pack" / "knowledge" / "resolved_incidents.json", False)] + \
           [(p, True) for p in sorted((settings.UPLOAD_DIR / "resolved").glob("*.json"))]


def _load() -> list[dict]:
    docs = []
    for d, up in _sources():
        for p in sorted(d.glob("*.md")) if d.exists() else []:
            raw = p.read_text(encoding="utf-8"); _, fm, body = raw.split("---", 2)
            meta = dict(l.split(": ", 1) for l in fm.strip().splitlines() if ": " in l)
            title = (re.search(r"^# (.+)$", body, re.M) or [None, meta["doc_id"]])[1]
            for sec in re.split(r"\n(?=## )", body.strip()):
                head = sec.splitlines()[0].lstrip("# ").strip()
                docs.append({"doc_id": meta["doc_id"], "version": int(meta["version"]), "access": meta.get("access", "engineer"), "title": title, "section": head,
                             "text": sec, "corpus": _corpus(meta["doc_id"], up)})
    for f, up in _resolved_files():
        if not f.exists(): continue
        for r in json.loads(f.read_text(encoding="utf-8")):
            did = r.get("doc_id") or r.get("incident_id")
            text = r.get("text") or ". ".join(f"{k.capitalize()}: {r[k]}" for k in ("title", "symptoms", "confirmed_root_cause", "resolution") if r.get(k))
            docs.append({"doc_id": did, "version": int(r.get("version", 1)), "access": r.get("access", "engineer"), "title": r.get("title", did), "section": "Resolution",
                         "text": text, "corpus": _corpus(did, up)})
    docs += [{"corpus": "legacy", **e} for e in _extra]
    latest = {}
    for d in docs: latest[d["doc_id"]] = max(latest.get(d["doc_id"], 0), d["version"])
    out = [d for d in docs if d["version"] == latest[d["doc_id"]]]  # superseded versions are never retrieved
    for d in out: d["chunk_id"] = f"{d['doc_id']}@v{d['version']}#{d['section']}"
    return out


def _ctext(d): return f"{d['title']}. {d['section']}. {d['text']}"
def _hash(t): return hashlib.sha1(t.encode()).hexdigest()


def reindex(db) -> dict:
    """Embed every chunk that has no current vector for the configured model. Raises EmbeddingUnavailable."""
    from backend import models as m
    docs = _load(); have = {v.chunk_id: v for v in db.query(m.ChunkVector).filter(m.ChunkVector.model == settings.EMBED_MODEL)}
    todo = [d for d in docs if d["chunk_id"] not in have or have[d["chunk_id"]].text_hash != _hash(_ctext(d))]
    vecs = embeddings.embed([_ctext(d) for d in todo]) if todo else []
    for d, v in zip(todo, vecs):
        if d["chunk_id"] in have: have[d["chunk_id"]].vector, have[d["chunk_id"]].text_hash = v, _hash(_ctext(d))
        else: db.add(m.ChunkVector(chunk_id=d["chunk_id"], model=settings.EMBED_MODEL, text_hash=_hash(_ctext(d)), vector=v))
    live = {d["chunk_id"] for d in docs}
    for cid, row in have.items():
        if cid not in live: db.delete(row)
    db.commit()
    return {"chunks": len(docs), "embedded_now": len(todo), "model": settings.EMBED_MODEL}


def status(db) -> dict:
    from backend import models as m
    n = db.query(m.ChunkVector).filter(m.ChunkVector.model == settings.EMBED_MODEL).count(); chunks = len(_load())
    return {"embed_provider": settings.EMBED_PROVIDER, "embed_model": settings.EMBED_MODEL, "chunks": chunks, "vectors": n,
            "mode": "hybrid (keyword + embeddings)" if embeddings.enabled() and n else "keyword only", "last_embedding_error": embeddings.last_error() or None}


def _cos(a, b):
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def search(query: str, role: str, k: int = 3, db=None, corpus=None, per_doc: int = 2) -> list[dict]:
    docs = [d for d in _load() if RANK[role] >= RANK.get(d["access"], 3) and (corpus is None or d["corpus"] in corpus)]  # retrieval authorization
    if not docs: return []
    df = Counter(t for d in docs for t in set(toks(d["title"] + " " + d["text"])))
    n = len(docs); q = Counter(toks(query)); lex = []
    for i, d in enumerate(docs):
        tf = Counter(toks(d["title"] + " " + d["text"])); length = math.sqrt(sum(v * v for v in tf.values())) or 1
        score = sum(q[t] * (tf[t] / length) * math.log(1 + n / df[t]) for t in q if t in tf)
        if score > 0: lex.append((score, i))
    lex.sort(key=lambda x: -x[0]); mode = "keyword"; dense = []
    if db is not None and embeddings.enabled():
        try:
            from backend import models as m
            vec = {v.chunk_id: v.vector for v in db.query(m.ChunkVector).filter(m.ChunkVector.model == settings.EMBED_MODEL)}
            if vec:
                qv = embeddings.embed_query(query)
                dense = sorted(((_cos(qv, vec[d["chunk_id"]]), i) for i, d in enumerate(docs) if d["chunk_id"] in vec), key=lambda x: -x[0])
                if settings.RAG_MIN_DENSE and (not dense or dense[0][0] < settings.RAG_MIN_DENSE): return []
                mode = "hybrid"
        except embeddings.EmbeddingUnavailable: mode = "keyword (embeddings unavailable)"
    if mode == "hybrid":
        fused = {}
        for ranking in (lex, dense):
            for rank, (_, i) in enumerate(ranking): fused[i] = fused.get(i, 0) + 1 / (60 + rank)
        ranked = sorted(((s, i) for i, s in fused.items()), key=lambda x: -x[0])
    else: ranked = lex
    out, seen, count = [], set(), Counter()
    for score, i in ranked:
        d = docs[i]
        if (d["doc_id"], d["section"]) in seen or count[d["doc_id"]] >= per_doc: continue  # at most per_doc chunks per document, so one runbook cannot crowd out the rest
        seen.add((d["doc_id"], d["section"])); count[d["doc_id"]] += 1; clean, flagged = sanitize(d["text"])
        out.append({"doc_id": d["doc_id"], "version": d["version"], "title": d["title"], "section": d["section"], "score": round(score, 4 if mode == "hybrid" else 3),
                    "passage": clean[:600], "injection_flagged": flagged, "mode": mode})
        if len(out) == k: break
    return out


def sanitize(text: str) -> tuple[str, bool]:
    lines, flagged = [], False
    for l in text.splitlines():
        if INJECTION.search(l):
            flagged = True; lines.append("[line removed: possible prompt injection]")
        else: lines.append(l)
    return "\n".join(lines), flagged
