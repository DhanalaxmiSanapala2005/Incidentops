import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["RETRY_BACKOFF_S"] = "0.001"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp()
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from integrations import client as ic
from integrations.mock_app import app as mock_app

MOCK = TestClient(mock_app)
ic.set_client(MOCK)
KEY = {"X-Service-Key": os.getenv("MOCK_SERVICE_KEY", "mock-monitoring-key")}


@pytest.fixture(scope="session")
def api():
    with TestClient(app) as c:
        yield c


def _login(api, u, p):
    return {"Authorization": "Bearer " + api.post("/auth/login", json={"username": u, "password": p}).json()["access_token"]}


@pytest.fixture(scope="session")
def H(api):
    return {"admin": _login(api, "admin", "admin123"), "eng": _login(api, "engineer", "engineer123"),
            "eng2": _login(api, "engineer2", "engineer123"), "viewer": _login(api, "viewer", "viewer123")}


@pytest.fixture(autouse=True)
def clean(api, H):
    api.post("/admin/reset", headers=H["admin"])
    api.put("/admin/settings", json={"key": "require_separation_of_duties", "value": "false"}, headers=H["admin"])
    yield


def inject(api, H, sid):
    r = api.post(f"/scenarios/{sid}/inject", headers=H["eng"]); assert r.status_code == 200, r.text
    return r.json()["id"]


def investigate(api, H, iid):
    r = api.post(f"/incidents/{iid}/investigate", headers=H["eng"]); assert r.status_code == 200, r.text
    return r.json()
