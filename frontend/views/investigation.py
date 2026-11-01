import pandas as pd
import streamlit as st
import ui

me = ui.guard()
ui.hero("AI investigation", "Evidence first. Every hypothesis cites logs or metrics, and states what is uncertain.")
incs = [i for i in (ui.call("GET", "/incidents") or [])]
if not incs: st.info("No incidents yet. Launch a scenario from the dashboard."); st.stop()
default = next((n for n, i in enumerate(incs) if i["id"] == st.session_state.get("selected_incident")), 0)
sel = st.selectbox("Incident", incs, index=default, format_func=lambda i: f"{i['ref']}  {i['title']}  [{i['status']}]")
st.session_state["selected_incident"] = sel["id"]
ui.incident_card(sel)

if me["role"] == "viewer": st.caption("Viewers can read results. Running an investigation needs the engineer role.")
elif st.button("Run investigation", type="primary"):
    with st.status("Agents working...", expanded=True) as s:
        st.write("Triage agent: classifying with documented rules")
        st.write("Log investigation agent: collecting metrics, logs, deployments, traces")
        st.write("Runbook retrieval agent: searching versioned runbooks")
        st.write("Remediation planner: building options and validating against the allowlist")
        r = ui.call("POST", f"/incidents/{sel['id']}/investigate", timeout=120)
        if r and r["status"] != "failed": s.update(label=f"Done in {r['duration_s']}s" + (" (degraded: see notes)" if r.get("degraded") else ""), state="complete")
        else: s.update(label="Investigation failed. The incident was escalated to a human.", state="error")
    st.rerun()

d = ui.call("GET", f"/incidents/{sel['id']}")
inv = d and d["investigation"]
if not inv: st.info("No investigation yet for this incident."); st.stop()
if inv["degraded"]: ui.box("warn", "Degraded run: " + " | ".join(inv["notes"]) if inv["notes"] else "Degraded run")
elif inv["notes"]: st.caption(" | ".join(inv["notes"]))
st.markdown(f"**Summary.** {ui.esc(inv['narrative'].get('summary', ''))}  \n<span class='mono'>narrative source: {ui.esc(inv['narrative'].get('source'))}</span>", unsafe_allow_html=True)

t1, t2, t3, t4, t5 = st.tabs(["Hypotheses", "Metrics", "Logs and evidence", "Runbooks", "Remediation options"])
with t1:
    if not inv["hypotheses"]: st.info("No hypothesis is supported by the evidence. A human should investigate.")
    for h in inv["hypotheses"]:
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"**{h['id']}  {ui.esc(h['title'])}**" + (ui.pill("uncertain", "#C4620A") if h["uncertain"] else ui.pill("supported", "#2E7D5B")), unsafe_allow_html=True)
        c1.caption(h["explanation"]); c1.caption(f"Evidence ids: {h['evidence_ids']}")
        c2.progress(h["confidence"], text=f"confidence {h['confidence']}")
with t2:
    m = None if sel.get("category") == "security" else ui.call("GET", f"/incidents/{sel['id']}/metrics")
    if sel.get("category") == "security": st.info("Security alerts have no CPU or latency series. See the Evidence tab for alert, identity and indicator data.")
    if m:
        df = pd.DataFrame(m["series"]).set_index("ts")
        a, b = st.columns(2)
        a.markdown("CPU and memory (%)"); a.line_chart(df[["cpu", "memory"]], color=["#C4620A", "#4A6B8A"])
        b.markdown("Latency (s) and error rate (%)"); b.line_chart(df[["latency", "error_rate"]], color=["#0E6F7E", "#B3261E"])
        st.json(m["current"])
with t3:
    types = sorted({e["type"] for e in d["evidence"]}); pick = st.multiselect("Evidence type", types, default=["log"] if "log" in types else types)
    logs = [e for e in d["evidence"] if e["type"] == "log" and "log" in pick]
    others = [e for e in d["evidence"] if e["type"] != "log" and e["type"] in pick]
    if others and not logs: st.dataframe(pd.DataFrame(others)[["id", "type", "source_ref", "content", "redacted"]], hide_index=True, width="stretch")
    if logs: st.markdown('<div class="log">' + ui.esc("\n".join(f"#{e['id']} {e['ts'][11:19]} {e['content']}" for e in logs)) + "</div>", unsafe_allow_html=True)
    other = [e for e in d["evidence"] if e["type"] != "log" and e["type"] in pick]
    if other: st.dataframe(pd.DataFrame(other)[["id", "type", "source_ref", "content", "redacted"]], hide_index=True, width="stretch")
    if any(e["redacted"] for e in d["evidence"]): st.caption("Secrets, emails and IP addresses were redacted before storage.")
with t4:
    for r in inv["runbooks"]:
        with st.expander(f"{r['doc_id']}  v{r['version']}  ·  {r['section']}  ·  score {r['score']}"): st.text(r["passage"])
        if r["injection_flagged"]: ui.box("warn", "Possible prompt injection was removed from this passage.")
    st.caption("Retrieved text is reference material. The backend allowlist and approval gate are unaffected by its content.")
with t5:
    for o in inv["options"]:
        title = f"{o['op']} {o['params']}" if o["op"] else "Escalate to an engineer (no automated action)"
        st.markdown(f"**{ui.esc(title)}**" + (ui.pill("recommended", "#0E6F7E") if o["recommended"] else "") + ui.pill(f"risk {o['risk']}", ui.SEV.get({"low": "low", "medium": "medium", "high": "high"}[o["risk"]])), unsafe_allow_html=True)
        st.caption(f"Side effects: {o['side_effects']}  \nRollback: {o['rollback_plan']}")
    if d["status"] == "awaiting_approval": ui.box("ok", "An action is waiting for an engineer in the Approval queue.")

ui.link("views/assistant.py", "Ask the assistant about this incident", ":material/chat:")
