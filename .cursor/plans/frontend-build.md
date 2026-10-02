# Frontend build sequence

The screens, copy, visibility, and interactions are specified in [frontend-spec.md](frontend-spec.md). This file is only the order of work. Do not restate the spec here.

Each step is done when `pnpm build` passes from `frontend/` and the spec section named in that step is true on screen.

## Already in place

Do not scaffold again. `frontend/` already has Vite, React, TypeScript, pnpm, Tailwind v4, Schibsted Grotesk, `VITE_API_URL`, and shadcn `button`, `card`, `input`, `label`, `textarea`, `select`, `badge`, `dialog`, `alert`, `separator`, `calendar`, and `popover`. `react-router` and `@tanstack/react-query` are installed. The dev server is `http://127.0.0.1:5173`.

`html` uses `font-sans`. That token is Schibsted Grotesk. There is no `frontend/README.md`. The root `README.md` records Node, pnpm, and `make web`.

ESLint is `@antfu/eslint-config` in `frontend/eslint.config.js`. New filenames are kebab-case. `App.tsx` stays, because `main.tsx` imports that name. Scripts from `frontend/`: `pnpm dev`, `pnpm build`, `pnpm lint`, `pnpm lint:fix`, `pnpm typecheck` (`tsc -b`), `pnpm preview`.

## Done

1. **API types and client.** `pnpm build` passes. `src/api/types.ts` matches the public models in `backend/app/schemas.py`. `src/api/client.ts` calls `VITE_API_URL`, sends `Authorization: Bearer` when a ticket is stored, unwraps the envelope, and returns `data`. A `401` or `AUTHENTICATION_REQUIRED` clears the ticket. Failures throw `ApiError`. Field errors stay on `error.details`. The ticket key is `debrief.ticket` (`TICKET_STORAGE_KEY`). Session uses `readTicket`, `storeTicket`, `clearTicket`, and `subscribeTicket` from this file. Do not add a second ticket key. The person id lives in `debrief.person`.

2. **Queries.** `pnpm build` passes. `src/api/queries.ts` loads people, practitioners, the consultation list, and one consultation. The list keeps its previous data while a visit opens. `prefetchConsultation` warms that visit with `queryClient.query`. Do not call the deprecated `prefetchQuery`. A warm-up that fails stays on the row. Book, cancel, complete, and every note write invalidate the list and that visit together. Client errors are not retried.

3. **Session.** `pnpm build` passes. `src/auth/session.tsx` keeps the ticket in `localStorage` under `debrief.ticket` and the chosen person id under `debrief.person`. The signed-in person is that id matched to `GET /people`. `signIn` stores both after `POST /auth/login`. `signOut` clears the ticket, and the person id leaves with it. A `401` clears the ticket through the client, and the session follows that. `SessionProvider` must sit inside `QueryClientProvider`.

4. **Time.** `pnpm build` passes. `src/lib/time.ts` formats the viewer's local range and the UTC range. A list row uses `listDate` (`27 Sep`), `localRange` (`2:30–3:30 pm`), and `utcRange` (`09:00–10:00 UTC`). Detail uses `detailWhen` (`27 Sep 2026, 2:30–3:30 pm`) with `utcRange` on the next line. `formatSharedAt` and `formatDay` are the note and addendum dates. `formatLocalInstant` is the closed booking picker (`9 Oct 2026, 2:30 pm`). Do not format these again in the pages.

5. **Shell.** `pnpm build` passes. `main.tsx` wraps `QueryClientProvider`, then `SessionProvider`, then `App`. `App.tsx` declares `/`, `/consultations`, `/consultations/:id`, and `/book`. No ticket stays on `/`. A ticket on `/` goes to `/consultations`. A practitioner opening `/book` returns to the list. An unknown path returns to `/`. The theme follows the system, then a stored `debrief.theme` of `light` or `dark` (`src/lib/theme.ts`). `backend/app/main.py` allows `http://127.0.0.1:5173` and `http://localhost:5173` with `Authorization`. Signed-in pages share `src/components/page-column.tsx`.

6. **Sign-in.** `pnpm build` passes. `src/pages/sign-in.tsx` is Screen 1 and is the `/` route. The document title is `Debrief`. People stay in the spec order. Each row's accessible name is "Sign in as {name}". The chosen row reads "Signing in…" and then opens `/consultations`. A failure leaves the five rows and puts the server sentence under "Choose a person". The wordmark is bold and tight. Under a hairline, the line "Welcome to the Debrief" sits above a light "Choose a person". Rows are ghost buttons: the name is light, the role is smaller and stone. The theme control is a ghost button with a moon or sun icon and the label "Use dark" or "Use light". Step 7 moves that control into the shared bar and keeps the icon and the label.

