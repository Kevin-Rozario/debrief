"""People, sign-in, and the practitioner list.

``list_people`` and ``login`` do not require a ticket. ``list_practitioners``
does: only a client may see it, and the service decides that.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.dependencies import CurrentPerson, IdentityServiceDep
from app.main import error_responses, respond
from app.schemas import (
    LoginRequest,
    PersonResponse,
    PractitionerResponse,
    TokenResponseData,
    UniformResponse,
)

router = APIRouter(tags=["Identity"])


@router.get(
    "/people",
    summary="List people",
    response_model=UniformResponse[list[PersonResponse]],
)
def list_people(request: Request, identity: IdentityServiceDep) -> JSONResponse:
    """Everyone, for the sign-in picker."""
    return respond(request, "People listed.", identity.list_people())


@router.post(
    "/auth/login",
    summary="Sign in",
    response_model=UniformResponse[TokenResponseData],
    responses=error_responses(422),
)
def login(
    request: Request,
    body: LoginRequest,
    identity: IdentityServiceDep,
) -> JSONResponse:
    """Issue a ticket for the chosen person. No password."""
    return respond(request, "Signed in.", identity.login(body.person_id))


@router.get(
    "/practitioners",
    summary="List practitioners",
    response_model=UniformResponse[list[PractitionerResponse]],
    responses=error_responses(401, 403),
)
def list_practitioners(
    request: Request,
    caller: CurrentPerson,
    identity: IdentityServiceDep,
) -> JSONResponse:
    """Names and specialty for a client who is booking."""
    return respond(request, "Practitioners listed.", identity.list_practitioners(caller))
