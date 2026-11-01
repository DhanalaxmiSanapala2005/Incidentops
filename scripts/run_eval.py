"""Evaluation harness against a RUNNING stack. Runs all 10 scenarios N times, checks expectations and
measures p50/p95 workflow latency, error rate, tokens and cost. Writes docs/evaluation_report.md."""
import os, sys, time, statistics, requests
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from data.scenarios import SCENARIOS
API = os.getenv("API_URL", "http://localhost:8000"); RUNS = int(os.getenv("EVAL_RUNS", "3"))


def tok(u, p): return {"Authorization": "Bearer " + requests.post(f"{API}/auth/login", json={"username": u, "password": p}).json()["access_token"]}


def pct(v, p): s = sorted(v); return s[max(0, -(-p * len(s) // 100) - 1)]


adm, eng = tok("admin", "admin123"), tok("engineer", "engineer123")
rows, lat, wall, fails = [], [], [], 0
for run in range(RUNS):
    requests.post(f"{API}/admin/reset", headers=adm)
    for sc in SCENARIOS:
        ex, t0, problems = sc["expect"], time.time(), []
        inc = requests.post(f"{API}/scenarios/{sc['id']}/inject", headers=eng).json()
        if inc["severity"] != ex["severity"]: problems.append(f"severity {inc['severity']}!={ex['severity']}")
        r = requests.post(f"{API}/incidents/{inc['id']}/investigate", headers=eng).json()
        lat.append(r.get("duration_s", 0))
        d = requests.get(f"{API}/incidents/{inc['id']}", headers=eng).json()
        acts = [a for a in d["actions"] if a["status"] != "superseded"]
        if (acts[0]["op"] if acts else None) != ex["op"]: problems.append(f"op {(acts[0]['op'] if acts else None)}!={ex['op']}")
        grounded = all(h["evidence_ids"] for h in (d["investigation"] or {}).get("hypotheses", []))
        if not grounded: problems.append("ungrounded hypothesis")
        if acts and ex["approve"]:
            requests.post(f"{API}/actions/{acts[0]['id']}/approve", headers=eng, json={"comment": "eval"})
            d = requests.get(f"{API}/incidents/{inc['id']}", headers=eng).json()
        if d["status"] != ex["final"]: problems.append(f"final {d['status']}!={ex['final']}")
        wall.append(time.time() - t0); fails += bool(problems)
        if run == 0: rows.append((sc["id"], sc["name"], ex["severity"], ex["op"] or "escalate", d["status"], r.get("duration_s"), "PASS" if not problems else "FAIL " + "; ".join(problems)))
dash = requests.get(f"{API}/dashboard", headers=adm).json()["workflow"]
total = RUNS * len(SCENARIOS)
md = ["# Evaluation report", "", f"- Test set: 10 scenarios x {RUNS} runs = {total} end-to-end workflows (inject -> investigate -> approve where applicable -> verify)",
      f"- Scenario pass rate: **{total - fails}/{total}**",
      f"- Investigation workflow latency: **p50 {pct(lat, 50):.3f}s, p95 {pct(lat, 95):.3f}s** (n={len(lat)}; includes mock-service HTTP calls and RAG; LLM provider here: see below)",
      f"- Full scenario wall time incl. approval/execution: p50 {pct(wall, 50):.3f}s, p95 {pct(wall, 95):.3f}s",
      f"- Workflow error rate: {dash['error_rate']:.1%}; degraded-but-safe rate: {dash['degraded_rate']:.1%}",
      f"- Tokens in/out: {dash['tokens_in']}/{dash['tokens_out']}; average cost per task: ${dash['avg_cost_usd']}",
      "", "## Run 1 detail", "", "| Scenario | Name | Severity | Proposed op | Final status | Latency (s) | Result |", "|---|---|---|---|---|---|---|"]
md += [f"| {a} | {b} | {c} | {d_} | {e} | {f} | {g} |" for a, b, c, d_, e, f, g in rows]
md += ["", "## Limitations", "- Latency/cost reflect the deterministic template narrative unless LLM_PROVIDER is configured; with a real LLM, re-run to measure model latency, tokens and cost.",
       "- Services are mocks; recovery behaviour is simulated by scenario definitions.", "- Retrieval is TF-IDF over a small synthetic corpus; use pgvector/Chroma embeddings at scale.",
       "- Severity/category/action rules are deterministic and unit-tested; no trained ML model is used for classification."]
open(os.path.join(ROOT, "docs", "evaluation_report.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
print("\n".join(md[:9])); sys.exit(1 if fails else 0)