7. **Chrome.** `pnpm build` passes. `src/components/theme-toggle.tsx` is the ghost button with a moon or sun icon and "Use dark" or "Use light". Sign-in uses it. `src/components/top-bar.tsx` is the signed-in bar. "Debrief" returns to `/consultations`. The identity line is "{name}, {role}". Then the theme control, Sign out, and Book. Book is a stone pill and is rendered for clients only. `src/components/status-badge.tsx` labels Scheduled, Completed, and Cancelled with the darker, mid, and muted stone weights. A visit and the booking page also show "Back to consultations" under the bar. The list does not.

8. **List.** `pnpm build` passes. `src/pages/consultation-list.tsx` is Screen 2 and is the `/consultations` route. Earliest start is first. A row names the other person, shows the status badge, `listDate`, `localRange`, and `utcRange`, and opens that visit. It never shows note text. Hover or focus warms the visit and a miss stays on the row. The first load keeps the heading. A failed load puts the server sentence under the heading and keeps any previous rows. Meera sees "You have no consultations." and "Book one with a practitioner.", and that second sentence opens `/book`. A practitioner with an empty list would see only the first sentence.

9. **Detail.** `pnpm build` passes. `src/pages/consultation-detail.tsx` is Screen 3 and is `/consultations/:id`. The status badge, the other person's name, the client's specialty line, `detailWhen`, and `utcRange` follow the visibility table. "Cancelled by {name}" shows only when cancelled. Cancel consultation is the red outline and is shown while scheduled. Mark completed is shown only to the practitioner once the start is reached, including if the page is left open. Before that, the practitioner sees "You can mark this completed once the start time has passed." The pressed control reads "Cancelling…" or "Completing…". A failed action shows the server sentence in an alert. A loaded visit shows "Back to consultations" under the bar. A missing, foreign, or invalid id keeps the bar and shows "The requested resource was not found." with that link as an outline button.

10. **Notes.** `pnpm build` passes. `src/components/note-region.tsx` is the note half of Screen 3 and the Interactions section, on `/consultations/:id`. A client with `note: null` gets no note region. Scheduled and cancelled visits get none either. A practitioner with no note sees an empty field and Save note. A draft can be saved, deleted, and shared. Share is the only confirm dialog: Keep private leaves the draft editable, and Share note locks the text. After share, the original is a paragraph with "Shared" and the local time, and the practitioner gets an addendum field. Addenda append in date order. Whitespace-only text stays in the field with the server sentence underneath.

11. **Booking.** `pnpm build` passes. `src/pages/book-consultation.tsx` is Screen 4 and is the `/book` route. The practitioner menu lists name and specialty. Start and end use `src/components/datetime-picker.tsx` (shadcn calendar and a time control). The closed field reads `formatLocalInstant`. End defaults to one hour after start and stays editable, then moves again when the start changes. Success opens the new visit. A field error sits under that field. An overlap, and any other failure, is one alert under the heading. The form keeps the chosen times. The pressed control reads "Booking…". The bar on this page has Sign out and omits Book. "Back to consultations" sits under the bar.

12. **Run it with the API.** The browser origins are allowed. `make setup` runs `pnpm install` in `frontend/`. `make web` runs `pnpm dev`. `README.md` records Node, pnpm, and that command. The locked-note decision in the README stays as it is.

## Files to add

```text
frontend/src/
├── api/
│   ├── client.ts          done
│   ├── types.ts           done
│   └── queries.ts         done
├── auth/
│   └── session.tsx        done
├── lib/
│   ├── time.ts            done
│   ├── theme.ts           done
│   ├── controls.ts        done
│   └── people.ts          done
├── components/
│   ├── top-bar.tsx        done
│   ├── theme-toggle.tsx   done
│   ├── status-badge.tsx   done
│   ├── note-region.tsx    done
│   ├── datetime-picker.tsx done
│   ├── page-column.tsx    done
│   └── field-message.tsx  done
└── pages/
    ├── sign-in.tsx          done
    ├── consultation-list.tsx done
    ├── consultation-detail.tsx done
    └── book-consultation.tsx done
```

`App.tsx` and `main.tsx` are edited in place. shadcn stays inside `src/components/ui/`. No test folder and no `features/` tree.

## Sequence

Steps 1 to 12 are done. Continue at step 13.

13. **Check the spec against a seeded API.** `make seed`, `make api`, and `make web`. Walk Priya, Dr. Asha Rao, Meera, and Rohan through the states in Screen 2 and Screen 3. `pnpm build` passes. There is no frontend test runner.
