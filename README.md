# Debrief

A client books a consultation with a practitioner. After the visit, the practitioner may write a note. The client can read that note only after the practitioner shares it. Sharing locks the original text. A later correction is a dated addendum, so a record the client has already read stays as they read it.

The API enforces every rule in this document. The app hides actions the signed-in person may not take, and the same refusals hold if you call the routes directly. Open the app at <http://127.0.0.1:5173>. Interactive API docs are at <http://127.0.0.1:4000/docs>.

FastAPI, SQLModel, and SQLite on the API. React, TypeScript, and Vite on the app. No Docker.

## Run it

Python **3.14+** and Git. The app also needs Node **20.19+** (or **22.12+**) and pnpm.

From the repository root, use two terminals:

```bash
make setup
make seed
make api
```

```bash
make web
```

| Target     | What it does                                                                 |
| :--------- | :--------------------------------------------------------------------------- |
| `make setup` | Creates `backend/.venv`, installs the Python packages, and runs `pnpm install` in `frontend/` |
| `make seed`  | Replaces `backend/debrief.db` with the example people and visits             |
| `make api`   | Serves the API at <http://127.0.0.1:4000>                                    |
| `make web`   | Serves the app at <http://127.0.0.1:5173>                                    |
| `make test`  | Runs the suite                                                               |

Open <http://127.0.0.1:5173> and pick a person. There is no password.

`make seed` replaces the database and does not issue tickets. Sign in again after a re-seed.

### Without Make

macOS and Linux:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
cd backend
.venv/bin/python -m app.seed
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 4000 --reload
```

Windows (PowerShell). Make uses `python` and `backend\.venv\Scripts\python.exe` on Windows.

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r backend\requirements-dev.txt
cd backend
.venv\Scripts\python.exe -m app.seed
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 4000 --reload
```

The app, from `frontend/`:

```bash
pnpm install
pnpm dev
```

Tests, from `backend/`: `.venv/bin/python -m pytest` on macOS and Linux, or `.venv\Scripts\python.exe -m pytest` on Windows.

## Walk through the example

Sign-in lists these five people, in this order. A practitioner's specialty is a display label.

| Name            | Role         | Specialty         |
| :-------------- | :----------- | :---------------- |
| Priya           | client       |                   |
| Rohan           | client       |                   |
| Meera           | client       |                   |
| Dr. Asha Rao    | practitioner | Continuity care   |
| Dr. Vikram Shah | practitioner | Recovery planning |

Meera has no consultations. Everyone else is placed so each rule has a row you can open. Times are the hour you run the seed, shifted by a fixed offset, and each consultation lasts one hour. The app shows that hour in your local zone, with the UTC range on the next line. Seeded at 09:00 UTC and viewed in India (UTC+5:30), a row reads 2:30–3:30 pm and 09:00–10:00 UTC.

| Who                    | When              | Status    | What to notice                                                                 |
| :--------------------- | :---------------- | :-------- | :----------------------------------------------------------------------------- |
| Priya, Dr. Asha Rao    | 5 days ago        | completed | Private draft. Priya's page ends after the time.                              |
| Priya, Dr. Asha Rao    | 1 day ago         | scheduled | The start has passed, so Dr. Asha Rao can mark it completed.                   |
| Priya, Dr. Vikram Shah | 3 days ahead      | cancelled | Cancelled by Priya. The slot does not block a new booking.                     |
| Priya, Dr. Asha Rao    | 7 days ahead      | scheduled | Cancel still works. Completion is refused until the start.                     |
| Rohan, Dr. Asha Rao    | 10 days ago       | completed | Shared note and one addendum. Rohan can read both.                             |
| Rohan, Dr. Vikram Shah | 2 days ahead      | scheduled | Priya is not on it. Booking Dr. Vikram Shah in that hour overlaps.             |

Lists are earliest start first. A row names the other person and never shows note text.

