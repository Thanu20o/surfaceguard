from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    root_domain: Mapped[str] = mapped_column(String(253), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    scans: Mapped[list["Scan"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    assets: Mapped[list["Asset"]] = relationship(back_populates="organization", cascade="all, delete-orphan")


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assets_found: Mapped[int] = mapped_column(Integer, default=0)
    findings_found: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    organization: Mapped[Organization] = relationship(back_populates="scans")


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("organization_id", "hostname", name="uq_asset_org_hostname"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    hostname: Mapped[str] = mapped_column(String(253), index=True)
    asset_type: Mapped[str] = mapped_column(String(30), default="Unknown")
    status: Mapped[str] = mapped_column(String(40), default="Active")
    ips: Mapped[list[str]] = mapped_column(JSON, default=list)
    discovery_sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    missed_scans: Mapped[int] = mapped_column(Integer, default=0)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    latest_scan_id: Mapped[int | None] = mapped_column(ForeignKey("scans.id"), nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    risk_details: Mapped[dict] = mapped_column(JSON, default=dict)
    organization: Mapped[Organization] = relationship(back_populates="assets")
    observations: Mapped[list["Observation"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    findings: Mapped[list["Finding"]] = relationship(back_populates="asset", cascade="all, delete-orphan")


class Observation(Base):
    __tablename__ = "asset_observations"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    asset: Mapped[Asset] = relationship(back_populates="observations")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(180))
    category: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="Open")
    description: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    recommendation: Mapped[str] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    asset: Mapped[Asset] = relationship(back_populates="findings")


class ScanChange(Base):
    __tablename__ = "scan_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(40))
    hostname: Mapped[str] = mapped_column(String(253))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)