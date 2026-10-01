# Debrief

A client books a consultation with a practitioner. After the session, the practitioner may write a note. The client can read that note only after the practitioner shares it.

The API enforces every rule below. The screen is not built yet, so there is nothing in front of the API that could hide a mistake.

## Status

| Piece                                             | State                                            |
| :------------------------------------------------ | :----------------------------------------------- |
| API (sign-in, booking, lifecycle, notes, addenda) | Done                                             |
| Example data (`make seed`)                        | Done                                             |
| Rule tests (48)                                   | Done                                             |
| Screen (`frontend/`)                              | Not started. `make web` exits with that message. |

Python **3.14+** and Git are enough to run the API and the tests. Node is not required until the screen exists.

## Quick start

From the repository root.

### macOS / Linux

```bash
make setup
make seed
make api
```

The API listens at <http://127.0.0.1:4000>. Interactive docs are at <http://127.0.0.1:4000/docs>.

The same steps without Make:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
cd backend
.venv/bin/python -m app.seed
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 4000 --reload
```

### Windows (PowerShell)

`make setup`, `make seed`, and `make api` are the same. Make uses `python` and `backend\.venv\Scripts\python.exe` on Windows.

Without Make:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r backend\requirements-dev.txt
cd backend
.venv\Scripts\python.exe -m app.seed
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 4000 --reload
```

`make test` runs the suite. From `backend/`, the plain command is `.venv/bin/python -m pytest` (or `.venv\Scripts\python.exe -m pytest` on Windows).

Run `make seed` again any time you want the example rows back. It replaces the database. It does not issue tickets, so sign in again after a re-seed.

## Example people

Sign-in lists these five people. Specialties are display labels for practitioners.

| Name            | Role         | Specialty         |
| :-------------- | :----------- | :---------------- |
| Priya           | client       |                   |
| Rohan           | client       |                   |
| Meera           | client       |                   |
| Dr. Asha Rao    | practitioner | Continuity care   |
| Dr. Vikram Shah | practitioner | Recovery planning |

Meera has no consultations. The others cover the states the rules care about. Times are the clock's current hour, shifted by a fixed offset. Each consultation lasts one hour.

| Who                    | When (from the hour you seed) | Status    | What it shows                                                                       |
| :--------------------- | :---------------------------- | :-------- | :---------------------------------------------------------------------------------- |
| Priya, Dr. Asha Rao    | 1 day ago                     | scheduled | Can be completed. Booking would refuse this start, so the seed inserts it directly. |
| Priya, Dr. Asha Rao    | 7 days ahead                  | scheduled | Completion is refused. Cancel still works.                                          |
| Priya, Dr. Asha Rao    | 5 days ago                    | completed | Private draft. Priya cannot see it.                                                 |
| Rohan, Dr. Asha Rao    | 10 days ago                   | completed | Shared note plus one addendum. Rohan can read both.                                 |
| Priya, Dr. Vikram Shah | 3 days ahead                  | cancelled | `cancelled_by` is Priya. The slot does not block a new booking.                     |
| Rohan, Dr. Vikram Shah | 2 days ahead                  | scheduled | Priya is not on it. Booking Dr. Vikram Shah in that hour overlaps.                  |

Past sessions are inserted by `backend/app/seed.py`, not by `POST /consultations`. Booking refuses a start that is not strictly in the future, and the past scheduled visit has to exist so it can still be completed.

## Sign-in

There are no passwords. `GET /people` returns id, name, and role. `POST /auth/login` with a person id stores a new random ticket and returns it. Older tickets stay valid. Later requests send `Authorization: Bearer <ticket>`.

This is not real security. Anyone who can call login can become any seeded person. A real deployment would replace `POST /auth/login` with a password check or an identity provider, and would keep the same bearer check in `backend/app/dependencies.py`. The consultation and note rules do not depend on how the ticket was issued.

## Scope

In this repository: two roles, the consultation lifecycle, notes with sharing and addenda, the ticket sign-in above, seed data, and tests.

Left out on purpose: passwords, one-time codes, payments, email, file upload, and a polished screen. Also left out: rescheduling, an approval step, a no-show state, checking the client's calendar, un-sharing a note, and editing or deleting an addendum.

## Who can do what

"Own" means the person is the client or the practitioner on that consultation.

| Action                                  | Client           | Practitioner                              |
| :-------------------------------------- | :--------------- | :---------------------------------------- |
| List practitioners (name and specialty) | Yes              | No                                        |
| Book                                    | Yes              | No                                        |
| See a consultation                      | Own only         | Own only                                  |
| Cancel while scheduled                  | Own              | Own                                       |
| Mark completed                          | No               | Own, once the start time has been reached |
| Create, edit, or delete a draft note    | No               | Own, on a completed consultation          |
| Share a note                            | No               | Own                                       |
| Add an addendum                         | No               | Own, and only after the note is shared    |
| Read the note and its addenda           | Own, shared only | Own, including the draft                  |

