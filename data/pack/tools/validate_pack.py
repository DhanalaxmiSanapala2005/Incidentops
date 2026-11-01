"""Integrity checks for the data pack. Usage: python validate_pack.py incident_data_pack   (exit code 1 on any failure)"""
import json, re, sys
from collections import Counter
from pathlib import Path
import pandas as pd
P = Path(sys.argv[1]); bad = []; ok = lambda c, m: (bad.append(m) if not c else None)
alerts, logs, deps, svcs = (pd.read_csv(P / f) for f in ("alerts/alerts.csv", "telemetry/logs.csv", "telemetry/deployments.csv", "reference/services.csv"))
metrics, traces = pd.read_csv(P / "telemetry/metrics.csv"), pd.read_csv(P / "telemetry/traces.csv")
gt = json.load(open(P / "evaluation/ground_truth.json")); hist = json.load(open(P / "knowledge/resolved_incidents.json")); q = json.load(open(P / "evaluation/rag_eval_queries.json"))
rbs = {}
for f in sorted((P / "knowledge/runbooks").glob("*.md")):
    meta = dict(l.split(": ", 1) for l in f.read_text().split("---")[1].strip().splitlines()); rbs[(meta["doc_id"], int(meta["version"]))] = meta
    body = f.read_text()
    for sec in ("Supported incident types", "Preconditions", "Investigation steps", "Approved remediation", "Required permission", "Risks and side effects", "Rollback procedure", "Verification criteria", "Escalation"): ok(f"## {sec}" in body, f"{f.name} missing section {sec}")
ids = {k[0] for k in rbs}
ok(alerts.alert_id.is_unique and logs.log_id.is_unique and deps.deployment_id.is_unique, "ids not unique")
ok(set(alerts.service_name) <= set(svcs.service_name), "alert for unknown service"); ok(set(logs.service_name) <= set(svcs.service_name), "log for unknown service")
ok(alerts.timestamp.is_monotonic_increasing, "alerts not sorted by time"); ok(alerts.alert_type.isin(["cpu", "memory", "latency", "error_rate", "downtime"]).all(), "bad alert_type")
ok((alerts.metric_value >= 0).all() and (alerts[alerts.alert_type.isin(["cpu", "memory", "error_rate"])].metric_value <= 100).all(), "alert value out of range")
TH = {"cpu": (80, 95), "memory": (85, 95), "latency": (1.0, 4.0), "error_rate": (5.0, 10.0)}
for r in alerts.itertuples():
    if r.alert_type == "downtime": exp = "critical"
    else:
        v = r.metric_value / 1000 if r.alert_type == "latency" else r.metric_value; w, h = TH[r.alert_type]; exp = "high" if v >= h else "medium" if v >= w else "low"
    ok(r.severity == exp, f"{r.alert_id} severity {r.severity} != {exp}")
seen = Counter(); lg, dp = set(logs.log_id), set(deps.deployment_id); al = set(alerts.alert_id)
for sid, g in gt.items():
    grouped = [a for e in g["expected_incidents"] for a in e["alert_ids"]]; seen.update(grouped)
    ok(set(grouped) <= al, f"{sid} unknown alert ids"); ok(set(g["supporting_log_ids"]) <= lg and set(g["injection_log_ids"]) <= lg and set(g["sensitive_log_ids"]) <= lg, f"{sid} unknown log ids")
    ok(set(g["supporting_deployment_ids"] + g["red_herring_deployment_ids"]) <= dp, f"{sid} unknown deployment ids")
    ok(set(g["relevant_runbooks"]) <= ids and all(h in {x["incident_id"] for x in hist} for h in g["relevant_resolved_incidents"]), f"{sid} unknown knowledge refs")
    sl = logs[logs.log_id.isin(g["supporting_log_ids"])]; ok(sl.service_name.eq(g["service"]).all(), f"{sid} supporting logs from other service")
sc_of = {a: s for s, g in gt.items() for e in g["expected_incidents"] for a in e["alert_ids"]}
ok({sc_of[a] for a in alerts[alerts.alert_type == "downtime"].alert_id} == {"S05", "S09"}, "downtime alerts must only exist in S05 and S09")
ok(set(seen) == al and max(seen.values()) == 1, "every alert must be in exactly one expected incident")
ok(all(h["playbook_id"] in ids for h in hist), "KB references unknown runbook"); ok(all(i in ids for x in q for i in x["expected_runbooks"] + x.get("forbidden_runbooks", [])), "RAG eval unknown runbook")
ok(all(i in {x["incident_id"] for x in hist} for x in q for i in x["expected_incidents"] + x.get("forbidden_incidents", [])), "RAG eval unknown incident")
ok(not any(re.search(r"\b\d{3}-\d{2}-\d{4}\b", t) for t in logs.message), "SSN-like string in logs")
ok(metrics.groupby("service_name").size().ge(60).all(), "metrics window too short")
alerts["dup"] = alerts.duplicated(["service_name", "alert_type"], keep="first")
stats = dict(scenarios=len(gt), alerts=len(alerts), alert_types=alerts.alert_type.value_counts().to_dict(), severities=alerts.severity.value_counts().to_dict(), logs=len(logs),
             log_levels=logs.level.value_counts().to_dict(), metric_rows=len(metrics), trace_spans=len(traces), traces=traces.trace_id.nunique(), deployments=len(deps), config_events=int((deps.change_type == "config").sum()),
             runbook_files=len(rbs), runbook_ids=len(ids), resolved_incidents=len(hist), rag_queries=len(q), rag_kinds=dict(Counter(x["kind"] for x in q)), services=len(svcs),
             expected_incidents=sum(len(g["expected_incidents"]) for g in gt.values()), per_scenario_alerts={s: g["alert_count"] for s, g in gt.items()},
             sensitive_log_lines=sum(len(g["sensitive_log_ids"]) for g in gt.values()), injection_log_lines=sum(len(g["injection_log_ids"]) for g in gt.values()),
             categories=dict(Counter(x["category"] for x in json.load(open(P / "scenarios/scenario_catalog.json")))))
json.dump(stats, open(P / "pack_stats.json", "w"), indent=1)
print(json.dumps(stats, indent=1)); print("FAILURES:", len(bad)); [print(" -", b) for b in bad[:20]]; sys.exit(1 if bad else 0)
