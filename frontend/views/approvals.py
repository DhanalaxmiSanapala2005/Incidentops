import pandas as pd
import streamlit as st
import ui

me = ui.guard("engineer")
ui.hero("Approval queue", "Nothing changes in the sandbox until an engineer approves. The result shown is what actually happened.")
acts = ui.call("GET", "/actions") or []
pending = [a for a in acts if a["status"] == "pending"]
st.subheader(f"Waiting for a decision ({len(pending)})")
if not pending: st.info("No actions are waiting. Run an investigation to propose one.")
for a in pending:
    d = ui.call("GET", f"/incidents/{a['incident_id']}")
    with st.container(border=True):
        st.markdown(f"**{a['incident_ref']}  ·  `{a['op']}`  {a['params']}**" + ui.sev_pill(a["risk"]), unsafe_allow_html=True)
        st.write(a["justification"])
        c1, c2 = st.columns(2); c1.markdown(f"**Side effects**  \n{a['side_effects']}"); c2.markdown(f"**Rollback plan**  \n{a['rollback_plan']}")
        if d:
            ev = [e for e in d["evidence"] if e["id"] in a["evidence_ids"]]
            with st.expander(f"Supporting evidence ({len(ev)})"):
                for e in ev: st.markdown(f"`#{e['id']}` {ui.esc(e['content'])}")
        st.caption(f"Requested by {a['requested_by']}  ·  expires {a['expires_at']} UTC")
        comment = st.text_input("Comment (kept in the audit trail)", key=f"c{a['id']}")
        b1, b2, _ = st.columns([1, 1, 4])
        if b1.button("Approve and execute", key=f"a{a['id']}", type="primary"):
            r = ui.call("POST", f"/actions/{a['id']}/approve", json={"comment": comment})
            if r:
                ui.flash(*(("ok", f"Executed and verified. Incident resolved. Checks: {r['verification'].get('checks')}") if r["status"] == "verified"
                           else ("bad", f"Not recovered ({r['status']}). {r['result'].get('error', '')} Recovery: {r['result'].get('recovery')}. Incident escalated to a human.")))
                st.rerun()
        if b2.button("Reject", key=f"r{a['id']}"):
            if ui.call("POST", f"/actions/{a['id']}/reject", json={"comment": comment}): ui.flash("warn", "Rejected. Nothing was executed."); st.rerun()
st.subheader("History")
done = [a for a in acts if a["status"] != "pending"]
if done:
    df = pd.DataFrame(done)[["id", "incident_ref", "op", "status", "requested_by", "executed_at", "verification"]]
    df["verification"] = df["verification"].apply(lambda v: str(v.get("checks", "")) if isinstance(v, dict) else "")
    st.dataframe(df, hide_index=True, width="stretch")
