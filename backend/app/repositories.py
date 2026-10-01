"""Database reads and writes for Debrief.

Repositories load and store rows. They do not decide whether a request is
allowed: that is the service's job. They also do not commit. The service
owns the transaction, including the immediate write lock taken before a
booking overlap check. ``add`` and ``delete`` flush so a new id is available
and a deleted draft frees its consultation before the service commits.

Nothing here follows a relationship. Each query names the table it reads.
"""

from datetime import datetime

from sqlmodel import Session, or_, select

from app.models import (
    Addendum,
    AuthToken,
    Consultation,
    ConsultationStatus,
    Note,
    Person,
    PersonRole,
)


class PersonRepository:
    """People: the sign-in picker and the practitioner list."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, person_id: int) -> Person | None:
        """The person with this id, or None if there is no such row."""
        return self._session.get(Person, person_id)

    def list_people(self) -> list[Person]:
        """Every person, in id order, for the sign-in picker."""
        return list(self._session.exec(select(Person).order_by(Person.id)))

    def list_practitioners(self) -> list[Person]:
        """People whose role is practitioner, in id order."""
        statement = (
            select(Person)
            .where(Person.role == PersonRole.PRACTITIONER)
            .order_by(Person.id)
        )
        return list(self._session.exec(statement))


class AuthTokenRepository:
    """Sign-in tickets. Creating the random token string is the service's job."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_token(self, token: str) -> AuthToken | None:
        """The ticket row for this string, or None if it was never issued."""
        statement = select(AuthToken).where(AuthToken.token == token)
        return self._session.exec(statement).first()

    def add(self, auth_token: AuthToken) -> AuthToken:
        """Stage a ticket and flush so its id is set. The caller commits."""
        self._session.add(auth_token)
        self._session.flush()
        return auth_token


class ConsultationRepository:
    """Consultations. Status changes are made on the loaded row by the service."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, consultation_id: int) -> Consultation | None:
        """The consultation with this id, or None if there is no such row."""
        return self._session.get(Consultation, consultation_id)

    def list_for_person(self, person_id: int) -> list[Consultation]:
        """Consultations where this person is the client or the practitioner.

        Ordered by start time. Cancelled and completed rows are included;
        hiding them is not a storage concern.
        """
        statement = (
            select(Consultation)
            .where(
                or_(
                    Consultation.client_id == person_id,
                    Consultation.practitioner_id == person_id,
                )
            )
            .order_by(Consultation.starts_at, Consultation.id)
        )
        return list(self._session.exec(statement))

    def add(self, consultation: Consultation) -> Consultation:
        """Stage a consultation and flush so its id is set. The caller commits."""
        self._session.add(consultation)
        self._session.flush()
        return consultation

    def find_scheduled_overlap(
        self,
        practitioner_id: int,
        starts_at: datetime,
        ends_at: datetime,
    ) -> Consultation | None:
        """A scheduled consultation of this practitioner that overlaps the window.

        Overlap uses the open edge: a booking that starts when another ends
        does not overlap. Cancelled and completed rows are ignored. Returns
        None when the window is free. The service decides whether that is a
        conflict; this method only finds the row.
        """
        statement = (
            select(Consultation)
            .where(Consultation.practitioner_id == practitioner_id)
            .where(Consultation.status == ConsultationStatus.SCHEDULED)
            .where(Consultation.starts_at < ends_at)
            .where(Consultation.ends_at > starts_at)
        )
        return self._session.exec(statement).first()


class NoteRepository:
    """Notes and their addenda. One note row per consultation.

    Editing the body or setting ``shared_at`` is done on the loaded note by
    the service. Addenda are stored here because they are always reached
    through their note.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_for_consultation(self, consultation_id: int) -> Note | None:
        """The note for this consultation, or None if it has none yet."""
        statement = select(Note).where(Note.consultation_id == consultation_id)
        return self._session.exec(statement).first()

    def add(self, note: Note) -> Note:
        """Stage a note and flush so its id is set. The caller commits."""
        self._session.add(note)
        self._session.flush()
        return note

    def delete(self, note: Note) -> None:
        """Stage deletion and flush so the consultation can take a new note.

        The caller commits. This does not remove addenda; a draft has none.
        """
        self._session.delete(note)
        self._session.flush()

    def list_addenda(self, note_id: int) -> list[Addendum]:
        """Corrections on this note, oldest first."""
        statement = (
            select(Addendum)
            .where(Addendum.note_id == note_id)
            .order_by(Addendum.created_at, Addendum.id)
        )
        return list(self._session.exec(statement))

    def add_addendum(self, addendum: Addendum) -> Addendum:
        """Stage an addendum and flush so its id is set. The caller commits."""
        self._session.add(addendum)
        self._session.flush()
        return addendum
