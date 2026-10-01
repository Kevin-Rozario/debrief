"""Application factory for the Debrief API.

``create_app`` owns the database, the clock, and the translation of every
failure into the uniform response envelope. Routers call the services and
wrap a successful result with ``respond``.
"""

import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.responses import Response

from app.clock import Clock
from app.database import DatabaseManager
from app.dependencies import set_database
from app.exceptions import (
    DomainError,
    ErrorDetail as DomainErrorDetail,
    InputValidationError,
    ResourceNotFoundError,
)
from app.schemas import ErrorBody, ErrorDetail, ResponseMeta, UniformResponse

logger = logging.getLogger(__name__)

_LOCATION_PREFIXES = frozenset({"body", "query", "path", "header", "cookie"})


def create_app(
    database: DatabaseManager | None = None,
    clock: Clock | None = None,
) -> FastAPI:
    """Build the API.

    The running server uses ``backend/debrief.db`` and the live clock. A test
    passes its own database and a ``FrozenClock`` instead.
    """
    database = DatabaseManager() if database is None else database
    clock = Clock() if clock is None else clock
    database.create_tables()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        database.dispose()

    app = FastAPI(title="Debrief", version="1.0.0", lifespan=lifespan)
    set_database(app, database)
    app.state.clock = clock
    app.middleware("http")(_attach_request_id)
    _register_exception_handlers(app)
    _include_routers(app)
    return app


def _include_routers(app: FastAPI) -> None:
    """Attach the identity, consultation, and note routes.

    Imported here so those modules can import ``respond`` from this one
    without a cycle while this module is still loading.
    """
    from app.routers.consultation_router import router as consultation_router
    from app.routers.identity_router import router as identity_router
    from app.routers.note_router import router as note_router

    app.include_router(identity_router)
    app.include_router(consultation_router)
    app.include_router(note_router)


def respond(request: Request, message: str, data: object = None) -> JSONResponse:
    """Wrap a service result in the success envelope."""
    body = UniformResponse(
        success=True,
        message=message,
        data=data,
        error=None,
        meta=_meta(request),
    )
    return _json(body, status_code=200)


async def _attach_request_id(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Give this request one id and copy it onto the response header."""
    request.state.request_id = str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


def _register_exception_handlers(app: FastAPI) -> None:
    """Map every failure onto the same envelope the success path uses."""

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        return _domain_error_response(request, exc)

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        details = [
            DomainErrorDetail(
                field=_detail_field(error.get("loc", ())),
                message=_detail_message(error),
            )
            for error in exc.errors()
        ]
        return _domain_error_response(request, InputValidationError(details=details))

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return _domain_error_response(request, ResourceNotFoundError())
        logger.error("HTTP %s", exc.status_code)
        return _domain_error_response(request, DomainError())

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error")
        return _domain_error_response(request, DomainError())


def _domain_error_response(request: Request, error: DomainError) -> JSONResponse:
    """The failure envelope: no data, and the error's own status and code."""
    body = UniformResponse(
        success=False,
        message=error.message,
        data=None,
        error=ErrorBody(
            code=error.error_code,
            status=error.status_code,
            details=[
                ErrorDetail(field=item.field, message=item.message) for item in error.details
            ],
        ),
        meta=_meta(request),
    )
    return _json(body, status_code=error.status_code)


def _meta(request: Request) -> ResponseMeta:
    """The request id for this call, and the clock's current UTC moment."""
    return ResponseMeta(request_id=_request_id(request), timestamp=_clock(request).now())


def _json(body: UniformResponse, *, status_code: int) -> JSONResponse:
    """Serialize the envelope and repeat ``meta.request_id`` as a header."""
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers={"X-Request-ID": body.meta.request_id},
    )


def _request_id(request: Request) -> str:
    """The id the middleware stored, or a new one if this call has none yet."""
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and request_id:
        return request_id
    request_id = str(uuid4())
    request.state.request_id = request_id
    return request_id


def _clock(request: Request) -> Clock:
    """The clock ``create_app`` stored. A missing clock is a setup error."""
    clock = getattr(request.app.state, "clock", None)
    if not isinstance(clock, Clock):
        raise RuntimeError("No clock is configured. Pass a Clock to create_app().")
    return clock


def _detail_field(location: object) -> str:
    """The field name from a validation location, without the body/query prefix."""
    if not isinstance(location, tuple):
        return "body"
    parts = [str(part) for part in location if part not in _LOCATION_PREFIXES]
    return ".".join(parts) if parts else "body"


def _detail_message(error: object) -> str:
    """The validator's own sentence, without Pydantic's ``Value error`` prefix."""
    if isinstance(error, dict):
        cause = (error.get("ctx") or {}).get("error")
        if isinstance(cause, Exception):
            text = str(cause).strip()
            if text:
                return text
        message = str(error.get("msg", "Invalid value."))
    else:
        message = "Invalid value."
    prefix = "Value error, "
    if message.startswith(prefix):
        return message.removeprefix(prefix)
    return message


app = create_app()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=4000, reload=True)
