"""Shared Streamlit helpers: API client, session auth, theme, small HTML components."""
import html, os
import requests
import streamlit as st

API = os.getenv("API_URL", "http://localhost:8000")
SEV = {"critical": "#F43F5E", "high": "#FB923C", "medium": "#FACC15", "low": "#38BDF8"}
STATUS = {"open": "#60A5FA", "investigating": "#2DD4BF", "awaiting_approval": "#C084FC", "remediating": "#2DD4BF", "resolved": "#34D399",
          "escalated": "#F87171", "needs_human": "#FB923C", "verified": "#34D399", "failed_escalated": "#F87171", "pending": "#A78BFA",
          "rejected": "#94A3B8", "expired": "#94A3B8", "superseded": "#94A3B8", "approved": "#2DD4BF", "executing": "#2DD4BF"}
VIOLET, TEAL = "#8B5CF6", "#2DD4BF"
CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=swap');
html, body, [class*="css"], .stMarkdown, button, input, textarea { font-family: 'Inter', system-ui, sans-serif; }
.block-container { padding-top: 1.4rem; max-width: 1400px; }
/* ---------- motion ---------- */
@keyframes aurora { 0% { background-position: 0% 0%, 100% 0%, 50% 100%, 0 0; } 50% { background-position: 60% 40%, 40% 60%, 80% 30%, 0 0; } 100% { background-position: 0% 0%, 100% 0%, 50% 100%, 0 0; } }
@keyframes fadeUp { from { opacity: 0; transform: translateY(20px) scale(.98); } to { opacity: 1; transform: none; } }
@keyframes slideIn { from { opacity: 0; transform: translateX(-28px); } to { opacity: 1; transform: none; } }
@keyframes grow { from { width: 0; } }
@keyframes pulse { 0% { box-shadow: 0 0 0 0 var(--c, rgba(52,211,153,.7)); } 70% { box-shadow: 0 0 0 10px rgba(0,0,0,0); } 100% { box-shadow: 0 0 0 0 rgba(0,0,0,0); } }
@keyframes flow { 0% { background-position: 0% 50%; } 100% { background-position: 300% 50%; } }
@keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }
@keyframes glow { 0%, 100% { box-shadow: 0 0 16px rgba(139,92,246,.5); } 50% { box-shadow: 0 0 32px rgba(45,212,191,.7); } }
@keyframes sweep { 0% { transform: translateX(-130%); } 60%, 100% { transform: translateX(230%); } }
.stApp { background: radial-gradient(900px 520px at 8% -5%, rgba(139,92,246,.30), transparent 62%), radial-gradient(900px 600px at 98% 8%, rgba(45,212,191,.20), transparent 62%),
         radial-gradient(800px 600px at 55% 108%, rgba(244,114,182,.18), transparent 62%), #0B1020; background-size: 140% 140%, 140% 140%, 140% 140%, 100% 100%; animation: aurora 24s ease-in-out infinite; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0C1230, #090D22); border-right: 1px solid #1E2748; }
[data-testid="stSidebar"] a { transition: transform .2s ease, background .2s ease; border-radius: 10px; }
[data-testid="stSidebar"] a:hover { transform: translateX(5px); background: rgba(139,92,246,.16); }
[data-testid="stSidebar"] a[aria-current="page"] { background: linear-gradient(90deg, rgba(139,92,246,.55), rgba(45,212,191,.22)); }
h1, h2, h3 { color: #F1F3FB; letter-spacing: -0.01em; font-weight: 600; }
h3 { font-size: 1.05rem !important; }
.mono { font-family: 'JetBrains Mono', monospace; font-size: .82em; color: #A5B4FC; }
.hero { padding: 6px 0 14px; }
.hero h1 { margin: 0; font-size: 2rem; font-weight: 700; background: linear-gradient(90deg, #A78BFA, #2DD4BF, #F472B6, #FBBF24, #A78BFA); background-size: 300% 100%;
           -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; color: transparent; animation: flow 9s linear infinite; }
.hero h1 span { -webkit-text-fill-color: transparent; }
.hero p { margin: 4px 0 0; color: #A9B6D8; animation: fadeUp .8s both .25s; }
.live { display: inline-block; width: 9px; height: 9px; border-radius: 50%; background: #34D399; margin-right: 8px; animation: pulse 1.6s infinite; }
.panel { position: relative; background: linear-gradient(160deg, rgba(139,92,246,.14), rgba(16,23,47,.95) 55%); border: 1px solid #2E3A6E; border-radius: 18px; padding: 16px 18px; height: 100%;
         animation: fadeUp .7s cubic-bezier(.2,.8,.2,1) both .2s; transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease; }
.panel:hover { transform: translateY(-4px); border-color: #8B5CF6; box-shadow: 0 14px 34px rgba(139,92,246,.28); }
.panel h4 { margin: 0 0 10px; font-size: .95rem; color: #E6E9F5; font-weight: 600; }
.kpi { position: relative; overflow: hidden; background: linear-gradient(160deg, rgba(var(--rgb, 139,92,246), .26), rgba(16,23,47,.94) 58%); border: 1px solid rgba(var(--rgb, 139,92,246), .55);
       border-radius: 18px; padding: 16px 20px; animation: fadeUp .75s cubic-bezier(.2,.8,.2,1) both; animation-delay: var(--d, 0s); transition: transform .25s ease, box-shadow .25s ease; }
.kpi:hover { transform: translateY(-7px) scale(1.025); box-shadow: 0 16px 38px rgba(var(--rgb, 139,92,246), .42); }
.kpi:after { content: ""; position: absolute; top: 0; left: 0; width: 40%; height: 100%; background: linear-gradient(100deg, transparent, rgba(255,255,255,.14), transparent);
             transform: translateX(-130%); animation: sweep 6s ease-in-out infinite; animation-delay: calc(var(--d, 0s) + 1.6s); pointer-events: none; }
.kpi .ic { float: right; font-size: 1.6rem; animation: float 3.4s ease-in-out infinite; animation-delay: var(--d, 0s); }
.kpi .l { color: #B6C2E2; font-size: .76rem; text-transform: uppercase; letter-spacing: .07em; }
.kpi .v { font-size: 2.3rem; font-weight: 700; line-height: 1.2; background: linear-gradient(90deg, #FFFFFF, rgb(var(--rgb, 139,92,246))); -webkit-background-clip: text; background-clip: text;
          -webkit-text-fill-color: transparent; color: transparent; }
.kpi .s { color: #8F9CC4; font-size: .78rem; }
.kpi .bar { height: 5px; border-radius: 5px; margin-top: 9px; background: rgba(255,255,255,.08); overflow: hidden; }
.kpi .bar i { display: block; height: 100%; width: var(--w, 100%); border-radius: 5px; background: linear-gradient(90deg, rgba(var(--rgb, 139,92,246), .55), rgb(var(--rgb, 139,92,246)));
              box-shadow: 0 0 12px rgba(var(--rgb, 139,92,246), .9); animation: grow 1.3s cubic-bezier(.2,.8,.2,1) both; animation-delay: calc(var(--d, 0s) + .35s); }
.rail { background: linear-gradient(120deg, rgba(20,28,56,.98), rgba(24,34,70,.92)); border: 1px solid #2A3566; border-left-width: 5px; border-radius: 14px; padding: 12px 16px; margin-bottom: 10px;
        animation: slideIn .65s cubic-bezier(.2,.8,.2,1) both; transition: transform .22s ease, box-shadow .22s ease; }
.rail:hover { transform: translateX(7px) scale(1.01); box-shadow: 0 10px 28px rgba(0,0,0,.45), 0 0 22px rgba(139,92,246,.22); }
div[data-testid="stColumn"]:nth-child(2) .rail { animation-delay: .12s; } div[data-testid="stColumn"]:nth-child(3) .rail { animation-delay: .24s; }
.rail .t { font-weight: 600; color: #F1F3FB; } .rail .s { color: #A5B2D6; font-size: .86rem; margin-top: 3px; }
.pill { display: inline-block; padding: 1px 10px; border-radius: 999px; font-size: .72rem; font-weight: 600; margin-left: 6px; text-transform: capitalize; }
.svc { background: linear-gradient(150deg, rgba(20,28,56,.98), rgba(16,23,47,.96)); border: 1px solid #2A3566; border-radius: 14px; padding: 12px 14px; margin-bottom: 10px;
       animation: fadeUp .6s cubic-bezier(.2,.8,.2,1) both; animation-delay: var(--d, 0s); transition: transform .22s ease, box-shadow .22s ease, border-color .22s ease; }
.svc:hover { transform: translateY(-5px); box-shadow: 0 12px 26px rgba(45,212,191,.22); border-color: #2DD4BF; }
.svc.bad { border-color: rgba(248,113,113,.55); box-shadow: 0 0 22px rgba(248,113,113,.14); } .svc.bad:hover { border-color: #F87171; box-shadow: 0 12px 28px rgba(248,113,113,.32); }
.svc .n { font-weight: 600; color: #F1F3FB; } .svc .m { color: #8F9CC4; font-size: .78rem; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
.dot.ok { background: #34D399; --c: rgba(52,211,153,.7); animation: pulse 2.2s infinite; } .dot.bad { background: #F87171; --c: rgba(248,113,113,.8); animation: pulse 1.1s infinite; }
.ctl { display: flex; justify-content: space-between; padding: 7px 0; border-bottom: 1px solid #1E2748; font-size: .88rem; color: #C8D0EA; }
.step { border-left: 2px solid #2A3562; padding: 0 0 12px 14px; margin-left: 6px; font-size: .9rem; position: relative; color: #D5DBF0; }
.step:before { content: ''; position: absolute; left: -6px; top: 5px; width: 10px; height: 10px; border-radius: 50%; background: #2DD4BF; box-shadow: 0 0 0 3px rgba(45,212,191,.18); }
.step .ts { color: #7C8AB0; font-size: .76rem; }
.warnbox, .okbox, .badbox { border-radius: 12px; padding: 10px 14px; margin: 8px 0; border: 1px solid; animation: fadeUp .5s both; }
.warnbox { background: rgba(251,191,36,.10); border-color: rgba(251,191,36,.4); color: #FCD34D; }
.okbox { background: rgba(52,211,153,.10); border-color: rgba(52,211,153,.4); color: #6EE7B7; }
.badbox { background: rgba(248,113,113,.10); border-color: rgba(248,113,113,.4); color: #FCA5A5; }
.log { font-family: 'JetBrains Mono', monospace; font-size: .78rem; background: #070B1A; color: #C7D2FE; padding: 12px 14px; border-radius: 12px; border: 1px solid #1E2748; white-space: pre-wrap; }
div[data-testid="stDataFrame"] { border: 1px solid #2E3A6E; border-radius: 12px; overflow: hidden; }
div[data-testid="stVegaLiteChart"], div[data-testid="stArrowVegaLiteChart"] { animation: fadeUp .9s cubic-bezier(.2,.8,.2,1) both .25s; }
button[kind="primary"], [data-testid="stBaseButton-primary"] { background: linear-gradient(90deg, #8B5CF6, #EC4899, #2DD4BF, #8B5CF6) !important; background-size: 300% 100% !important; border: 0 !important; color: #fff !important;
  font-weight: 600 !important; animation: flow 6s linear infinite, glow 2.6s ease-in-out infinite; transition: transform .2s ease; }
button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover { transform: translateY(-3px) scale(1.04); }
@media (prefers-reduced-motion: reduce) { *, *:before, *:after { animation: none !important; transition: none !important; } }
</style>"""


def inject_css(): st.markdown(CSS, unsafe_allow_html=True)
def esc(x): return html.escape(str(x))
def pill(text, color): return f'<span class="pill" style="background:{color}26;color:{color};border:1px solid {color}66">{esc(text).replace("_", " ")}</span>'
def sev_pill(s): return pill(s, SEV.get(s, "#6B7785"))
def status_pill(s): return pill(s, STATUS.get(s, "#6B7785"))
def flash(kind, text): st.session_state["_flash"] = (kind, text)  # survives one st.rerun()
def hero(title, sub):
    st.markdown(f'<div class="hero"><h1>{esc(title)}</h1><p>{esc(sub)}</p></div>', unsafe_allow_html=True)
    f = st.session_state.pop("_flash", None)
    if f: box(*f)
def _rgb(h): return ",".join(str(int(h.lstrip("#")[k:k + 2], 16)) for k in (0, 2, 4))
def kpi(col, label, value, sub="", accent=VIOLET, pct=None, icon="", delay=0.0):
    """Animated gradient KPI card: fades up, bar grows, shine sweeps, lifts on hover."""
    bar = '<div class="bar"><i></i></div>' if pct is not None else ""
    w = max(4, min(100, pct)) if pct is not None else 100
    col.markdown(f'<div class="kpi" style="--rgb:{_rgb(accent)};--d:{delay}s;--w:{w}%"><span class="ic">{icon}</span><div class="l">{esc(label)}</div><div class="v">{esc(value)}</div>'
                 f'<div class="s">{esc(sub)}</div>{bar}</div>', unsafe_allow_html=True)
def svc_card(name, meta, bad, delay=0.0):
    """Service health card with a pulsing status dot (fast red pulse when an incident is open)."""
    st_ = "bad" if bad else "ok"; color = "#F87171" if bad else "#34D399"
    return (f'<div class="svc {st_ if bad else ""}" style="--d:{delay}s"><div class="n">{esc(name)}</div><div class="m">{esc(meta)}</div>'
            f'<div style="margin-top:6px;color:{color};font-size:.85rem"><span class="dot {st_}"></span>{"Incident open" if bad else "Healthy"}</div></div>')
def box(kind, text): st.markdown(f'<div class="{kind}box">{esc(text)}</div>', unsafe_allow_html=True)


def incident_card(i):
    st.markdown(f'<div class="rail" style="border-left-color:{SEV.get(i["severity"], "#6B7785")}"><div class="t"><span class="mono">{esc(i["ref"])}</span> &nbsp;{esc(i["title"])}'
                f'{sev_pill(i["severity"])}{status_pill(i["status"])}</div><div class="s">{esc(i["summary"])}</div></div>', unsafe_allow_html=True)


def user(): return st.session_state.get("user")
def logout():
    for k in ("token", "user"): st.session_state.pop(k, None)
    st.rerun()


class ApiError(Exception):
    def __init__(self, status, detail): super().__init__(detail); self.status = status


def api(method, path, **kw):
    headers = {"Authorization": f"Bearer {st.session_state.get('token', '')}"}
    try:
        r = requests.request(method, f"{API}{path}", headers=headers, timeout=kw.pop("timeout", 60), **kw)
    except requests.RequestException:
        raise ApiError(0, f"Cannot reach the API at {API}. Start the backend and try again.")
    if r.status_code == 401 and st.session_state.get("token"):
        st.session_state.pop("token", None); st.session_state.pop("user", None)
        raise ApiError(401, "Your session expired. Sign in again.")
    if r.status_code >= 400:
        try: d = r.json().get("detail", r.text)
        except Exception: d = r.text
        raise ApiError(r.status_code, d if isinstance(d, str) else str(d))
    return r.text if "text/plain" in r.headers.get("content-type", "") else r.json()


def guard(min_role="viewer"):
    """Call at top of every view. Server-side RBAC is the real control; this only shapes the UI."""
    inject_css()
    u = user()
    if not u:
        st.warning("Sign in to continue."); st.stop()
    if {"viewer": 1, "engineer": 2, "admin": 3}[u["role"]] < {"viewer": 1, "engineer": 2, "admin": 3}[min_role]:
        box("bad", f"This page needs the {min_role} role. You are signed in as {u['role']}."); st.stop()
    return u


def call(method, path, ok_msg=None, **kw):
    """API call that shows a clear error instead of a stack trace."""
    try:
        r = api(method, path, **kw)
        if ok_msg: st.toast(ok_msg)
        return r
    except ApiError as e:
        box("bad", f"{e}" + (f" (HTTP {e.status})" if e.status else "")); return None


def panel(title, body_html): st.markdown(f'<div class="panel"><h4>{esc(title)}</h4>{body_html}</div>', unsafe_allow_html=True)


def link(path, label, icon=None):
    """Page link that degrades to plain text when the page is not registered (for example when a view is rendered on its own in tests)."""
    try: st.page_link(path, label=label, icon=icon)
    except Exception: st.caption(label)
