import streamlit as st
import ui

me = ui.guard()
ui.hero("Incident assistant", "Ask about an incident. Answers come from stored evidence with citations. I am read-only and never run changes.")
incs = ui.call("GET", "/incidents") or []
opts = [None] + [i["id"] for i in incs]
cur = st.session_state.get("selected_incident")
sel = st.selectbox("Incident context", opts, index=opts.index(cur) if cur in opts else 0,
                   format_func=lambda i: "No incident (portfolio questions)" if i is None else next(f"{x['ref']}  {x['title']}" for x in incs if x["id"] == i))
if sel: st.session_state["selected_incident"] = sel
hist = ui.call("GET", "/chat/history", params={"incident_id": sel} if sel else {}) or []
with st.sidebar:
    if st.button("Clear my chat history", width="stretch"):
        ui.call("DELETE", "/chat/history", "Chat history cleared"); st.rerun()
    st.caption("Chats are stored per user, redacted, and visible only to you.")

if not hist:
    with st.chat_message("assistant"):
        st.markdown("Hi, I'm the incident assistant. Pick an incident above and ask why it happened, what the evidence shows, what the runbook says, or which actions are proposed. I can't approve or run anything.")
for msg in hist:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        meta = msg.get("meta") or {}
        if msg["role"] == "assistant" and meta:
            cites = " · ".join(dict.fromkeys(c["label"] for c in meta.get("citations", [])))
            st.caption((f"Sources: {cites}  |  " if cites else "") + f"answered by {meta.get('source', 'rules')}" + ("  |  no action taken" if meta.get("intent") == "refused" else ""))
            if meta.get("intent") == "refused" and me["role"] in ("engineer", "admin"):
                ui.link("views/approvals.py", "Open the Approval queue", ":material/verified_user:")

last = next((m_ for m_ in reversed(hist) if m_["role"] == "assistant"), None)
sugg = (last or {}).get("meta", {}).get("suggestions") or (["Why did this happen?", "Show the evidence", "What actions are proposed?"] if sel else ["What incidents are open?", "Which incidents are awaiting approval?", "What is the current MTTR?"])
cols = st.columns(len(sugg[:4]))
for c, s_ in zip(cols, sugg[:4]):
    if c.button(s_, key=f"sg-{s_}", width="stretch"): st.session_state["_ask"] = s_
q = st.session_state.pop("_ask", None) or st.chat_input("Ask about this incident...", max_chars=500)
if q:
    with st.spinner("Checking the incident data..."):
        ui.call("POST", "/chat", json={"message": q, "incident_id": sel})
    st.rerun()
