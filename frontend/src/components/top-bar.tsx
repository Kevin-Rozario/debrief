import { Link } from "react-router";
import { useSession } from "@/auth/session.tsx";
import { ThemeToggle } from "@/components/theme-toggle.tsx";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils.ts";

export function TopBar() {
  const { person, signOut } = useSession();

  if (person === null) {
    return null;
  }

  return (
    <header className="flex items-start justify-between gap-4">
      <Link
        to="/consultations"
        className="rounded-sm text-2xl font-bold tracking-tighter outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        Debrief
      </Link>
      <div className="flex flex-col items-end gap-2">
        <p className="font-medium">{`${person.name}, ${person.role}`}</p>
        <div className="flex flex-wrap items-center justify-end gap-1">
          <ThemeToggle />
          <Button
            variant="ghost"
            className="text-sm motion-reduce:transition-none motion-reduce:active:translate-y-0"
            onClick={signOut}
          >
            Sign out
          </Button>
          {person.role === "client"
            ? (
                <Link
                  to="/book"
                  className={cn(
                    buttonVariants(),
                    "rounded-full bg-stone-900 px-4 text-stone-50 hover:bg-stone-800 dark:bg-stone-100 dark:text-stone-900 dark:hover:bg-stone-200 motion-reduce:transition-none motion-reduce:active:translate-y-0",
                  )}
                >
                  Book
                </Link>
              )
            : null}
        </div>
      </div>
    </header>
  );
}
