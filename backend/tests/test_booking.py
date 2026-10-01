"""Booking rules: who may book, when the window is valid, and which rows block it.

Only a client's future booking is accepted. A practitioner's scheduled
consultation blocks an overlap. A booking that starts when another ends does
not. Cancelled and completed consultations leave the slot free, and the
client's own calendar is not checked.
"""

from datetime import timedelta
from threading import Barrier, Thread

from tests.conftest import Api, expect_error, expect_ok, field_message, zulu

INVALID = "The request contains invalid data."


def test_a_client_books_a_future_consultation(api: Api) -> None:
    starts_at, ends_at = api.window()
    response = api.book(api.priya, api.asha_id, starts_at, ends_at)
    payload = expect_ok(response)
    consultation = payload["data"]

    assert payload["message"] == "Consultation booked."
    assert set(consultation) == {
        "id",
        "client_id",
        "practitioner_id",
        "starts_at",
        "ends_at",
        "status",
        "cancelled_by_id",
    }
    assert consultation["client_id"] == api.priya_id
    assert consultation["practitioner_id"] == api.asha_id
    assert consultation["starts_at"] == zulu(starts_at)
    assert consultation["ends_at"] == zulu(ends_at)
    assert consultation["status"] == "scheduled"
    assert consultation["cancelled_by_id"] is None


def test_a_practitioner_cannot_book(api: Api) -> None:
    starts_at, ends_at = api.window()
    response = api.book(api.asha, api.vikram_id, starts_at, ends_at)

    expect_error(response, 403, "PERMISSION_DENIED", "Only a client can book a consultation.")


def test_a_missing_practitioner_matches_a_person_who_is_not_one(api: Api) -> None:
    starts_at, ends_at = api.window()
    missing = api.book(api.priya, 999, starts_at, ends_at)
    client_as_practitioner = api.book(api.priya, api.rohan_id, starts_at, ends_at)

    for response in (missing, client_as_practitioner):
        payload = expect_error(response, 422, "VALIDATION_ERROR", INVALID)
        assert payload["error"]["details"] == [
            {"field": "practitioner_id", "message": "Choose a practitioner."}
        ]


def test_the_start_must_be_in_the_future(api: Api) -> None:
    now = api.clock.now()
    past = api.book(api.priya, api.asha_id, now - timedelta(hours=1), now)
    exact = api.book(api.priya, api.asha_id, now, now + timedelta(hours=1))
    upcoming = api.book(
        api.priya,
        api.asha_id,
        now + timedelta(seconds=1),
        now + timedelta(hours=1),
    )

    for response in (past, exact):
        payload = expect_error(response, 422, "VALIDATION_ERROR", INVALID)
        assert field_message(payload, "starts_at") == "Must be in the future."
    expect_ok(upcoming)


def test_the_end_must_be_strictly_after_the_start(api: Api) -> None:
    starts_at, _ends_at = api.window()
    response = api.client.post(
        "/consultations",
        headers=api.priya,
        json={
            "practitioner_id": api.asha_id,
            "starts_at": zulu(starts_at),
            "ends_at": zulu(starts_at),
        },
    )
    payload = expect_error(response, 422, "VALIDATION_ERROR", INVALID)

    assert field_message(payload, "ends_at") == "Must be strictly after starts_at."


def test_naive_datetimes_are_rejected(api: Api) -> None:
    response = api.client.post(
        "/consultations",
        headers=api.priya,
        json={
            "practitioner_id": api.asha_id,
            "starts_at": "2026-10-02T10:00:00",
            "ends_at": "2026-10-02T11:00:00",
        },
    )
    payload = expect_error(response, 422, "VALIDATION_ERROR", INVALID)

    assert field_message(payload, "starts_at") == "Datetime values must be timezone-aware (UTC)."


def test_the_client_id_cannot_be_sent_in_the_body(api: Api) -> None:
    starts_at, ends_at = api.window()
    response = api.client.post(
        "/consultations",
        headers=api.priya,
        json={
            "practitioner_id": api.asha_id,
            "client_id": api.priya_id,
            "starts_at": zulu(starts_at),
            "ends_at": zulu(ends_at),
        },
    )
    payload = expect_error(response, 422, "VALIDATION_ERROR")

    assert field_message(payload, "client_id") == "Extra inputs are not permitted"


def test_an_overlapping_scheduled_consultation_is_refused(api: Api) -> None:
    starts_at, ends_at = api.window()
    api.book_ok(starts_at=starts_at, ends_at=ends_at)
    overlap = api.book(
        api.rohan,
        api.asha_id,
        starts_at + timedelta(minutes=30),
        ends_at + timedelta(minutes=30),
    )

    expect_error(
        overlap,
        409,
        "SCHEDULING_CONFLICT",
        "The practitioner already has a consultation at that time.",
    )


def test_a_booking_that_starts_when_another_ends_is_allowed(api: Api) -> None:
    starts_at, ends_at = api.window()
    api.book_ok(starts_at=starts_at, ends_at=ends_at)
    touching_after = api.book(api.rohan, api.asha_id, ends_at, ends_at + timedelta(hours=1))
    touching_before = api.book(
        api.rohan,
        api.asha_id,
        starts_at - timedelta(hours=1),
        starts_at,
    )

    expect_ok(touching_after)
    expect_ok(touching_before)


def test_a_cancelled_consultation_does_not_block_the_slot(api: Api) -> None:
    starts_at, ends_at = api.window()
    consultation_id, _starts_at, _ends_at = api.book_ok(starts_at=starts_at, ends_at=ends_at)
    expect_ok(api.cancel(consultation_id))

    rebooked = expect_ok(api.book(api.rohan, api.asha_id, starts_at, ends_at))
    assert rebooked["data"]["status"] == "scheduled"


def test_a_completed_consultation_does_not_block_a_later_overlap(api: Api) -> None:
    starts_at, ends_at = api.window()
    consultation_id, _starts_at, _ends_at = api.book_ok(starts_at=starts_at, ends_at=ends_at)
    api.clock.move_to(starts_at)
    expect_ok(api.complete(consultation_id))

    overlapping_start = starts_at + timedelta(minutes=30)
    response = api.book(api.rohan, api.asha_id, overlapping_start, ends_at + timedelta(minutes=30))
    expect_ok(response)


def test_the_client_calendar_is_not_checked(api: Api) -> None:
    starts_at, ends_at = api.window()
    api.book_ok(practitioner_id=api.asha_id, starts_at=starts_at, ends_at=ends_at)
    second = api.book(api.priya, api.vikram_id, starts_at, ends_at)

    expect_ok(second)


def test_simultaneous_bookings_of_one_slot_cannot_both_succeed(api: Api) -> None:
    starts_at, ends_at = api.window()
    barrier = Barrier(2)
    statuses: list[int] = []

    def book(headers: dict[str, str]) -> None:
        barrier.wait(timeout=5)
        response = api.book(headers, api.asha_id, starts_at, ends_at)
        statuses.append(response.status_code)

    threads = [
        Thread(target=book, args=(api.priya,)),
        Thread(target=book, args=(api.rohan,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(statuses) == [200, 409]
