import json, logging
from conftest import inject

def test_request_id_header_and_structured_log(api, H, caplog):
    with caplog.at_level(logging.INFO, logger="incidentops"):
        r = api.get("/incidents", headers=H["eng"])
    assert r.headers["X-Request-ID"]
    lines = [json.loads(x.message) for x in caplog.records if x.name == "incidentops" and x.message.startswith("{")]
    assert any(l["event"] == "http" and l["path"] == "/incidents" and l["status"] == 200 for l in lines)

def test_async_investigation_worker_persists_result(api, H):
    iid = inject(api, H, "s01")
    r = api.post(f"/incidents/{iid}/investigate/async", headers=H["eng"]); assert r.status_code == 202
    run = api.get(f"/incidents/{iid}/run", headers=H["eng"]).json()
    assert run["status"] in ("completed", "degraded") and run["steps"]
    assert api.get(f"/incidents/{iid}", headers=H["eng"]).json()["investigation"]["hypotheses"]

def test_async_requires_engineer_role(api, H):
    iid = inject(api, H, "s01")
    assert api.post(f"/incidents/{iid}/investigate/async", headers=H["viewer"]).status_code == 403

def test_agent_steps_are_logged_with_incident_id(api, H, caplog):
    iid = inject(api, H, "s02")
    with caplog.at_level(logging.INFO, logger="incidentops.agent"):
        api.post(f"/incidents/{iid}/investigate", headers=H["eng"])
    nodes = {json.loads(r.message)["node"] for r in caplog.records if r.name == "incidentops.agent"}
    assert {"triage", "investigate", "retrieve", "plan", "verify"} <= nodes

def test_tracing_status_reported_without_leaking_key(api, H):
    s = api.get("/admin/settings", headers=H["admin"]).json()
    assert s["tracing"] in ("disabled", "langsmith") and "key" not in json.dumps(s).lower()
