from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_service
from app.service import TourService
from app.storage import InMemoryTourStorage


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    storage = InMemoryTourStorage()
    service = TourService(storage=storage)
    app.dependency_overrides[get_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _build_payload(offset_minutes: int) -> dict[str, str]:
    start = datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)
    end = start + timedelta(minutes=30)
    return {
        "property_id": "prop-test",
        "customer_id": "cust-test",
        "start_at": start.isoformat().replace("+00:00", "Z"),
        "end_at": end.isoformat().replace("+00:00", "Z"),
    }


def test_prevents_overlapping_tours(client: TestClient) -> None:
    payload = _build_payload(60)
    response = client.post("/v1/tours", json=payload)
    assert response.status_code == 201

    response_conflict = client.post("/v1/tours", json=payload)
    assert response_conflict.status_code == 409
    assert response_conflict.json()["code"] == "CONFLICT"


def test_idempotency_returns_same_result(client: TestClient) -> None:
    payload = _build_payload(180)
    headers = {"Idempotency-Key": "test-key-123"}

    first = client.post("/v1/tours", json=payload, headers=headers)
    assert first.status_code == 201
    body_first = first.json()

    second = client.post("/v1/tours", json=payload, headers=headers)
    assert second.status_code == 200
    assert second.json() == body_first


def test_rate_limit_per_customer_per_day(client: TestClient) -> None:
    base_offset = 300
    for i in range(3):
        payload = _build_payload(base_offset + i * 60)
        payload["property_id"] = f"prop-{i}"
        response = client.post("/v1/tours", json=payload)
        assert response.status_code == 201

    fourth_payload = _build_payload(base_offset + 240)
    fourth_payload["property_id"] = "prop-3"
    response_fourth = client.post("/v1/tours", json=fourth_payload)
    assert response_fourth.status_code == 429
    assert response_fourth.json()["code"] == "RATE_LIMIT"
