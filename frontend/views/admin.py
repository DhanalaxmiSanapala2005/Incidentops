import pandas as pd
import streamlit as st
import ui

me = ui.guard("admin")
ui.hero("Admin and monitoring", "Workflow health, audit trail, roles, settings and environment control.")
tabs = st.tabs(["Monitoring", "Audit log", "Users and roles", "Settings", "Environment"])
with tabs[0]:
    d = ui.call("GET", "/dashboard")
    if d:
        w = d["workflow"]; c = st.columns(5)
        ui.kpi(c[0], "Mean time to recovery", f"{d['mttr_min']} min"); ui.kpi(c[1], "Workflow p50", f"{w['p50_s']} s"); ui.kpi(c[2], "Workflow p95", f"{w['p95_s']} s")
        ui.kpi(c[3], "Error rate", f"{w['error_rate']:.1%}"); ui.kpi(c[4], "Avg cost per task", f"${w['avg_cost_usd']}")
        st.caption(f"{w['runs']} workflow runs · degraded {w['degraded_rate']:.0%} · tokens in {w['tokens_in']} / out {w['tokens_out']}")
        a, b = st.columns(2)
        if d["action_outcomes"]: a.markdown("**Action outcomes**"); a.bar_chart(pd.Series(d["action_outcomes"]), color="#0E6F7E")
        if d["by_status"]: b.markdown("**Incidents by status**"); b.bar_chart(pd.Series(d["by_status"]), color="#4A6B8A")
        if w["recent"]: st.markdown("**Recent workflow runs**"); st.dataframe(pd.DataFrame(w["recent"]), hide_index=True, width="stretch")
with tabs[1]:
    ev = st.text_input("Filter by event type", placeholder="action_approved, sandbox_call, login ...")
    rows = ui.call("GET", "/admin/audit", params={"event_type": ev} if ev else None) or []
    if rows:
        df = pd.DataFrame(rows); df["detail"] = df["detail"].astype(str)
        st.dataframe(df, hide_index=True, width="stretch", height=420)
        st.download_button("Download audit log (.csv)", df.to_csv(index=False), file_name="audit.csv", mime="text/csv")
    else: st.info("No audit events match.")
with tabs[2]:
    for u in ui.call("GET", "/admin/users") or []:
        c = st.columns([2, 2, 1])
        c[0].write(f"**{u['username']}**")
        role = c[1].selectbox("Role", ["viewer", "engineer", "admin"], index=["viewer", "engineer", "admin"].index(u["role"]), key=f"role{u['id']}", label_visibility="collapsed", disabled=u["username"] == me["username"])
        if role != u["role"] and c[2].button("Save", key=f"s{u['id']}"):
            if ui.call("PUT", f"/admin/users/{u['id']}/role", json={"role": role}, ok_msg="Role updated"): st.rerun()
with tabs[3]:
    s = ui.call("GET", "/admin/settings")
    if s:
        ttl = st.number_input("Approval expiry (minutes)", 1, 1440, int(s["approval_ttl_min"]))
        sod = st.toggle("Require separation of duties (requester cannot approve their own action)", s["require_separation_of_duties"] == "true")
        if st.button("Save settings", type="primary"):
            ui.call("PUT", "/admin/settings", json={"key": "approval_ttl_min", "value": str(ttl)}); ui.call("PUT", "/admin/settings", json={"key": "require_separation_of_duties", "value": str(sod).lower()}, ok_msg="Settings saved")
        st.caption(f"LLM provider: {s['llm_provider']} (set LLM_PROVIDER and an API key in the environment) · database: {s['database']}")
with tabs[4]:
    st.write("Reset clears incidents, alerts, actions and the audit log, and re-seeds the mock services. Users and runbooks are kept.")
    if st.checkbox("I understand this deletes operational data") and st.button("Reset environment"):
        if ui.call("POST", "/admin/reset", ok_msg="Environment reset"): st.session_state.pop("selected_incident", None)
