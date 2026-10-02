import type { ConsultationStatus, NoteResponse, PersonRole } from "@/api/types.ts";
import { useState } from "react";
import { ApiError } from "@/api/client.ts";
import {
  useAddAddendum,
  useCreateNote,
  useDeleteNote,
  useShareNote,
  useUpdateNote,
} from "@/api/queries.ts";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { formatDay, formatSharedAt } from "@/lib/time.ts";

const stonePill
  = "rounded-full bg-stone-900 px-4 text-stone-50 hover:bg-stone-800 dark:bg-stone-100 dark:text-stone-900 dark:hover:bg-stone-200 motion-reduce:transition-none motion-reduce:active:translate-y-0";

const quietPress = "motion-reduce:transition-none motion-reduce:active:translate-y-0";

const redOutline
  = "border-red-800 text-red-800 hover:bg-red-50 hover:text-red-800 dark:border-red-400 dark:text-red-400 dark:hover:bg-red-950 dark:hover:text-red-400 motion-reduce:transition-none motion-reduce:active:translate-y-0";

const noteText
  = "min-h-32 text-2xl font-light leading-relaxed md:text-2xl";

export function NoteRegion({
  consultationId,
  status,
  role,
  note,
}: {
  consultationId: number;
  status: ConsultationStatus;
  role: PersonRole;
  note: NoteResponse | null;
}) {
  const createNote = useCreateNote();
  const updateNote = useUpdateNote();
  const deleteNote = useDeleteNote();
  const shareNote = useShareNote();
  const addAddendum = useAddAddendum();
  const savedBody = note !== null && note.shared_at === null ? note.body : "";
  const [draft, setDraft] = useState(savedBody);
  const [trackedBody, setTrackedBody] = useState(savedBody);
  const [addendum, setAddendum] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [shareOpen, setShareOpen] = useState(false);

  if (savedBody !== trackedBody) {
    setTrackedBody(savedBody);
    setDraft(savedBody);
  }

  const saving = createNote.isPending || updateNote.isPending;
  const deleting = deleteNote.isPending;
  const sharing = shareNote.isPending;
  const adding = addAddendum.isPending;
  const busy = saving || deleting || sharing || adding;
  const shared = note !== null && note.shared_at !== null;
  const draftNote = note !== null && note.shared_at === null;
  const visible = status === "completed" && (role === "practitioner" || shared);

  if (!visible) {
    return null;
  }

  async function save() {
    if (busy) {
      return;
    }
    setFieldError(null);
    setActionError(null);
    try {
      if (draftNote) {
        await updateNote.mutateAsync({ consultationId, body: draft });
      }
      else {
        await createNote.mutateAsync({ consultationId, body: draft });
      }
    }
    catch (caught) {
      applyFailure(caught, setFieldError, setActionError);
    }
  }

  async function remove() {
    if (busy) {
      return;
    }
    setFieldError(null);
    setActionError(null);
    try {
      await deleteNote.mutateAsync(consultationId);
    }
    catch (caught) {
      applyFailure(caught, setFieldError, setActionError);
    }
  }

  async function confirmShare() {
    if (busy) {
      return;
    }
    setFieldError(null);
    setActionError(null);
    try {
      await shareNote.mutateAsync(consultationId);
      setShareOpen(false);
    }
    catch (caught) {
      setShareOpen(false);
      applyFailure(caught, setFieldError, setActionError);
    }
  }

  async function appendAddendum() {
    if (busy) {
      return;
    }
    setFieldError(null);
    setActionError(null);
    try {
      await addAddendum.mutateAsync({ consultationId, body: addendum });
      setAddendum("");
    }
    catch (caught) {
      applyFailure(caught, setFieldError, setActionError);
    }
  }

  return (
    <section className="mt-8">
      {note !== null && note.shared_at !== null
        ? (
            <SharedNote
              note={note}
              addendum={addendum}
              adding={adding}
              fieldError={fieldError}
              showComposer={role === "practitioner"}
              onAddendumChange={(value) => {
                setAddendum(value);
                setFieldError(null);
              }}
              onSubmit={() => {
                void appendAddendum();
              }}
            />
          )
        : (
            <DraftNote
              draft={draft}
              saving={saving}
              deleting={deleting}
              sharing={sharing}
              hasDraft={draftNote}
              fieldError={fieldError}
              onDraftChange={(value) => {
                setDraft(value);
                setFieldError(null);
              }}
              onSave={() => {
                void save();
              }}
              onDelete={() => {
                void remove();
              }}
              onShare={() => {
                if (!sharing) {
                  setShareOpen(true);
                }
              }}
            />
          )}
      {actionError === null
        ? null
        : (
            <Alert variant="destructive" className="mt-8">
              <AlertDescription>{actionError}</AlertDescription>
            </Alert>
          )}
      <ShareDialog
        open={shareOpen}
        sharing={sharing}
        onOpenChange={setShareOpen}
        onKeepPrivate={() => setShareOpen(false)}
        onShare={() => {
          void confirmShare();
        }}
      />
    </section>
  );
}

