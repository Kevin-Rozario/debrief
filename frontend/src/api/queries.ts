import type { QueryClient } from "@tanstack/react-query";
import type {
  AddendumResponse,
  BookConsultationRequest,
  ConsultationDetailResponse,
  ConsultationResponse,
  NoteResponse,
  PersonResponse,
  PractitionerResponse,
} from "./types.ts";
import {
  keepPreviousData,
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { ApiError, readTicket, request } from "./client.ts";

/** Separate from each visit so refreshing the list does not refetch every open detail. */
export const peopleKey = ["people"] as const;
export const practitionersKey = ["practitioners"] as const;
export const consultationListKey = ["consultations", "list"] as const;

export function consultationDetailKey(consultationId: number) {
  return ["consultations", "detail", consultationId] as const;
}

export function peopleOptions() {
  return queryOptions({
    queryKey: peopleKey,
    queryFn: () => request<PersonResponse[]>("/people"),
    retry: retryUnlessClientError,
  });
}

export function practitionersOptions() {
  return queryOptions({
    queryKey: practitionersKey,
    queryFn: () => request<PractitionerResponse[]>("/practitioners"),
    enabled: readTicket() !== null,
    retry: retryUnlessClientError,
  });
}

export function consultationListOptions() {
  return queryOptions({
    queryKey: consultationListKey,
    queryFn: () => request<ConsultationResponse[]>("/consultations"),
    enabled: readTicket() !== null,
    placeholderData: keepPreviousData,
    retry: retryUnlessClientError,
  });
}

export function consultationDetailOptions(consultationId: number) {
  return queryOptions({
    queryKey: consultationDetailKey(consultationId),
    queryFn: () =>
      request<ConsultationDetailResponse>(`/consultations/${consultationId}`),
    enabled: readTicket() !== null,
    retry: retryUnlessClientError,
  });
}

/** Warm one visit before it opens. A miss stays on the row and does not surface. */
export function prefetchConsultation(
  queryClient: QueryClient,
  consultationId: number,
) {
  const options = consultationDetailOptions(consultationId);
  if (!options.enabled) {
    return Promise.resolve();
  }
  return queryClient.query(options).then(
    () => undefined,
    () => undefined,
  );
}

export function usePeople() {
  return useQuery(peopleOptions());
}

export function usePractitioners() {
  return useQuery(practitionersOptions());
}

export function useConsultationList() {
  return useQuery(consultationListOptions());
}

export function useConsultation(consultationId: number) {
  return useQuery(consultationDetailOptions(consultationId));
}

export function useBookConsultation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: BookConsultationRequest) =>
      request<ConsultationResponse>("/consultations", { method: "POST", body }),
    onSuccess: async consultation =>
      refreshVisit(queryClient, consultation.id),
  });
}

export function useCancelConsultation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (consultationId: number) =>
      request<ConsultationResponse>(`/consultations/${consultationId}/cancel`, {
        method: "POST",
      }),
    onSuccess: async (_consultation, consultationId) =>
      refreshVisit(queryClient, consultationId),
  });
}

export function useCompleteConsultation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (consultationId: number) =>
      request<ConsultationResponse>(
        `/consultations/${consultationId}/complete`,
        { method: "POST" },
      ),
    onSuccess: async (_consultation, consultationId) =>
      refreshVisit(queryClient, consultationId),
  });
}

export function useCreateNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ consultationId, body }: NoteWrite) =>
      request<NoteResponse>(`/consultations/${consultationId}/note`, {
        method: "POST",
        body: { body },
      }),
    onSuccess: async (_note, { consultationId }) =>
      refreshVisit(queryClient, consultationId),
  });
}

export function useUpdateNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ consultationId, body }: NoteWrite) =>
      request<NoteResponse>(`/consultations/${consultationId}/note`, {
        method: "PATCH",
        body: { body },
      }),
    onSuccess: async (_note, { consultationId }) =>
      refreshVisit(queryClient, consultationId),
  });
}

export function useDeleteNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (consultationId: number) =>
      request<null>(`/consultations/${consultationId}/note`, {
        method: "DELETE",
      }),
    onSuccess: async (_empty, consultationId) =>
      refreshVisit(queryClient, consultationId),
  });
}

export function useShareNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (consultationId: number) =>
      request<NoteResponse>(`/consultations/${consultationId}/note/share`, {
        method: "POST",
      }),
    onSuccess: async (_note, consultationId) =>
      refreshVisit(queryClient, consultationId),
  });
}

export function useAddAddendum() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ consultationId, body }: NoteWrite) =>
      request<AddendumResponse>(
        `/consultations/${consultationId}/note/addenda`,
        {
          method: "POST",
          body: { body },
        },
      ),
    onSuccess: async (_addendum, { consultationId }) =>
      refreshVisit(queryClient, consultationId),
  });
}

interface NoteWrite {
  consultationId: number;
  body: string;
}

async function refreshVisit(queryClient: QueryClient, consultationId: number) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: consultationListKey }),
    queryClient.invalidateQueries({
      queryKey: consultationDetailKey(consultationId),
    }),
  ]);
}

function retryUnlessClientError(failureCount: number, error: Error) {
  if (error instanceof ApiError && error.status < 500) {
    return false;
  }
  return failureCount < 3;
}
