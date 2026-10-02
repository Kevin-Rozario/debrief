# Debrief — frontend design brief

Build the Debrief screen from this document. It is the visual spec. Use the example copy below so the screens look like the real product.

Debrief is a consultation record. A client books a practitioner. After the visit, the practitioner may write a note. The client can read that note only after the practitioner shares it. Sharing locks the original text. A correction is a dated addendum.

Design four views and every state in this brief. Do not add dashboards, calendars, avatars, photos, search, filters, payments, messaging, or extra roles.

## Stack

- React, TypeScript, Vite
- React Router
- TanStack Query for server state
- shadcn/ui components: button, card, input, label, textarea, select, badge, dialog, alert, separator
- Tailwind CSS
- One Google font for every line of text: **Schibsted Grotesk**
- Colour is Tailwind's **stone** scale (warm gray / taupe), which is already oklch. Destructive actions use red. No second accent hue.

## Visual language

The page is a narrow column, about 40rem, centered. It should feel like a book page, not an admin dashboard.

- Names and the note body are the largest type.
- Rows are separated by hairlines.
- Status is a word in a stone badge: Scheduled darker, Completed mid, Cancelled muted.
- No avatars, no decorative icons, no toasts, no full-page spinner.
- Hover and press move a control by a pixel or two and finish quickly. Honor `prefers-reduced-motion`.
- Light mode is warm paper (stone-50 surface, stone-900 text). Dark mode is the same layout in deep stone (stone-950 surface, stone-50 text). First paint follows the system. A toggle stores the person's choice.
- Cancel and Delete are the only red controls. They are outline buttons, not filled blocks.
- Primary actions are solid stone pills: Save note, Share note (inside the dialog), Book consultation, Book.
- The note, once shared, is set like a paragraph. Addenda sit under it, each with its date, separated by a hairline.

## Routes

| Route                | Who                         | View                |
| :------------------- | :-------------------------- | :------------------ |
| `/`                  | Anyone without a ticket     | Sign-in picker      |
| `/consultations`     | Signed-in person            | Their consultations |
| `/consultations/:id` | A participant in that visit | Detail              |
| `/book`              | Client only                 | Booking form        |

A stored ticket skips `/` and opens `/consultations`. Sign out clears it and returns to `/`. A practitioner who opens `/book` is returned to the list. Booking is a page, not a modal. After a successful booking, open that new visit's detail page.

A missing consultation, or one that belongs to someone else, stays on the detail route and shows: "The requested resource was not found." Use that same sentence for anything the person must not know about. Do not explain whether the row is missing, private, or someone else's.

## Global chrome

Signed-in pages share this bar. The picker has the wordmark and the theme control only.

```text
+----------------------------------------------------------+
| Debrief                    Priya, client                 |
|                            [ Use dark ] [ Sign out ] [ Book ] |
+----------------------------------------------------------+
```

- "Debrief" returns to `/consultations`.
- The theme control reads "Use dark" or "Use light".
- "Book" is present for clients only. Practitioners never see it. The booking page omits it.
- A visit and the booking page show "Back to consultations" under the bar. The list does not.
- Under the bar, one column. Times show the viewer's local range, with the UTC range on the next line.

## Screen 1 — Sign-in

```text
+----------------------------------------------------------+
| Debrief                                    [ Use dark ]  |
|                                                          |
| Choose a person                                          |
| No password. Picking someone signs you in as them.       |
|                                                          |
| Priya                                       Client       |
| -------------------------------------------------------- |
| Rohan                                       Client       |
| -------------------------------------------------------- |
| Meera                                       Client       |
| -------------------------------------------------------- |
| Dr. Asha Rao                                Practitioner |
| -------------------------------------------------------- |
| Dr. Vikram Shah                             Practitioner |
+----------------------------------------------------------+
```

Each row is the control. The accessible name is "Sign in as Priya", and the same pattern for the others. The chosen row reads "Signing in…" until the next page opens. On failure, the five rows stay and the error sentence sits under the heading.

People, in this order: Priya (client), Rohan (client), Meera (client), Dr. Asha Rao (practitioner), Dr. Vikram Shah (practitioner).

## Screen 2 — Consultation list

Earliest start time is at the top. The whole row opens the visit. A row shows the other person's name, a status badge, the local time, and the UTC time. It never shows a note, a draft, or a snippet of note text.

The client sees the practitioner's name. The practitioner sees the client's name.

Priya's example list. Times below assume a seed hour of 09:00 UTC, shown in India (UTC+5:30):

