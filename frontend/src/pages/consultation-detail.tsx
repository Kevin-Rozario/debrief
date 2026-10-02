import type { ConsultationDetailResponse, PersonResponse, PractitionerResponse } from "@/api/types.ts";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { ApiError, readTicket } from "@/api/client.ts";
import {
  consultationDetailOptions,
  practitionersOptions,
  useCancelConsultation,
  useCompleteConsultation,
  usePeople,
} from "@/api/queries.ts";
import { useSession } from "@/auth/session.tsx";
import { StatusBadge } from "@/components/status-badge.tsx";
import { TopBar } from "@/components/top-bar.tsx";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { formatConsultationTime } from "@/lib/time.ts";
import { cn } from "@/lib/utils.ts";

const NOT_FOUND = "The requested resource was not found.";

export function ConsultationDetail() {
  const params = useParams();
  const consultationId = Number(params.id);
  const validId = Number.isInteger(consultationId) && consultationId > 0;
  const { person } = useSession();
  const people = usePeople();
  const detailOptions = consultationDetailOptions(validId ? consultationId : 0);
  const consultation = useQuery({
    ...detailOptions,
    enabled: validId && detailOptions.enabled !== false,
  });
  const practitionerOptions = practitionersOptions();
  const practitioners = useQuery({
    ...practitionerOptions,
    enabled: person?.role === "client" && readTicket() !== null,
  });
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

  const missing = !validId || (consultation.isError && visit === undefined && isMissing(consultation.error));
  const loading = validId && visit === undefined && !consultation.isError;

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-160 flex-col px-6 py-8">
      <TopBar />
      {missing
        ? <MissingVisit />
        : null}
      {loading || visit === undefined || missing
        ? null
        : (
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
          )}
      {!missing && consultation.isError && visit === undefined
        ? (
            <>
              <p className="mt-10" role="alert">
                {loadError(consultation.error)}
              </p>
              <BackToList />
            </>
          )
        : null}
    </main>
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
  const otherId = visit.client_id === caller.id ? visit.practitioner_id : visit.client_id;
  const foundSpecialty = caller.role === "client"
    ? practitioners.find(practitioner => practitioner.id === otherId)?.specialty
    : null;
  const specialty = foundSpecialty !== undefined && foundSpecialty !== null && foundSpecialty.trim() !== ""
    ? foundSpecialty
    : null;
  const cancelledByName = visit.status === "cancelled" && visit.cancelled_by_id !== null
    ? personName(visit.cancelled_by_id, people)
    : "";
  const cancelledBy = cancelledByName === "" ? null : cancelledByName;
  const scheduled = visit.status === "scheduled";
  const showCancel = scheduled;
  const showComplete = caller.role === "practitioner" && scheduled && started;
  const showHint = caller.role === "practitioner" && scheduled && !started;

  return (
    <>
      <div className="mt-10">
        <StatusBadge status={visit.status} />
        <h1 className="mt-3 text-4xl font-light">{personName(otherId, people)}</h1>
        {specialty
          ? <p className="mt-2 text-stone-500 dark:text-stone-400">{specialty}</p>
          : null}
      </div>
      <div className="mt-8">
        <p>{time.detailWhen}</p>
        <p className="text-sm text-stone-500 dark:text-stone-400">{time.utcRange}</p>
      </div>
      {cancelledBy
        ? <p className="mt-8">{`Cancelled by ${cancelledBy}`}</p>
        : null}
      {showHint
        ? <p className="mt-8">You can mark this completed once the start time has passed.</p>
        : null}
      {showCancel || showComplete
        ? (
            <div className="mt-8 flex flex-wrap gap-3">
              {showCancel
                ? (
                    <Button
                      variant="outline"
                      className="border-red-800 text-red-800 hover:bg-red-50 hover:text-red-800 dark:border-red-400 dark:text-red-400 dark:hover:bg-red-950 dark:hover:text-red-400"
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
      <BackToList />
    </>
  );
}

function BackToList() {
  return (
    <Link
      to="/consultations"
      className={cn(buttonVariants({ variant: "outline" }), "mt-8 w-fit")}
    >
      Back to consultations
    </Link>
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
    setActionError(caught instanceof ApiError ? caught.message : "The consultation could not be updated.");
  }
}

function personName(personId: number, people: PersonResponse[]) {
  return people.find(person => person.id === personId)?.name ?? "";
}

function isMissing(error: unknown) {
  return error instanceof ApiError && (error.status === 404 || error.code === "RESOURCE_NOT_FOUND");
}

function loadError(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "The consultation could not be loaded.";
}
