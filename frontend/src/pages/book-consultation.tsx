import type { FormEvent } from "react";
import type { PractitionerResponse } from "@/api/types.ts";
import { useState } from "react";
import { useNavigate } from "react-router";
import { ApiError, errorMessage } from "@/api/client.ts";
import { useBookConsultation, usePractitioners } from "@/api/queries.ts";
import { DateTimePicker } from "@/components/datetime-picker.tsx";
import { FieldMessage } from "@/components/field-message.tsx";
import { SignedInPage } from "@/components/page-column.tsx";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { stonePill } from "@/lib/controls.ts";
import { cn } from "@/lib/utils.ts";

export function BookConsultation() {
  const practitioners = usePractitioners();
  const book = useBookConsultation();
  const navigate = useNavigate();
  const options = practitioners.data ?? [];
  const [chosenId, setChosenId] = useState<number | null>(null);
  const practitionerId = chosenId ?? options[0]?.id ?? null;
  const [initialTimes] = useState(defaultTimes);
  const [starts, setStarts] = useState(initialTimes.starts);
  const [ends, setEnds] = useState(initialTimes.ends);
  const [fields, setFields] = useState<FieldMessages>({});
  const [alertMessage, setAlertMessage] = useState<string | null>(null);
  const loadMessage = errorMessage(
    practitioners.error,
    "The practitioners could not be loaded.",
  );

  function changeStart(value: Date) {
    setStarts(value);
    setEnds(oneHourLater(value));
    setFields(current => ({
      ...current,
      starts_at: undefined,
      ends_at: undefined,
    }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (book.isPending) {
      return;
    }
    setAlertMessage(null);
    if (practitionerId === null) {
      setFields(current => ({
        ...current,
        practitioner_id: "Choose a practitioner.",
      }));
      return;
    }
    setFields(current => ({ ...current, practitioner_id: undefined }));
    try {
      const consultation = await book.mutateAsync({
        practitioner_id: practitionerId,
        starts_at: starts.toISOString(),
        ends_at: ends.toISOString(),
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
    <SignedInPage back>
      <h1 className="mt-4 text-4xl font-light">Book a consultation</h1>
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
      <form
        className="mt-8 flex flex-col gap-8"
        onSubmit={event => void submit(event)}
      >
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
              setChosenId(value);
              setFields(current => ({
                ...current,
                practitioner_id: undefined,
              }));
            }}
          >
            <SelectTrigger
              id="practitioner"
              className="mt-3 h-11 w-full text-base"
              aria-invalid={fields.practitioner_id !== undefined}
              aria-describedby={
                fields.practitioner_id === undefined
                  ? undefined
                  : "practitioner-error"
              }
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
          <FieldMessage id="practitioner-error" message={fields.practitioner_id} />
        </div>
        <div>
          <Label htmlFor="starts">Starts</Label>
          <DateTimePicker
            id="starts"
            value={starts}
            onChange={changeStart}
            invalid={fields.starts_at !== undefined}
            describedBy={fields.starts_at === undefined ? undefined : "starts-error"}
          />
          <FieldMessage id="starts-error" message={fields.starts_at} />
        </div>
        <div>
          <Label htmlFor="ends">Ends</Label>
          <DateTimePicker
            id="ends"
            value={ends}
            onChange={(value) => {
              setEnds(value);
              setFields(current => ({ ...current, ends_at: undefined }));
            }}
            invalid={fields.ends_at !== undefined}
            describedBy={fields.ends_at === undefined ? undefined : "ends-error"}
          />
          <FieldMessage id="ends-error" message={fields.ends_at} />
        </div>
        <Button type="submit" className={cn("w-fit", stonePill)}>
          {book.isPending ? "Booking…" : "Book consultation"}
        </Button>
      </form>
    </SignedInPage>
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
  return (
    messages.practitioner_id !== undefined
    || messages.starts_at !== undefined
    || messages.ends_at !== undefined
  );
}

function isField(field: string): field is keyof FieldMessages {
  return (
    field === "practitioner_id" || field === "starts_at" || field === "ends_at"
  );
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
    starts: start,
    ends: oneHourLater(start),
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
