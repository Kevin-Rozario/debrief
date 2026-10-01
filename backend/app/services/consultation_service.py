"""Booking, listing, cancel, and complete.

Access is decided here, before any role check. A missing consultation and
someone else's consultation both raise ``ResourceNotFoundError``, so the
caller cannot tell them apart (rule R6).

Booking takes the write lock before it looks anyone up or checks the
practitioner's calendar (rule R5). The client calendar is not checked.
"""

from datetime import UTC, datetime

from sqlmodel import Session

from app.clock import Clock
from app.database import begin_write_transaction
from app.exceptions import (
    ConsultationNotScheduledError,
    ConsultationNotStartedError,
    ErrorDetail,
    InputValidationError,
    PermissionDeniedError,
    ResourceNotFoundError,
    SchedulingConflictError,
)
from app.models import Consultation, ConsultationStatus, Person, PersonRole
from app.repositories import ConsultationRepository, NoteRepository, PersonRepository
from app.schemas import ConsultationDetailResponse, ConsultationResponse


class ConsultationService:
    """Consultation rules. Holds the request's session and the clock."""

    def __init__(self, session: Session, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._people = PersonRepository(session)
        self._consultations = ConsultationRepository(session)
        self._notes = NoteRepository(session)

    def book(
        self,
        caller: Person,
        practitioner_id: int,
        starts_at: datetime,
        ends_at: datetime,
    ) -> ConsultationResponse:
        """Book a future consultation for the signed-in client.

        The first use of the session in this method is the write lock. Time
        checks use the clock only, so they happen before that lock.
        """
        if caller.role != PersonRole.CLIENT:
            raise PermissionDeniedError("Only a client can book a consultation.")
        now = self._clock.now()
        starts_at, ends_at = _bookable_window(starts_at, ends_at, now)

        begin_write_transaction(self._session)
        practitioner = self._people.get(practitioner_id)
        if practitioner is None or practitioner.role != PersonRole.PRACTITIONER:
            self._session.rollback()
            raise InputValidationError(
                details=[ErrorDetail("practitioner_id", "Choose a practitioner.")]
            )
        if (
            self._consultations.find_scheduled_overlap(practitioner_id, starts_at, ends_at)
            is not None
        ):
            self._session.rollback()
            raise SchedulingConflictError()

        consultation = self._consultations.add(
            Consultation(
                client_id=_row_id(caller.id),
                practitioner_id=practitioner_id,
                starts_at=starts_at,
                ends_at=ends_at,
                status=ConsultationStatus.SCHEDULED,
                created_at=now,
                updated_at=now,
            )
        )
        self._session.commit()
        return consultation_response(consultation)

    def list_consultations(self, caller: Person) -> list[ConsultationResponse]:
        """The caller's own consultations. No note is attached."""
        rows = self._consultations.list_for_person(_row_id(caller.id))
        return [consultation_response(row) for row in rows]

    def get(self, caller: Person, consultation_id: int) -> ConsultationDetailResponse:
        """One consultation. The note is included only when this caller may read it."""
        # Imported here so this module and note_service do not import each other at load time.
        from app.services.note_service import visible_note

        consultation = require_participant(self._consultations.get(consultation_id), caller)
        base = consultation_response(consultation)
        return ConsultationDetailResponse(
            **base.model_dump(),
            note=visible_note(caller, consultation, self._notes),
        )

    def cancel(self, caller: Person, consultation_id: int) -> ConsultationResponse:
        """Cancel while scheduled. Either participant may do this, including after the start."""
        consultation = require_participant(self._consultations.get(consultation_id), caller)
        if consultation.status != ConsultationStatus.SCHEDULED:
            raise ConsultationNotScheduledError()
        consultation.status = ConsultationStatus.CANCELLED
        consultation.cancelled_by_id = _row_id(caller.id)
        self._session.commit()
        return consultation_response(consultation)

    def complete(self, caller: Person, consultation_id: int) -> ConsultationResponse:
        """Mark completed. Practitioner only, and only once the start time has been reached."""
        consultation = require_participant(self._consultations.get(consultation_id), caller)
        if caller.id != consultation.practitioner_id:
            raise PermissionDeniedError(
                "Only the practitioner can mark a consultation as completed."
            )
        if consultation.status != ConsultationStatus.SCHEDULED:
            raise ConsultationNotScheduledError()
        if not consultation.has_started(self._clock.now()):
            raise ConsultationNotStartedError()
        consultation.status = ConsultationStatus.COMPLETED
        self._session.commit()
        return consultation_response(consultation)


def require_participant(consultation: Consultation | None, caller: Person) -> Consultation:
    """The consultation, when this person is its client or its practitioner.

    Missing and not-yours are the same error, with the same message.
    """
    caller_id = caller.id
    if consultation is None or caller_id is None or not consultation.has_participant(caller_id):
        raise ResourceNotFoundError()
    return consultation


def consultation_response(consultation: Consultation) -> ConsultationResponse:
    """The public consultation fields. No note, so a list cannot reveal a draft."""
    return ConsultationResponse(
        id=_row_id(consultation.id),
        client_id=consultation.client_id,
        practitioner_id=consultation.practitioner_id,
        starts_at=consultation.starts_at,
        ends_at=consultation.ends_at,
        status=consultation.status,
        cancelled_by_id=consultation.cancelled_by_id,
    )


def _bookable_window(
    starts_at: datetime,
    ends_at: datetime,
    now: datetime,
) -> tuple[datetime, datetime]:
    """UTC bounds that start in the future and end strictly later. Raises 422 otherwise."""
    details: list[ErrorDetail] = []
    if starts_at.tzinfo is None:
        details.append(ErrorDetail("starts_at", "Datetime values must be timezone-aware (UTC)."))
    if ends_at.tzinfo is None:
        details.append(ErrorDetail("ends_at", "Datetime values must be timezone-aware (UTC)."))
    if details:
        raise InputValidationError(details=details)

    starts_at = starts_at.astimezone(UTC)
    ends_at = ends_at.astimezone(UTC)
    if starts_at <= now:
        details.append(ErrorDetail("starts_at", "Must be in the future."))
    if ends_at <= starts_at:
        details.append(ErrorDetail("ends_at", "Must be strictly after starts_at."))
    if details:
        raise InputValidationError(details=details)
    return starts_at, ends_at


def _row_id(value: int | None) -> int:
    if value is None:
        raise RuntimeError("Expected a saved row with an id.")
    return value
