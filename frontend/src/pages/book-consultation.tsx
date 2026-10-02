import type { FormEvent } from "react";
import type { PractitionerResponse } from "@/api/types.ts";
import { useState } from "react";
import { useNavigate } from "react-router";
import { ApiError } from "@/api/client.ts";
import { useBookConsultation, usePractitioners } from "@/api/queries.ts";
import { TopBar } from "@/components/top-bar.tsx";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatLocalInstant, parseLocalInstant } from "@/lib/time.ts";

const TIME_HINT = "Use a time like 9 Oct 2026, 2:30 pm.";

const stonePill
  = "rounded-full bg-stone-900 px-4 text-stone-50 hover:bg-stone-800 dark:bg-stone-100 dark:text-stone-900 dark:hover:bg-stone-200 motion-reduce:transition-none motion-reduce:active:translate-y-0";

const fieldClass = "mt-3 h-11 text-base md:text-base";

export function BookConsultation() {
  const practitioners = usePractitioners();
  const book = useBookConsultation();
  const navigate = useNavigate();
  const options = practitioners.data ?? [];
  const [practitionerId, setPractitionerId] = useState<number | null>(null);
  const [initialTimes] = useState(defaultTimes);
  const [starts, setStarts] = useState(initialTimes.starts);
  const [ends, setEnds] = useState(initialTimes.ends);
  const [fields, setFields] = useState<FieldMessages>({});
  const [alertMessage, setAlertMessage] = useState<string | null>(null);
  const loadMessage = loadError(practitioners.error);

  if (practitionerId === null && options[0] !== undefined) {
    setPractitionerId(options[0].id);
  }

  function changeStart(value: string) {
    setStarts(value);
    const parsed = parseLocalInstant(value);
    if (parsed !== null) {
      setEnds(formatLocalInstant(oneHourLater(parsed)));
    }
    setFields(current => ({
      ...current,
      starts_at: undefined,
      ends_at: parsed === null ? current.ends_at : undefined,
    }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (book.isPending) {
      return;
    }
    setAlertMessage(null);
    const start = parseLocalInstant(starts);
    const end = parseLocalInstant(ends);
    const nextFields: FieldMessages = {};
    if (practitionerId === null) {
      nextFields.practitioner_id = "Choose a practitioner.";
    }
    if (start === null) {
      nextFields.starts_at = TIME_HINT;
    }
    if (end === null) {
      nextFields.ends_at = TIME_HINT;
    }
    setFields(nextFields);
    if (practitionerId === null || start === null || end === null) {
      return;
    }
    try {
      const consultation = await book.mutateAsync({
        practitioner_id: practitionerId,
        starts_at: start.toISOString(),
        ends_at: end.toISOString(),
      });
      await navigate(`/consultations/${consultation.id}`);
    }
    catch (caught) {
      if (!(caught instanceof ApiError)) {
        setAlertMessage("The consultation could not be booked.");
        return;
      }
      const messages = messagesFor(caught);
      if (hasFieldMessage(messages)) {
        setFields(messages);
        return;
      }
      setAlertMessage(caught.message);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-160 flex-col px-6 py-8">
      <TopBar />
      <h1 className="mt-10 text-4xl font-light">Book a consultation</h1>
      {loadMessage === null
        ? null
        : (
            <p className="mt-2" role="alert">
              {loadMessage}
            </p>
          )}
      {alertMessage === null
        ? null
        : (
            <Alert variant="destructive" className="mt-8">
              <AlertDescription>{alertMessage}</AlertDescription>
            </Alert>
          )}
      <form className="mt-8 flex flex-col gap-8" onSubmit={event => void submit(event)}>
        <div>
          <Label htmlFor="practitioner">Practitioner</Label>
          <Select
            value={practitionerId}
            items={options.map(practitioner => ({
              value: practitioner.id,
              label: practitionerLabel(practitioner),
            }))}
            onValueChange={(value) => {
              if (typeof value !== "number") {
                return;
              }
              setPractitionerId(value);
              setFields(current => ({ ...current, practitioner_id: undefined }));
            }}
          >
            <SelectTrigger
              id="practitioner"
              className="mt-3 h-11 w-full text-base"
              aria-invalid={fields.practitioner_id !== undefined}
              aria-describedby={fields.practitioner_id === undefined ? undefined : "practitioner-error"}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {options.map(practitioner => (
                <SelectItem key={practitioner.id} value={practitioner.id}>
                  {practitionerLabel(practitioner)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FieldError id="practitioner-error" message={fields.practitioner_id} />
        </div>
        <div>
          <Label htmlFor="starts">Starts</Label>
          <Input
            id="starts"
            value={starts}
            onChange={event => changeStart(event.target.value)}
            autoComplete="off"
            spellCheck={false}
            aria-invalid={fields.starts_at !== undefined}
            aria-describedby={fields.starts_at === undefined ? undefined : "starts-error"}
            className={fieldClass}
          />
          <FieldError id="starts-error" message={fields.starts_at} />
        </div>
        <div>
          <Label htmlFor="ends">Ends</Label>
          <Input
            id="ends"
            value={ends}
            onChange={(event) => {
              setEnds(event.target.value);
              setFields(current => ({ ...current, ends_at: undefined }));
            }}
            autoComplete="off"
            spellCheck={false}
            aria-invalid={fields.ends_at !== undefined}
            aria-describedby={fields.ends_at === undefined ? undefined : "ends-error"}
            className={fieldClass}
          />
          <FieldError id="ends-error" message={fields.ends_at} />
        </div>
        <Button type="submit" className={`w-fit ${stonePill}`}>
          {book.isPending ? "Booking…" : "Book consultation"}
        </Button>
      </form>
    </main>
  );
}

function FieldError({ id, message }: { id: string; message: string | undefined }) {
  if (message === undefined) {
    return null;
  }
  return (
    <p id={id} className="mt-2" role="alert">
      {message}
    </p>
  );
}

interface FieldMessages {
  practitioner_id?: string;
  starts_at?: string;
  ends_at?: string;
}

function messagesFor(error: ApiError): FieldMessages {
  const messages: FieldMessages = {};
  for (const detail of error.details) {
    if (isField(detail.field)) {
      messages[detail.field] = detail.message;
    }
  }
  return messages;
}

function hasFieldMessage(messages: FieldMessages) {
  return messages.practitioner_id !== undefined
    || messages.starts_at !== undefined
    || messages.ends_at !== undefined;
}

function isField(field: string): field is keyof FieldMessages {
  return field === "practitioner_id" || field === "starts_at" || field === "ends_at";
}

function practitionerLabel(practitioner: PractitionerResponse) {
  if (practitioner.specialty !== null && practitioner.specialty.trim() !== "") {
    return `${practitioner.name}, ${practitioner.specialty}`;
  }
  return practitioner.name;
}

function defaultTimes() {
  const start = defaultStart();
  return {
    starts: formatLocalInstant(start),
    ends: formatLocalInstant(oneHourLater(start)),
  };
}

function defaultStart(now = new Date()) {
  const start = new Date(now);
  start.setSeconds(0, 0);
  start.setMinutes(0);
  if (start.getTime() <= now.getTime()) {
    start.setHours(start.getHours() + 1);
  }
  return start;
}

function oneHourLater(instant: Date) {
  return new Date(instant.getTime() + 60 * 60 * 1000);
}

function loadError(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error == null) {
    return null;
  }
  return "The practitioners could not be loaded.";
}
