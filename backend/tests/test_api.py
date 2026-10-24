from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.dependencies import get_db
from app.main import app
from app.models import Asset, Finding, Scan
from app.api import scans as scans_api

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_create_organization_normalizes_authorized_scope():
    response = client.post("/api/organizations", json={"name": "Portfolio", "root_domain": " Example.COM. "})
    assert response.status_code == 201
    assert response.json()["root_domain"] == "example.com"


def test_organization_rejects_ip_as_scope():
    response = client.post("/api/organizations", json={"name": "Bad scope", "root_domain": "127.0.0.1"})
    assert response.status_code == 422


def test_dashboard_uses_database_values():
    organizations = client.get("/api/organizations").json()
    assert organizations
    response = client.get(f"/api/organizations/{organizations[0]['id']}/dashboard")
    assert response.status_code == 200
    assert response.json()["total_assets"] == 0


def test_finding_status_can_be_updated_and_listed():
    organization = client.post("/api/organizations", json={"name": "Finding test", "root_domain": "findings.example"}).json()
    with TestingSession() as db:
        asset = Asset(organization_id=organization["id"], hostname="www.findings.example")
        db.add(asset)
        db.flush()
        scan = Scan(organization_id=organization["id"], status="completed")
        db.add(scan)
        db.flush()
        finding = Finding(organization_id=organization["id"], asset_id=asset.id, scan_id=scan.id, fingerprint="test-finding", title="Header review", category="HTTP security headers", severity="Low", description="Review headers.", evidence={"missing_headers": ["content-security-policy"]}, recommendation="Configure a policy.")
        db.add(finding)
        db.commit()
        finding_id = finding.id

    response = client.patch(f"/api/findings/{finding_id}", json={"status": "Acknowledged"})
    assert response.status_code == 200
    assert response.json()["status"] == "Acknowledged"
    assert "_sa_instance_state" not in response.json()
    listed = client.get(f"/api/organizations/{organization['id']}/findings", params={"finding_status": "Acknowledged"})
    assert listed.status_code == 200
    assert listed.json()[0]["hostname"] == "www.findings.example"


def test_second_active_scan_is_rejected(monkeypatch):
    organization = client.post("/api/organizations", json={"name": "Scan test", "root_domain": "scans.example"}).json()
    monkeypatch.setattr(scans_api, "_run_in_background", lambda _scan_id: None)
    first = client.post(f"/api/organizations/{organization['id']}/scans")
    second = client.post(f"/api/organizations/{organization['id']}/scans")
    assert first.status_code == 202
    assert first.json()["status"] == "queued"
    assert second.status_code == 409