"""FastAPI wiring for the database session and the signed-in person.

A protected route depends on ``CurrentPerson``. That reads
``Authorization: Bearer <ticket>`` and asks the repositories for the ticket
row and then the person row. The two tables have no relationship.

Missing and unknown tickets raise ``AuthenticationRequiredError``. Turning
that into the 401 envelope is ``main.py``'s job.

This module does not check client versus practitioner. That check needs the
consultation as well as the person: someone who is not a participant must
get 404, and only the service can tell that apart from a real 403.
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.database import DatabaseManager
from app.exceptions import AuthenticationRequiredError
from app.models import Person
from app.repositories import AuthTokenRepository, PersonRepository

# auto_error is off so a missing header becomes our 401, not FastAPI's 403.
_bearer = HTTPBearer(auto_error=False)


def set_database(app: FastAPI, database: DatabaseManager) -> None:
    """Store the database the session dependency reads on each request."""
    app.state.database = database


def get_database(request: Request) -> DatabaseManager:
    """Return the DatabaseManager attached to this application."""
    database = getattr(request.app.state, "database", None)
    if not isinstance(database, DatabaseManager):
        raise RuntimeError(
            "No database is configured. Call set_database() when creating the app."
        )
    return database


def get_session(database: Annotated[DatabaseManager, Depends(get_database)]) -> Iterator[Session]:
    """One session for the request, closed when the request finishes.

    FastAPI caches this per request, so the ticket lookup and the route share it.
    The lookup is a plain read. A later write (booking) may commit that read
    before taking the immediate write lock; ``begin_write_transaction`` allows
    that only when the session has no pending changes.
    """
    yield from database.get_session()


SessionDep = Annotated[Session, Depends(get_session)]


def get_current_person(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Person:
    """The person whose ticket was sent as ``Authorization: Bearer <ticket>``."""
    token = _require_bearer_token(credentials)
    person = _person_for_token(session, token)
    if person is None:
        raise AuthenticationRequiredError()
    return person


CurrentPerson = Annotated[Person, Depends(get_current_person)]


def _require_bearer_token(credentials: HTTPAuthorizationCredentials | None) -> str:
    """The ticket string, or an authentication error if the header is unusable."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationRequiredError()
    token = credentials.credentials.strip()
    if not token:
        raise AuthenticationRequiredError()
    return token


def _person_for_token(session: Session, token: str) -> Person | None:
    """Load the person for this ticket, or None if the ticket is unknown.

    An unknown ticket and a ticket whose person row is missing both return
    None, so the caller responds with the same 401 either way.
    """
    auth_token = AuthTokenRepository(session).get_by_token(token)
    if auth_token is None:
        return None
    return PersonRepository(session).get(auth_token.person_id)
