"""Who may call the API, and what they are allowed to see.

A missing ticket is 401. The right consultation with the wrong role is 403.
A missing row, someone else's consultation, and a draft the client must not
see are all 404, with the same message.
"""

from tests.conftest import Api, expect_error, expect_ok, zulu

NOT_FOUND = "The requested resource was not found."
TICKET_REQUIRED = "A valid sign-in ticket is required."


def test_people_list_needs_no_ticket_and_hides_specialty(api: Api) -> None:
    response = api.client.get("/people", headers={"Authorization": "Bearer not-a-ticket"})
    payload = expect_ok(response)

    assert payload["message"] == "People listed."
    assert payload["meta"]["timestamp"] == zulu(api.clock.now())
    assert [person["name"] for person in payload["data"]] == [
        "Priya",
        "Rohan",
        "Dr. Asha Rao",
        "Dr. Vikram Shah",
    ]
    assert all(set(person) == {"id", "name", "role"} for person in payload["data"])
    assert [person["role"] for person in payload["data"]] == [
        "client",
        "client",
        "practitioner",
        "practitioner",
    ]


def test_login_issues_a_ticket_and_keeps_older_tickets_valid(api: Api) -> None:
    first = expect_ok(api.client.post("/auth/login", json={"person_id": api.priya_id}))
    second = expect_ok(api.client.post("/auth/login", json={"person_id": api.priya_id}))

    assert first["message"] == "Signed in."
    assert first["data"]["token"] != second["data"]["token"]
    assert set(first["data"]) == {"token"}
    for token in (first["data"]["token"], second["data"]["token"]):
        response = api.client.get("/consultations", headers={"Authorization": f"Bearer {token}"})
        expect_ok(response)


def test_unknown_person_id_is_invalid_input(api: Api) -> None:
    response = api.client.post("/auth/login", json={"person_id": 999})
    payload = expect_error(response, 422, "VALIDATION_ERROR", "The request contains invalid data.")

    assert payload["error"]["details"] == [
        {"field": "person_id", "message": "Choose a person from the list."}
    ]


def test_login_rejects_a_non_positive_person_id(api: Api) -> None:
    response = api.client.post("/auth/login", json={"person_id": 0})
    payload = expect_error(response, 422, "VALIDATION_ERROR")

    assert payload["error"]["details"][0]["field"] == "person_id"
    assert payload["error"]["details"][0]["message"] == "Input should be greater than 0"


def test_protected_routes_reject_a_missing_or_unknown_ticket(api: Api) -> None:
    consultation_id, _starts_at, _ends_at = api.book_ok()
    cases = [
        api.client.get("/consultations"),
        api.client.get("/consultations", headers={"Authorization": "Bearer    "}),
        api.client.get("/consultations", headers={"Authorization": "Basic abc"}),
        api.client.get("/consultations", headers={"Authorization": "Bearer nope"}),
        api.client.get("/practitioners"),
        api.client.get(f"/consultations/{consultation_id}/note"),
    ]
    for response in cases:
        payload = expect_error(response, 401, "AUTHENTICATION_REQUIRED", TICKET_REQUIRED)
        assert payload["error"]["details"] == []


def test_lowercase_bearer_scheme_is_accepted(api: Api) -> None:
    token = api.priya["Authorization"].removeprefix("Bearer ")
    response = api.client.get("/consultations", headers={"Authorization": f"bearer {token}"})
    expect_ok(response)


def test_only_a_client_can_list_practitioners(api: Api) -> None:
    listed = expect_ok(api.client.get("/practitioners", headers=api.priya))

    assert listed["message"] == "Practitioners listed."
    assert listed["data"] == [
        {"id": api.asha_id, "name": "Dr. Asha Rao", "specialty": "Cardiology"},
        {"id": api.vikram_id, "name": "Dr. Vikram Shah", "specialty": "Dermatology"},
    ]
    expect_error(
        api.client.get("/practitioners", headers=api.asha),
        403,
        "PERMISSION_DENIED",
        "Only a client can view practitioners.",
    )


def test_someone_elses_consultation_matches_a_missing_one(api: Api) -> None:
    consultation_id, _starts_at, _ends_at = api.book_ok()
    missing = api.client.get("/consultations/999999", headers=api.priya)
    foreign = api.client.get(f"/consultations/{consultation_id}", headers=api.rohan)
    missing_payload = expect_error(missing, 404, "RESOURCE_NOT_FOUND", NOT_FOUND)
    foreign_payload = expect_error(foreign, 404, "RESOURCE_NOT_FOUND", NOT_FOUND)

    assert missing_payload["message"] == foreign_payload["message"]
    assert api.client.get("/consultations", headers=api.rohan).json()["data"] == []
    own = expect_ok(api.client.get("/consultations", headers=api.priya))["data"]
    assert [item["id"] for item in own] == [consultation_id]
    assert "note" not in own[0]


def test_an_outsider_practitioner_is_not_told_the_consultation_exists(api: Api) -> None:
    consultation_id, _starts_at, _ends_at = api.book_ok()

    for response in (
        api.client.get(f"/consultations/{consultation_id}", headers=api.vikram),
        api.complete(consultation_id, headers=api.vikram),
        api.cancel(consultation_id, headers=api.vikram),
        api.create_note(consultation_id, "Hidden", headers=api.vikram),
    ):
        expect_error(response, 404, "RESOURCE_NOT_FOUND", NOT_FOUND)


def test_the_client_on_a_consultation_cannot_complete_it(api: Api) -> None:
    consultation_id, starts_at, _ends_at = api.book_ok()
    api.clock.move_to(starts_at)

    expect_error(
        api.complete(consultation_id, headers=api.priya),
        403,
        "PERMISSION_DENIED",
        "Only the practitioner can mark a consultation as completed.",
    )


def test_a_private_note_is_invisible_to_the_client(api: Api) -> None:
    consultation_id = api.schedule_and_complete()
    expect_ok(api.create_note(consultation_id, "Private draft"))

    expect_error(
        api.client.get(f"/consultations/{consultation_id}/note", headers=api.priya),
        404,
        "RESOURCE_NOT_FOUND",
        NOT_FOUND,
    )
    client_detail = expect_ok(
        api.client.get(f"/consultations/{consultation_id}", headers=api.priya)
    )["data"]
    practitioner_detail = expect_ok(
        api.client.get(f"/consultations/{consultation_id}", headers=api.asha)
    )["data"]

    assert client_detail["note"] is None
    assert practitioner_detail["note"]["body"] == "Private draft"
    assert "note" not in expect_ok(api.client.get("/consultations", headers=api.asha))["data"][0]
    expect_error(
        api.create_note(consultation_id, "I can write too", headers=api.priya),
        403,
        "PERMISSION_DENIED",
        "Only the practitioner can write a note.",
    )
