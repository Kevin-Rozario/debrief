# Debrief: Project Architecture & Development Rules

**Project Name:** Debrief
**Purpose:** Supershyft engineering take-home (consultation + practitioner notes app).
**Stack:** Python 3.14+ FastAPI backend, React + TypeScript + Vite frontend, SQLite database.

## 1. Core Business Logic & State Machines

### Consultations

- **Lifecycle States:** `scheduled` ➔ `completed` OR `cancelled`.
- **Rules:**
  - No "no-show", "approval", or "reschedule" states.
  - Record the ID of the person who cancelled.
  - **Cancellation:** Allowed even after the start time has passed (handles no-shows).
  - **Completion:** Practitioner only, and only once the start time has been reached. `Consultation.has_started` is `now >= starts_at`, so the exact start moment counts. Earlier than that is `409 CONSULTATION_NOT_STARTED`.
  - **Booking Validation:**
    - Refused if the end time is not strictly after the start time.
    - Refused if the `practitioner_id` does not belong to a valid practitioner.
    - Start/End times are always stored and processed in UTC.

### Conflict Prevention (Double-Booking)

- **Overlap Rule:** A booking is refused if the chosen practitioner already has an overlapping `scheduled` consultation. A booking that starts at the exact moment another ends does not overlap (`existing.starts_at < new_ends` and `existing.ends_at > new_starts`).
- Only the practitioner's calendar is checked (client calendar conflicts are ignored).
- `cancelled` or `completed` consultations do not block new bookings.
- **Database Constraint:** Requires a strict write lock (`BEGIN IMMEDIATE`) as the very first database action in `book_consultation` before checking availability.

### Practitioner Notes & Addenda

- **Creation:** A practitioner can only create one note per consultation, and only if the consultation is `completed`.
- **Draft State (Private):** Editable and deletable by the practitioner. Hidden from the client.
- **Shared State (Locked):** Once shared, the original note text is locked permanently and cannot be edited or deleted.
- **Addenda:** Corrections to shared notes happen via dated, append-only addenda.
  - Only allowed on shared notes.
  - Authored only by the original practitioner.
  - Instantly visible to the client (no separate share step).
  - Empty notes or empty addenda are strictly refused.

## 2. Authentication & Authorization

- **Minimal Sign-in:** The frontend lists 5 seeded people. Picking one requests a random token from the backend, saved in the database.
- All subsequent requests carry this token. No passwords.
- **Visibility Rules:**
  - `404 RESOURCE_NOT_FOUND` applies if a person tries to access a consultation belonging to someone else, or a note that has not yet been shared with the client.
  - Clear `403 PERMISSION_DENIED` when accessing things they are aware of but lack the role to modify.
  - Clients only see practitioner names when booking; practitioners get a display-only specialty label (no email/phone/bio/photo).

## 3. Tech Stack & Environment Setup

- **OS Agnostic:** `.gitattributes` enforces `* text=auto eol=lf` for cross-platform line endings.
- **Backend:** FastAPI, SQLModel (SQLAlchemy + Pydantic), SQLite (`backend/debrief.db`), `pytest` + `httpx2` for testing. Starlette's test client uses `httpx2`; the dev requirements list that package.
- **Frontend:** React, TypeScript, React Router, TanStack Query, Vite.
- **Infrastructure:** No Docker. Relies on `Makefile` shortcuts and standard `README.md` instructions.
- **Timekeeping:** All datetimes are UTC. `Clock.now()` is the live clock. Tests pass a `FrozenClock` and move it with `move_to`. Services take a `Clock` in their constructor; it is not a FastAPI dependency. Booking refuses `starts_at <= now` (the exact current moment is not in the future). Naive datetimes are rejected.

## 4. API Contract & Response Envelope

Every API response strictly follows this uniform envelope structure.

**Success Payload (2xx):**

```json
{
  "success": true,
  "message": "Consultation booked.",
  "data": { "id": 7, "status": "scheduled" },
  "error": null,
  "meta": { "request_id": "b1f0c2e4-...", "timestamp": "2026-10-01T09:30:00Z" }
}
```

**Error Payload (4xx/5xx):**

```json
{
  "success": false,
  "message": "This consultation has already been completed.",
  "data": null,
  "error": {
    "code": "CONSULTATION_NOT_SCHEDULED",
    "status": 409,
    "details": []
  },
  "meta": { "request_id": "b1f0c2e4-...", "timestamp": "2026-10-01T09:30:00Z" }
}
```

_Note: `request_id` must also be attached to the `X-Request-ID` response header. `error.details` is populated for validation errors, otherwise empty._

## 5. Error Code Catalog

