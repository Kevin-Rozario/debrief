import type { ConsultationResponse } from "@/api/types.ts";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";
import { errorMessage } from "@/api/client.ts";
import {
  prefetchConsultation,
  useConsultationList,
  usePeople,
} from "@/api/queries.ts";
import { useSession } from "@/auth/session.tsx";
import { SignedInPage } from "@/components/page-column.tsx";
import { StatusBadge } from "@/components/status-badge.tsx";
import { otherPersonId, personName } from "@/lib/people.ts";
import { formatConsultationTime } from "@/lib/time.ts";

export function ConsultationList() {
  const { person } = useSession();
  const people = usePeople();
  const consultations = useConsultationList();
  const queryClient = useQueryClient();
  const message = errorMessage(
    consultations.error,
    "The consultation list could not be loaded.",
  );
  const rows = orderedConsultations(consultations.data);
  const showRows = consultations.data !== undefined && rows.length > 0;
  const showEmpty =
    consultations.data !== undefined && rows.length === 0 && message === null;

  if (person === null) {
    return null;
  }

  return (
    <SignedInPage>
      <h1 className="mt-4 text-4xl font-light">Consultations</h1>
      {message === null ? null : (
        <p className="mt-2" role="alert">
          {message}
        </p>
      )}
      {showEmpty ? (
        <div className="mt-8">
          <p>You have no consultations.</p>
          {person.role === "client" ? (
            <p>
              <Link
                to="/book"
                className="rounded-sm underline-offset-4 outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                Book one with a practitioner.
              </Link>
            </p>
          ) : null}
        </div>
      ) : null}
      {showRows ? (
        <ul className="mt-8">
          {rows.map((consultation) => {
            const time = formatConsultationTime(
              consultation.starts_at,
              consultation.ends_at,
            );
            const name = personName(
              people.data ?? [],
              otherPersonId(consultation, person.id),
            );
            return (
              <li
                key={consultation.id}
                className="border-b border-stone-200 dark:border-stone-800"
              >
                <Link
                  to={`/consultations/${consultation.id}`}
                  className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-6 gap-y-1 rounded-sm py-6 px-3 outline-none hover:bg-stone-100 focus-visible:ring-3 focus-visible:ring-ring/50 active:translate-y-px motion-reduce:transition-none motion-reduce:active:translate-y-0 dark:hover:bg-stone-900"
                  onMouseEnter={() => {
                    void prefetchConsultation(queryClient, consultation.id);
                  }}
                  onFocus={() => {
                    void prefetchConsultation(queryClient, consultation.id);
                  }}
                >
                  <p>{time.listDate}</p>
                  <p className="text-right text-xl font-light">{name}</p>
                  <p>{time.localRange}</p>
                  <span className="justify-self-end">
                    <StatusBadge status={consultation.status} />
                  </span>
                  <p className="text-sm text-stone-500 dark:text-stone-400">
                    {time.utcRange}
                  </p>
                </Link>
              </li>
            );
          })}
        </ul>
      ) : null}
    </SignedInPage>
  );
}

function orderedConsultations(
  consultations: ConsultationResponse[] | undefined,
) {
  return [...(consultations ?? [])].sort((left, right) => {
    const byStart = left.starts_at.localeCompare(right.starts_at);
    if (byStart !== 0) {
      return byStart;
    }
    return left.id - right.id;
  });
}
