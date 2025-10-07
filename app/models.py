from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum


class TourStatus(str, Enum):
    BOOKED = "BOOKED"
    CANCELLED = "CANCELLED"


@dataclass
class Tour:
    id: str
    property_id: str
    customer_id: str
    start_at: datetime
    end_at: datetime
    status: TourStatus
    created_at: datetime
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def cancel(self) -> None:
        if self.status != TourStatus.CANCELLED:
            self.status = TourStatus.CANCELLED
            self.updated_at = datetime.now(timezone.utc)


@dataclass
class IdempotencyRecord:
    key: str
    tour_id: str
    fingerprint: str
    created_at: datetime
    expires_at: datetime


@dataclass
class RateLimitCounter:
    customer_id: str
    day: date
    count: int = 0

    def increment(self) -> None:
        self.count += 1
