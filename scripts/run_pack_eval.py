"""End-to-end evaluation of the whole workflow on the 12 pack scenarios against evaluation/ground_truth.json, through the public API.
Needs the mock service and API running. Resets the database, loads the pack, investigates every incident, approves and executes
proposed actions, and writes docs/pack_eval_report.md. Numbers are MEASURED on synthetic data."""
import json, os, re, statistics, sys, time
from collections import defaultdict
from itertools import combinations
from pathlib import Path
import requests
ROOT = Path(__file__).resolve().parents[1]; API = os.getenv("API_URL", "http://localhost:8000"); GT = json.loads((ROOT / "data/pack/evaluation/ground_truth.json").read_text(encoding="utf-8"))
tok = lambda u, p: {"Authorization": "Bearer " + requests.post(f"{API}/auth/login", json={"username": u, "password": p}).json()["access_token"]}
adm, eng, eng2 = tok("admin", "admin123"), tok("engineer", "engineer123"), tok("engineer2", "engineer123")
norm = lambda v: str(v).lstrip("v")
requests.post(f"{API}/admin/reset", headers=adm)
load = requests.post(f"{API}/pack/load", headers=eng).json(); assert load["alerts_imported"] > 0, load
alerts = requests.get(f"{API}/alerts", params={"limit": 500}, headers=eng).json(); incs = {i["id"]: i for i in requests.get(f"{API}/incidents", headers=eng).json()}
pred = {a["external_id"]: a["incident_id"] for a in alerts if a["external_id"]}
# 1. correlation
true_pairs = pred_pairs = tp = 0; groups = {}
for sid, g in GT.items():
    for e in g["expected_incidents"]: groups[e["group"]] = (sid, e)
by_pred = defaultdict(list)
for aid, iid in pred.items(): by_pred[iid].append(aid)
gold = {a: gname for gname, (_, e) in groups.items() for a in e["alert_ids"]}
for ids in by_pred.values():
    for x, y in combinations(ids, 2): pred_pairs += 1; tp += gold.get(x) == gold.get(y)
for gname, (_, e) in groups.items(): n = len(e["alert_ids"]); true_pairs += n * (n - 1) // 2
corr_p, corr_r = tp / pred_pairs, tp / true_pairs
# 2. investigate, compare
rows, lat = [], []; sev_ok = cat_ok = 0; tot_h = cit_h = 0; log_cited = log_good = 0; rb_hit = rb_n = kb_hit = kb_n = 0; unc_ok = act_ok = disc_bad = out_ok = out_n = 0; scen = 0
for gname, (sid, e) in groups.items():
    iids = {pred[a] for a in e["alert_ids"]}; main = max(iids, key=lambda i: sum(pred[a] == i for a in e["alert_ids"])); inc = incs[main]
    sev_ok += inc["severity"] == e["expected_severity"]; cat_ok += inc["category"] == e["expected_category"]
    if not gname.startswith("INC-"): continue
    scen += 1; g = GT[sid]
    t = time.time(); requests.post(f"{API}/incidents/{main}/investigate", headers=eng); lat.append(time.time() - t)
    d = requests.get(f"{API}/incidents/{main}", headers=eng).json(); inv = d["investigation"]; hyps = inv["hypotheses"]; ev = {x["id"]: x for x in d["evidence"]}
    tot_h += len(hyps); cit_h += sum(bool(h["evidence_ids"]) for h in hyps)
    sup = set(g["supporting_log_ids"]); cited = {re.sub(r".*#", "", ev[i]["source_ref"]) for h in hyps for i in h["evidence_ids"] if i in ev and ev[i]["type"] == "log"}
    log_cited += len(cited); log_good += len(cited & sup)
    rbs = [r["doc_id"] for r in inv["runbooks"] if r["doc_id"].startswith("RB-")]; hist = [r["doc_id"] for r in inv["runbooks"] if r["doc_id"].startswith("HIST-")]
    rb_n += 1; rb_hit += bool(set(rbs[:3]) & set(g["relevant_runbooks"])); kb_n += 1; kb_hit += bool(set(hist[:3]) & set(g["relevant_resolved_incidents"]))
    top = hyps[0] if hyps else None
    unc_ok += (top is None or top["uncertain"]) if g["hypothesis_should_be_uncertain"] else (top is not None and not top["uncertain"])
    act = next((a for a in d["actions"] if a["status"] == "pending"), None); exp = g["expected_action"]
    if exp is None: good = act is None
    elif act is None or act["op"] != exp["operation"]: good = False
    else:
        p, x = act["params"], exp["parameters"]
        good = (norm(p.get("target_version")) == norm(x.get("target_version")) if act["op"] == "rollback" else p.get("replicas", 0) >= 5 if act["op"] == "scale" else
                (p.get("key"), p.get("value")) == (x.get("key"), x.get("value")) if act["op"] == "config_change" else True)
    if exp is None and act is None and None in g["acceptable_alternatives"]: good = True
    if act is not None and exp is None: good = False
    if act and act["op"] in g["discouraged_operations"]: disc_bad += 1
    if act is None and None in g["acceptable_alternatives"]: good = True
    act_ok += bool(good); final = d["status"]
    if act:
        requests.post(f"{API}/actions/{act['id']}/approve", json={"comment": "eval"}, headers=eng2)
        final = requests.get(f"{API}/incidents/{main}", headers=eng).json()["status"]
    out_n += 1; out_ok += (final == "resolved") if g["expected_final_outcome"] == "resolved" else final in ("escalated", "needs_human")
    rows.append((sid, g["service"], len(e["alert_ids"]), inc["severity"], e["expected_severity"], (top or {}).get("signal", "none"), "uncertain" if (top is None or top["uncertain"]) else "firm",
                 (act or {}).get("op", "none"), (exp or {}).get("operation", "none"), "yes" if good else "NO", final, g["expected_final_outcome"], ", ".join(rbs[:2]) or "-"))
