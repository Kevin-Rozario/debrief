"""The example database has the people and consultation states the screen needs."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.clock import FrozenClock
from app.database import DatabaseManager
from app.main import create_app
from app.seed import (
    ASHA_SPECIALTY,
    CANCELLED_OFFSET,
    CONSULTATION_LENGTH,
    DRAFT_NOTE,
    DRAFT_OFFSET,
    FUTURE_SCHEDULED_OFFSET,
    OVERLAP_OFFSET,
    PAST_SCHEDULED_OFFSET,
    SHARED_ADDENDUM,
    SHARED_NOTE,
    SHARED_OFFSET,
    VIKRAM_SPECIALTY,
    SeedRunner,
    consultation_start,
)
from tests.conftest import expect_error, expect_ok

NOW = datetime(2026, 10, 1, 9, 30, tzinfo=UTC)


@pytest.fixture
def seeded(tmp_path):
    """A client against a database SeedRunner just filled, at a fixed clock."""
    clock = FrozenClock(NOW)
    database = DatabaseManager(tmp_path / "debrief.db")
    SeedRunner(database, clock).run()
    SeedRunner(database, clock).run()  # a second run replaces the rows
    application = create_app(database=database, clock=clock)
    with TestClient(application) as client:
        people = expect_ok(client.get("/people"))["data"]
        yield client, clock, {person["name"]: person["id"] for person in people}


def _sign_in(client: TestClient, person_id: int) -> dict[str, str]:
    token = expect_ok(client.post("/auth/login", json={"person_id": person_id}))["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def _by_start(rows: list[dict], start: datetime) -> dict:
    matches = [row for row in rows if row["starts_at"] == _z(start)]
    assert len(matches) == 1
    return matches[0]


def _z(moment: datetime) -> str:
    text = moment.astimezone(UTC).isoformat()
    if text.endswith("+00:00"):
        return f"{text[:-6]}Z"
    return text


def test_seed_lists_the_five_people_and_two_practitioners(seeded) -> None:
    client, _clock, ids = seeded
    people = expect_ok(client.get("/people"))["data"]
    priya = _sign_in(client, ids["Priya"])

    assert [person["name"] for person in people] == [
        "Priya",
        "Rohan",
        "Meera",
        "Dr. Asha Rao",
        "Dr. Vikram Shah",
    ]
    assert [person["role"] for person in people] == [
        "client",
        "client",
        "client",
        "practitioner",
        "practitioner",
    ]
    practitioners = expect_ok(client.get("/practitioners", headers=priya))["data"]
    assert practitioners == [
        {"id": ids["Dr. Asha Rao"], "name": "Dr. Asha Rao", "specialty": ASHA_SPECIALTY},
        {"id": ids["Dr. Vikram Shah"], "name": "Dr. Vikram Shah", "specialty": VIKRAM_SPECIALTY},
    ]


def test_seed_covers_each_consultation_state(seeded) -> None:
    client, _clock, ids = seeded
    priya = _sign_in(client, ids["Priya"])
    rohan = _sign_in(client, ids["Rohan"])
    asha = _sign_in(client, ids["Dr. Asha Rao"])
    def hour(offset):
        return consultation_start(NOW, offset)

    priya_rows = expect_ok(client.get("/consultations", headers=priya))["data"]
    past = _by_start(priya_rows, hour(PAST_SCHEDULED_OFFSET))
    future = _by_start(priya_rows, hour(FUTURE_SCHEDULED_OFFSET))
    draft = _by_start(priya_rows, hour(DRAFT_OFFSET))
    cancelled = _by_start(priya_rows, hour(CANCELLED_OFFSET))

    assert past["status"] == "scheduled"
    assert future["status"] == "scheduled"
    assert draft["status"] == "completed"
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancelled_by_id"] == ids["Priya"]
    assert len(priya_rows) == 4

    priya_draft = expect_ok(client.get(f"/consultations/{draft['id']}", headers=priya))["data"]
    asha_draft = expect_ok(client.get(f"/consultations/{draft['id']}", headers=asha))["data"]
    assert priya_draft["note"] is None
    assert asha_draft["note"]["body"] == DRAFT_NOTE
    assert asha_draft["note"]["shared_at"] is None

    rohan_rows = expect_ok(client.get("/consultations", headers=rohan))["data"]
    shared = _by_start(rohan_rows, hour(SHARED_OFFSET))
    shared_detail = expect_ok(client.get(f"/consultations/{shared['id']}", headers=rohan))["data"]
    assert shared_detail["note"]["body"] == SHARED_NOTE
    assert shared_detail["note"]["shared_at"] is not None
    assert [item["body"] for item in shared_detail["note"]["addenda"]] == [SHARED_ADDENDUM]

    hidden = _by_start(rohan_rows, hour(OVERLAP_OFFSET))
    expect_error(
        client.get(f"/consultations/{hidden['id']}", headers=priya),
        404,
        "RESOURCE_NOT_FOUND",
    )
    overlap_start = hour(OVERLAP_OFFSET)
    expect_error(
        client.post(
            "/consultations",
            headers=priya,
            json={
                "practitioner_id": ids["Dr. Vikram Shah"],
                "starts_at": _z(overlap_start),
                "ends_at": _z(overlap_start + CONSULTATION_LENGTH),
            },
        ),
        409,
        "SCHEDULING_CONFLICT",
    )
    expect_error(
        client.post(f"/consultations/{future['id']}/complete", headers=asha),
        409,
        "CONSULTATION_NOT_STARTED",
    )
    cancelled_future = expect_ok(
        client.post(f"/consultations/{future['id']}/cancel", headers=priya)
    )["data"]
    assert cancelled_future["status"] == "cancelled"
    assert cancelled_future["cancelled_by_id"] == ids["Priya"]
    completed = expect_ok(client.post(f"/consultations/{past['id']}/complete", headers=asha))
    assert completed["data"]["status"] == "completed"


def test_meera_has_no_consultations(seeded) -> None:
    client, _clock, ids = seeded
    meera = _sign_in(client, ids["Meera"])
    listed = expect_ok(client.get("/consultations", headers=meera))["data"]
    assert listed == []
