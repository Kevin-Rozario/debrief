import type { PersonResponse } from "@/api/types.ts";
import { useState } from "react";
import { useNavigate } from "react-router";
import { ApiError, errorMessage } from "@/api/client.ts";
import { usePeople } from "@/api/queries.ts";
import { useSession } from "@/auth/session.tsx";
import { PageColumn } from "@/components/page-column.tsx";
import { ThemeToggle } from "@/components/theme-toggle.tsx";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

const PERSON_ORDER = [
  "Priya",
  "Rohan",
  "Meera",
  "Dr. Asha Rao",
  "Dr. Vikram Shah",
];

export function SignIn() {
  const people = usePeople();
  const { signIn } = useSession();
  const navigate = useNavigate();
  const [pendingId, setPendingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const message = error ?? errorMessage(people.error, "The people list could not be loaded.");

  async function choose(person: PersonResponse) {
    if (pendingId !== null) {
      return;
    }
    setError(null);
    setPendingId(person.id);
    try {
      await signIn(person.id);
      await navigate("/consultations");
    }
    catch (caught) {
      setPendingId(null);
      setError(caught instanceof ApiError ? caught.message : "Sign-in failed.");
    }
  }

  return (
    <PageColumn>
      <header className="flex items-center justify-between gap-4">
        <p className="text-2xl font-bold tracking-tighter">Debrief</p>
        <ThemeToggle />
      </header>
      <Separator className="my-5 bg-stone-200 dark:bg-stone-800" />
      <p className="uppercase text-sm tracking-wider mt-6">
        Welcome to the Debrief
      </p>
      <h1 className="mt-4 text-4xl font-light">Choose a person</h1>
      {message === null
        ? null
        : (
            <p className="mt-2" role="alert">
              {message}
            </p>
          )}
      <p className="mt-4 text-stone-500 dark:text-stone-400">
        No password. Picking someone signs you in as them.
      </p>
      <ul className="mt-8">
        {orderedPeople(people.data ?? []).map(person => (
          <li
            key={person.id}
            className="border-b border-stone-200 dark:border-stone-800"
          >
            <Button
              variant="ghost"
              className="flex w-full items-center justify-between gap-4 py-8 text-left"
              aria-label={`Sign in as ${person.name}`}
              onClick={() => void choose(person)}
            >
              {pendingId === person.id
                ? (
                    <span className="text-2xl">Signing in…</span>
                  )
                : (
                    <>
                      <span className="text-xl font-light">{person.name}</span>
                      <span className="text-sm font-light text-stone-500 dark:text-stone-400">
                        {roleLabel(person.role)}
                      </span>
                    </>
                  )}
            </Button>
          </li>
        ))}
      </ul>
    </PageColumn>
  );
}

function orderedPeople(people: PersonResponse[]) {
  return [...people].sort((left, right) => rank(left.name) - rank(right.name));
}

function rank(name: string) {
  const index = PERSON_ORDER.indexOf(name);
  return index === -1 ? PERSON_ORDER.length : index;
}

function roleLabel(role: PersonResponse["role"]) {
  return role === "client" ? "Client" : "Practitioner";
}