```text
+----------------------------------------------------------+
| Debrief              Priya, client    [ Use dark ]       |
|                          [ Sign out ] [ Book ]           |
|                                                          |
| Consultations                                            |
|                                                          |
| 27 Sep                       Dr. Asha Rao                |
| 2:30–3:30 pm                 Completed                   |
| 09:00–10:00 UTC                                          |
| -------------------------------------------------------- |
| 1 Oct                        Dr. Asha Rao                |
| 2:30–3:30 pm                 Scheduled                   |
| 09:00–10:00 UTC                                          |
| -------------------------------------------------------- |
| 5 Oct                        Dr. Vikram Shah             |
| 2:30–3:30 pm                 Cancelled                   |
| 09:00–10:00 UTC                                          |
| -------------------------------------------------------- |
| 9 Oct                        Dr. Asha Rao                |
| 2:30–3:30 pm                 Scheduled                   |
| 09:00–10:00 UTC                                          |
+----------------------------------------------------------+
```

Dr. Asha Rao's list uses the same frame. Her rows name Priya, Priya, Priya, and Rohan. Rohan's visit with Dr. Vikram Shah appears on Rohan's list and on Dr. Vikram Shah's list only.

Meera has no visits:

```text
Consultations

You have no consultations.
Book one with a practitioner.
```

"Book one with a practitioner." opens `/book`. The Book pill in the bar does the same. A practitioner with an empty list gets the first sentence only.

While the list loads the first time, keep the heading. Do not replace the page with a spinner. On a later visit, keep the previous rows until the refresh arrives. A failed load shows the error sentence under the heading.

## Screen 3 — Detail

One stack for every visit. A block that does not apply is omitted. Do not show it disabled.

```text
+----------------------------------------------------------+
| Debrief              Priya, client    [ Use dark ]       |
|                          [ Sign out ] [ Book ]           |
|                                                          |
| Back to consultations                                    |
| Completed                                                |
| Dr. Asha Rao                                             |
| Continuity care                                          |
|                                                          |
| 27 Sep 2026, 2:30–3:30 pm                                |
| 09:00–10:00 UTC                                          |
|                                                          |
| (cancelled-by line, only when someone cancelled)         |
| (action row, only the actions this person may take)      |
| (note region, only when this person may know about it)   |
| (alert, only after a failed action)                      |
+----------------------------------------------------------+
```

The title is the other person. A client sees the practitioner's specialty under the name. A practitioner sees the client name and no specialty line. "Back to consultations" sits above the status on a visit that loaded.

### Priya — scheduled, start still in the future

```text
Scheduled
Dr. Asha Rao
Continuity care

9 Oct 2026, 2:30–3:30 pm
09:00–10:00 UTC

[ Cancel consultation ]
```

### Priya — completed visit that has a private draft

The page ends after the time. A private draft and a missing note are the same screen. There is no "no note yet" line, no locked placeholder, and no empty card.

```text
Completed
Dr. Asha Rao
Continuity care

27 Sep 2026, 2:30–3:30 pm
09:00–10:00 UTC
```

### Priya — cancelled

```text
Cancelled
Dr. Vikram Shah
Recovery planning

5 Oct 2026, 2:30–3:30 pm
09:00–10:00 UTC

Cancelled by Priya
```

### Not found

The bar stays. The column is one sentence and one control:

```text
The requested resource was not found.

[ Back to consultations ]
```

### What each role sees

Consultation blocks:

| Block                                                               | Scheduled, before start | Scheduled, start reached | Completed   | Cancelled   |
| :------------------------------------------------------------------ | :---------------------- | :----------------------- | :---------- | :---------- |
| Status badge                                                        | Both                    | Both                     | Both        | Both        |
| Other person's name                                                 | Both                    | Both                     | Both        | Both        |
| Specialty                                                           | Client only             | Client only              | Client only | Client only |
| Local time and UTC                                                  | Both                    | Both                     | Both        | Both        |
| "Cancelled by {name}"                                               | Hidden                  | Hidden                   | Hidden      | Both        |
| Cancel consultation                                                 | Both                    | Both                     | Hidden      | Hidden      |
| Mark completed                                                      | Hidden                  | Practitioner only        | Hidden      | Hidden      |
| Line: "You can mark this completed once the start time has passed." | Practitioner only       | Hidden                   | Hidden      | Hidden      |

Mark completed appears on its own when the clock reaches the start, including if the page is left open. The client never sees that line or that button.

Note region. This exists only on a completed visit, and only for the person allowed to know:

| What is stored         | Client                                                                            | Practitioner                                                      |
| :--------------------- | :-------------------------------------------------------------------------------- | :---------------------------------------------------------------- |
| No note                | No note region                                                                    | Empty field. Button: Save note                                    |
| Private draft          | No note region                                                                    | Editable field with the draft. Save note, Delete note, Share note |
| Shared note            | Locked paragraph, "Shared" plus the local time, then each addendum under its date | The same locked page, plus an addendum field and Add addendum     |
| Scheduled or cancelled | No note region                                                                    | No note region                                                    |

### Rohan — shared note, read only

