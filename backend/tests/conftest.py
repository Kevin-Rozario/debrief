"""One fresh database and a frozen clock for each test.

Tests talk to the API through FastAPI's test client. People are inserted
directly because the API has no request that creates a person: sign-in only
issues a ticket for someone who is already there.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlmodel import Session

from app.clock import FrozenClock
from app.database import DatabaseManager
from app.main import create_app
from app.models import Person, PersonRole

# A fixed "now" so every test books against the same moment until it moves the clock.
NOW = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def zulu(moment: datetime) -> str:
    """The API's UTC timestamp form, with a trailing Z."""
    text = moment.astimezone(UTC).isoformat()
    if text.endswith("+00:00"):
        return f"{text[:-6]}Z"
    return text


def envelope(response: Response) -> dict:
    """The uniform body, with the request id echoed in the response header."""
    payload = response.json()
    assert set(payload) == {"success", "message", "data", "error", "meta"}
    assert set(payload["meta"]) == {"request_id", "timestamp"}
    assert payload["meta"]["timestamp"].endswith("Z")
    assert response.headers["X-Request-ID"] == payload["meta"]["request_id"]
    return payload


def expect_ok(response: Response) -> dict:
    """A 200 envelope with data and no error."""
    payload = envelope(response)
    assert response.status_code == 200, payload
    assert payload["success"] is True
    assert payload["error"] is None
    return payload


def expect_error(
    response: Response,
    status: int,
    code: str,
    message: str | None = None,
) -> dict:
    """A failure envelope whose status, code, and message match."""
    payload = envelope(response)
    assert response.status_code == status, payload
    assert payload["success"] is False
    assert payload["data"] is None
    assert payload["error"]["code"] == code
    assert payload["error"]["status"] == status
    if message is not None:
        assert payload["message"] == message
    return payload


def field_message(payload: dict, field: str) -> str:
    """The validation message for one field."""
    messages = [
        item["message"] for item in payload["error"]["details"] if item["field"] == field
    ]
    assert messages, payload["error"]["details"]
    return messages[0]


class Api:
    """The test client plus the four people a test can sign in as."""

    def __init__(self, client: TestClient, database: DatabaseManager, clock: FrozenClock) -> None:
        self.client = client
        self.database = database
        self.clock = clock
        self.priya_id = self._add_person("Priya", PersonRole.CLIENT)
        self.rohan_id = self._add_person("Rohan", PersonRole.CLIENT)
        self.asha_id = self._add_person("Dr. Asha Rao", PersonRole.PRACTITIONER, "Cardiology")
        self.vikram_id = self._add_person("Dr. Vikram Shah", PersonRole.PRACTITIONER, "Dermatology")
        self.priya = self._sign_in(self.priya_id)
        self.rohan = self._sign_in(self.rohan_id)
        self.asha = self._sign_in(self.asha_id)
        self.vikram = self._sign_in(self.vikram_id)

    def window(self, *, start_in_hours: float = 24, hours: float = 1) -> tuple[datetime, datetime]:
        """A future interval measured from the frozen clock."""
        starts_at = self.clock.now() + timedelta(hours=start_in_hours)
        return starts_at, starts_at + timedelta(hours=hours)

    def book(
        self,
        headers: dict[str, str],
        practitioner_id: int,
        starts_at: datetime,
        ends_at: datetime,
    ) -> Response:
        """POST /consultations, without deciding whether it should succeed."""
        return self.client.post(
            "/consultations",
            headers=headers,
            json={
                "practitioner_id": practitioner_id,
                "starts_at": zulu(starts_at),
                "ends_at": zulu(ends_at),
            },
        )

    def book_ok(
        self,
        headers: dict[str, str] | None = None,
        practitioner_id: int | None = None,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        start_in_hours: float = 24,
    ) -> tuple[int, datetime, datetime]:
        """Book as Priya with Asha unless the caller says otherwise. Returns the id and window."""
        if starts_at is None or ends_at is None:
            starts_at, ends_at = self.window(start_in_hours=start_in_hours)
        response = self.book(
            self.priya if headers is None else headers,
            self.asha_id if practitioner_id is None else practitioner_id,
            starts_at,
            ends_at,
        )
        consultation_id = expect_ok(response)["data"]["id"]
        return consultation_id, starts_at, ends_at

    def complete(self, consultation_id: int, headers: dict[str, str] | None = None) -> Response:
        """POST /consultations/{id}/complete."""
        return self.client.post(
            f"/consultations/{consultation_id}/complete",
            headers=self.asha if headers is None else headers,
        )

    def cancel(self, consultation_id: int, headers: dict[str, str] | None = None) -> Response:
        """POST /consultations/{id}/cancel."""
        return self.client.post(
            f"/consultations/{consultation_id}/cancel",
            headers=self.priya if headers is None else headers,
        )

    def create_note(
        self,
        consultation_id: int,
        body: str,
        headers: dict[str, str] | None = None,
    ) -> Response:
        """POST /consultations/{id}/note."""
        return self.client.post(
            f"/consultations/{consultation_id}/note",
            headers=self.asha if headers is None else headers,
            json={"body": body},
        )

    def schedule_and_complete(self, start_in_hours: float = 24) -> int:
        """A completed consultation between Priya and Asha. The clock stops at its start."""
        consultation_id, starts_at, _ends_at = self.book_ok(start_in_hours=start_in_hours)
        self.clock.move_to(starts_at)
        expect_ok(self.complete(consultation_id))
        return consultation_id

    def _add_person(self, name: str, role: PersonRole, specialty: str | None = None) -> int:
        with Session(self.database.engine) as session:
            person = Person(name=name, role=role, specialty=specialty)
            session.add(person)
            session.commit()
            session.refresh(person)
            if person.id is None:
                raise RuntimeError("Expected a saved person with an id.")
            return person.id

    def _sign_in(self, person_id: int) -> dict[str, str]:
        response = self.client.post("/auth/login", json={"person_id": person_id})
        token = expect_ok(response)["data"]["token"]
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def api(tmp_path: Path) -> Iterator[Api]:
    """A client bound to a new database and a clock pinned at ``NOW``."""
    database = DatabaseManager(tmp_path / "debrief.db")
    clock = FrozenClock(NOW)
    application = create_app(database=database, clock=clock)
    with TestClient(application) as client:
        yield Api(client, database, clock)
