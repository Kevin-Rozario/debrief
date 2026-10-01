"""Database tables for Debrief (SQLModel / SQLAlchemy).

These classes describe how data is stored. They deliberately contain no
business rules beyond tiny read-only helpers; rules live in the services.
Validation of incoming data lives in ``schemas.py``.
"""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    """Current moment as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


class UtcDateTime(TypeDecorator):
    """A datetime column that always holds and returns timezone-aware UTC values.

    SQLite does not keep time-zone information, so a plain DateTime column
    would hand back naive datetimes. This type enforces PRD rule R15
    ("all times stored in UTC"): it refuses naive values on the way in and
    attaches UTC on the way out.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Datetime values must be timezone-aware (UTC).")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


class PersonRole(StrEnum):
    """A person has one role: client or practitioner."""

    CLIENT = "client"
    PRACTITIONER = "practitioner"


class ConsultationStatus(StrEnum):
    """scheduled, then completed or cancelled. Both later states are final."""

    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CreatedAtMixin(SQLModel):
    """created_at on every table, stored as UTC."""

    created_at: datetime = Field(default_factory=_utc_now, sa_type=UtcDateTime)


class TimestampMixin(CreatedAtMixin):
    """created_at plus updated_at. updated_at moves on each ORM update."""

    updated_at: datetime = Field(
        default_factory=_utc_now,
        sa_type=UtcDateTime,
        sa_column_kwargs={"onupdate": _utc_now},
    )


class Person(CreatedAtMixin, table=True):
    """A client or a practitioner. Specialty is display-only and used for practitioners."""

    __tablename__ = "person"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    role: PersonRole
    specialty: str | None = Field(default=None)


class AuthToken(CreatedAtMixin, table=True):
    """The sign-in ticket issued when someone picks a person to sign in as."""

    __tablename__ = "auth_token"

    id: int | None = Field(default=None, primary_key=True)
    token: str = Field(unique=True, index=True)
    person_id: int = Field(foreign_key="person.id", index=True)


class Consultation(TimestampMixin, table=True):
    """One booked session. cancelled_by_id is set when the session is cancelled."""

    __tablename__ = "consultation"

    id: int | None = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="person.id", index=True)
    practitioner_id: int = Field(foreign_key="person.id", index=True)
    starts_at: datetime = Field(sa_type=UtcDateTime)
    ends_at: datetime = Field(sa_type=UtcDateTime)
    status: ConsultationStatus = Field(default=ConsultationStatus.SCHEDULED, index=True)
    cancelled_by_id: int | None = Field(default=None, foreign_key="person.id")

    def has_participant(self, person_id: int) -> bool:
        """True if the person is this consultation's client or practitioner."""
        return person_id in (self.client_id, self.practitioner_id)

    def has_started(self, now: datetime) -> bool:
        """True once ``now`` has reached the scheduled start time."""
        return now >= self.starts_at


class Note(TimestampMixin, table=True):
    """One note for one consultation. shared_at stays empty while the draft is private."""

    __tablename__ = "note"

    id: int | None = Field(default=None, primary_key=True)
    consultation_id: int = Field(foreign_key="consultation.id", unique=True)
    body: str
    shared_at: datetime | None = Field(default=None, sa_type=UtcDateTime)

    @property
    def is_shared(self) -> bool:
        """True after the practitioner shares the note. Sharing is permanent."""
        return self.shared_at is not None


class Addendum(TimestampMixin, table=True):
    """A dated correction on a shared note. The API never edits or deletes one."""

    __tablename__ = "addendum"

    id: int | None = Field(default=None, primary_key=True)
    note_id: int = Field(foreign_key="note.id", index=True)
    body: str