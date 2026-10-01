import type { PersonResponse } from "@/api/types.ts";
import { useState, useSyncExternalStore } from "react";
import { useNavigate } from "react-router";
import { ApiError } from "@/api/client.ts";
import { usePeople } from "@/api/queries.ts";
import { useSession } from "@/auth/session.tsx";
import { storeTheme } from "@/lib/theme.ts";

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
  const theme = useAppliedTheme();
  const [pendingId, setPendingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const message = error ?? loadError(people.error);

  async function choose(person: PersonResponse) {
    if (pendingId !== null) {
      return;
    }
    setError(null);
    setPendingId(person.id);
    try {
      await signIn(person.id);
      await navigate("/consultations");
    } catch (caught) {
      setPendingId(null);
      setError(caught instanceof ApiError ? caught.message : "Sign-in failed.");
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-160 flex-col px-6 py-8">
      <header className="flex items-center justify-between gap-4">
        <p className="text-lg">Debrief</p>
        <button
          type="button"
          className="text-sm transition-transform hover:-translate-y-px active:translate-y-px motion-reduce:transform-none"
          onClick={() => storeTheme(theme === "dark" ? "light" : "dark")}
        >
          {theme === "dark" ? "Use light" : "Use dark"}
        </button>
      </header>
      <h1 className="mt-10 text-xl">Choose a person</h1>
      {message === null ? null : (
        <p className="mt-2" role="alert">
          {message}
        </p>
      )}
      <p className="mt-2 text-stone-600 dark:text-stone-400">
        No password. Picking someone signs you in as them.
      </p>
      <ul className="mt-8">
        {orderedPeople(people.data ?? []).map((person) => (
          <li
            key={person.id}
            className="border-b border-stone-200 dark:border-stone-800"
          >
            <button
              type="button"
              className="flex w-full items-baseline justify-between gap-4 py-4 text-left transition-transform hover:-translate-y-px active:translate-y-px motion-reduce:transform-none"
              aria-label={`Sign in as ${person.name}`}
              onClick={() => void choose(person)}
            >
              {pendingId === person.id ? (
                <span className="text-2xl">Signing in…</span>
              ) : (
                <>
                  <span className="text-2xl">{person.name}</span>
                  <span className="text-sm text-stone-500">
                    {roleLabel(person.role)}
                  </span>
                </>
              )}
            </button>
          </li>
        ))}
      </ul>
    </main>
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

function loadError(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error == null) {
    return null;
  }
  return "The people list could not be loaded.";
}

function useAppliedTheme() {
  return useSyncExternalStore(
    subscribeThemeClass,
    readThemeClass,
    () => "light" as const,
  );
}

function readThemeClass() {
  return document.documentElement.classList.contains("dark")
    ? ("dark" as const)
    : ("light" as const);
}

function subscribeThemeClass(listener: () => void) {
  const observer = new MutationObserver(listener);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });
  return () => observer.disconnect();
}
