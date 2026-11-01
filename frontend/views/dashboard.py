import altair as alt
import pandas as pd
import streamlit as st
import ui

me = ui.guard()
d = ui.call("GET", "/dashboard")
head, btn = st.columns([4, 1.3])
with head:
    st.markdown(f'<div class="hero"><h1>Welcome back, <span>{ui.esc(me["username"])}</span></h1>'
                '<p>What is broken now, what needs a decision, and how fast we recover.</p></div>', unsafe_allow_html=True)
f = st.session_state.pop("_flash", None)
if f: ui.box(*f)


def load_demo():
    """Reset (admin only), load the incident data pack (12 scenarios as files), investigate every incident, add the SOC sample."""
    bar = st.progress(0.0, text="Preparing sandbox")
    if me["role"] == "admin": ui.call("POST", "/admin/reset")
    bar.progress(0.1, text="Loading alerts, logs, metrics, traces, deployments and runbooks")
    pack = ui.call("POST", "/pack/load", timeout=120)
    ids, fails = (pack["incident_ids"] if pack else []), (0 if pack else 1)
    for n, i in enumerate(ids):
        r = ui.call("POST", f"/incidents/{i}/investigate", timeout=120)
        if not r or r.get("status") == "failed": fails += 1
        bar.progress(0.1 + 0.7 * (n + 1) / max(len(ids), 1), text=f"Agents investigating ({n + 1} of {len(ids)})")
    soc = ui.call("POST", "/import/sample/soc_real")  # one alert per SOC playbook type, from the bundled real alert file
    for i in (soc["incident_ids"] if soc else []):
        r = ui.call("POST", f"/incidents/{i}/investigate", timeout=60)
        if not r or r.get("status") == "failed": fails += 1
    bar.progress(1.0, text="Done")
    n_soc = len(soc["incident_ids"]) if soc else 0
    if ids: st.session_state["selected_incident"] = ids[0]
    ui.flash("ok" if not fails else "warn", f"Demo loaded: {len(ids)} incidents from the data pack (12 scenarios) and {n_soc} SOC alerts investigated" + (f", {fails} step(s) failed, see messages above" if fails else ". Review the Approval queue next."))


with btn:
    st.write("")
    if me["role"] == "viewer": st.caption("Viewers cannot load demo data.")
    elif st.button("⚡ Load Demo Scenario", type="primary", width="stretch"):
        load_demo(); st.rerun()
if not d: st.stop()

c = st.columns(4)
tot = max(d["total_incidents"], 1)
ui.kpi(c[0], "Open incidents", d["open"], f"{d['total_incidents']} total", "#F87171", 100 * d["open"] / tot)
ui.kpi(c[1], "Awaiting approval", d["awaiting_approval"], "human decision required", ui.VIOLET, 100 * d["awaiting_approval"] / tot)
ui.kpi(c[2], "Mean time to recovery", f"{d['mttr_min']} min", f"{d['resolved']} resolved", ui.TEAL, 100 * d["resolved"] / tot)
ui.kpi(c[3], "Escalated to humans", d["escalated"], "needs engineer", "#FB923C", 100 * d["escalated"] / tot)
st.write("")

if d["total_incidents"] == 0:
    ui.panel("Nothing to show yet", '<p style="color:#94A3C4">Click <b>Load Demo Scenario</b> to load consistent synthetic alerts, logs, metrics, deployment events and runbooks. No file uploads are required.</p>')
left, right = st.columns([3, 2])
with left:
    st.markdown("### Alert volume")
    al = ui.call("GET", "/alerts", params={"limit": 500}) or []
    if al:
        df = pd.DataFrame(al); df["ts"] = pd.to_datetime(df["ts"])
        df["kind"] = df["duplicate"].map({True: "duplicate", False: "unique"})
        g = df.groupby([pd.Grouper(key="ts", freq="5min"), "kind"]).size().reset_index(name="alerts")
        ch = alt.Chart(g).mark_area(opacity=.55, line=True, interpolate="monotone").encode(
            x=alt.X("ts:T", title=None), y=alt.Y("alerts:Q", title=None, stack=True),
            color=alt.Color("kind:N", scale=alt.Scale(domain=["unique", "duplicate"], range=[ui.TEAL, ui.VIOLET]), legend=alt.Legend(orient="top", title=None))
        ).properties(height=240).configure_view(strokeWidth=0).configure_axis(gridColor="#1E2748", labelColor="#94A3C4")
        st.altair_chart(ch, width="stretch")
        st.caption(f"{len(al)} alerts received, {int(df['duplicate'].sum())} correlated as duplicates. Source alerts are kept.")
    else: st.info("No alerts yet.")
with right:
    st.markdown("### Incidents by severity")
    if d["by_severity"]:
        sv = pd.DataFrame({"severity": list(d["by_severity"]), "count": list(d["by_severity"].values())})
        dom = [s for s in ui.SEV if s in d["by_severity"]]
        ch = alt.Chart(sv).mark_arc(innerRadius=62, cornerRadius=4).encode(
            theta="count:Q", color=alt.Color("severity:N", scale=alt.Scale(domain=dom, range=[ui.SEV[s] for s in dom]), legend=alt.Legend(orient="right", title=None))
        ).properties(height=240).configure_view(strokeWidth=0)
        st.altair_chart(ch, width="stretch")
    else: st.caption("No incidents yet.")

a, b = st.columns([3, 2])
with a:
    st.markdown("### Service health")
    svcs = ui.call("GET", "/services") or []
    cols = st.columns(3)
    for n, s in enumerate(svcs):
        bad = s["open_incident"]; col = "#F87171" if bad else "#34D399"
        cols[n % 3].markdown(f'<div class="svc"><div class="n">{ui.esc(s["name"])}</div><div class="m">{ui.esc(s["environment"])} · {ui.esc(s["owner"])}</div>'
                             f'<div style="margin-top:6px;color:{col};font-size:.85rem"><span class="dot" style="background:{col}"></span>{"Incident open" if bad else "Healthy"}</div></div>', unsafe_allow_html=True)
with b:
    st.markdown("### Safety controls")
    rows = [("Human approval before any change", "Enforced"), ("Allowlisted sandbox actions only", "Enforced"),
            ("Secret and PII redaction", "Active"), ("Retrieved text treated as untrusted", "Active"),
            ("Pending approvals", str(d["awaiting_approval"]))]
    ui.panel("AI governance", "".join(f'<div class="ctl"><span>{ui.esc(k)}</span><span style="color:#6EE7B7">{ui.esc(v)}</span></div>' for k, v in rows))

st.markdown("### Active incidents")
incs = ui.call("GET", "/incidents") or []
cols = st.columns(3)
for n, i in enumerate(incs[:6]):
    with cols[n % 3]: ui.incident_card(i)
if me["role"] != "viewer":
    with st.expander("Launch a single scenario"):
        sc = ui.call("GET", "/scenarios") or []
        pick = st.selectbox("Scenario", sc, format_func=lambda s: f"{s['id']}  {s['name']}")
        if pick:
            st.caption(pick["description"])
            if st.button("Inject alerts"):
                r = ui.call("POST", f"/scenarios/{pick['id']}/inject", f"Created {pick['id']}")
                if r: st.session_state["selected_incident"] = r["id"]; ui.flash("ok", f"{r['ref']} opened ({r['severity']})."); st.rerun()
