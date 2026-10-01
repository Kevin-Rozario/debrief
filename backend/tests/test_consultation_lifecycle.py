"""Scheduled consultations can be cancelled or completed, and then they stay finished.

Either participant may cancel, including after the start. Only the
practitioner may complete, and only once the start time has been reached.
The exact start moment counts. A finished consultation cannot be finished again.
"""

from datetime import timedelta

from tests.conftest import Api, expect_error, expect_ok, zulu

NOT_SCHEDULED = "This consultation is no longer scheduled."


def test_the_caller_lists_and_reads_their_own_consultations(api: Api) -> None:
    later_start, later_end = api.window(start_in_hours=48)
    sooner_start, sooner_end = api.window(start_in_hours=24)
    later_id, _later_start, _later_end = api.book_ok(starts_at=later_start, ends_at=later_end)
    sooner_id, _sooner_start, _sooner_end = api.book_ok(starts_at=sooner_start, ends_at=sooner_end)

    listed = expect_ok(api.client.get("/consultations", headers=api.asha))["data"]
    detail = expect_ok(api.client.get(f"/consultations/{sooner_id}", headers=api.asha))["data"]

    assert [item["id"] for item in listed] == [sooner_id, later_id]
    assert [item["starts_at"] for item in listed] == [zulu(sooner_start), zulu(later_start)]
    assert "note" not in listed[0]
    assert set(detail) == set(listed[0]) | {"note"}
    assert detail["note"] is None


def test_either_participant_can_cancel_and_the_caller_is_recorded(api: Api) -> None:
    client_cancelled, _starts_at, _ends_at = api.book_ok()
    by_client = expect_ok(api.cancel(client_cancelled, headers=api.priya))["data"]

    practitioner_cancelled, _starts_at, _ends_at = api.book_ok(start_in_hours=48)
    by_practitioner = expect_ok(api.cancel(practitioner_cancelled, headers=api.asha))["data"]

    assert by_client["status"] == "cancelled"
    assert by_client["cancelled_by_id"] == api.priya_id
    assert by_practitioner["status"] == "cancelled"
    assert by_practitioner["cancelled_by_id"] == api.asha_id


def test_cancel_is_allowed_after_the_start_time(api: Api) -> None:
    consultation_id, starts_at, _ends_at = api.book_ok()
    api.clock.move_to(starts_at + timedelta(minutes=5))

    cancelled = expect_ok(api.cancel(consultation_id, headers=api.asha))["data"]

    assert cancelled["status"] == "cancelled"
    assert cancelled["cancelled_by_id"] == api.asha_id


def test_cancel_and_complete_require_a_scheduled_consultation(api: Api) -> None:
    consultation_id, starts_at, _ends_at = api.book_ok()
    expect_ok(api.cancel(consultation_id))

    expect_error(api.cancel(consultation_id), 409, "CONSULTATION_NOT_SCHEDULED", NOT_SCHEDULED)
    api.clock.move_to(starts_at - timedelta(seconds=1))
    expect_error(api.complete(consultation_id), 409, "CONSULTATION_NOT_SCHEDULED", NOT_SCHEDULED)

    finished_id, finished_start, _ends_at = api.book_ok(start_in_hours=48)
    api.clock.move_to(finished_start)
    expect_ok(api.complete(finished_id))
    expect_error(api.complete(finished_id), 409, "CONSULTATION_NOT_SCHEDULED", NOT_SCHEDULED)
    expect_error(
        api.cancel(finished_id),
        409,
        "CONSULTATION_NOT_SCHEDULED",
        NOT_SCHEDULED,
    )


def test_complete_is_refused_until_the_start_and_accepted_at_that_moment(api: Api) -> None:
    consultation_id, starts_at, _ends_at = api.book_ok()
    api.clock.move_to(starts_at - timedelta(seconds=1))
    expect_error(
        api.complete(consultation_id),
        409,
        "CONSULTATION_NOT_STARTED",
        "This consultation has not started yet.",
    )

    api.clock.move_to(starts_at)
    completed = expect_ok(api.complete(consultation_id))["data"]

    assert completed["status"] == "completed"
    assert completed["cancelled_by_id"] is None


def test_a_cancelled_consultation_stays_visible_to_its_participants(api: Api) -> None:
    consultation_id, _starts_at, _ends_at = api.book_ok()
    expect_ok(api.cancel(consultation_id))

    detail = expect_ok(api.client.get(f"/consultations/{consultation_id}", headers=api.priya))
    listed = expect_ok(api.client.get("/consultations", headers=api.asha))["data"]

    assert detail["data"]["status"] == "cancelled"
    assert [item["id"] for item in listed] == [consultation_id]
