import json, pathlib
def req(name, method, path, body=None, auth=True):
    r = {"name": name, "request": {"method": method, "header": [{"key": "Content-Type", "value": "application/json"}] + ([{"key": "Authorization", "value": "Bearer {{token}}"}] if auth else []),
         "url": {"raw": "{{base}}" + path, "host": ["{{base}}"], "path": path.strip("/").split("/")}}}
    if body: r["request"]["body"] = {"mode": "raw", "raw": json.dumps(body, indent=1)}
    if name == "Login": r["event"] = [{"listen": "test", "script": {"exec": ["pm.collectionVariables.set('token', pm.response.json().access_token);"]}}]
    return r
items = [req("Login", "POST", "/auth/login", {"username": "engineer", "password": "engineer123"}, False),
 req("Inject scenario s03", "POST", "/scenarios/s03/inject"), req("Ingest alert", "POST", "/alerts", {"service": "payment-api", "metric": "cpu", "value": 96}),
 req("List incidents", "GET", "/incidents"), req("Get incident", "GET", "/incidents/1"), req("Investigate", "POST", "/incidents/1/investigate"),
 req("List pending actions", "GET", "/actions?status=pending"), req("Approve action", "POST", "/actions/1/approve", {"comment": "approved"}),
 req("Reject action", "POST", "/actions/1/reject", {"comment": "rejected"}), req("Incident report", "GET", "/incidents/1/report"),
 req("Dashboard", "GET", "/dashboard"), req("Import requirements", "GET", "/import/requirements"),
 req("Load SOC sample (real_alerts)", "POST", "/import/sample/soc_real"), req("Investigate (background)", "POST", "/incidents/1/investigate/async"),
 req("Latest workflow run", "GET", "/incidents/1/run"), req("Ask the assistant", "POST", "/chat", {"message": "Why did this happen?", "incident_id": 1}),
 req("Assistant history", "GET", "/chat/history?incident_id=1"), req("Audit log (admin)", "GET", "/admin/audit")]
pathlib.Path(__file__).resolve().parents[1].joinpath("docs/IncidentOps.postman_collection.json").write_text(json.dumps(
 {"info": {"name": "IncidentOps AI", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"}, "item": items,
  "variable": [{"key": "base", "value": "http://localhost:8000"}, {"key": "token", "value": ""}]}, indent=1), encoding="utf-8")
