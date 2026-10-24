from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    root_domain: str = Field(min_length=3, max_length=253)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Organization name must contain at least two non-space characters.")
        return normalized


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)


class OrganizationOut(BaseModel):
    id: int
    name: str
    root_domain: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FindingStatusUpdate(BaseModel):
    status: Literal["Open", "Acknowledged", "Resolved", "Accepted risk"]
