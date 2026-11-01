import streamlit as st
import ui

st.set_page_config(page_title="IncidentOps", page_icon=":material/crisis_alert:", layout="wide")

import os, sys, subprocess, time, socket
from pathlib import Path


@st.cache_resource(show_spinner="Starting backend, this takes a few seconds...")
def start_backend():
    """On Streamlit Cloud there is no separate server, so launch the mock service and API here."""
    if os.getenv("API_URL"):          # an external backend is configured, don't start another
        return "external"
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(root)}
    subprocess.Popen([sys.executable, "-m", "uvicorn", "integrations.mock_app:app", "--port", "8001"], cwd=root, env=env)
    subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--port", "8000"], cwd=root, env=env)
    for _ in range(60):               # wait until the API accepts connections
        try:
            socket.create_connection(("127.0.0.1", 8000), timeout=1).close(); break
        except OSError:
            time.sleep(1)
    return "local"


start_backend()
ui.inject_css()

   
def login():
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        ui.hero("IncidentOps", "Investigate incidents with evidence. Fix them only with approval.")
        with st.form("login"):
            u = st.text_input("Username"); p = st.text_input("Password", type="password")
            if st.form_submit_button("Sign in", type="primary", width="stretch"):
                if not u or not p: ui.box("bad", "Enter both a username and a password.")
                else:
                    try:
                        import requests
                        r = requests.post(f"{ui.API}/auth/login", json={"username": u, "password": p}, timeout=10)
                        if r.status_code == 200:
                            d = r.json(); st.session_state.update(token=d["access_token"], user={"username": d["username"], "role": d["role"]}); st.rerun()
                        else: ui.box("bad", "Wrong username or password.")
                    except Exception: ui.box("bad", f"Cannot reach the API at {ui.API}. Start the backend first.")
        st.caption("Demo accounts: admin / admin123, engineer / engineer123, engineer2 / engineer123, viewer / viewer123")


me = ui.user()
if not me:
    st.navigation([st.Page(login, title="Sign in", icon=":material/lock:")]).run()
else:
    pages = [st.Page("views/dashboard.py", title="Dashboard", icon=":material/space_dashboard:", default=True),
             st.Page("views/incidents.py", title="Incident records", icon=":material/folder_open:"),
             st.Page("views/investigation.py", title="AI investigation", icon=":material/troubleshoot:"),
             st.Page("views/assistant.py", title="Assistant", icon=":material/chat:")]
    if me["role"] in ("engineer", "admin"): pages.append(st.Page("views/approvals.py", title="Approval queue", icon=":material/verified_user:"))
    if me["role"] in ("engineer", "admin"): pages.append(st.Page("views/data.py", title="Data and import", icon=":material/upload_file:"))
    if me["role"] == "admin": pages.append(st.Page("views/models.py", title="Models and RAG", icon=":material/model_training:"))
    if me["role"] == "admin": pages.append(st.Page("views/governance.py", title="AI governance", icon=":material/policy:"))
    if me["role"] == "admin": pages.append(st.Page("views/admin.py", title="Admin and monitoring", icon=":material/tune:"))
    with st.sidebar:
        st.markdown("### 🛡️ IncidentOps")
        st.caption(f"{me['username']} · {me['role']}")
        if st.button("Sign out", width="stretch"): ui.logout()
    st.navigation(pages).run()
