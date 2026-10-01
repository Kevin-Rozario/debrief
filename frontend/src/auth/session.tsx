import type { QueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { PersonResponse, TokenResponseData } from "@/api/types.ts";
import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  use,
  useEffect,
  useState,
  useSyncExternalStore,
} from "react";
import {
  clearTicket,
  readTicket,
  request,
  storeTicket,
  subscribeTicket,
} from "@/api/client.ts";
import { practitionersKey, usePeople } from "@/api/queries.ts";

const PERSON_STORAGE_KEY = "debrief.person";

export type SessionStatus = "signed-out" | "loading" | "signed-in";

export interface SessionState {
  status: SessionStatus;
  person: PersonResponse | null;
  signIn: (personId: number) => Promise<void>;
  signOut: () => void;
}

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const ticket = useSyncTicket();
  const people = usePeople();
  const [personId, setPersonId] = useState<number | null>(readPersonId);

  useEffect(() => {
    if (ticket !== null) {
      setPersonId(readPersonId());
      return;
    }
    clearPersonId();
    setPersonId(null);
  }, [ticket]);

  const person
    = ticket === null || personId === null
      ? null
      : (people.data?.find(item => item.id === personId) ?? null);

  useEffect(() => {
    if (ticket === null || !people.isSuccess) {
      return;
    }
    const known = people.data.some(item => item.id === personId);
    if (!known) {
      clearTicket();
    }
  }, [ticket, personId, people.isSuccess, people.data]);

  async function signIn(personIdToStore: number) {
    const issued = await request<TokenResponseData>("/auth/login", {
      method: "POST",
      body: { person_id: personIdToStore },
    });
    clearSignedInQueries(queryClient);
    storePersonId(personIdToStore);
    setPersonId(personIdToStore);
    storeTicket(issued.token);
  }

  function signOut() {
    clearSignedInQueries(queryClient);
    clearTicket();
  }

  let status: SessionStatus = "loading";
  if (ticket === null || (people.isSuccess && person === null)) {
    status = "signed-out";
  }
  else if (person !== null) {
    status = "signed-in";
  }

  const value: SessionState = { status, person, signIn, signOut };

  return <SessionContext value={value}>{children}</SessionContext>;
}

export function useSession() {
  const session = use(SessionContext);
  if (session === null) {
    throw new Error("useSession must be used within SessionProvider.");
  }
  return session;
}

function useSyncTicket() {
  return useSyncExternalStore(subscribeTicket, readTicket, () => null);
}

function readPersonId() {
  const raw = localStorage.getItem(PERSON_STORAGE_KEY);
  if (raw === null) {
    return null;
  }
  const personId = Number(raw);
  if (!Number.isInteger(personId) || personId <= 0) {
    return null;
  }
  return personId;
}

function storePersonId(personId: number) {
  localStorage.setItem(PERSON_STORAGE_KEY, String(personId));
}

function clearPersonId() {
  localStorage.removeItem(PERSON_STORAGE_KEY);
}

function clearSignedInQueries(queryClient: QueryClient) {
  queryClient.removeQueries({ queryKey: ["consultations"] });
  queryClient.removeQueries({ queryKey: practitionersKey });
}
