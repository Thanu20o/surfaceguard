from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Asset, Observation, Organization

router = APIRouter(tags=["assets"])


@router.get("/api/organizations/{organization_id}/assets")
def list_assets(organization_id: int, q: str = "", limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    if not db.get(Organization, organization_id):
        raise HTTPException(status_code=404, detail="Organization not found.")
    query = select(Asset).where(Asset.organization_id == organization_id)
    if q.strip():
        query = query.where(Asset.hostname.contains(q.strip().lower()))
    return db.scalars(query.order_by(Asset.risk_score.desc(), Asset.hostname).offset(offset).limit(min(limit, 200))).all()


@router.get("/api/assets/{asset_id}")
def get_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found.")
    observations = db.scalars(select(Observation).where(Observation.asset_id == asset_id).order_by(Observation.observed_at.desc())).all()
    return {"asset": asset, "observations": observations}