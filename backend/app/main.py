"""Application factory for the Debrief API.

``create_app`` owns the database, the clock, and the translation of every
failure into the uniform response envelope. Routers call the services and
wrap a successful result with ``respond``.
"""

import logging
import os
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.responses import Response

from app.clock import Clock
from app.database import DatabaseManager
from app.dependencies import get_clock, get_database, set_database
from app.exceptions import (
    DomainError,
    ErrorDetail as DomainErrorDetail,
    InputValidationError,
    ResourceNotFoundError,
)
from app.schemas import (
    ErrorBody,
    ErrorDetail,
    HealthStatus,
    ResponseMeta,
    ServiceInfo,
    UniformResponse,
)
from app.seed import SeedRunner

logger = logging.getLogger(__name__)

API_VERSION = "1.0.0"
API_SUMMARY = "Book a consultation, then share the practitioner's note."
API_DESCRIPTION = """
Debrief lets a **client** book a consultation with a **practitioner**. After the
session the practitioner may write a **note**. The client can read that note
only after it has been shared.

There is no password. `GET /people` lists the people who can sign in.
`POST /auth/login` accepts a person id and returns a ticket. Every later
request sends `Authorization: Bearer <ticket>`.

Every body is one envelope:

* `success` and `message` say what happened.
* `data` is the payload, or null when a success has nothing to return.
* `error` is null on success. On failure it carries `code`, `status`, and `details`.
* `meta.request_id` is also the `X-Request-ID` header.
* `meta.timestamp` is UTC and ends with `Z`.

A missing resource, someone else's consultation, and a note the client is not
allowed to see are all **404** with the same message. Times are stored and
returned in UTC.
""".strip()
OPENAPI_TAGS = [
    {
        "name": "System",
        "description": "Name, version, liveness, and restoring the example data. No ticket is required.",
    },
    {
        "name": "Identity",
        "description": (
            "Sign-in picker, tickets, and the practitioner list. "
            "People and login need no ticket. Only a client may list practitioners."
        ),
    },
    {
        "name": "Consultations",
        "description": (
            "Book, list, read, cancel, and complete. "
            "Only the two people on a consultation can see it."
        ),
    },
    {
        "name": "Notes",
        "description": (
            "One note on a completed consultation. Sharing locks the original text. "
            "Corrections are dated addenda."
        ),
    },
]
_ERROR_RESPONSES = {
    401: "Missing or unknown sign-in ticket.",
    403: "The caller can see the resource but their role may not do this.",
    404: "Missing, belonging to someone else, or still private. These look the same.",
    409: "Wrong state, too early, already shared, or the practitioner's time overlaps.",
    422: "The input is invalid.",
    500: "Unexpected failure.",
}
_LOCATION_PREFIXES = frozenset({"body", "query", "path", "header", "cookie"})


def _allowed_origins() -> list[str]:
    """Local Vite addresses, plus ``FRONTEND_ORIGIN`` when a host sets it.

    The value is the frontend origin only: scheme and host, no path. A trailing
    slash is dropped. Leave it unset locally. ``make api`` already allows the
    Vite dev server.
    """
    origins = ["http://127.0.0.1:5173", "http://localhost:5173"]
    frontend = os.environ.get("FRONTEND_ORIGIN", "").strip().rstrip("/")
    if frontend:
        origins.append(frontend)
    return origins


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

    app = FastAPI(
        title="Debrief",
        summary=API_SUMMARY,
        description=API_DESCRIPTION,
        version=API_VERSION,
        openapi_tags=OPENAPI_TAGS,
        servers=[{"url": "http://127.0.0.1:4000", "description": "Local server from make api."}],
        lifespan=lifespan,
    )
    set_database(app, database)
    app.state.clock = clock
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.middleware("http")(_attach_request_id)
    _register_exception_handlers(app)
    _include_routers(app)
    return app


def _include_routers(app: FastAPI) -> None:
    """Attach the identity, consultation, and note routes, plus ``/``, ``/health``, and ``/seed/reset``.

    Imported here so those modules can import ``respond`` from this one
    without a cycle while this module is still loading.
    """
    from app.routers.consultation_router import router as consultation_router
    from app.routers.identity_router import router as identity_router
    from app.routers.note_router import router as note_router

    app.include_router(identity_router)
    app.include_router(consultation_router)
    app.include_router(note_router)
    app.add_api_route(
        "/",
        root,
        methods=["GET"],
        tags=["System"],
        summary="API name and version",
        response_model=UniformResponse[ServiceInfo],
    )
    app.add_api_route(
        "/health",
        health,
        methods=["GET"],
        tags=["System"],
        summary="Health check",
        response_model=UniformResponse[HealthStatus],
    )
    app.add_api_route(
        "/seed/reset",
        reset_example_data,
        methods=["POST"],
        tags=["System"],
        summary="Restore the example data",
        response_model=UniformResponse[None],
    )


def error_responses(*statuses: int) -> dict[int, dict[str, object]]:
    """OpenAPI entries for the failure envelope. Every error uses that same shape."""
    return {
        status: {"model": UniformResponse[None], "description": _ERROR_RESPONSES[status]}
        for status in statuses
    }


def root(request: Request) -> JSONResponse:
    """The API name and version. No ticket is required."""
    return respond(request, "Debrief API.", {"name": "Debrief", "version": API_VERSION})


def health(request: Request) -> JSONResponse:
    """Liveness check. No ticket is required."""
    return respond(request, "Healthy.", {"status": "ok"})


def reset_example_data(request: Request) -> JSONResponse:
    """Replace every row with the example people and consultations.

    No ticket is required. Tickets that were already issued are deleted with
    the other rows, so the caller has to sign in again.
    """
    SeedRunner(get_database(request), get_clock(request)).run()
    return respond(request, "Example data restored.")


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
