"""Draft notes, sharing, and addenda.

A client who is not allowed to see a note gets the same not-found error as
a missing note (rule R10). That includes reading, editing, deleting, sharing,
and adding an addendum while the note is still a draft. Creating a note is
different: a client who is on the consultation is told they may not write
one (403), which does not reveal whether a draft already exists.

The practitioner of that consultation is the only person who can change a note.
Once it is shared, the body is locked and corrections are addenda.
"""

import sqlite3

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.clock import Clock
from app.exceptions import (
    ConsultationNotCompletedError,
    ErrorDetail,
    InputValidationError,
    NoteAlreadyExistsError,
    NoteAlreadySharedError,
    NoteNotSharedError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from app.models import Addendum, Consultation, ConsultationStatus, Note, Person
from app.repositories import ConsultationRepository, NoteRepository
from app.schemas import AddendumResponse, NoteResponse
from app.services.consultation_service import require_participant


class NoteService:
    """Note rules. Holds the request's session and the clock used to date a share."""

    def __init__(self, session: Session, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._consultations = ConsultationRepository(session)
        self._notes = NoteRepository(session)

    def get(self, caller: Person, consultation_id: int) -> NoteResponse:
        """The note this caller is allowed to read. A hidden draft is not found."""
        consultation = require_participant(self._consultations.get(consultation_id), caller)
        note = self._load_note(consultation)
        if note is None or _hides_note(caller, consultation, note):
            raise ResourceNotFoundError()
        return to_note_response(note, self._notes)

    def create(self, caller: Person, consultation_id: int, body: str) -> NoteResponse:
        """Start a private draft on a completed consultation. One note per consultation."""
        consultation = require_participant(self._consultations.get(consultation_id), caller)
        _require_practitioner(caller, consultation, "Only the practitioner can write a note.")
        if consultation.status != ConsultationStatus.COMPLETED:
            raise ConsultationNotCompletedError()
        if self._notes.get_for_consultation(_row_id(consultation.id)) is not None:
            raise NoteAlreadyExistsError()
        text = _require_text(body)
        now = self._clock.now()
        note = Note(
            consultation_id=_row_id(consultation.id),
            body=text,
            shared_at=None,
            created_at=now,
            updated_at=now,
        )
        try:
            self._notes.add(note)
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            if not _is_duplicate_note(exc):
                raise
            raise NoteAlreadyExistsError() from None
        return to_note_response(note, self._notes)

    def update(self, caller: Person, consultation_id: int, body: str) -> NoteResponse:
        """Replace the body of a private draft."""
        consultation, note = self._draft_for_practitioner(
            caller,
            consultation_id,
            "Only the practitioner can change a note.",
        )
        note.body = _require_text(body)
        self._session.commit()
        return to_note_response(note, self._notes)

    def delete(self, caller: Person, consultation_id: int) -> None:
        """Delete a private draft so the consultation can take a new note."""
        _consultation, note = self._draft_for_practitioner(
            caller,
            consultation_id,
            "Only the practitioner can change a note.",
        )
        self._notes.delete(note)
        self._session.commit()

    def share(self, caller: Person, consultation_id: int) -> NoteResponse:
        """Share a draft with the client. The body cannot be edited after this."""
        consultation, note = self._existing_note_for_practitioner(
            caller,
            consultation_id,
            "Only the practitioner can share a note.",
        )
        if consultation.status != ConsultationStatus.COMPLETED:
            raise ConsultationNotCompletedError()
        if note.is_shared:
            raise NoteAlreadySharedError()
        note.shared_at = self._clock.now()
        self._session.commit()
        return to_note_response(note, self._notes)

    def add_addendum(self, caller: Person, consultation_id: int, body: str) -> AddendumResponse:
        """Append a dated correction to a shared note. The client can read it immediately."""
        consultation, note = self._existing_note_for_practitioner(
            caller,
            consultation_id,
            "Only the practitioner can add an addendum.",
        )
        if consultation.status != ConsultationStatus.COMPLETED:
            raise ConsultationNotCompletedError()
        if not note.is_shared:
            raise NoteNotSharedError()
        text = _require_text(body)
        now = self._clock.now()
        addendum = self._notes.add_addendum(
            Addendum(
                note_id=_row_id(note.id),
                body=text,
                created_at=now,
                updated_at=now,
            )
        )
        self._session.commit()
        return AddendumResponse(
            id=_row_id(addendum.id),
            note_id=addendum.note_id,
            body=addendum.body,
            created_at=addendum.created_at,
        )

    def _load_note(self, consultation: Consultation) -> Note | None:
        return self._notes.get_for_consultation(_row_id(consultation.id))

    def _existing_note_for_practitioner(
        self,
        caller: Person,
        consultation_id: int,
        denied_message: str,
    ) -> tuple[Consultation, Note]:
        """The consultation and its note, for a practitioner action.

        A client who cannot see the note gets not-found, before the 403 that
        a client who can see a shared note gets. The practitioner gets
        not-found only when there is no note.
        """
        consultation = require_participant(self._consultations.get(consultation_id), caller)
        note = self._load_note(consultation)
        if _hides_note(caller, consultation, note):
            raise ResourceNotFoundError()
        _require_practitioner(caller, consultation, denied_message)
        if note is None:
            raise ResourceNotFoundError()
        return consultation, note

    def _draft_for_practitioner(
        self,
        caller: Person,
        consultation_id: int,
        denied_message: str,
    ) -> tuple[Consultation, Note]:
        """A private note on a completed consultation, for edit or delete."""
        consultation, note = self._existing_note_for_practitioner(
            caller,
            consultation_id,
            denied_message,
        )
        if consultation.status != ConsultationStatus.COMPLETED:
            raise ConsultationNotCompletedError()
        if note.is_shared:
            raise NoteAlreadySharedError()
        return consultation, note


def visible_note(
    caller: Person,
    consultation: Consultation,
    notes: NoteRepository,
) -> NoteResponse | None:
    """The note to embed on a consultation, or None when this caller must not see one.

    None covers both "there is no note" and "a draft the client must not see".
    Call this only after the caller has been confirmed as a participant.
    """
    note = notes.get_for_consultation(_row_id(consultation.id))
    if note is None or _hides_note(caller, consultation, note):
        return None
    return to_note_response(note, notes)


def to_note_response(note: Note, notes: NoteRepository) -> NoteResponse:
    """The public note. Addenda are loaded only after the note is shared."""
    note_id = _row_id(note.id)
    rows = () if not note.is_shared else notes.list_addenda(note_id)
    return NoteResponse(
        id=note_id,
        consultation_id=note.consultation_id,
        body=note.body,
        shared_at=note.shared_at,
        created_at=note.created_at,
        addenda=[
            AddendumResponse(
                id=_row_id(item.id),
                note_id=item.note_id,
                body=item.body,
                created_at=item.created_at,
            )
            for item in rows
        ],
    )


def _is_duplicate_note(exc: IntegrityError) -> bool:
    """True when SQLite rejected a second note for the same consultation."""
    original = exc.orig
    if not isinstance(original, sqlite3.IntegrityError):
        return False
    if original.sqlite_errorcode != sqlite3.SQLITE_CONSTRAINT_UNIQUE:
        return False
    return "note.consultation_id" in str(original)


def _hides_note(caller: Person, consultation: Consultation, note: Note | None) -> bool:
    """True when this caller is the client and the note is missing or still private."""
    if caller.id != consultation.client_id:
        return False
    return note is None or not note.is_shared


def _require_practitioner(caller: Person, consultation: Consultation, message: str) -> None:
    if caller.id != consultation.practitioner_id:
        raise PermissionDeniedError(message)


def _require_text(body: str) -> str:
    """The stored text. Empty and whitespace-only bodies are invalid input (rule R14)."""
    stripped = body.strip()
    if not stripped:
        raise InputValidationError(
            details=[ErrorDetail("body", "Must not be empty or whitespace.")]
        )
    return stripped


def _row_id(value: int | None) -> int:
    if value is None:
        raise RuntimeError("Expected a saved row with an id.")
    return value
