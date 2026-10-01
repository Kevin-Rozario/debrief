"""Sign-in, the people list, and the practitioner list.

``list_people`` and ``login`` do not require a ticket (rule R1). The router
must not ask for the signed-in person on those two calls. ``list_practitioners``
does: only a client may see it.

Login checks that the person exists, then stores a new random ticket. Old
tickets keep working. There is no password.
"""

import secrets

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.exceptions import ErrorDetail, InputValidationError, PermissionDeniedError
from app.models import AuthToken, Person, PersonRole
from app.repositories import AuthTokenRepository, PersonRepository
from app.schemas import PersonResponse, PractitionerResponse, TokenResponseData


class IdentityService:
    """People and tickets. Holds the request's session and commits login itself."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._people = PersonRepository(session)
        self._tokens = AuthTokenRepository(session)

    def list_people(self) -> list[PersonResponse]:
        """Everyone, for the sign-in picker. Specialty is not included."""
        return [_person_response(person) for person in self._people.list_people()]

    def login(self, person_id: int) -> TokenResponseData:
        """Issue a ticket for this person.

        An unknown id is invalid input (422), the same outcome as any other
        person id that is not in the picker.
        """
        person = self._people.get(person_id)
        if person is None:
            raise InputValidationError(
                details=[ErrorDetail("person_id", "Choose a person from the list.")]
            )
        token = self._issue_token(person_id)
        return TokenResponseData(token=token)

    def list_practitioners(self, caller: Person) -> list[PractitionerResponse]:
        """Names and specialty. Practitioners are not allowed to call this."""
        if caller.role != PersonRole.CLIENT:
            raise PermissionDeniedError("Only a client can view practitioners.")
        return [
            PractitionerResponse(
                id=_row_id(person.id),
                name=person.name,
                specialty=person.specialty,
            )
            for person in self._people.list_practitioners()
        ]

    def _issue_token(self, person_id: int) -> str:
        """Store a new ticket. Retry only if the random string is already taken."""
        for _ in range(3):
            try:
                auth_token = self._tokens.add(
                    AuthToken(token=secrets.token_urlsafe(32), person_id=person_id)
                )
                self._session.commit()
            except IntegrityError:
                self._session.rollback()
                continue
            return auth_token.token
        raise RuntimeError("Could not issue a sign-in ticket.")


def _person_response(person: Person) -> PersonResponse:
    """id, name, and role only."""
    return PersonResponse(id=_row_id(person.id), name=person.name, role=person.role)


def _row_id(value: int | None) -> int:
    if value is None:
        raise RuntimeError("Expected a saved row with an id.")
    return value