lat.sort(); p = lambda q: lat[min(len(lat) - 1, int(q * len(lat)))]
body = (f"# Pack evaluation (measured, synthetic data)\n\nRun against the live API on the 12 pack scenarios ({len(alerts)} alerts, {len(groups)} expected incidents). Ground truth: `data/pack/evaluation/ground_truth.json`.\n\n"
        f"| Measure | Result |\n|---|---|\n| Alert correlation, pairwise precision | {corr_p:.1%} ({tp}/{pred_pairs}) |\n| Alert correlation, pairwise recall | {corr_r:.1%} ({tp}/{true_pairs}) |\n"
        f"| Incident severity matches rules | {sev_ok}/{len(groups)} |\n| Incident category matches rules | {cat_ok}/{len(groups)} |\n"
        f"| Hypotheses citing at least one evidence item | {cit_h}/{tot_h} |\n| Cited log lines that are in the ground-truth supporting set | {log_good}/{log_cited} |\n"
        f"| Correct runbook in top 3 (scenarios) | {rb_hit}/{rb_n} |\n| Relevant past incident in top 3 | {kb_hit}/{kb_n} |\n"
        f"| Uncertainty flag as expected | {unc_ok}/{scen} |\n| Proposed action matches expected (or correctly none) | {act_ok}/{scen} |\n| Discouraged action proposed | {disc_bad} |\n"
        f"| Final outcome as expected after approval | {out_ok}/{out_n} |\n| Investigation latency p50 / p95 | {statistics.median(lat):.2f}s / {p(0.95):.2f}s |\n\n"
        "| Scenario | Service | Alerts | Severity | Expected | Top hypothesis | Certainty | Action | Expected action | Match | Final | Expected final | Runbooks |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
        + "\n".join("| " + " | ".join(map(str, r)) + " |" for r in rows) + "\n\nLimits: synthetic and tidy data; one run; the matching rules are mine (a scale action counts when replicas rise by at least 2).\n")
(ROOT / "docs/pack_eval_report.md").write_text(body, encoding="utf-8"); print(body)