| Situation                                          | HTTP | error.code                   |
| :------------------------------------------------- | :--- | :--------------------------- |
| Missing or unknown ticket                          | 401  | `AUTHENTICATION_REQUIRED`    |
| Right resource, wrong role                         | 403  | `PERMISSION_DENIED`          |
| Not yours, private note, or unknown route          | 404  | `RESOURCE_NOT_FOUND`         |
| Cancel/complete when not scheduled                 | 409  | `CONSULTATION_NOT_SCHEDULED` |
| Complete before the start time                     | 409  | `CONSULTATION_NOT_STARTED`   |
| Note on a consultation that isn't completed        | 409  | `CONSULTATION_NOT_COMPLETED` |
| Second note on the same consultation               | 409  | `NOTE_ALREADY_EXISTS`        |
| Edit, delete, or share a note already shared       | 409  | `NOTE_ALREADY_SHARED`        |
| Addendum on a note that isn't shared yet           | 409  | `NOTE_NOT_SHARED`            |
| Booking overlaps practitioner's schedule           | 409  | `SCHEDULING_CONFLICT`        |
| Bad input (past start, invalid practitioner, etc.) | 422  | `VALIDATION_ERROR`           |
| Anything unexpected                                | 500  | `INTERNAL_SERVER_ERROR`      |

## 6. Backend Directory Structure

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # create_app(): registers routers and error handlers
│   ├── database.py                # DatabaseManager: engine for debrief.db, session per request
│   ├── dependencies.py            # wiring: signed-in person, services
│   ├── clock.py                   # Clock: what "now" is (UTC), replaceable in tests
│   ├── exceptions.py              # domain errors and their HTTP mapping
│   ├── models.py                  # Person, AuthToken, Consultation, Note, Addendum + enums
│   ├── schemas.py                 # request and response shapes
│   ├── repositories.py            # PersonRepository, AuthTokenRepository, ConsultationRepository, NoteRepository
│   ├── services/
│   │   ├── __init__.py
│   │   ├── identity_service.py    # sign-in, ticket lookup, people and practitioner lists
│   │   ├── consultation_service.py # book, cancel, complete, access checks
│   │   └── note_service.py        # draft, edit, delete, share, addenda, client visibility
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── identity_router.py     # /people, /practitioners, /auth/login
│   │   ├── consultation_router.py
│   │   └── note_router.py
│   └── seed.py                    # SeedRunner: replaces debrief.db with the example data
├── tests/
│   ├── conftest.py                # temporary database, test client, sign-in helpers
│   ├── test_authentication_and_access.py
│   ├── test_booking.py
│   ├── test_consultation_lifecycle.py
│   ├── test_notes.py
│   └── test_seed.py
├── pytest.ini
├── requirements.txt
└── requirements-dev.txt
```

## 7. Deliverable Targets

- **One Non-Obvious Decision (README):** Highlight the note-locking mechanism. Explain that sharing a note locks it permanently and forces corrections through dated addenda, establishing guaranteed trust so clients know health records won't quietly change beneath them.
- **Seed Data Integrity:** Ensure 2 practitioners, 3 clients, and a variety of states: past scheduled, future scheduled, completed (draft note), completed (shared note + addendum), cancelled, a deliberate double-booking attempt, and a "not-yours" cross-client consultation for validation.

## 8. Implementation Status

Rules live in the services. Repositories only read and write rows. Schemas are the JSON contract and are not the tables. Routers call one service method and wrap the result with `respond()`. The API is reachable over HTTP.

**Done**

- **Root scaffolding:** `.gitattributes`, `.gitignore`, `Makefile`. `make setup` installs the backend dependencies. `make seed` loads the example data. `make api` serves the API at `http://127.0.0.1:4000`. `make test` runs pytest. `make web` still reports that the screen is not built. `.gitignore` keeps `PRD.md` local. `CLAUDE.md` is in the repository.
- **`backend/app/exceptions.py`:** The error-code catalog. Services raise these. `main.py` translates them into the envelope.
- **`backend/app/models.py`:** `Person`, `AuthToken`, `Consultation`, `Note`, `Addendum`. Integer ids, `UtcDateTime` columns, no ORM `Relationship` attributes. `Consultation.has_participant` and `Consultation.has_started` are the only rule helpers on the tables.
- **`backend/app/database.py`:** `DatabaseManager` and `begin_write_transaction()` (`BEGIN IMMEDIATE`). Sessions use `expire_on_commit=False`.
- **`backend/app/schemas.py`:** Generic `UniformResponse[T]` (one envelope for success and failure). Request and response models for identity, consultations, notes, and addenda. Response models list only public fields, including `ServiceInfo` and `HealthStatus`. `from_attributes` copies declared fields only.
- **`backend/app/clock.py`:** `Clock` and `FrozenClock`.
- **`backend/app/dependencies.py`:** `set_database(app, database)`, `SessionDep`, and `CurrentPerson`. Reads `Authorization: Bearer <ticket>` and loads the person through the repositories. A missing, blank, non-bearer, or unknown ticket raises `AuthenticationRequiredError`. The OpenAPI bearer scheme is named `Ticket`. Each request builds `IdentityService(session)`, `ConsultationService(session, clock)`, and `NoteService(session, clock)` from the clock stored on the app. This module does **not** check client versus practitioner.
- **`backend/app/repositories.py`:** `PersonRepository`, `AuthTokenRepository`, `ConsultationRepository`, `NoteRepository`. Addenda are stored on `NoteRepository` (there is no fifth repository). `add` and `delete` flush and do **not** commit. The service owns the transaction.
- **`backend/app/services/identity_service.py`:** `list_people()`, `login(person_id)`, `list_practitioners(caller)`. People list and login do not take a caller. An unknown person id on login is `422`, not `404`. Each login inserts a new ticket; older tickets stay valid. Only a client may list practitioners.
- **`backend/app/services/consultation_service.py`:** `book`, `list_consultations`, `get`, `cancel`, `complete`. `get` returns `ConsultationDetailResponse` and embeds a note only when that caller may read it.
- **`backend/app/services/note_service.py`:** `get`, `create`, `update`, `delete`, `share`, `add_addendum`. `delete` returns `None` (the HTTP success body has `data: null`). `visible_note` is what consultation detail uses so a hidden draft and a missing note are both `note: null`. Addenda are loaded only after the note is shared. A second insert is `409 NOTE_ALREADY_EXISTS` only when SQLite reports the unique `note.consultation_id` constraint; any other integrity error stays a 500.
- **`backend/app/main.py`:** `create_app(database=None, clock=None)` builds one `DatabaseManager`, calls `set_database`, stores one `Clock` on the app, and creates tables. It maps `DomainError` onto the envelope, request validation onto `422 VALIDATION_ERROR` with `error.details` as `{field, message}`, an unknown route onto `404 RESOURCE_NOT_FOUND`, and anything else onto `500 INTERNAL_SERVER_ERROR`. `meta.request_id` is also the `X-Request-ID` header. `meta.timestamp` comes from the app clock and is UTC with a trailing `Z`. `respond()` wraps a successful service result. Tests pass their own database and a `FrozenClock`. The running app is `app = create_app()`. `GET /` returns the API name and version, and `GET /health` returns `{"status": "ok"}`. Neither route needs a ticket. OpenAPI (`/docs`, `/openapi.json`) describes that envelope, tags the routes System, Identity, Consultations, and Notes, and documents the bearer scheme as `Ticket`. Success and error bodies in that document are `UniformResponse`, including `422`.
- **Routers:** `identity_router.py`, `consultation_router.py`, `note_router.py` are registered from `create_app`. They do not repeat business rules.

