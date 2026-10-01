"""Notes start private, lock when shared, and are corrected only by addenda.

A note exists only on a completed consultation, one per consultation, written
by that practitioner. The client cannot tell a draft from a missing note.
Sharing locks the original text. Addenda are dated, append-only, and visible
to the client immediately.
"""

from datetime import timedelta

from tests.conftest import Api, expect_error, expect_ok, field_message, zulu

NOT_FOUND = "The requested resource was not found."
INVALID = "The request contains invalid data."
EMPTY = "Must not be empty or whitespace."


def test_a_note_can_be_written_only_on_a_completed_consultation(api: Api) -> None:
    scheduled_id, _starts_at, _ends_at = api.book_ok()
    expect_error(
        api.create_note(scheduled_id, "Too soon"),
        409,
        "CONSULTATION_NOT_COMPLETED",
        "A note can only be written on a completed consultation.",
    )

    cancelled_id, _starts_at, _ends_at = api.book_ok(start_in_hours=48)
    expect_ok(api.cancel(cancelled_id))
    expect_error(
        api.create_note(cancelled_id, "Too late"),
        409,
        "CONSULTATION_NOT_COMPLETED",
        "A note can only be written on a completed consultation.",
    )


def test_a_practitioner_creates_edits_and_deletes_a_draft(api: Api) -> None:
    consultation_id = api.schedule_and_complete()
    written_at = api.clock.now()
    created = expect_ok(api.create_note(consultation_id, "  Draft text  "))
    note = created["data"]

    assert created["message"] == "Note created."
    assert note["body"] == "Draft text"
    assert note["shared_at"] is None
    assert note["created_at"] == zulu(written_at)
    assert note["addenda"] == []
    assert "updated_at" not in note

    edited_at = written_at + timedelta(hours=1)
    api.clock.move_to(edited_at)
    edited = expect_ok(
        api.client.patch(
            f"/consultations/{consultation_id}/note",
            headers=api.asha,
            json={"body": " Revised "},
        )
    )["data"]
    assert edited["body"] == "Revised"
    assert edited["created_at"] == zulu(written_at)

    deleted = expect_ok(
        api.client.delete(f"/consultations/{consultation_id}/note", headers=api.asha)
    )
    assert deleted["message"] == "Note deleted."
    assert deleted["data"] is None

    detail = expect_ok(api.client.get(f"/consultations/{consultation_id}", headers=api.asha))
    assert detail["data"]["note"] is None
    replacement = expect_ok(api.create_note(consultation_id, "Fresh draft"))
    assert replacement["data"]["body"] == "Fresh draft"


def test_a_second_note_is_refused_until_the_draft_is_deleted(api: Api) -> None:
    consultation_id = api.schedule_and_complete()
    expect_ok(api.create_note(consultation_id, "First"))

    expect_error(
        api.create_note(consultation_id, "Second"),
        409,
        "NOTE_ALREADY_EXISTS",
        "This consultation already has a note.",
    )


def test_empty_note_and_addendum_text_is_refused(api: Api) -> None:
    consultation_id = api.schedule_and_complete()
    for body in ("", "   "):
        payload = expect_error(
            api.create_note(consultation_id, body),
            422,
            "VALIDATION_ERROR",
            INVALID,
        )
        assert field_message(payload, "body") == EMPTY

    expect_ok(api.create_note(consultation_id, "Draft"))
    for body in ("", "   "):
        payload = expect_error(
            api.client.patch(
                f"/consultations/{consultation_id}/note",
                headers=api.asha,
                json={"body": body},
            ),
            422,
            "VALIDATION_ERROR",
            INVALID,
        )
        assert field_message(payload, "body") == EMPTY


