"""Request and response contracts for the Debrief API.

These pydantic models are the JSON the API accepts and returns. They are
deliberately not the SQLModel tables in ``models.py``. A response class names
every field it emits, so a column that exists only for storage (or that a
caller is not allowed to see) cannot leak just because the row was loaded.

Every HTTP body is one ``UniformResponse`` envelope. On success ``data`` holds
the payload and ``error`` is null. On failure ``data`` is null and ``error``
is set. ``meta.request_id`` is the same value sent in the ``X-Request-ID``
response header.
"""

from datetime import UTC, datetime
from typing import Annotated, Generic, Self, TypeVar

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    ValidationInfo,
    field_validator,
    model_validator,
)

from app.exceptions import ErrorCode
from app.models import ConsultationStatus, PersonRole

DataT = TypeVar("DataT")


def _require_aware_utc(value: datetime) -> datetime:
    """Reject a naive datetime and normalise everything else to UTC."""
    if value.tzinfo is None:
        raise ValueError("Datetime values must be timezone-aware (UTC).")
    return value.astimezone(UTC)


def _dump_utc(value: datetime) -> str:
    """JSON form of a UTC datetime, matching ``2026-10-01T09:30:00Z``."""
    text = value.astimezone(UTC).isoformat()
    if text.endswith("+00:00"):
        return f"{text[:-6]}Z"
    return text


def _require_note_text(value: str) -> str:
    """Refuse empty or whitespace-only note and addendum text (rule R14)."""
    stripped = value.strip()
    if not stripped:
        raise ValueError("Must not be empty or whitespace.")
    return stripped


# Aware UTC on the way in; a trailing "Z" on the way out to JSON.
UtcDateTime = Annotated[
    datetime,
    AfterValidator(_require_aware_utc),
    PlainSerializer(_dump_utc, return_type=str, when_used="json"),
]

# Stored text is the stripped value, so a body of spaces is a validation error.
NoteText = Annotated[str, AfterValidator(_require_note_text)]


class RequestModel(BaseModel):
    """JSON a client sends. Unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    """JSON the API returns.

    ``from_attributes`` copies only the fields declared on the subclass when a
    service builds a response from a row. Columns that are not declared here
    are dropped, which is what keeps the response shape separate from the table.
    """

    model_config = ConfigDict(from_attributes=True)


# Envelope
class ErrorDetail(BaseModel):
    """One field-level problem. Populated for validation errors, otherwise unused."""

    model_config = ConfigDict(extra="forbid")

    field: str
    message: str


class ErrorBody(BaseModel):
    """The ``error`` object on a failed response."""

    model_config = ConfigDict(extra="forbid")

    code: ErrorCode
    status: int
    details: list[ErrorDetail] = Field(default_factory=list)


class ResponseMeta(BaseModel):
    """Present on every response, success or failure."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    timestamp: UtcDateTime


class UniformResponse(BaseModel, Generic[DataT]):
    """The single response envelope (option A) for every endpoint.

    ``data`` is the success payload. It may be null when a success has nothing
    to return (for example deleting a draft). On failure it is always null.
    """

    model_config = ConfigDict(extra="forbid")

    success: bool
    message: str
    data: DataT | None = None
    error: ErrorBody | None = None
    meta: ResponseMeta

    @model_validator(mode="after")
    def success_matches_error(self) -> Self:
        if self.success and self.error is not None:
            raise ValueError("A successful response cannot include an error.")
        if not self.success and (self.error is None or self.data is not None):
            raise ValueError("A failed response has an error and no data.")
        return self


# Identity
class LoginRequest(RequestModel):
    """Body of ``POST /auth/login``. The id comes from the sign-in picker."""

    person_id: int = Field(gt=0)


class TokenResponseData(ResponseModel):
    """The sign-in ticket returned by login.

    The token row's id, owner and created-at stay in the database. Later
    requests send this string as ``Authorization: Bearer <ticket>``.
    """

    token: str


class PersonResponse(ResponseModel):
    """One entry of ``GET /people``.

    Specialty is omitted on purpose: the picker only needs id, name and role.
    """

    id: int
    name: str
    role: PersonRole


class PractitionerResponse(ResponseModel):
    """One entry of ``GET /practitioners``: the name and the display-only specialty."""

    id: int
    name: str
    specialty: str | None


# Consultations
class BookConsultationRequest(RequestModel):
    """Body of ``POST /consultations``.

    The signed-in client is the consultation's client, so ``client_id`` is not
    accepted here. Whether ``starts_at`` is in the future is checked by the
    service, because "now" comes from the clock. This model checks the shape
    that does not depend on the clock: timezone-aware times, and an end
    strictly after the start.
    """

    practitioner_id: int = Field(gt=0)
    starts_at: UtcDateTime
    ends_at: UtcDateTime

    @field_validator("ends_at")
    @classmethod
    def end_is_after_start(cls, ends_at: datetime, info: ValidationInfo) -> datetime:
        starts_at = info.data.get("starts_at")
        if isinstance(starts_at, datetime) and ends_at <= starts_at:
            raise ValueError("Must be strictly after starts_at.")
        return ends_at


class ConsultationResponse(ResponseModel):
    """A consultation the caller participates in.

    Used for the list, for booking, and for cancel and complete. It carries no
    note. Note visibility is only on ``ConsultationDetailResponse``, so a list
    payload cannot hint that a private draft exists.
    """

    id: int
    client_id: int
    practitioner_id: int
    starts_at: UtcDateTime
    ends_at: UtcDateTime
    status: ConsultationStatus
    cancelled_by_id: int | None


# Notes and addenda
class CreateNoteRequest(RequestModel):
    """Body of ``POST /consultations/{id}/note``. Creates a private draft."""

    body: NoteText


class UpdateNoteRequest(RequestModel):
    """Body of ``PATCH /consultations/{id}/note``. Draft notes only."""

    body: NoteText


class CreateAddendumRequest(RequestModel):
    """Body of ``POST /consultations/{id}/note/addenda``. Shared notes only."""

    body: NoteText


class AddendumResponse(ResponseModel):
    """A dated correction appended to a shared note.

    Addenda cannot be edited or deleted, so the response has no updated-at
    and no operation for changing ``body``.
    """

    id: int
    note_id: int
    body: str
    created_at: UtcDateTime


class NoteResponse(ResponseModel):
    """A note the caller is allowed to read.

    A client receives this only once the note has been shared. The service
    must not build it for a client while the note is still a draft: a private
    note is invisible, including any hint that it exists. ``shared_at`` is
    null only when this object is a draft being returned to its practitioner.
    ``addenda`` is empty until the note has been shared and a correction written.
    """

    id: int
    consultation_id: int
    body: str
    shared_at: UtcDateTime | None
    created_at: UtcDateTime
    addenda: list[AddendumResponse] = Field(default_factory=list)


class ConsultationDetailResponse(ConsultationResponse):
    """``GET /consultations/{id}``.

    ``note`` is present when the caller may read it, and null otherwise.
    Null covers both "there is no note" and "a draft the client must not see".
    Those two cases use the same JSON so the response cannot give the draft away.
    """

    note: NoteResponse | None = None
