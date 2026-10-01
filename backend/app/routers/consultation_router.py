"""Book, list, read, cancel, and complete consultations.

The signed-in person is the caller. The service decides who may see or change
a consultation. These routes do not repeat those checks.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.dependencies import ConsultationServiceDep, CurrentPerson
from app.main import error_responses, respond
from app.schemas import (
    BookConsultationRequest,
    ConsultationDetailResponse,
    ConsultationResponse,
    UniformResponse,
)

router = APIRouter(tags=["Consultations"])


@router.post(
    "/consultations",
    summary="Book a consultation",
    response_model=UniformResponse[ConsultationResponse],
    responses=error_responses(401, 403, 409, 422),
)
def book_consultation(
    request: Request,
    booking: BookConsultationRequest,
    caller: CurrentPerson,
    consultations: ConsultationServiceDep,
) -> JSONResponse:
    """Book a future consultation for the signed-in client."""
    consultation = consultations.book(
        caller,
        booking.practitioner_id,
        booking.starts_at,
        booking.ends_at,
    )
    return respond(request, "Consultation booked.", consultation)


@router.get(
    "/consultations",
    summary="List consultations",
    response_model=UniformResponse[list[ConsultationResponse]],
    responses=error_responses(401),
)
def list_consultations(
    request: Request,
    caller: CurrentPerson,
    consultations: ConsultationServiceDep,
) -> JSONResponse:
    """The caller's own consultations, without notes."""
    return respond(request, "Consultations listed.", consultations.list_consultations(caller))


@router.get(
    "/consultations/{consultation_id}",
    summary="Read a consultation",
    response_model=UniformResponse[ConsultationDetailResponse],
    responses=error_responses(401, 404, 422),
)
def get_consultation(
    consultation_id: int,
    request: Request,
    caller: CurrentPerson,
    consultations: ConsultationServiceDep,
) -> JSONResponse:
    """One consultation. A private draft is omitted for the client."""
    return respond(request, "Consultation retrieved.", consultations.get(caller, consultation_id))


@router.post(
    "/consultations/{consultation_id}/cancel",
    summary="Cancel a consultation",
    response_model=UniformResponse[ConsultationResponse],
    responses=error_responses(401, 404, 409, 422),
)
def cancel_consultation(
    consultation_id: int,
    request: Request,
    caller: CurrentPerson,
    consultations: ConsultationServiceDep,
) -> JSONResponse:
    """Cancel while the consultation is still scheduled."""
    consultation = consultations.cancel(caller, consultation_id)
    return respond(request, "Consultation cancelled.", consultation)


@router.post(
    "/consultations/{consultation_id}/complete",
    summary="Complete a consultation",
    response_model=UniformResponse[ConsultationResponse],
    responses=error_responses(401, 403, 404, 409, 422),
)
def complete_consultation(
    consultation_id: int,
    request: Request,
    caller: CurrentPerson,
    consultations: ConsultationServiceDep,
) -> JSONResponse:
    """Mark the consultation completed once it has started."""
    consultation = consultations.complete(caller, consultation_id)
    return respond(request, "Consultation completed.", consultation)
