"""Domain errors -> consistent JSON error envelope: {"error": {"code", "message", "details"}}."""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, details: dict | list | None = None):
        super().__init__(message)
        self.message, self.details = message, details


class NotFound(DomainError):
    status_code, code = 404, "not_found"


class Unauthenticated(DomainError):
    status_code, code = 401, "unauthenticated"


class Forbidden(DomainError):
    status_code, code = 403, "forbidden"


class Conflict(DomainError):
    status_code, code = 409, "conflict"


class RuleViolation(DomainError):
    status_code, code = 422, "business_rule_violation"


async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code,
                        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}})
