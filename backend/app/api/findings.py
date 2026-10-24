from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Asset, Finding, Organization
from app.schemas import FindingStatusUpdate

router = APIRouter(tags=["findings"])


def serialize_finding(finding: Finding, hostname: str) -> dict:
    return {
        "id": finding.id,
        "organization_id": finding.organization_id,
        "asset_id": finding.asset_id,
        "scan_id": finding.scan_id,
        "title": finding.title,
        "category": finding.category,
        "severity": finding.severity,
        "status": finding.status,
        "description": finding.description,
        "evidence": finding.evidence,
        "recommendation": finding.recommendation,
        "detected_at": finding.detected_at,
        "last_observed_at": finding.last_observed_at,
        "hostname": hostname,
    }


@router.get("/api/organizations/{organization_id}/findings")
def list_findings(organization_id: int, severity: str | None = None, category: str | None = None, finding_status: str | None = None, q: str | None = None, limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    if not db.get(Organization, organization_id):
        raise HTTPException(status_code=404, detail="Organization not found.")
    query = select(Finding, Asset.hostname).join(Asset).where(Finding.organization_id == organization_id)
    if severity:
        query = query.where(Finding.severity == severity)
    if category:
        query = query.where(Finding.category == category)
    if finding_status:
        query = query.where(Finding.status == finding_status)
    if q:
        query = query.where(Asset.hostname.contains(q.strip().lower()))
    return [serialize_finding(finding, hostname) for finding, hostname in db.execute(query.order_by(Finding.detected_at.desc()).offset(offset).limit(min(limit, 200))).all()]


@router.get("/api/findings/{finding_id}")
def get_finding(finding_id: int, db: Session = Depends(get_db)):
    finding = db.get(Finding, finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")
    return serialize_finding(finding, finding.asset.hostname)


@router.patch("/api/findings/{finding_id}")
def update_finding(finding_id: int, payload: FindingStatusUpdate, db: Session = Depends(get_db)):
    finding = db.get(Finding, finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")
    finding.status = payload.status
    db.commit()
    db.refresh(finding)
    return serialize_finding(finding, finding.asset.hostname)