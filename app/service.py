from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Tuple
from uuid import uuid4

from .errors import BadRequestError, ConflictError, NotFoundError, RateLimitError
from .models import IdempotencyRecord, RateLimitCounter, Tour, TourStatus
from .storage import InMemoryTourStorage

logger = logging.getLogger(__name__)


def ensure_utc(dt: datetime, field: str) -> datetime:
    if dt.tzinfo is None:
        raise BadRequestError("timestamp must be timezone-aware", field=field)
    return dt.astimezone(timezone.utc)


def overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and start_b < end_a


class TourService:
    def __init__(self, storage: InMemoryTourStorage) -> None:
        self._storage = storage

    def create_tour(
        self,
        *,
        property_id: str,
        customer_id: str,
        start_at: datetime,
        end_at: datetime,
        idempotency_key: str | None,
    ) -> Tuple[Tour, bool]:
        start_at_utc = ensure_utc(start_at, "start_at")
        end_at_utc = ensure_utc(end_at, "end_at")
        if start_at_utc >= end_at_utc:
            raise BadRequestError("end_at must be after start_at", field="end_at")

        now = datetime.now(timezone.utc)
        fingerprint = self._fingerprint(property_id, customer_id, start_at_utc, end_at_utc)

        with self._storage.lock:
            record = None
            if idempotency_key:
                record = self._storage.get_idempotency_record(idempotency_key)
                if record and record.fingerprint != fingerprint:
                    raise ConflictError("idempotency key already used with different parameters")

            if record:
                existing = self._storage.get_tour(record.tour_id)
                if existing:
                    return existing, False

            self._storage.cleanup_rate_limits(now)
            day_key = now.date()
            counter = self._get_or_create_rate_limit(customer_id, day_key)
            if counter.count >= 3:
                raise RateLimitError("daily tour creation limit reached")

            self._ensure_no_overlap(property_id, start_at_utc, end_at_utc)

            tour = Tour(
                id=self._generate_tour_id(),
                property_id=property_id,
                customer_id=customer_id,
                start_at=start_at_utc,
                end_at=end_at_utc,
                status=TourStatus.BOOKED,
                created_at=now,
                updated_at=now,
            )
            self._storage.save_tour(tour)

            counter.increment()
            self._storage.upsert_rate_limit(counter)

            if idempotency_key:
                expires_at = now + timedelta(hours=24)
                record = IdempotencyRecord(
                    key=idempotency_key,
                    tour_id=tour.id,
                    fingerprint=fingerprint,
                    created_at=now,
                    expires_at=expires_at,
                )
                self._storage.save_idempotency_record(record)

            logger.info(
                "Tour created",
                extra={
                    "tour_id": tour.id,
                    "property_id": property_id,
                    "customer_id": customer_id,
                },
            )

            return tour, True

    def get_tour(self, tour_id: str) -> Tour:
        tour = self._storage.get_tour(tour_id)
        if not tour:
            raise NotFoundError("tour not found")
        return tour

    def list_tours(
        self,
        *,
        property_id: str | None,
        date_filter: date | None,
        sort: str,
        page: int,
        page_size: int,
    ) -> tuple[list[Tour], int]:
        tours = self._storage.list_tours()
        filtered = [tour for tour in tours if self._matches_filters(tour, property_id, date_filter)]
        reverse = False
        sort_field = sort
        if sort.startswith("-"):
            reverse = True
            sort_field = sort[1:]
        if sort_field != "start_at":
            raise BadRequestError("unsupported sort field", field="sort")
        filtered.sort(key=lambda t: t.start_at, reverse=reverse)

        total = len(filtered)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        paginated = filtered[start_index:end_index]
        return paginated, total

    def cancel_tour(self, tour_id: str) -> None:
        with self._storage.lock:
            tour = self._storage.get_tour(tour_id)
            if not tour:
                raise NotFoundError("tour not found")
            previous_status = tour.status
            tour.cancel()
            self._storage.save_tour(tour)
            if previous_status != TourStatus.CANCELLED:
                logger.info(
                    "Tour cancelled",
                    extra={"tour_id": tour.id, "property_id": tour.property_id, "customer_id": tour.customer_id},
                )

    def _matches_filters(
        self,
        tour: Tour,
        property_id: str | None,
        date_filter: date | None,
    ) -> bool:
        if property_id and tour.property_id != property_id:
            return False
        if date_filter:
            day_start = datetime.combine(date_filter, datetime.min.time(), tzinfo=timezone.utc)
            day_end = day_start + timedelta(days=1)
            if not overlaps(tour.start_at, tour.end_at, day_start, day_end):
                return False
        return True

    def _ensure_no_overlap(self, property_id: str, start_at: datetime, end_at: datetime) -> None:
        tours = self._storage.list_tours()
        for tour in tours:
            if tour.property_id != property_id:
                continue
            if tour.status != TourStatus.BOOKED:
                continue
            if overlaps(tour.start_at, tour.end_at, start_at, end_at):
                raise ConflictError("overlapping tour for property")

    def _get_or_create_rate_limit(self, customer_id: str, day_key: date) -> RateLimitCounter:
        counter = self._storage.get_rate_limit(customer_id, day_key.isoformat())
        if counter:
            return counter
        counter = RateLimitCounter(customer_id=customer_id, day=day_key)
        self._storage.upsert_rate_limit(counter)
        return counter

    def _generate_tour_id(self) -> str:
        return f"tour_{uuid4().hex[:12]}"

    def _fingerprint(
        self,
        property_id: str,
        customer_id: str,
        start_at: datetime,
        end_at: datetime,
    ) -> str:
        return "|".join(
            [property_id, customer_id, start_at.isoformat(), end_at.isoformat()]
        )
