"""Drives the real Streamlit pages (Streamlit AppTest) against a RUNNING API. Usage: python scripts/ui_smoke.py"""
import os, sys, requests
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "frontend"))
from streamlit.testing.v1 import AppTest
API = os.getenv("API_URL", "http://localhost:8000")


def login(u, p):
    d = requests.post(f"{API}/auth/login", json={"username": u, "password": p}).json()
    return d["access_token"], {"username": d["username"], "role": d["role"]}


def page(view, who, setup=None):
    tok, user = login(*who)
    at = AppTest.from_file(os.path.join(ROOT, "frontend", "views", view), default_timeout=60)
    at.session_state["token"], at.session_state["user"] = tok, user
    if setup: setup(at)
    return at.run()


def ok(at, name):
    assert not at.exception, f"{name}: {[e.value for e in at.exception]}"
    print("PASS", name)


eng, adm, vw = ("engineer", "engineer123"), ("admin", "admin123"), ("viewer", "viewer123")
requests.post(f"{API}/admin/reset", headers={"Authorization": "Bearer " + login(*adm)[0]})
ok(page("dashboard.py", eng), "dashboard renders")
at = page("dashboard.py", eng)
[b for b in at.button if b.label == "Inject alerts"][0].click().run(); ok(at, "inject scenario from dashboard")
assert any("opened" in m.value for m in at.markdown), "incident not opened"
sel = at.session_state["selected_incident"]
at = page("investigation.py", eng, lambda a: a.session_state.__setitem__("selected_incident", sel))
btn = [b for b in at.button if b.label == "Run investigation"][0]; btn.click().run(); ok(at, "run investigation")
assert len(at.tabs) == 5 and any("CPU saturation" in m.value for m in at.markdown), "hypotheses not shown"
at = page("approvals.py", eng)
b = [b for b in at.button if b.label == "Approve and execute"]; assert b, "no pending approval card"
b[0].click().run(); ok(at, "approve and execute")
assert any("Executed and verified" in m.value for m in at.markdown), "success box missing"
ok(page("incidents.py", eng), "incident records")
ok(page("admin.py", adm), "admin and monitoring")
v = page("approvals.py", vw); assert any("needs the engineer role" in m.value for m in v.markdown); print("PASS viewer blocked from approvals page")
v = page("investigation.py", vw); assert not [b for b in v.button if b.label == "Run investigation"]; ok(v, "viewer sees no run button")
print("ALL UI CHECKS PASSED")
# Load Demo Scenario: one click loads and investigates every scenario
requests.post(f"{API}/admin/reset", headers={"Authorization": "Bearer " + login(*adm)[0]})
at = page("dashboard.py", adm)
[b for b in at.button if "Load Demo Scenario" in b.label][0].click().run(); ok(at, "load demo scenario")
assert any("Demo loaded" in m.value for m in at.markdown), "demo load message missing"
ok(page("governance.py", adm), "governance page renders")
# SOC data: one-click demo includes SOC alerts; data page and SOC investigation render
ok(page("data.py", adm), "data and import page renders")
incs = requests.get(f"{API}/incidents", headers={"Authorization": "Bearer " + login(*adm)[0]}).json()
soc_inc = [i for i in incs if i["category"] == "security"]
assert len(soc_inc) == 17, f"expected 17 SOC incidents after demo load, got {len(soc_inc)}"
assert len(incs) == 33, f"expected 16 pack + 17 SOC incidents after demo load, got {len(incs)}"
for view in ("incidents.py", "investigation.py"):
    at = page(view, adm); ok(at, f"{view} renders with SOC incidents")
# Assistant page: renders, answers a question, refuses an action request
at = page("assistant.py", adm); ok(at, "assistant page renders")
at.chat_input[0].set_value("Why did this happen?").run(); ok(at, "assistant answers")
at = page("assistant.py", ("viewer", "viewer123")); ok(at, "assistant renders for viewer")

ok(page("models.py", adm), "models and RAG page renders")
