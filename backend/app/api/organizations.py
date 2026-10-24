from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import Organization
from app.schemas import OrganizationCreate, OrganizationOut, OrganizationUpdate
from app.services.scope import normalize_domain

router = APIRouter(prefix="/api/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
def create_organization(payload: OrganizationCreate, db: Session = Depends(get_db)):
    try:
        domain = normalize_domain(payload.root_domain)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    organization = Organization(name=payload.name.strip(), root_domain=domain)
    db.add(organization)
    db.commit()
    db.refresh(organization)
    return organization


@router.get("", response_model=list[OrganizationOut])
def list_organizations(db: Session = Depends(get_db)):
    return db.scalars(select(Organization).order_by(Organization.created_at.desc())).all()


@router.get("/{organization_id}", response_model=OrganizationOut)
def get_organization(organization_id: int, db: Session = Depends(get_db)):
    organization = db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return organization


@router.patch("/{organization_id}", response_model=OrganizationOut)
def update_organization(organization_id: int, payload: OrganizationUpdate, db: Session = Depends(get_db)):
    organization = db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found.")
    if payload.name is not None:
        organization.name = payload.name.strip()
    db.commit()
    db.refresh(organization)
    return organization


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organization(organization_id: int, db: Session = Depends(get_db)):
    organization = db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found.")
    db.delete(organization)
    db.commit()