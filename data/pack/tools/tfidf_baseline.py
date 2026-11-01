"""Keyword (TF-IDF) retrieval baseline on the RAG evaluation set. This is the BASELINE the embedding-based RAG must beat.
Usage: python tfidf_baseline.py incident_data_pack   (needs scikit-learn)"""
import json, re, sys
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
P = Path(sys.argv[1]); q = json.load(open(P / "evaluation/rag_eval_queries.json")); hist = json.load(open(P / "knowledge/resolved_incidents.json"))
docs = []
for f in sorted((P / "knowledge/runbooks").glob("*.md")):
    t = f.read_text(); meta = dict(l.split(": ", 1) for l in t.split("---")[1].strip().splitlines())
    for ch in re.split(r"\n(?=## )", t.split("---", 2)[2]): docs.append(dict(id=meta["doc_id"], v=int(meta["version"]), status=meta["status"], access=meta["access"], text=meta["title"] + " " + ch))
for h in hist: docs.append(dict(id=h["incident_id"], v=1, status="current", access=h["access"], text=h["text"]))
vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True).fit([d["text"] for d in docs]); M = vec.transform([d["text"] for d in docs])
ROLE = {"viewer": {"viewer"}, "engineer": {"viewer", "engineer"}, "admin": {"viewer", "engineer", "admin"}}
def rank(query, role, current_only):
    s = (M @ vec.transform([query]).T).toarray().ravel(); best = {}
    for i in np.argsort(-s):
        d = docs[i]
        if d["access"] not in ROLE[role] or (current_only and d["status"] != "current"): continue
        best.setdefault((d["id"], d["v"]), s[i])
    return sorted(best.items(), key=lambda kv: -kv[1])
def run(current_only):
    r = {"n": 0, "r1": 0, "r3": 0, "r5": 0, "mrr": 0.0, "kb_n": 0, "kb3": 0, "leak": 0, "ver_n": 0, "ver_ok": 0}
    for x in q:
        rk = rank(x["query"], x["role"], current_only); rbs = [(i, v) for (i, v), _ in rk if i.startswith("RB-")]; kb = [i for (i, v), _ in rk if i.startswith("HIST-")]
        r["leak"] += sum(1 for (i, v) in [k for k, _ in rk][:5] if i in x.get("forbidden_runbooks", []) + x.get("forbidden_incidents", []))
        if x.get("expected_runbooks"):
            r["n"] += 1; ids = [i for i, _ in rbs]; pos = next((k for k, i in enumerate(ids) if i in x["expected_runbooks"]), None)
            r["r1"] += pos == 0; r["r3"] += pos is not None and pos < 3; r["r5"] += pos is not None and pos < 5; r["mrr"] += 1 / (pos + 1) if pos is not None else 0
        if x.get("expected_incidents"): r["kb_n"] += 1; r["kb3"] += any(i in x["expected_incidents"] for i in kb[:3])
        if x.get("expected_version"):
            r["ver_n"] += 1; top = [(i, v) for i, v in rbs if i == "RB-001"]; r["ver_ok"] += bool(top) and top[0][1] == 2
    return r
ab = [x for x in q if x.get("expect_abstain") and x["kind"] != "injection"]; inn = [x for x in q if x.get("expected_runbooks")]
top = lambda x: rank(x["query"], x["role"], True)[0][1]
res = dict(current_versions_only=run(True), all_versions_included=run(False),
           top1_similarity=dict(out_of_scope_mean=round(float(np.mean([top(x) for x in ab])), 3), out_of_scope_max=round(float(max(top(x) for x in ab)), 3),
                                in_scope_mean=round(float(np.mean([top(x) for x in inn])), 3), in_scope_min=round(float(min(top(x) for x in inn)), 3)))
print(json.dumps(res, indent=1)); json.dump(res, open(P / "evaluation/tfidf_baseline_results.json", "w"), indent=1)
