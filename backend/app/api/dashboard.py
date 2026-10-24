from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Asset, Finding, Organization, Scan

router = APIRouter(tags=["dashboard"])


@router.get("/api/organizations/{organization_id}/dashboard")
def dashboard(organization_id: int, db: Session = Depends(get_db)):
    if not db.get(Organization, organization_id):
        raise HTTPException(status_code=404, detail="Organization not found.")
    assets = db.scalars(select(Asset).where(Asset.organization_id == organization_id)).all()
    findings = db.scalars(select(Finding).where(Finding.organization_id == organization_id)).all()
    scans = db.scalars(select(Scan).where(Scan.organization_id == organization_id).order_by(Scan.started_at.desc()).limit(8)).all()
    return {
        "total_assets": len(assets),
        "active_assets": sum(asset.status == "Active" for asset in assets),
        "open_findings": sum(f.status in ("Open", "Acknowledged") for f in findings),
        "critical_findings": sum(f.severity == "Critical" and f.status == "Open" for f in findings),
        "high_risk_assets": sum(asset.risk_score >= 60 for asset in assets),
        "assets_by_type": dict(db.execute(select(Asset.asset_type, func.count()).where(Asset.organization_id == organization_id).group_by(Asset.asset_type)).all()),
        "findings_by_severity": dict(db.execute(select(Finding.severity, func.count()).where(Finding.organization_id == organization_id, Finding.status == "Open").group_by(Finding.severity)).all()),
        "latest_scan": scans[0] if scans else None,
        "recent_scans": scans,
        "risk_scores": [asset.risk_score for asset in assets],
    }