from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Asset, Finding, Observation, Organization, Scan, ScanChange
from app.services import scanner


def test_repeat_scan_deduplicates_assets_and_records_changes(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(scanner, "discover_ct", lambda _domain: ([], None))
    monkeypatch.setattr(scanner, "resolve_host", lambda hostname: (["8.8.8.8"], [{"hostname": hostname, "type": "A", "value": "8.8.8.8", "ttl": 60}], []))
    monkeypatch.setattr(scanner, "_http_observation", lambda _hostname, _ips: {"state": "completed", "status_code": 200, "headers": {name: False for name in scanner.SECURITY_HEADERS}, "response_ms": 20})
    monkeypatch.setattr(scanner, "_tls_observation", lambda _hostname, _ips: {"state": "skipped", "reason": "mocked"})

    with Session(engine, expire_on_commit=False) as db:
        organization = Organization(name="Test", root_domain="example.test")
        db.add(organization)
        db.commit()
        first = Scan(organization_id=organization.id)
        db.add(first)
        db.commit()
        scanner.execute_scan(db, first.id)
        second = Scan(organization_id=organization.id)
        db.add(second)
        db.commit()
        scanner.execute_scan(db, second.id)

        assets = db.scalars(select(Asset).where(Asset.organization_id == organization.id)).all()
        findings = db.scalars(select(Finding).where(Finding.organization_id == organization.id)).all()
        observations = db.scalars(select(Observation).where(Observation.scan_id == second.id)).all()
        changes = db.scalars(select(ScanChange).where(ScanChange.scan_id == first.id)).all()
        assert first.status == "completed"
        assert second.status == "completed"
        assert second.assets_found == 0
        assert len(assets) == 1
        assert assets[0].status == "Active"
        assert len(findings) == 1
        assert observations
        assert any(change.kind == "new_asset" for change in changes)


def test_openapi_metadata_is_extracted_without_retaining_spec(monkeypatch):
    document = {"openapi": "3.0.0", "info": {"title": "Test API", "version": "1"}, "paths": {"/health": {"get": {}}}, "components": {"securitySchemes": {"token": {"type": "http"}}}}
    monkeypatch.setattr(scanner, "_https_get", lambda *_args, **_kwargs: {"state": "completed", "status_code": 200, "content_type": "application/json", "body": __import__("json").dumps(document), "body_size_limited": False})
    result = scanner._api_document("api.example.test", ["8.8.8.8"])
    assert result == {"state": "completed", "public": True, "url": "https://api.example.test/openapi.json", "title": "Test API", "version": "1", "path_count": 1, "method_count": 1, "authentication_schemes_documented": True}


def test_malformed_or_oversized_openapi_documents_are_ignored(monkeypatch):
    monkeypatch.setattr(scanner, "_https_get", lambda *_args, **_kwargs: {"state": "completed", "status_code": 200, "content_type": "application/json", "body": "{", "body_size_limited": True})
    result = scanner._api_document("api.example.test", ["8.8.8.8"])
    assert result["state"] == "completed"
    assert result["public"] is False
    assert "body" not in result


def test_malformed_openapi_metadata_shape_is_ignored(monkeypatch):
    body = '{"openapi":"3.0.0","paths":{},"components":[]}'
    monkeypatch.setattr(scanner, "_https_get", lambda *_args, **_kwargs: {"state": "completed", "status_code": 200, "content_type": "application/json", "body": body, "body_size_limited": False})
    result = scanner._api_document("api.example.test", ["8.8.8.8"])
    assert result["state"] == "completed"
    assert result["public"] is True
    assert result["authentication_schemes_documented"] is False


def test_openapi_check_skips_private_addresses_by_default(monkeypatch):
    called = False

    def unexpected_request(*_args, **_kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(scanner, "_https_get", unexpected_request)
    result = scanner._api_document("api.example.test", ["192.168.1.4"])
    assert result["state"] == "skipped"
    assert not called


def test_missing_asset_becomes_inactive_after_three_scans(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    discovery = {"names": ["old.example.test"]}
    monkeypatch.setattr(scanner, "discover_ct", lambda _domain: (discovery["names"], None))
    monkeypatch.setattr(scanner, "resolve_host", lambda hostname: (["8.8.8.8"], [{"hostname": hostname, "type": "A", "value": "8.8.8.8", "ttl": 60}], []))
    monkeypatch.setattr(scanner, "_http_observation", lambda *_args: {"state": "skipped"})
    monkeypatch.setattr(scanner, "_tls_observation", lambda *_args: {"state": "skipped"})

    with Session(engine, expire_on_commit=False) as db:
        organization = Organization(name="Test", root_domain="example.test")
        db.add(organization)
        db.commit()
        for _ in range(1):
            scan = Scan(organization_id=organization.id)
            db.add(scan)
            db.commit()
            scanner.execute_scan(db, scan.id)
        discovery["names"] = []
        for miss_count in range(1, 4):
            scan = Scan(organization_id=organization.id)
            db.add(scan)
            db.commit()
            scanner.execute_scan(db, scan.id)
            asset = db.scalar(select(Asset).where(Asset.hostname == "old.example.test"))
            if miss_count < 3:
                assert asset.status == "Not observed in latest scan"
            else:
                assert asset.status == "Inactive"
