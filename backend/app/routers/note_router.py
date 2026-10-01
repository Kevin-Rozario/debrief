"""Draft notes, sharing, and addenda.

Who may read or change a note is decided by the service. Deleting a draft
succeeds with ``data`` null.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.dependencies import CurrentPerson, NoteServiceDep
from app.main import error_responses, respond
from app.schemas import (
    AddendumResponse,
    CreateAddendumRequest,
    CreateNoteRequest,
    NoteResponse,
    UniformResponse,
    UpdateNoteRequest,
)

router = APIRouter(tags=["Notes"])


@router.get(
    "/consultations/{consultation_id}/note",
    summary="Read a note",
    response_model=UniformResponse[NoteResponse],
    responses=error_responses(401, 404, 422),
)
def get_note(
    consultation_id: int,
    request: Request,
    caller: CurrentPerson,
    notes: NoteServiceDep,
) -> JSONResponse:
    """The note this caller is allowed to read."""
    return respond(request, "Note retrieved.", notes.get(caller, consultation_id))


@router.post(
    "/consultations/{consultation_id}/note",
    summary="Create a draft note",
    response_model=UniformResponse[NoteResponse],
    responses=error_responses(401, 403, 404, 409, 422),
)
def create_note(
    consultation_id: int,
    request: Request,
    note: CreateNoteRequest,
    caller: CurrentPerson,
    notes: NoteServiceDep,
) -> JSONResponse:
    """Start a private draft on a completed consultation."""
    created = notes.create(caller, consultation_id, note.body)
    return respond(request, "Note created.", created)


@router.patch(
    "/consultations/{consultation_id}/note",
    summary="Edit a draft note",
    response_model=UniformResponse[NoteResponse],
    responses=error_responses(401, 403, 404, 409, 422),
)
def update_note(
    consultation_id: int,
    request: Request,
    note: UpdateNoteRequest,
    caller: CurrentPerson,
    notes: NoteServiceDep,
) -> JSONResponse:
    """Replace the body of a private draft."""
    updated = notes.update(caller, consultation_id, note.body)
    return respond(request, "Note updated.", updated)


@router.delete(
    "/consultations/{consultation_id}/note",
    summary="Delete a draft note",
    response_model=UniformResponse[None],
    responses=error_responses(401, 403, 404, 409, 422),
)
def delete_note(
    consultation_id: int,
    request: Request,
    caller: CurrentPerson,
    notes: NoteServiceDep,
) -> JSONResponse:
    """Delete a private draft. The success body has no data."""
    notes.delete(caller, consultation_id)
    return respond(request, "Note deleted.")


@router.post(
    "/consultations/{consultation_id}/note/share",
    summary="Share a note",
    response_model=UniformResponse[NoteResponse],
    responses=error_responses(401, 403, 404, 409, 422),
)
def share_note(
    consultation_id: int,
    request: Request,
    caller: CurrentPerson,
    notes: NoteServiceDep,
) -> JSONResponse:
    """Share a draft with the client and lock its original text."""
    return respond(request, "Note shared.", notes.share(caller, consultation_id))


@router.post(
    "/consultations/{consultation_id}/note/addenda",
    summary="Add an addendum",
    response_model=UniformResponse[AddendumResponse],
    responses=error_responses(401, 403, 404, 409, 422),
)
def add_addendum(
    consultation_id: int,
    request: Request,
    addendum: CreateAddendumRequest,
    caller: CurrentPerson,
    notes: NoteServiceDep,
) -> JSONResponse:
    """Append a dated correction to a shared note."""
    created = notes.add_addendum(caller, consultation_id, addendum.body)
    return respond(request, "Addendum added.", created)