1. **Priya.** Four visits. The completed one with Dr. Asha Rao has a private draft on the server, and her page does not mention it. The visit one day ago and the visit seven days ahead can be cancelled. The cancelled visit names her and shows Recovery planning.
2. **Dr. Asha Rao.** The same visits from the other side, plus Rohan's completed visit. There is no Book control. Rohan's visit with Dr. Vikram Shah is absent from her list. Rohan's note is a locked paragraph, dated when it was shared, with the addendum under its date and a field for another. Priya's draft can still be saved, deleted, or shared. Share is the only action that asks first. After that, the original is locked. The visit from one day ago offers Mark completed. The visit seven days ahead explains that completion waits until the start time.
3. **Rohan.** The shared note is read only, with Continuity care under Dr. Asha Rao's name. His visit with Dr. Vikram Shah can be cancelled and shows Recovery planning.
4. **Meera.** "You have no consultations." The second line, "Book one with a practitioner.", opens the booking form. A practitioner with an empty list would see only the first sentence.
5. **Overlap.** As Priya, book Dr. Vikram Shah across the hour Rohan already holds. The API answers `409` `SCHEDULING_CONFLICT`, and the form keeps the chosen times. A window that starts at the exact moment that visit ends is accepted. Booking the cancelled hour with Dr. Vikram Shah is also accepted.
6. **Someone else's visit.** Open a consultation id that is not yours, or an id that does not exist. The page says "The requested resource was not found." The API returns `404` with that same message in both cases.

Past consultations are inserted by `backend/app/seed.py`. Booking refuses a start that is not strictly in the future, and the visit from one day ago has to exist so it can still be completed.

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

A private draft is invisible to the client. Reading it, and reading the consultation, use the same not-found result as a missing note. Consultation detail returns `note: null` both when there is no note and when the caller is the client and the note is still a draft. The list never includes a note.

## Consultations

A consultation is booked as `scheduled`. It then becomes `completed` or `cancelled`. Both of those are final. The row does not change again, and a cancelled consultation accepts no note.

- **Book.** Clients only. The chosen person must be a practitioner. A missing id and a person who is not a practitioner are the same validation error. The start must be strictly in the future, and the end must be strictly after the start. Naive datetimes are refused.
- **Cancel.** Either participant, only while `scheduled`, including after the start time. That is how a client who never arrived is recorded. The consultation stores who cancelled.
- **Complete.** The practitioner on that consultation, only while `scheduled`, and only once `now >= starts_at`. The exact start moment counts. Earlier than that is refused.

**Times are UTC.** Stored values are timezone-aware UTC. The API clock is UTC. Tests freeze that clock at `2026-10-01T09:00:00Z`.

**Only the practitioner's calendar is checked.** A booking is refused when that practitioner already has a `scheduled` consultation that overlaps the new window (`existing.starts_at < new_ends` and `existing.ends_at > new_starts`). A visit that starts at the exact moment another ends does not overlap. `cancelled` and `completed` visits do not block the slot. The client's other appointments are ignored.

The overlap check and the insert are one write. `book` takes `BEGIN IMMEDIATE` before it reads availability, so two simultaneous bookings for the same practitioner cannot both succeed.

## Notes

One note per consultation, written by that consultation's practitioner, and only after the consultation is `completed`. Empty or whitespace-only text is refused. Stored text is stripped.

1. The note starts as a private draft. The practitioner may edit or delete it. Deleting frees the consultation for a new note.
2. Share makes it readable by that consultation's client. Sharing cannot be undone, and the original text is locked.
3. After sharing, the practitioner may add addenda. Each addendum is dated, append-only, and visible to the client immediately. An addendum cannot be edited or deleted, and one cannot be added before the note is shared.

### A shared note stays locked

Sharing locks the original text. A correction is a new dated addendum.

The simpler rule would let the practitioner edit a note at any time. That fails the moment a client has already read it: the sentence they relied on can disappear, and they have no record of the change. Locking the original keeps that sentence. A dated addendum still lets the practitioner correct a mistake, in the open, under the text the client already saw. Addenda stay append-only so the correction cannot grow into a second editable document.

The share dialog in the app says the same thing before the lock is applied.

## Sign-in

There are no passwords. `GET /people` returns id, name, and role. `POST /auth/login` with a person id stores a new random ticket and returns it. Older tickets stay valid. Later requests send `Authorization: Bearer <ticket>`.

