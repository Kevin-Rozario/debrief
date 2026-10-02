import type {
  ConsultationDetailResponse,
  PersonResponse,
  PractitionerResponse,
} from "@/api/types.ts";
import { useEffect, useState } from "react";
import { useParams } from "react-router";
import { ApiError, errorMessage } from "@/api/client.ts";
import {
  useCancelConsultation,
  useCompleteConsultation,
  useConsultation,
  usePeople,
  usePractitioners,
} from "@/api/queries.ts";
import { useSession } from "@/auth/session.tsx";
import { NoteRegion } from "@/components/note-region.tsx";
import { BackToConsultations, SignedInPage } from "@/components/page-column.tsx";
import { StatusBadge } from "@/components/status-badge.tsx";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { redOutline } from "@/lib/controls.ts";
import { otherPersonId, personName } from "@/lib/people.ts";
import { formatConsultationTime } from "@/lib/time.ts";

const NOT_FOUND = "The requested resource was not found.";

export function ConsultationDetail() {
  const params = useParams();
  const consultationId = Number(params.id);
  const validId = Number.isInteger(consultationId) && consultationId > 0;
  const { person } = useSession();
  const people = usePeople();
  const consultation = useConsultation(validId ? consultationId : 0, validId);
  const practitioners = usePractitioners(person?.role === "client");
  const cancelConsultation = useCancelConsultation();
  const completeConsultation = useCompleteConsultation();
  const [actionError, setActionError] = useState<string | null>(null);
  const visit = consultation.data;
  const started = useStartReached(visit?.starts_at);

  useEffect(() => {
    setActionError(null);
  }, [consultationId]);

  if (person === null) {
    return null;
  }

  const missing
    = !validId
      || (consultation.isError && visit === undefined && isMissing(consultation.error));
  const loading = validId && visit === undefined && !consultation.isError;
  const showVisit = !missing && !loading && visit !== undefined;

  return (
    <SignedInPage back={showVisit}>
      {missing ? <MissingVisit /> : null}
      {showVisit
        ? (
            <Visit
              visit={visit}
              caller={person}
              people={people.data ?? []}
              practitioners={practitioners.data ?? []}
              started={started}
              actionError={actionError}
              cancelling={cancelConsultation.isPending}
              completing={completeConsultation.isPending}
              onCancel={() => {
                void runAction(
                  () => cancelConsultation.mutateAsync(visit.id),
                  setActionError,
                  cancelConsultation.isPending || completeConsultation.isPending,
                );
              }}
              onComplete={() => {
                void runAction(
                  () => completeConsultation.mutateAsync(visit.id),
                  setActionError,
                  cancelConsultation.isPending || completeConsultation.isPending,
                );
              }}
            />
          )
        : null}
      {!missing && consultation.isError && visit === undefined
        ? (
            <>
              <p className="mt-10" role="alert">
                {errorMessage(consultation.error, "The consultation could not be loaded.")}
              </p>
              <BackToConsultations variant="button" className="mt-8" />
            </>
          )
        : null}
    </SignedInPage>
  );
}

function Visit({
  visit,
  caller,
  people,
  practitioners,
  started,
  actionError,
  cancelling,
  completing,
  onCancel,
  onComplete,
}: {
  visit: ConsultationDetailResponse;
  caller: PersonResponse;
  people: PersonResponse[];
  practitioners: PractitionerResponse[];
  started: boolean;
  actionError: string | null;
  cancelling: boolean;
  completing: boolean;
  onCancel: () => void;
  onComplete: () => void;
}) {
  const time = formatConsultationTime(visit.starts_at, visit.ends_at);
  const otherId = otherPersonId(visit, caller.id);
  const specialty
    = caller.role === "client"
      ? practitioners.find(practitioner => practitioner.id === otherId)?.specialty?.trim() || null
      : null;
  const cancelledBy
    = visit.status === "cancelled" && visit.cancelled_by_id !== null
      ? personName(people, visit.cancelled_by_id)
      : "";
  const scheduled = visit.status === "scheduled";
  const showCancel = scheduled;
  const showComplete = caller.role === "practitioner" && scheduled && started;
  const showHint = caller.role === "practitioner" && scheduled && !started;

  return (
    <>
      <div className="mt-4">
        <StatusBadge status={visit.status} />
        <h1 className="mt-3 text-4xl font-light">
          {personName(people, otherId)}
        </h1>
        {specialty
          ? (
              <p className="mt-2 text-stone-500 dark:text-stone-400">{specialty}</p>
            )
          : null}
      </div>
      <div className="mt-8">
        <p>{time.detailWhen}</p>
        <p className="text-sm text-stone-500 dark:text-stone-400">
          {time.utcRange}
        </p>
      </div>
      {cancelledBy === ""
        ? null
        : (
            <p className="mt-8">{`Cancelled by ${cancelledBy}`}</p>
          )}
      {showHint
        ? (
            <p className="mt-8">
              You can mark this completed once the start time has passed.
            </p>
          )
        : null}
      {showCancel || showComplete
        ? (
            <div className="mt-8 flex flex-wrap gap-3">
              {showCancel
                ? (
                    <Button
                      variant="outline"
                      className={redOutline}
                      onClick={onCancel}
                    >
                      {cancelling ? "Cancelling…" : "Cancel consultation"}
                    </Button>
                  )
                : null}
              {showComplete
                ? (
                    <Button variant="outline" onClick={onComplete}>
                      {completing ? "Completing…" : "Mark completed"}
                    </Button>
                  )
                : null}
            </div>
          )
        : null}
      <NoteRegion
        key={visit.id}
        consultationId={visit.id}
        status={visit.status}
        role={caller.role}
        note={visit.note}
      />
      {actionError === null
        ? null
        : (
            <Alert variant="destructive" className="mt-8">
              <AlertDescription>{actionError}</AlertDescription>
            </Alert>
          )}
    </>
  );
}

function MissingVisit() {
  return (
    <>
      <p className="mt-10">{NOT_FOUND}</p>
      <BackToConsultations variant="button" className="mt-8" />
    </>
  );
}

function useStartReached(startsAt: string | undefined) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (startsAt === undefined) {
      return;
    }
    const start = new Date(startsAt).getTime();
    if (Number.isNaN(start)) {
      return;
    }
    const delay = start - Date.now();
    if (delay <= 0) {
      return;
    }
    const timer = window.setTimeout(() => setNow(Date.now()), delay);
    return () => window.clearTimeout(timer);
  }, [startsAt]);

  if (startsAt === undefined) {
    return false;
  }
  const start = new Date(startsAt).getTime();
  return !Number.isNaN(start) && now >= start;
}

async function runAction(
  start: () => Promise<unknown>,
  setActionError: (message: string | null) => void,
  busy: boolean,
) {
  if (busy) {
    return;
  }
  setActionError(null);
  try {
    await start();
  }
  catch (caught) {
    setActionError(
      caught instanceof ApiError
        ? caught.message
        : "The consultation could not be updated.",
    );
  }
}

function isMissing(error: unknown) {
  return (
    error instanceof ApiError
    && (error.status === 404 || error.code === "RESOURCE_NOT_FOUND")
  );
}
