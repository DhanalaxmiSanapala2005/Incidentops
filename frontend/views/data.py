import io
from pathlib import Path
import pandas as pd
import streamlit as st
import ui

me = ui.guard("engineer")
PACK = Path(__file__).resolve().parents[2] / "data" / "pack"
ui.hero("Data and import", "Everything here is optional. Load the bundled data pack to test the whole workflow, or upload your own files.")
f = st.session_state.pop("_flash", None)
if f: ui.box(*f)
req = ui.call("GET", "/import/requirements")
if req:
    with st.expander("Which files each feature needs", expanded=False): st.dataframe(pd.DataFrame(req), hide_index=True, width="stretch")

st.markdown("### Load bundled data")
a, b, c, d = st.columns(4)
a.caption("12 scenarios: alerts, logs, metrics, traces, deployments, runbooks, past incidents")
if a.button("Load incident data pack", type="primary", width="stretch"):
    r = ui.call("POST", "/pack/load", timeout=120)
    if r: ui.flash("ok", ("Pack was already loaded. " if r["already_loaded"] else f"Loaded {r['alerts_imported']} alerts. ") + f"{len(r['incident_ids'])} incidents. Search index: {r['rag']}."); st.rerun()
for col, (key, label, help_) in zip((b, c, d), [("soc_real", "SOC alerts (real file)", "17 alert types, one per playbook"), ("soc_labelled", "SOC labelled sample", "Has signals, so the triage score works"),
                                                ("infra_template", "Infrastructure alerts template", "Alerts only, no telemetry")]):
    col.caption(help_)
    if col.button(label, width="stretch", key=key):
        r = ui.call("POST", f"/import/sample/{key}")
        if r: ui.flash("ok" if not r["rejected_count"] else "warn", f"Imported {r['imported']} alerts into {len(r['incident_ids'])} incidents ({r['skipped_existing']} already present, {r['rejected_count']} rejected)."); st.rerun()

with st.expander("Download sample files to try the upload"):
    files = [("incident_test_workbook.xlsx", "Excel workbook with every table"), ("alerts/alerts.csv", "Alerts"), ("alerts/invalid_alerts.csv", "Bad alerts (to see validation)"), ("telemetry/logs.csv", "Logs"),
             ("telemetry/metrics.csv", "Metrics"), ("telemetry/traces.csv", "Traces"), ("telemetry/deployments.csv", "Deployments"), ("knowledge/runbooks/RB-001_v2.md", "Example runbook"),
             ("knowledge/resolved_incidents.json", "Resolved incidents"), ("README.md", "Describes every file")]
    cols = st.columns(3)
    for n, (rel, label) in enumerate(files):
        p = PACK / rel
        if p.exists(): cols[n % 3].download_button(f"{label}", p.read_bytes(), file_name=p.name, key=f"dl{n}")

st.markdown("### Upload your own file")
kind = st.selectbox("What are you uploading?", ["Table: alerts, logs, metrics, traces, deployments or SOC alerts (auto-detected)", "Runbook (.md), admin only", "Resolved incidents (.json or .csv), admin only"])
up = st.file_uploader("File (.xlsx, .csv, .json or .md, max 15 MB)", type=["xlsx", "csv", "json", "md"])
limit = st.slider("Maximum alerts to import (alerts only)", 5, 500, 100)
if up:
    raw = up.getvalue(); tabular = kind.startswith("Table") or up.name.lower().endswith((".csv", ".xlsx"))
    try:
        if up.name.lower().endswith(".csv"): st.caption("Preview (first 8 rows)"); st.dataframe(pd.read_csv(io.BytesIO(raw)).head(8), hide_index=True, width="stretch")
        elif up.name.lower().endswith(".xlsx"): st.caption("Preview (first 8 rows)"); st.dataframe(pd.read_excel(io.BytesIO(raw)).head(8), hide_index=True, width="stretch")
        elif up.name.lower().endswith(".md"): st.caption("Preview"); st.code(raw.decode("utf-8", "replace")[:1200], language="markdown")
    except Exception as e: st.warning(f"Preview not available: {str(e)[:100]}")
    path, params = ("/import/file", {"limit": limit}) if kind.startswith("Table") else (("/import/runbook", {}) if kind.startswith("Runbook") else ("/import/resolved", {}))
    files = {"file": (up.name, raw)}; x, y = st.columns(2)
    if kind.startswith("Table") and x.button("Validate only", width="stretch"):
        r = ui.call("POST", path, params={**params, "dry_run": True}, files=files)
        if r:
            ui.box("ok" if not r["rejected_count"] else "warn", f"Detected: {r['schema']}. {r['valid']} valid rows, {r['rejected_count']} rejected, {r['rows_in_file']} rows in the file.")
            if r["rejected"]: st.dataframe(pd.DataFrame(r["rejected"]), hide_index=True, width="stretch")
    if y.button("Import", type="primary", width="stretch"):
        r = ui.call("POST", path, params=params, files=files)
        if r:
            if "doc_id" in r:
                ui.box("warn" if r["warnings"] or r["injection_flagged"] else "ok", f"Runbook {r['doc_id']} version {r['version']} saved. Search index: {r['index']}.")
                for w in r["warnings"]: st.caption(w)
                if r["injection_flagged"]: st.warning("The text contains instruction-like lines; they are removed before the AI sees them.")
            elif "schema" in r:
                ui.box("ok", f"Imported {r['imported']} {r['schema']} rows" + (f" into {len(r['incident_ids'])} incidents" if r["incident_ids"] else "") + f" ({r['skipped_existing']} already present).")
                if r["rejected"]: st.dataframe(pd.DataFrame(r["rejected"]), hide_index=True, width="stretch")
            else:
                ui.box("ok", f"Imported {r['imported']} resolved incidents. Search index: {r['index']}.")
                if r["rejected"]: st.dataframe(pd.DataFrame(r["rejected"]), hide_index=True, width="stretch")

st.markdown("### Investigate open incidents")
incs = [i for i in (ui.call("GET", "/incidents") or []) if i["status"] == "open"]
st.caption(f"{len(incs)} open incidents waiting for investigation.")
if incs and st.button("Run AI investigation on all", type="primary"):
    bar = st.progress(0.0)
    for n, i in enumerate(incs): ui.call("POST", f"/incidents/{i['id']}/investigate", timeout=120); bar.progress((n + 1) / len(incs))
    ui.flash("ok", f"Investigated {len(incs)} incidents. Open AI investigation or the Approval queue."); st.rerun()
