"""Shared Streamlit helpers: API client, session auth, theme, small HTML components."""
import html, os
import requests
import streamlit as st

API = os.getenv("API_URL", "http://localhost:8000")
SEV = {"critical": "#F87171", "high": "#FB923C", "medium": "#FBBF24", "low": "#60A5FA"}
STATUS = {"open": "#60A5FA", "investigating": "#2DD4BF", "awaiting_approval": "#A78BFA", "remediating": "#2DD4BF", "resolved": "#34D399",
          "escalated": "#F87171", "needs_human": "#FB923C", "verified": "#34D399", "failed_escalated": "#F87171", "pending": "#A78BFA",
          "rejected": "#94A3B8", "expired": "#94A3B8", "superseded": "#94A3B8", "approved": "#2DD4BF", "executing": "#2DD4BF"}
VIOLET, TEAL = "#8B5CF6", "#2DD4BF"
CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=swap');
html, body, [class*="css"], .stMarkdown, button, input, textarea { font-family: 'Inter', system-ui, sans-serif; }
.block-container { padding-top: 1.4rem; max-width: 1400px; }
.stApp { background: radial-gradient(1200px 500px at 85% -10%, rgba(139,92,246,.16), transparent), #0B1020; }
[data-testid="stSidebar"] { background: #0A0F24; border-right: 1px solid #1E2748; }
[data-testid="stSidebar"] a[aria-current="page"] { background: rgba(139,92,246,.22); border-radius: 10px; }
h1, h2, h3 { color: #F1F3FB; letter-spacing: -0.01em; font-weight: 600; }
h3 { font-size: 1.05rem !important; }
.mono { font-family: 'JetBrains Mono', monospace; font-size: .82em; color: #A5B4FC; }
.hero { padding: 6px 0 14px; } .hero h1 { margin: 0; font-size: 1.9rem; } .hero h1 span { color: #A78BFA; }
.hero p { margin: 4px 0 0; color: #94A3C4; }
.panel { background: linear-gradient(180deg,#141C38,#10172F); border: 1px solid #26305A; border-radius: 16px; padding: 16px 18px; height: 100%; }
.panel h4 { margin: 0 0 10px; font-size: .95rem; color: #E6E9F5; font-weight: 600; }
.kpi { background: linear-gradient(180deg,#141C38,#10172F); border: 1px solid #26305A; border-radius: 16px; padding: 14px 18px; }
.kpi .l { color: #94A3C4; font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; }
.kpi .v { font-size: 2rem; font-weight: 600; color: #F1F3FB; line-height: 1.2; } .kpi .s { color: #7C8AB0; font-size: .78rem; }
.kpi .bar { height: 4px; border-radius: 4px; margin-top: 8px; background: #1E2748; overflow: hidden; } .kpi .bar i { display: block; height: 100%; }
.rail { background: #141C38; border: 1px solid #26305A; border-left-width: 5px; border-radius: 14px; padding: 12px 16px; margin-bottom: 10px; }
.rail .t { font-weight: 600; color: #F1F3FB; } .rail .s { color: #94A3C4; font-size: .86rem; margin-top: 3px; }
.pill { display: inline-block; padding: 1px 10px; border-radius: 999px; font-size: .72rem; font-weight: 600; margin-left: 6px; text-transform: capitalize; }
.svc { background: #141C38; border: 1px solid #26305A; border-radius: 14px; padding: 12px 14px; margin-bottom: 10px; }
.svc .n { font-weight: 600; color: #F1F3FB; } .svc .m { color: #7C8AB0; font-size: .78rem; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
.ctl { display: flex; justify-content: space-between; padding: 7px 0; border-bottom: 1px solid #1E2748; font-size: .88rem; color: #C8D0EA; }
.step { border-left: 2px solid #2A3562; padding: 0 0 12px 14px; margin-left: 6px; font-size: .9rem; position: relative; color: #D5DBF0; }
.step:before { content: ''; position: absolute; left: -6px; top: 5px; width: 10px; height: 10px; border-radius: 50%; background: #2DD4BF; box-shadow: 0 0 0 3px rgba(45,212,191,.18); }
.step .ts { color: #7C8AB0; font-size: .76rem; }
.warnbox, .okbox, .badbox { border-radius: 12px; padding: 10px 14px; margin: 8px 0; border: 1px solid; }
.warnbox { background: rgba(251,191,36,.10); border-color: rgba(251,191,36,.4); color: #FCD34D; }
.okbox { background: rgba(52,211,153,.10); border-color: rgba(52,211,153,.4); color: #6EE7B7; }
.badbox { background: rgba(248,113,113,.10); border-color: rgba(248,113,113,.4); color: #FCA5A5; }
.log { font-family: 'JetBrains Mono', monospace; font-size: .78rem; background: #070B1A; color: #C7D2FE; padding: 12px 14px; border-radius: 12px; border: 1px solid #1E2748; white-space: pre-wrap; }
div[data-testid="stDataFrame"] { border: 1px solid #26305A; border-radius: 12px; overflow: hidden; }
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
def kpi(col, label, value, sub="", accent=VIOLET, pct=None):
    bar = f'<div class="bar"><i style="width:{max(4, min(100, pct))}%;background:{accent}"></i></div>' if pct is not None else ""
    col.markdown(f'<div class="kpi"><div class="l">{esc(label)}</div><div class="v">{esc(value)}</div><div class="s">{esc(sub)}</div>{bar}</div>', unsafe_allow_html=True)
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
