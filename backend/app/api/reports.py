import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Asset, Finding, Organization

router = APIRouter(tags=["reports"])


@router.get("/api/organizations/{organization_id}/reports/assets.csv")
def export_assets(organization_id: int, db: Session = Depends(get_db)):
    organization = db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found.")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Organization", organization.name])
    writer.writerow(["Authorized scope", organization.root_domain])
    writer.writerow([])
    writer.writerow(["Hostname", "Type", "IPs", "Risk score", "Status", "First seen", "Last seen"])
    for asset in db.scalars(select(Asset).where(Asset.organization_id == organization_id).order_by(Asset.hostname)):
        writer.writerow([asset.hostname, asset.asset_type, ", ".join(asset.ips or []), asset.risk_score, asset.status, asset.first_seen.isoformat(), asset.last_seen.isoformat()])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=surfaceguard-{organization_id}-assets.csv"})