| Route                                   | Auth            | Service                                  |
| :-------------------------------------- | :-------------- | :--------------------------------------- |
| `GET /`                                 | none            | `root` in `main.py`                      |
| `GET /health`                           | none            | `health` in `main.py`                    |
| `GET /people`                           | none            | `IdentityService.list_people`            |
| `POST /auth/login`                      | none            | `IdentityService.login`                  |
| `GET /practitioners`                    | `CurrentPerson` | `IdentityService.list_practitioners`     |
| `POST /consultations`                   | `CurrentPerson` | `ConsultationService.book`               |
| `GET /consultations`                    | `CurrentPerson` | `ConsultationService.list_consultations` |
| `GET /consultations/{id}`               | `CurrentPerson` | `ConsultationService.get`                |
| `POST /consultations/{id}/cancel`       | `CurrentPerson` | `ConsultationService.cancel`             |
| `POST /consultations/{id}/complete`     | `CurrentPerson` | `ConsultationService.complete`           |
| `GET /consultations/{id}/note`          | `CurrentPerson` | `NoteService.get`                        |
| `POST /consultations/{id}/note`         | `CurrentPerson` | `NoteService.create`                     |
| `PATCH /consultations/{id}/note`        | `CurrentPerson` | `NoteService.update`                     |
| `DELETE /consultations/{id}/note`       | `CurrentPerson` | `NoteService.delete` (`data: null`)      |
| `POST /consultations/{id}/note/share`   | `CurrentPerson` | `NoteService.share`                      |
| `POST /consultations/{id}/note/addenda` | `CurrentPerson` | `NoteService.add_addendum`               |

