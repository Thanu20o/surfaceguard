from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.dependencies import get_db
from app.models import Organization, Scan, ScanChange
from app.services.scanner import execute_scan

router = APIRouter(tags=["scans"])


def _run_in_background(scan_id: int) -> None:
    with SessionLocal() as db:
        execute_scan(db, scan_id)


@router.post("/api/organizations/{organization_id}/scans", status_code=status.HTTP_202_ACCEPTED)
def start_scan(organization_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    organization = db.scalar(select(Organization).where(Organization.id == organization_id).with_for_update())
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found.")
    running = db.scalar(select(Scan).where(Scan.organization_id == organization_id, Scan.status.in_(["queued", "running"])))
    if running:
        raise HTTPException(status_code=409, detail="A scan is already running for this organization.")
    scan = Scan(organization_id=organization_id)
    db.add(scan)
    db.commit()
    db.refresh(scan)
    background_tasks.add_task(_run_in_background, scan.id)
    return scan


@router.get("/api/organizations/{organization_id}/scans")
def list_scans(organization_id: int, limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    if not db.get(Organization, organization_id):
        raise HTTPException(status_code=404, detail="Organization not found.")
    return db.scalars(select(Scan).where(Scan.organization_id == organization_id).order_by(Scan.started_at.desc()).offset(offset).limit(min(limit, 100))).all()


@router.get("/api/scans/{scan_id}")
def get_scan(scan_id: int, db: Session = Depends(get_db)):
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")
    return scan


@router.get("/api/scans/{scan_id}/changes")
def get_scan_changes(scan_id: int, db: Session = Depends(get_db)):
    if not db.get(Scan, scan_id):
        raise HTTPException(status_code=404, detail="Scan not found.")
    return db.scalars(select(ScanChange).where(ScanChange.scan_id == scan_id).order_by(ScanChange.detected_at)).all()