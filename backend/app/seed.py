"""Example people and consultations for the local database.

Past consultations are inserted here. ``POST /consultations`` refuses a start
time that is not in the future, so a session that has already begun cannot be
created through booking.

Run from ``backend/`` with ``python -m app.seed``. Running it again replaces
the rows already in the database.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlmodel import Session

from app.clock import Clock
from app.database import DEFAULT_DATABASE_PATH, DatabaseManager
from app.models import (
    Addendum,
    AuthToken,
    Consultation,
    ConsultationStatus,
    Note,
    Person,
    PersonRole,
)

PAST_SCHEDULED_OFFSET = timedelta(days=-1)
FUTURE_SCHEDULED_OFFSET = timedelta(days=7)
DRAFT_OFFSET = timedelta(days=-5)
SHARED_OFFSET = timedelta(days=-10)
CANCELLED_OFFSET = timedelta(days=3)
OVERLAP_OFFSET = timedelta(days=2)
CONSULTATION_LENGTH = timedelta(hours=1)

ASHA_SPECIALTY = "Continuity care"
VIKRAM_SPECIALTY = "Recovery planning"

DRAFT_NOTE = "Private draft: review the walking plan before sharing."
SHARED_NOTE = "Agreed on a short walk after lunch and a fixed bedtime."
SHARED_ADDENDUM = "Correction: the walk is three days a week, not every day."


def consultation_start(now: datetime, offset: timedelta) -> datetime:
    """The clock hour of ``now``, shifted by ``offset``, in UTC."""
    if now.tzinfo is None:
        raise ValueError("Datetime values must be timezone-aware (UTC).")
    hour = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    return hour + offset


class SeedRunner:
    """Creates the tables and loads the example rows.

    Pass a database and a clock in tests. The script uses ``backend/debrief.db``
    and the live clock.
    """

    def __init__(
        self,
        database: DatabaseManager | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._database = DatabaseManager() if database is None else database
        self._clock = Clock() if clock is None else clock

    def run(self) -> None:
        """Replace whatever is stored with the example people and consultations."""
        self._database.create_tables()
        with Session(self._database.engine, expire_on_commit=False) as session:
            _clear(session)
            _load(session, self._clock.now())
            session.commit()


def _clear(session: Session) -> None:
    """Remove every row. Children go first so the foreign keys stay valid."""
    for table in (Addendum, Note, Consultation, AuthToken, Person):
        session.execute(delete(table))
    session.flush()


def _load(session: Session, now: datetime) -> None:
    """Insert the five people and one consultation for each required state."""
    priya = _person(session, "Priya", PersonRole.CLIENT)
    rohan = _person(session, "Rohan", PersonRole.CLIENT)
    _person(session, "Meera", PersonRole.CLIENT)  # listed at sign-in, with no consultation
    asha = _person(session, "Dr. Asha Rao", PersonRole.PRACTITIONER, ASHA_SPECIALTY)
    vikram = _person(session, "Dr. Vikram Shah", PersonRole.PRACTITIONER, VIKRAM_SPECIALTY)

    _consultation(
        session,
        client_id=priya,
        practitioner_id=asha,
        offset=PAST_SCHEDULED_OFFSET,
        now=now,
        status=ConsultationStatus.SCHEDULED,
    )
    _consultation(
        session,
        client_id=priya,
        practitioner_id=asha,
        offset=FUTURE_SCHEDULED_OFFSET,
        now=now,
        status=ConsultationStatus.SCHEDULED,
    )
    draft_id = _consultation(
        session,
        client_id=priya,
        practitioner_id=asha,
        offset=DRAFT_OFFSET,
        now=now,
        status=ConsultationStatus.COMPLETED,
    )
    shared_id = _consultation(
        session,
        client_id=rohan,
        practitioner_id=asha,
        offset=SHARED_OFFSET,
        now=now,
        status=ConsultationStatus.COMPLETED,
    )
    _consultation(
        session,
        client_id=priya,
        practitioner_id=vikram,
        offset=CANCELLED_OFFSET,
        now=now,
        status=ConsultationStatus.CANCELLED,
        cancelled_by_id=priya,
    )
    # Rohan with Dr. Vikram Shah, still scheduled. Priya is not on it, so that hour overlaps.
    _consultation(
        session,
        client_id=rohan,
        practitioner_id=vikram,
        offset=OVERLAP_OFFSET,
        now=now,
        status=ConsultationStatus.SCHEDULED,
    )

    draft_end = consultation_start(now, DRAFT_OFFSET) + CONSULTATION_LENGTH
    _note(session, draft_id, DRAFT_NOTE, written_at=draft_end, shared_at=None)

    shared_end = consultation_start(now, SHARED_OFFSET) + CONSULTATION_LENGTH
    shared_at = shared_end + timedelta(hours=2)
    note_id = _note(session, shared_id, SHARED_NOTE, written_at=shared_end, shared_at=shared_at)
    _addendum(session, note_id, SHARED_ADDENDUM, written_at=shared_at + timedelta(days=1))


def _person(session: Session, name: str, role: PersonRole, specialty: str | None = None) -> int:
    person = Person(name=name, role=role, specialty=specialty)
    session.add(person)
    session.flush()
    return _row_id(person.id)


def _consultation(
    session: Session,
    *,
    client_id: int,
    practitioner_id: int,
    offset: timedelta,
    now: datetime,
    status: ConsultationStatus,
    cancelled_by_id: int | None = None,
) -> int:
    starts_at = consultation_start(now, offset)
    ends_at = starts_at + CONSULTATION_LENGTH
    written_at = starts_at - timedelta(days=2)
    consultation = Consultation(
        client_id=client_id,
        practitioner_id=practitioner_id,
        starts_at=starts_at,
        ends_at=ends_at,
        status=status,
        cancelled_by_id=cancelled_by_id,
        created_at=written_at,
        updated_at=ends_at if status == ConsultationStatus.COMPLETED else written_at,
    )
    session.add(consultation)
    session.flush()
    return _row_id(consultation.id)


def _note(
    session: Session,
    consultation_id: int,
    body: str,
    *,
    written_at: datetime,
    shared_at: datetime | None,
) -> int:
    note = Note(
        consultation_id=consultation_id,
        body=body,
        shared_at=shared_at,
        created_at=written_at,
        updated_at=shared_at or written_at,
    )
    session.add(note)
    session.flush()
    return _row_id(note.id)


def _addendum(session: Session, note_id: int, body: str, *, written_at: datetime) -> None:
    session.add(
        Addendum(
            note_id=note_id,
            body=body,
            created_at=written_at,
            updated_at=written_at,
        )
    )
    session.flush()


def _row_id(value: int | None) -> int:
    if value is None:
        raise RuntimeError("Expected a saved row with an id.")
    return value


def main() -> None:
    """Load ``backend/debrief.db`` and close the connection."""
    database = DatabaseManager()
    SeedRunner(database).run()
    database.dispose()
    print(f"Seeded {DEFAULT_DATABASE_PATH}")


if __name__ == "__main__":
    main()