This is not real security. Anyone who can call login can become any seeded person. A real deployment would replace `POST /auth/login` with a password check or an identity provider, and would keep the bearer check in `backend/app/dependencies.py`. The consultation and note rules do not depend on how the ticket was issued.

The app stores the ticket as `debrief.ticket` and the chosen person as `debrief.person`. A missing or unknown ticket clears both and returns to the picker.

## Scope

In this repository: two roles, the consultation lifecycle, notes with sharing and addenda, the ticket sign-in above, seed data, tests, and the app.

Left out on purpose: passwords, one-time codes, payments, email, and file upload. Also left out: rescheduling, an approval step, a no-show state, checking the client's calendar, un-sharing a note, and editing or deleting an addendum.

The app is four views.

| Route                | Who              | View                         |
| :------------------- | :--------------- | :--------------------------- |
| `/`                  | No ticket        | Sign-in picker               |
| `/consultations`     | Signed-in person | Their consultations          |
| `/consultations/:id` | A participant    | Status, actions, and the note |
| `/book`              | Client only      | Booking form                 |

A stored ticket skips `/` and opens the list. A practitioner who opens `/book` returns to the list. After a successful booking, the new visit opens.

## API

Every response uses one envelope. `meta.request_id` is also the `X-Request-ID` header. `meta.timestamp` is UTC with a trailing `Z`. `error.details` lists `{field, message}` for validation errors and is otherwise empty.

```json
{
  "success": true,
  "message": "Consultation booked.",
  "data": { "id": 7, "status": "scheduled" },
  "error": null,
  "meta": { "request_id": "b1f0c2e4-...", "timestamp": "2026-10-01T09:30:00Z" }
}
```

`GET /` and `GET /health` need no ticket. `GET /people` and `POST /auth/login` need no ticket. Every other route does.

| Request                                 | Who          | Result                                      |
| :-------------------------------------- | :----------- | :------------------------------------------ |
| `GET /people`                           | anyone       | id, name, and role, for the picker          |
| `POST /auth/login`                      | anyone       | body is a person id; returns a ticket       |
| `GET /practitioners`                    | client       | name and specialty                          |
| `POST /consultations`                   | client       | practitioner, start, and end                |
| `GET /consultations`                    | either       | the caller's own consultations              |
| `GET /consultations/{id}`               | participant  | the client sees `note` only after sharing   |
| `POST /consultations/{id}/cancel`       | participant  | records who cancelled                       |
| `POST /consultations/{id}/complete`     | practitioner | once the start time has been reached        |
| `GET /consultations/{id}/note`          | participant  | the client receives it only after sharing   |
| `POST /consultations/{id}/note`         | practitioner | creates the private draft                   |
| `PATCH /consultations/{id}/note`        | practitioner | draft only                                  |
| `DELETE /consultations/{id}/note`       | practitioner | draft only; success has `data: null`        |
| `POST /consultations/{id}/note/share`   | practitioner | locks the original                          |
| `POST /consultations/{id}/note/addenda` | practitioner | shared note only                            |

Response shapes are separate from the tables. A field that is private on the row is absent from the JSON, so it cannot leak by being selected.

Someone else's consultation and a note the client is not allowed to see are both **404**, with the same message. **403** is a resource the caller may know about but may not change, such as a client writing a note or completing a visit. **409** is the wrong state or the wrong moment. **422** is bad input.

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

## Where the rules live

```text
backend/app/services/     book, cancel, complete, notes, and access checks
backend/app/routers/      one service call, then the envelope
backend/app/repositories/ read and write rows
backend/app/models.py     Person, ticket, consultation, note, addendum
backend/app/schemas.py    request and response shapes
backend/app/seed.py       the example rows
backend/tests/            the rules, through the HTTP client
frontend/src/pages/       sign-in, list, visit, booking
```

Routers do not repeat the rules. A missing consultation and someone else's consultation raise the same not-found error, with the same message.

## Tests

`make test` gives each test a fresh SQLite file and a clock frozen at `2026-10-01T09:00:00Z`. People are inserted in the test setup, because the API cannot create a person.

The 48 tests cover each refusal in the table above, the happy path for each route, a simultaneous double-book, empty text, a private draft that must not appear for the client, and the example seed, including completing the past scheduled visit and cancelling the future one.