function DraftNote({
  draft,
  saving,
  deleting,
  sharing,
  hasDraft,
  fieldError,
  onDraftChange,
  onSave,
  onDelete,
  onShare,
}: {
  draft: string;
  saving: boolean;
  deleting: boolean;
  sharing: boolean;
  hasDraft: boolean;
  fieldError: string | null;
  onDraftChange: (value: string) => void;
  onSave: () => void;
  onDelete: () => void;
  onShare: () => void;
}) {
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSave();
      }}
    >
      <Label htmlFor="consultation-note">Note</Label>
      <Textarea
        id="consultation-note"
        value={draft}
        onChange={event => onDraftChange(event.target.value)}
        aria-invalid={fieldError !== null}
        aria-describedby={fieldError === null ? undefined : "consultation-note-error"}
        className={`mt-3 ${noteText}`}
      />
      {fieldError === null
        ? null
        : (
            <p id="consultation-note-error" className="mt-2" role="alert">
              {fieldError}
            </p>
          )}
      <div className="mt-4 flex flex-wrap gap-3">
        <Button type="submit" className={stonePill}>
          {saving ? "Saving…" : "Save note"}
        </Button>
        {hasDraft
          ? (
              <>
                <Button
                  type="button"
                  variant="outline"
                  className={redOutline}
                  onClick={onDelete}
                >
                  {deleting ? "Deleting…" : "Delete note"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className={quietPress}
                  onClick={onShare}
                >
                  {sharing ? "Sharing…" : "Share note"}
                </Button>
              </>
            )
          : null}
      </div>
    </form>
  );
}

function SharedNote({
  note,
  addendum,
  adding,
  fieldError,
  showComposer,
  onAddendumChange,
  onSubmit,
}: {
  note: NoteResponse;
  addendum: string;
  adding: boolean;
  fieldError: string | null;
  showComposer: boolean;
  onAddendumChange: (value: string) => void;
  onSubmit: () => void;
}) {
  if (note.shared_at === null) {
    return null;
  }
  const sharedAt = note.shared_at;
  const addenda = orderedAddenda(note);

  return (
    <>
      <p className="text-2xl font-light leading-relaxed whitespace-pre-wrap">{note.body}</p>
      <p className="mt-2 text-sm text-stone-500 dark:text-stone-400">
        {`Shared ${formatSharedAt(sharedAt)}`}
      </p>
      {addenda.length === 0
        ? null
        : (
            <ul>
              {addenda.map(item => (
                <li
                  key={item.id}
                  className="mt-6 border-t border-stone-200 pt-6 dark:border-stone-800"
                >
                  <p className="text-sm text-stone-500 dark:text-stone-400">
                    {formatDay(item.created_at)}
                  </p>
                  <p className="mt-2 text-2xl font-light leading-relaxed whitespace-pre-wrap">
                    {item.body}
                  </p>
                </li>
              ))}
            </ul>
          )}
      {showComposer
        ? (
            <form
              className="mt-8"
              onSubmit={(event) => {
                event.preventDefault();
                onSubmit();
              }}
            >
              <Label htmlFor="consultation-addendum">Addendum</Label>
              <Textarea
                id="consultation-addendum"
                value={addendum}
                onChange={event => onAddendumChange(event.target.value)}
                aria-invalid={fieldError !== null}
                aria-describedby={fieldError === null ? undefined : "consultation-addendum-error"}
                className={`mt-3 ${noteText}`}
              />
              {fieldError === null
                ? null
                : (
                    <p id="consultation-addendum-error" className="mt-2" role="alert">
                      {fieldError}
                    </p>
                  )}
              <Button type="submit" variant="outline" className={`mt-4 ${quietPress}`}>
                {adding ? "Adding…" : "Add addendum"}
              </Button>
            </form>
          )
        : null}
    </>
  );
}

function ShareDialog({
  open,
  sharing,
  onOpenChange,
  onKeepPrivate,
  onShare,
}: {
  open: boolean;
  sharing: boolean;
  onOpenChange: (open: boolean) => void;
  onKeepPrivate: () => void;
  onShare: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent showCloseButton={false} className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Share this note</DialogTitle>
          <DialogDescription className="text-base leading-relaxed text-foreground">
            Sharing locks the original text.
            <br />
            A later correction is a dated addendum.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap justify-end gap-3">
          <Button type="button" variant="outline" className={quietPress} onClick={onKeepPrivate}>
            Keep private
          </Button>
          <Button type="button" className={stonePill} onClick={onShare}>
            {sharing ? "Sharing…" : "Share note"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function orderedAddenda(note: NoteResponse) {
  return [...note.addenda].sort((left, right) => {
    const byTime = left.created_at.localeCompare(right.created_at);
    if (byTime !== 0) {
      return byTime;
    }
    return left.id - right.id;
  });
}

function applyFailure(
  caught: unknown,
  setFieldError: (message: string | null) => void,
  setActionError: (message: string | null) => void,
) {
  if (!(caught instanceof ApiError)) {
    setActionError("The note could not be updated.");
    return;
  }
  const field = caught.details.find(item => item.field === "body")?.message;
  if (field !== undefined) {
    setFieldError(field);
    return;
  }
  if (caught.code === "VALIDATION_ERROR") {
    setFieldError(caught.message);
    return;
  }
  setActionError(caught.message);
}
