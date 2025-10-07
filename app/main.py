from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, FastAPI, Header, Request, Response, status
from fastapi.responses import JSONResponse

from .errors import AppError
from .schemas import TourCreateRequest, TourListQuery, TourResponse, ToursListResponse
from .service import TourService
from .storage import InMemoryTourStorage

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Tour Scheduling API", version="1.0.0")


def get_service() -> TourService:
    if not hasattr(get_service, "_instance"):
        storage = InMemoryTourStorage()
        get_service._instance = TourService(storage=storage)
    return get_service._instance  # type: ignore[attr-defined]


@app.exception_handler(AppError)
async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    logging.getLogger(__name__).warning("Request failed", extra={"code": exc.code, "message": exc.message})
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


@app.post("/v1/tours", response_model=TourResponse, status_code=status.HTTP_201_CREATED)
async def create_tour(
    payload: TourCreateRequest,
    response: Response,
    service: TourService = Depends(get_service),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
) -> TourResponse:
    tour, created = service.create_tour(
        property_id=payload.property_id,
        customer_id=payload.customer_id,
        start_at=payload.start_at,
        end_at=payload.end_at,
        idempotency_key=idempotency_key,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return TourResponse.from_domain(tour)


@app.get("/v1/tours/{tour_id}", response_model=TourResponse)
async def get_tour(tour_id: str, service: TourService = Depends(get_service)) -> TourResponse:
    tour = service.get_tour(tour_id)
    return TourResponse.from_domain(tour)


@app.get("/v1/tours", response_model=ToursListResponse)
async def list_tours(
    query: TourListQuery = Depends(),
    service: TourService = Depends(get_service),
) -> ToursListResponse:
    tours, total = service.list_tours(
        property_id=query.property_id,
        date_filter=query.date,
        sort=query.sort,
        page=query.page,
        page_size=query.page_size,
    )
    items = [TourResponse.from_domain(tour) for tour in tours]
    return ToursListResponse(items=items, page=query.page, page_size=query.page_size, total=total)


@app.delete("/v1/tours/{tour_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_tour(tour_id: str, service: TourService = Depends(get_service)) -> Response:
    service.cancel_tour(tour_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