def test_a_client_cannot_see_or_change_a_draft(api: Api) -> None:
    consultation_id = api.schedule_and_complete()
    expect_error(
        api.create_note(consultation_id, "Mine", headers=api.priya),
        403,
        "PERMISSION_DENIED",
        "Only the practitioner can write a note.",
    )
    expect_ok(api.create_note(consultation_id, "Private"))
    expect_error(
        api.create_note(consultation_id, "Still mine", headers=api.priya),
        403,
        "PERMISSION_DENIED",
        "Only the practitioner can write a note.",
    )

    hidden = [
        api.client.get(f"/consultations/{consultation_id}/note", headers=api.priya),
        api.client.patch(
            f"/consultations/{consultation_id}/note",
            headers=api.priya,
            json={"body": "Changed"},
        ),
        api.client.delete(f"/consultations/{consultation_id}/note", headers=api.priya),
        api.client.post(f"/consultations/{consultation_id}/note/share", headers=api.priya),
        api.client.post(
            f"/consultations/{consultation_id}/note/addenda",
            headers=api.priya,
            json={"body": "Correction"},
        ),
    ]
    for response in hidden:
        expect_error(response, 404, "RESOURCE_NOT_FOUND", NOT_FOUND)

    assert (
        expect_ok(api.client.get(f"/consultations/{consultation_id}", headers=api.priya))["data"][
            "note"
        ]
        is None
    )


def test_sharing_locks_the_note_and_addenda_stay_visible(api: Api) -> None:
    consultation_id = api.schedule_and_complete()
    expect_ok(api.create_note(consultation_id, "Original"))
    expect_error(
        api.client.post(
            f"/consultations/{consultation_id}/note/addenda",
            headers=api.asha,
            json={"body": "Too early"},
        ),
        409,
        "NOTE_NOT_SHARED",
        "An addendum can only be added to a shared note.",
    )

    shared_at = api.clock.now() + timedelta(hours=2)
    api.clock.move_to(shared_at)
    shared = expect_ok(
        api.client.post(f"/consultations/{consultation_id}/note/share", headers=api.asha)
    )["data"]
    assert shared["shared_at"] == zulu(shared_at)
    assert shared["body"] == "Original"

    locked = "This note has already been shared and can no longer be changed."
    expect_error(
        api.client.patch(
            f"/consultations/{consultation_id}/note",
            headers=api.asha,
            json={"body": "Quiet edit"},
        ),
        409,
        "NOTE_ALREADY_SHARED",
        locked,
    )
    expect_error(
        api.client.delete(f"/consultations/{consultation_id}/note", headers=api.asha),
        409,
        "NOTE_ALREADY_SHARED",
        locked,
    )
    expect_error(
        api.client.post(f"/consultations/{consultation_id}/note/share", headers=api.asha),
        409,
        "NOTE_ALREADY_SHARED",
        locked,
    )
    still = expect_ok(api.client.get(f"/consultations/{consultation_id}/note", headers=api.asha))
    assert still["data"]["body"] == "Original"

    first_at = shared_at
    first = expect_ok(
        api.client.post(
            f"/consultations/{consultation_id}/note/addenda",
            headers=api.asha,
            json={"body": "  First correction  "},
        )
    )["data"]
    assert first["body"] == "First correction"
    assert first["created_at"] == zulu(first_at)
    assert "updated_at" not in first

    second_at = shared_at + timedelta(days=1)
    api.clock.move_to(second_at)
    expect_ok(
        api.client.post(
            f"/consultations/{consultation_id}/note/addenda",
            headers=api.asha,
            json={"body": "Second correction"},
        )
    )
    payload = expect_error(
        api.client.post(
            f"/consultations/{consultation_id}/note/addenda",
            headers=api.asha,
            json={"body": "   "},
        ),
        422,
        "VALIDATION_ERROR",
        INVALID,
    )
    assert field_message(payload, "body") == EMPTY

    visible = expect_ok(
        api.client.get(f"/consultations/{consultation_id}/note", headers=api.priya)
    )["data"]
    detail = expect_ok(api.client.get(f"/consultations/{consultation_id}", headers=api.priya))[
        "data"
    ]
    assert [item["body"] for item in visible["addenda"]] == [
        "First correction",
        "Second correction",
    ]
    assert visible["addenda"][0]["created_at"] == zulu(first_at)
    assert visible["addenda"][1]["created_at"] == zulu(second_at)
    assert detail["note"]["addenda"] == visible["addenda"]

    for response in (
        api.client.patch(
            f"/consultations/{consultation_id}/note",
            headers=api.priya,
            json={"body": "Changed"},
        ),
        api.client.delete(f"/consultations/{consultation_id}/note", headers=api.priya),
        api.client.post(f"/consultations/{consultation_id}/note/share", headers=api.priya),
        api.client.post(
            f"/consultations/{consultation_id}/note/addenda",
            headers=api.priya,
            json={"body": "My correction"},
        ),
    ):
        expect_error(response, 403, "PERMISSION_DENIED")
