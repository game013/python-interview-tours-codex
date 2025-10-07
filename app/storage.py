from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Dict, Optional

from .models import IdempotencyRecord, RateLimitCounter, Tour


class InMemoryTourStorage:
    """Thread-safe in-memory storage for tours and related metadata."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._tours: Dict[str, Tour] = {}
        self._idempotency: Dict[str, IdempotencyRecord] = {}
        self._rate_limits: Dict[tuple[str, str], RateLimitCounter] = {}

    @property
    def lock(self) -> RLock:
        return self._lock

    def get_tour(self, tour_id: str) -> Optional[Tour]:
        with self._lock:
            return self._tours.get(tour_id)

    def save_tour(self, tour: Tour) -> None:
        with self._lock:
            self._tours[tour.id] = tour

    def list_tours(self) -> list[Tour]:
        with self._lock:
            return list(self._tours.values())

    def upsert_rate_limit(self, counter: RateLimitCounter) -> None:
        key = (counter.customer_id, counter.day.isoformat())
        with self._lock:
            self._rate_limits[key] = counter

    def get_rate_limit(self, customer_id: str, day_iso: str) -> Optional[RateLimitCounter]:
        with self._lock:
            return self._rate_limits.get((customer_id, day_iso))

    def get_idempotency_record(self, key: str) -> Optional[IdempotencyRecord]:
        with self._lock:
            record = self._idempotency.get(key)
            if record and record.expires_at <= datetime.now(timezone.utc):
                del self._idempotency[key]
                return None
            return record

    def save_idempotency_record(self, record: IdempotencyRecord) -> None:
        with self._lock:
            self._idempotency[record.key] = record

    def cleanup_rate_limits(self, now: datetime) -> None:
        threshold = now.date().isoformat()
        with self._lock:
            keys_to_drop = [key for key in self._rate_limits.keys() if key[1] < threshold]
            for key in keys_to_drop:
                del self._rate_limits[key]
