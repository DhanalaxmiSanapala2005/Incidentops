import pandas as pd
import streamlit as st
import ui

ui.guard()
ui.hero("Incident records", "Search incidents, alerts, services, runbooks and the action history.")
tabs = st.tabs(["Incidents", "Alerts", "Services", "Runbooks", "Actions"])
with tabs[0]:
    c = st.columns([2, 1, 1, 1])
    q = c[0].text_input("Search", placeholder="service, metric or text")
    status = c[1].selectbox("Status", ["", "open", "investigating", "awaiting_approval", "needs_human", "resolved", "escalated"])
    sev = c[2].selectbox("Severity", ["", "critical", "high", "medium", "low"])
    svc = c[3].text_input("Service")
    params = {k: v for k, v in dict(q=q, status=status, severity=sev, service=svc).items() if v}
    incs = ui.call("GET", "/incidents", params=params) or []
    if not incs: st.info("No incidents match these filters.")
    else:
        df = pd.DataFrame(incs)[["ref", "service", "severity", "status", "category", "opened_at", "resolved_at", "outcome"]]
        st.dataframe(df, hide_index=True, width="stretch")
        sel = st.selectbox("Inspect incident", incs, format_func=lambda i: f"{i['ref']}  {i['title']}")
        d = ui.call("GET", f"/incidents/{sel['id']}")
        if d:
            ui.incident_card(d)
            a, b = st.columns(2)
            with a:
                st.markdown("**Alerts** (source evidence is never discarded)")
                st.dataframe(pd.DataFrame(d["alerts"]), hide_index=True, width="stretch", height=240)
            with b:
                st.markdown("**Timeline**")
                for t in d["timeline"][-12:]: st.markdown(f'<div class="step"><span class="ts">{ui.esc(t["ts"])}</span><br>{ui.esc(t["text"])} <span class="mono">· {ui.esc(t["actor"])}</span></div>', unsafe_allow_html=True)
            rep = ui.call("GET", f"/incidents/{sel['id']}/report")
            if rep:
                with st.expander("Post-incident report"): st.markdown(rep)
                st.download_button("Download report (.md)", rep, file_name=f"{d['ref']}-report.md", mime="text/markdown")
with tabs[1]:
    al = ui.call("GET", "/alerts") or []
    st.dataframe(pd.DataFrame(al), hide_index=True, width="stretch") if al else st.info("No alerts received.")
with tabs[2]:
    sv = ui.call("GET", "/services") or []
    st.dataframe(pd.DataFrame(sv), hide_index=True, width="stretch")
with tabs[3]:
    rb = ui.call("GET", "/runbooks") or []
    st.dataframe(pd.DataFrame(rb), hide_index=True, width="stretch")
    st.caption("You only see runbooks your role may read. Retrieval enforces the same rule.")
with tabs[4]:
    ac = ui.call("GET", "/actions") or []
    if ac:
        df = pd.DataFrame(ac)[["id", "incident_ref", "op", "params", "status", "risk", "requested_by", "executed_at"]]
        df["params"] = df["params"].astype(str)
        st.dataframe(df, hide_index=True, width="stretch")
        st.download_button("Export actions (.csv)", df.to_csv(index=False), file_name="actions.csv", mime="text/csv")
    else: st.info("No remediation actions proposed yet.")
