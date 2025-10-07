from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .models import Tour


class TourCreateRequest(BaseModel):
    property_id: str = Field(..., min_length=1)
    customer_id: str = Field(..., min_length=1)
    start_at: datetime
    end_at: datetime


class TourResponse(BaseModel):
    id: str
    status: str
    property_id: str
    customer_id: str
    start_at: datetime
    end_at: datetime
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, tour: Tour) -> "TourResponse":
        return cls(
            id=tour.id,
            status=tour.status.value,
            property_id=tour.property_id,
            customer_id=tour.customer_id,
            start_at=tour.start_at,
            end_at=tour.end_at,
            created_at=tour.created_at,
            updated_at=tour.updated_at,
        )


class ToursListResponse(BaseModel):
    items: List[TourResponse]
    page: int
    page_size: int
    total: int


class ErrorResponse(BaseModel):
    code: str
    message: str
    field: Optional[str] = None


class TourListQuery(BaseModel):
    property_id: Optional[str] = None
    date: Optional[date] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort: str = Field(default="start_at")
