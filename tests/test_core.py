import pytest
from backend.rules import incident_severity, severity_for, validate_alert, validate_action
from tests.conftest import inject, investigate


def test_severity_thresholds():
    assert severity_for("cpu", 79) == "low" and severity_for("cpu", 80) == "medium" and severity_for("cpu", 95) == "high"
    assert severity_for("downtime", 1) == "critical"
    assert incident_severity([{"metric": "cpu", "value": 96}, {"metric": "latency", "value": 4.2}, {"metric": "error_rate", "value": 12}]) == "critical"


@pytest.mark.parametrize("bad", [{"service": "", "metric": "cpu", "value": 1}, {"service": "x", "metric": "disk", "value": 1},
                                 {"service": "x", "metric": "cpu", "value": 150}, {"service": "x", "metric": "cpu", "value": "abc"}])
def test_invalid_alerts_rejected(bad):
    with pytest.raises(ValueError): validate_alert(bad)


def test_api_rejects_invalid_alert(api, H):
    assert api.post("/alerts", json={"service": "x", "metric": "disk", "value": 1}, headers=H["eng"]).status_code == 422
    assert api.post("/alerts", json={"service": "x", "metric": "cpu", "value": -5}, headers=H["eng"]).status_code == 422


def test_alert_storm_correlates_without_losing_alerts(api, H):
    iid = inject(api, H, "s06")
    d = api.get(f"/incidents/{iid}", headers=H["eng"]).json()
    assert len(d["alerts"]) == 12 and sum(a["duplicate"] for a in d["alerts"]) == 11
    assert len(api.get("/incidents", headers=H["eng"]).json()) == 1


def test_different_services_get_separate_incidents(api, H):
    inject(api, H, "s01"); inject(api, H, "s02")
    assert len(api.get("/incidents", headers=H["eng"]).json()) == 2


@pytest.mark.parametrize("sid", [f"s{n:02d}" for n in range(1, 11)])
def test_all_ten_scenarios_meet_expectations(api, H, sid):
    from data.scenarios import BY_ID
    ex = BY_ID[sid]["expect"]; iid = inject(api, H, sid)
    assert api.get(f"/incidents/{iid}", headers=H["eng"]).json()["severity"] == ex["severity"]
    r = investigate(api, H, iid)
    d = api.get(f"/incidents/{iid}", headers=H["eng"]).json()
    acts = [a for a in d["actions"] if a["status"] != "superseded"]
    if ex["op"]:
        assert acts and acts[0]["op"] == ex["op"] and d["status"] == "awaiting_approval"
        if "target" in ex: assert acts[0]["params"]["target_version"] == ex["target"]
        if ex["approve"]:
            a = api.post(f"/actions/{acts[0]['id']}/approve", headers=H["eng"]); assert a.status_code == 200, a.text
            d = api.get(f"/incidents/{iid}", headers=H["eng"]).json()
    else:
        assert not acts
    assert d["status"] == ex["final"]
    if ex.get("degraded"): assert r["degraded"]


def test_validate_action_allowlist():
    s = {"svc"}
    for op, p in [("drop_db", {"service": "svc"}), ("scale", {"service": "svc", "replicas": 50}), ("scale", {"service": "svc", "replicas": True}),
                  ("config_change", {"service": "svc", "key": "admin.password", "value": "x"}), ("config_change", {"service": "svc", "key": "cache.ttl_seconds", "value": 99999}),
                  ("restart", {"service": "prod-db"}), ("rollback", {"service": "svc", "target_version": "9.9"})]:
        with pytest.raises(ValueError): validate_action(op, p, services=s, versions=["1.0"])