- **Tests:** `backend/tests/` calls the API through FastAPI's test client. `conftest.py` gives every test a new SQLite file and a `FrozenClock` pinned at `2026-10-01T09:00:00Z`. People are inserted directly, because the API cannot create a person. `test_authentication_and_access.py`, `test_booking.py`, `test_consultation_lifecycle.py`, and `test_notes.py` cover the rules in section 9, including a simultaneous double-book. They also cover every protected route without a ticket, an unknown route, an unsupported method, offset times stored as UTC, a window that covers or sits inside an existing booking, a missing note, and the absence of any edit or delete for an addendum. `test_seed.py` checks the example data through the same API, including completing the past scheduled consultation and cancelling the future one. From `backend/`, run `.venv/bin/python -m pytest`. The last run was 48 passed. `backend/pytest.ini` sets `testpaths = tests`. Dev requirements are `pytest` and `httpx2`.
- **`backend/app/seed.py`:** `SeedRunner` creates the tables and replaces the rows in `backend/debrief.db`. From `backend/`, run `python -m app.seed`. Past consultations are inserted directly, because booking refuses a start that is not in the future. Times are the clock's current hour plus a fixed offset, and each consultation lasts one hour. Running the seed again replaces the rows. It does not issue tickets.
  - **People:** Priya, Rohan, Meera (clients). Dr. Asha Rao, specialty "Continuity care". Dr. Vikram Shah, specialty "Recovery planning". Meera has no consultation.
  - **Priya and Dr. Asha Rao, one day ago:** still `scheduled`, so it can be completed.
  - **Priya and Dr. Asha Rao, seven days ahead:** `scheduled`, so completion is refused and cancel still works.
  - **Priya and Dr. Asha Rao, five days ago:** `completed`, with a private draft Priya cannot see.
  - **Rohan and Dr. Asha Rao, ten days ago:** `completed`, with a shared note and one addendum.
  - **Priya and Dr. Vikram Shah, three days ahead:** `cancelled`, and `cancelled_by_id` is Priya.
  - **Rohan and Dr. Vikram Shah, two days ahead:** Priya is not a participant. The hour is still `scheduled`, so a new booking with Dr. Vikram Shah in that hour overlaps.

The app factory, services, routers, rule tests, example seed, and Makefile targets are committed. The latest GitHub commit on `main` is `6ba10c5`.

**Not started**

- **Frontend:** No `frontend/` app yet. `make web` exits with that message.
- **README:** The locked-note decision and the other must-records are not written.

## 9. Rules the services already enforce

Do not re-decide these in the routers. The router calls the service and wraps the return value.

- **404 before 403.** `require_participant` runs first. A missing row and someone else's row raise `ResourceNotFoundError` with the **same default message**. Do not specialize that message.
- **Booking.** A practitioner caller is `403`. A missing id and a person who is not a practitioner are the same `422` (`practitioner_id`: "Choose a practitioner."). Past start, end not strictly after start, and naive datetimes are `422`. `begin_write_transaction` is the first database call inside `book`, after those in-memory checks. Then the practitioner is loaded and the overlap query runs. The client calendar is not checked.
- **Cancel.** Either participant, only while `scheduled`, including after the start. Sets `cancelled_by_id` to the caller. A completed or already-cancelled row is `409 CONSULTATION_NOT_SCHEDULED`.
- **Complete.** Participant check, then role. The client on that consultation is `403`. Another practitioner who is not on it is `404`. Then status (`409 CONSULTATION_NOT_SCHEDULED`), then `has_started` (`409 CONSULTATION_NOT_STARTED`).
- **Notes.** Only that consultation's practitioner, and only when status is `completed`. A second note is `409 NOTE_ALREADY_EXISTS` (the unique column is the backstop). Empty or whitespace-only text is `422` and the stored value is stripped.
- **Private notes stay invisible.** A client who reads, edits, deletes, shares, or adds an addendum while the note is missing or still a draft gets `404`, same as not-found. A client who **creates** a note on their own consultation gets `403` (that does not reveal a draft). Once the note is shared, the client can read it, and a client trying to change it gets `403`. Edit, delete, or share of an already shared note by the practitioner is `409 NOTE_ALREADY_SHARED`. An addendum on a draft is `409 NOTE_NOT_SHARED`.
- **Consultation detail.** `note` is null both when there is no note and when the caller is the client and the note is still a draft. The list endpoint never includes a note.
- **Dates on writes.** Share sets `shared_at` from `Clock.now()`. New notes and addenda take `created_at` from the clock. `updated_at` on later edits is the column's `onupdate` and is not part of any response.

Service methods return schema objects, not rows and not `UniformResponse`. They raise `DomainError`. They commit successful writes themselves.

## 10. Next step

**Immediate:** Build the screen. Sign-in picker, then the consultation list, then a detail view (status, note, addenda, and only the actions that person may take), plus a booking form for clients. TanStack Query refreshes lists after every action. Hide buttons for disallowed actions. The API remains the guard.

**After the screen:** the README, including the locked-note decision, and a `make web` target that starts it. `make setup`, `make seed`, `make api`, and `make test` already run the backend.
