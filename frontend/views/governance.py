import altair as alt
import pandas as pd
import streamlit as st
import ui

me = ui.guard("admin")
ui.hero("AI governance and audit", "Policy checks, evidence coverage, blocked actions, approvals and model configuration.")
aud = ui.call("GET", "/admin/audit", params={"limit": 500}) or []
d = ui.call("GET", "/dashboard"); s = ui.call("GET", "/admin/settings") or {}
incs = ui.call("GET", "/incidents") or []
hyp = cited = 0; sources = set()
for i in incs[:25]:
    x = ui.call("GET", f"/incidents/{i['id']}")
    inv = x and x.get("investigation")
    if inv:
        sources.add(str(inv["narrative"].get("source")))
        for h in inv["hypotheses"]: hyp += 1; cited += bool(h["evidence_ids"])
blocked = [e for e in aud if e["outcome"] != "ok"]
c = st.columns(4)
ui.kpi(c[0], "Audit events", len(aud), "last 500 shown", ui.VIOLET)
ui.kpi(c[1], "Blocked or failed", len(blocked), "fail-closed outcomes", "#F87171", 100 * len(blocked) / max(len(aud), 1))
ui.kpi(c[2], "Evidence coverage", f"{cited}/{hyp}" if hyp else "n/a", "hypotheses with cited evidence", ui.TEAL, 100 * cited / hyp if hyp else 0)
ui.kpi(c[3], "Approval policy", "Separation of duties" if s.get("require_separation_of_duties") == "true" else "Standard", f"expiry {s.get('approval_ttl_min', '?')} min", "#FBBF24")
st.write("")
a, b = st.columns(2)
with a:
    ui.panel("Model and tracing", "".join(f'<div class="ctl"><span>{ui.esc(k)}</span><span>{ui.esc(v)}</span></div>' for k, v in [
        ("LLM provider", s.get("llm_provider", "?")), ("Narrative sources seen", ", ".join(sorted(sources)) or "none yet"),
        ("Database", s.get("database", "?")), ("LangSmith tracing", ("Enabled via environment" if s.get("tracing") == "langsmith" else "Disabled (set LANGSMITH_TRACING and LANGSMITH_API_KEY)") + (", inputs hidden" if s.get("trace_inputs_hidden") else ", inputs visible")), ("Structured logs", "JSON, one line per request and agent step"),
        ("Workflow runs", d["workflow"]["runs"] if d else "?"), ("Tokens in / out", f"{d['workflow']['tokens_in']} / {d['workflow']['tokens_out']}" if d else "?")]))
with b:
    ui.panel("Policy checks", "".join(f'<div class="ctl"><span>{ui.esc(k)}</span><span style="color:#6EE7B7">{v}</span></div>' for k, v in [
        ("Backend role enforcement", "Active"), ("Approval gate on state changes", "Active"), ("Action allowlist (sandbox only)", "Active"),
        ("Redaction before storage", "Active"), ("Prompt-injection stripping on retrieval", "Active")]))
st.write("")
if aud:
    df = pd.DataFrame(aud); df["detail"] = df["detail"].astype(str)
    cnt = df.groupby("event").size().reset_index(name="count")
    st.markdown("### Events by type")
    st.altair_chart(alt.Chart(cnt).mark_bar(color=ui.VIOLET, cornerRadiusEnd=4).encode(x="count:Q", y=alt.Y("event:N", sort="-x", title=None)).properties(height=max(120, 26 * len(cnt))).configure_axis(gridColor="#1E2748", labelColor="#94A3C4"), width="stretch")
    t1, t2, t3 = st.tabs(["Approval history", "Blocked actions", "All events"])
    with t1: st.dataframe(df[df["event"].str.contains("approv|reject", regex=True)], hide_index=True, width="stretch")
    with t2:
        if blocked: st.dataframe(df[df["outcome"] != "ok"], hide_index=True, width="stretch")
        else: st.info("No blocked or failed events recorded.")
    with t3:
        st.dataframe(df, hide_index=True, width="stretch", height=380)
        st.download_button("Download audit log (.csv)", df.to_csv(index=False), file_name="audit.csv", mime="text/csv")
else: st.info("No audit events yet. Use Load Demo Scenario on the dashboard.")
