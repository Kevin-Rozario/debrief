import { Link, useLocation } from "react-router";
import { useSession } from "@/auth/session.tsx";
import { ResetExampleButton } from "@/components/reset-example.tsx";
import { ThemeToggle } from "@/components/theme-toggle.tsx";
import { Button, buttonVariants } from "@/components/ui/button";
import { stonePill } from "@/lib/controls.ts";
import { cn } from "@/lib/utils.ts";

export function TopBar() {
  const { person, signOut } = useSession();
  const { pathname } = useLocation();

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
          <ResetExampleButton />
          <Button variant="ghost" className="text-sm" onClick={signOut}>
            Sign out
          </Button>
          {person.role === "client" && pathname !== "/book"
            ? (
                <Link to="/book" className={cn(buttonVariants(), stonePill)}>
                  Book
                </Link>
              )
            : null}
        </div>
      </div>
    </header>
  );
}