```text
Completed
Dr. Asha Rao
Continuity care

22 Sep 2026, 2:30–3:30 pm
09:00–10:00 UTC

Agreed on a short walk after lunch and a fixed bedtime.
Shared 22 Sep 2026, 4:30 pm
----------------------------------------------------------
23 Sep 2026
Correction: the walk is three days a week, not every day.
```

The note paragraph is larger than the surrounding interface. Rohan has no field and no button on this note.

### Dr. Asha Rao — private draft, before sharing

```text
Completed
Priya

27 Sep 2026, 2:30–3:30 pm
09:00–10:00 UTC

Note
+--------------------------------------------------------+
| Private draft: review the walking plan before sharing. |
+--------------------------------------------------------+
[ Save note ]   [ Delete note ]   [ Share note ]
```

Save note is the solid button. Delete note is the red outline. Share note is a plain outline.

## Screen 4 — Book a consultation

```text
+----------------------------------------------------------+
| Debrief              Priya, client    [ Use dark ]       |
|                          [ Sign out ]                    |
|                                                          |
| Back to consultations                                    |
| Book a consultation                                      |
|                                                          |
| Practitioner                                             |
| +------------------------------------------------------+ |
| | Dr. Asha Rao, Continuity care                      v | |
| +------------------------------------------------------+ |
|                                                          |
| Starts                                                   |
| +------------------------------------------------------+ |
| | 9 Oct 2026, 2:30 pm                                  | |
| +------------------------------------------------------+ |
|                                                          |
| Ends                                                     |
| +------------------------------------------------------+ |
| | 9 Oct 2026, 3:30 pm                                  | |
| +------------------------------------------------------+ |
|                                                          |
| [ Book consultation ]                                    |
+----------------------------------------------------------+
```

The practitioner menu lists name and specialty: "Dr. Asha Rao, Continuity care" and "Dr. Vikram Shah, Recovery planning". Start and end open a calendar and a time control. The closed field reads "9 Oct 2026, 2:30 pm". When the start changes, the end becomes one hour later and stays editable. A field error sits under that field. Any other failure, including a scheduling overlap, is one alert under the heading. The form keeps the chosen times. Success opens the new visit.

## Interactions

Only Share asks for confirmation. Cancel, Mark completed, Save note, Delete note, Add addendum, and Book consultation run when pressed. The pressed control changes its label and the rest of the page stays put.

Pending labels: Signing in…, Cancelling…, Completing…, Saving…, Deleting…, Sharing…, Adding…, Booking…

### Share dialog

```text
+------------------------------------------+
| Share this note                          |
|                                          |
| Sharing locks the original text.         |
| A later correction is a dated addendum.  |
|                                          |
| [ Keep private ]      [ Share note ]     |
+------------------------------------------+
```

Keep private closes the dialog. The draft stays editable.

Share note closes the dialog and replaces the editor with the locked page:

```text
Agreed text, now locked.
Shared {local time}

Addendum
+--------------------------------------------------------+
|                                                        |
+--------------------------------------------------------+
[ Add addendum ]
```

The original text is not an input. Add addendum appends a new dated block under the original, then clears the field. A second addendum stacks below the first. There is no edit or delete on an addendum, and no way to un-share.

### What each action does to the page

| Action                | The page becomes                                                                                                                                             |
| :-------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cancel consultation   | Status is Cancelled. The cancel button leaves. "Cancelled by {signed-in name}" appears.                                                                      |
| Mark completed        | Status is Completed. Cancel and Mark completed leave. The practitioner sees an empty note field and Save note. The client sees the visit end after the time. |
| Save note, first time | The field holds the draft. Delete note and Share note appear beside Save note.                                                                               |
| Save note, again      | The text updates. The shape of the page stays.                                                                                                               |
| Delete note           | The field is empty again. Delete note and Share note leave. A client looking at this visit still has no note region.                                         |
| Add addendum          | The new date and paragraph appear under the locked text. The field clears.                                                                                   |
| Book consultation     | The new visit's detail page opens.                                                                                                                           |

Whitespace-only text stays on the page. The error sentence sits under the field, and the button label returns to normal.

An alert uses the server's message. There is no toast. A signed-out response clears the ticket and shows the picker.

## Speed

The list does not blank while a visit opens. Keep the last list on screen. A row may warm its detail on hover. After every successful write, refresh the list and that visit together. No full-page spinner.

## Example note copy

Use these strings in the designed states:

- Private draft: "Private draft: review the walking plan before sharing."
- Shared note: "Agreed on a short walk after lunch and a fixed bedtime."
- Addendum: "Correction: the walk is three days a week, not every day."

Specialties: Dr. Asha Rao, Continuity care. Dr. Vikram Shah, Recovery planning.

## Out of scope

Passwords, rescheduling, no-show as its own state, editing or deleting an addendum, un-sharing, file upload, email, and a client's other appointments. The screen does not warn a client about their own calendar.
