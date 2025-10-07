from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class AppError(Exception):
    code: str
    message: str
    status_code: int
    field: Optional[str] = None

    def to_dict(self) -> dict[str, str]:
        payload = {"code": self.code, "message": self.message}
        if self.field:
            payload["field"] = self.field
        return payload


class BadRequestError(AppError):
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(code="BAD_REQUEST", message=message, status_code=400, field=field)


class ConflictError(AppError):
    def __init__(self, message: str):
        super().__init__(code="CONFLICT", message=message, status_code=409)


class NotFoundError(AppError):
    def __init__(self, message: str):
        super().__init__(code="NOT_FOUND", message=message, status_code=404)


class RateLimitError(AppError):
    def __init__(self, message: str):
        super().__init__(code="RATE_LIMIT", message=message, status_code=429)