A private draft is invisible to the client. Reading it, and consultation detail, both return the same not-found result as a missing note. The list of consultations never includes a note.

## Consultations

A consultation is booked as `scheduled`. It then becomes `completed` or `cancelled`. Both of those are final: the row does not change again, and a cancelled consultation accepts no note.

- **Book.** Clients only. The chosen person must be a practitioner. The start must be strictly in the future, and the end must be strictly after the start. Naive datetimes are refused. A missing id and a person who is not a practitioner are the same validation error.
- **Cancel.** Either participant, only while `scheduled`, including after the start time. That is how a client who never arrived is recorded. The consultation stores who cancelled.
- **Complete.** The practitioner on that consultation, only while `scheduled`, and only once `now >= starts_at`. The exact start moment counts. Earlier than that is refused.

**Times are UTC.** Stored values are timezone-aware UTC. The API clock is UTC. Tests freeze that clock.

**Only the practitioner's calendar is checked.** A booking is refused when that practitioner already has a `scheduled` consultation that overlaps the new window (`existing.starts_at < new_ends` and `existing.ends_at > new_starts`). A visit that starts at the exact moment another ends does not overlap. `cancelled` and `completed` visits do not block the slot. The client's other appointments are ignored.

The overlap check and the insert are one write. `book` takes `BEGIN IMMEDIATE` before it reads availability, so two simultaneous bookings for the same practitioner cannot both succeed.

## Notes

One note per consultation, written by that consultation's practitioner, and only after the consultation is `completed`. Empty or whitespace-only text is refused. Stored text is stripped.

1. The note starts as a private draft. The practitioner may edit or delete it. Deleting frees the consultation for a new note.
2. Share makes it readable by that consultation's client. Sharing cannot be undone, and the original text is locked: no edit, no delete.
3. After sharing, the practitioner may add addenda. Each addendum is dated, append-only, and visible to the client immediately. An addendum cannot be edited or deleted, and one cannot be added before the note is shared.

### Decision: a shared note stays locked

Sharing locks the original text. A correction is a new dated addendum, not a silent edit.

A client who has already read the note needs to know that text will still be there later. An edit after sharing would replace what they read. A lock with a visible, dated addendum keeps the original and still lets the practitioner correct a mistake. Addenda stay append-only so that correction cannot grow into a second editable document.

## Errors

Someone else's consultation and a note the client is not allowed to see are both **404**, with the same message. The client learns nothing about a draft. **403** is for a resource the caller may know about but may not change (a client writing a note, a client completing a visit). **409** is the wrong state or the wrong moment. **422** is bad input.

| Situation                                                | HTTP | `error.code`                 |
| :------------------------------------------------------- | :--- | :--------------------------- |
| Missing or unknown ticket                                | 401  | `AUTHENTICATION_REQUIRED`    |
| Right resource, wrong role                               | 403  | `PERMISSION_DENIED`          |
| Not yours, private note, or unknown route                | 404  | `RESOURCE_NOT_FOUND`         |
| Cancel or complete when not scheduled                    | 409  | `CONSULTATION_NOT_SCHEDULED` |
| Complete before the start time                           | 409  | `CONSULTATION_NOT_STARTED`   |
| Note on a consultation that is not completed             | 409  | `CONSULTATION_NOT_COMPLETED` |
| Second note on the same consultation                     | 409  | `NOTE_ALREADY_EXISTS`        |
| Edit, delete, or share a note already shared             | 409  | `NOTE_ALREADY_SHARED`        |
| Addendum on a note that is not shared                    | 409  | `NOTE_NOT_SHARED`            |
| Booking overlaps the practitioner's schedule             | 409  | `SCHEDULING_CONFLICT`        |
| Bad input (past start, invalid practitioner, empty text) | 422  | `VALIDATION_ERROR`           |
| Anything unexpected                                      | 500  | `INTERNAL_SERVER_ERROR`      |

Every response uses one envelope. `meta.request_id` is also the `X-Request-ID` header. `error.details` is filled for validation errors and is otherwise empty.

```json
{
  "success": true,
  "message": "Consultation booked.",
  "data": { "id": 7, "status": "scheduled" },
  "error": null,
  "meta": { "request_id": "b1f0c2e4-...", "timestamp": "2026-10-01T09:30:00Z" }
}
```

`GET /` and `GET /health` need no ticket. Every other route does, except `GET /people` and `POST /auth/login`.

## Tests

`make test` uses a fresh SQLite file per test and a clock frozen at `2026-10-01T09:00:00Z`. People are inserted in the test setup, because the API cannot create a person. The 48 tests cover each refusal in the table above, the happy path for each route, a simultaneous double-book, and the example seed (including completing the past scheduled visit and cancelling the future one).
