"""Domain errors for Debrief.

Services raise these exceptions when a business rule is broken. This module has
no web-framework imports on purpose: the translation of an error into the HTTP
response envelope lives in ``main.py``.

Every error carries three things the envelope needs:
    * ``status_code``  - the HTTP status the client receives
    * ``error_code``   - a stable, machine-readable identifier
    * ``message``      - a human-readable sentence
plus an optional list of field-level ``details`` (used for validation errors).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from typing import ClassVar


class ErrorCode(StrEnum):
    """Stable identifiers sent to clients in ``error.code``."""

    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    CONSULTATION_NOT_SCHEDULED = "CONSULTATION_NOT_SCHEDULED"
    CONSULTATION_NOT_STARTED = "CONSULTATION_NOT_STARTED"
    CONSULTATION_NOT_COMPLETED = "CONSULTATION_NOT_COMPLETED"
    NOTE_ALREADY_EXISTS = "NOTE_ALREADY_EXISTS"
    NOTE_ALREADY_SHARED = "NOTE_ALREADY_SHARED"
    NOTE_NOT_SHARED = "NOTE_NOT_SHARED"
    SCHEDULING_CONFLICT = "SCHEDULING_CONFLICT"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"


@dataclass(frozen=True, slots=True)
class ErrorDetail:
    """One field-level problem, e.g. ``ErrorDetail("ends_at", "Must be after starts_at.")``."""

    field: str
    message: str


class DomainError(Exception):
    """Base class for every business-rule error.

    Subclasses set ``status_code``, ``error_code`` and ``default_message``.
    Callers may override the message and attach field-level details.
    """

    status_code: ClassVar[int] = HTTPStatus.INTERNAL_SERVER_ERROR.value
    error_code: ClassVar[ErrorCode] = ErrorCode.INTERNAL_SERVER_ERROR
    default_message: ClassVar[str] = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: Sequence[ErrorDetail] = (),
    ) -> None:
        self.message: str = message or self.default_message
        self.details: tuple[ErrorDetail, ...] = tuple(details)
        super().__init__(self.message)


# 401 / 403 / 404
class AuthenticationRequiredError(DomainError):
    """The request carries no ticket, or the ticket is not recognised."""

    status_code = HTTPStatus.UNAUTHORIZED.value
    error_code = ErrorCode.AUTHENTICATION_REQUIRED
    default_message = "A valid sign-in ticket is required."


class PermissionDeniedError(DomainError):
    """The caller can see the resource but their role may not do this."""

    status_code = HTTPStatus.FORBIDDEN.value
    error_code = ErrorCode.PERMISSION_DENIED
    default_message = "You are not allowed to perform this action."


class ResourceNotFoundError(DomainError):
    """The resource does not exist, belongs to someone else, or is still private.

    The message is deliberately generic so a caller cannot tell these cases apart.
    """

    status_code = HTTPStatus.NOT_FOUND.value
    error_code = ErrorCode.RESOURCE_NOT_FOUND
    default_message = "The requested resource was not found."


# 409
class ConflictError(DomainError):
    """Base class for state and timing conflicts."""

    status_code = HTTPStatus.CONFLICT.value


class ConsultationNotScheduledError(ConflictError):
    error_code = ErrorCode.CONSULTATION_NOT_SCHEDULED
    default_message = "This consultation is no longer scheduled."


class ConsultationNotStartedError(ConflictError):
    error_code = ErrorCode.CONSULTATION_NOT_STARTED
    default_message = "This consultation has not started yet."


class ConsultationNotCompletedError(ConflictError):
    error_code = ErrorCode.CONSULTATION_NOT_COMPLETED
    default_message = "A note can only be written on a completed consultation."


class NoteAlreadyExistsError(ConflictError):
    error_code = ErrorCode.NOTE_ALREADY_EXISTS
    default_message = "This consultation already has a note."


class NoteAlreadySharedError(ConflictError):
    error_code = ErrorCode.NOTE_ALREADY_SHARED
    default_message = "This note has already been shared and can no longer be changed."


class NoteNotSharedError(ConflictError):
    error_code = ErrorCode.NOTE_NOT_SHARED
    default_message = "An addendum can only be added to a shared note."


class SchedulingConflictError(ConflictError):
    error_code = ErrorCode.SCHEDULING_CONFLICT
    default_message = "The practitioner already has a consultation at that time."



# 422
class InputValidationError(DomainError):
    """The input is well-formed but breaks a rule (e.g. start time in the past)."""

    status_code = HTTPStatus.UNPROCESSABLE_ENTITY.value
    error_code = ErrorCode.VALIDATION_ERROR
    default_message = "The request contains invalid data."