import type { ReactNode } from "react";
import { Link } from "react-router";
import { TopBar } from "@/components/top-bar.tsx";
import { buttonVariants } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils.ts";

const column = "mx-auto flex min-h-dvh w-full max-w-160 flex-col px-6 py-8";

export function PageColumn({ children }: { children: ReactNode }) {
  return <main className={column}>{children}</main>;
}

export function SignedInPage({
  children,
  back = false,
}: {
  children: ReactNode;
  back?: boolean;
}) {
  return (
    <PageColumn>
      <TopBar />
      <Separator className="my-5 bg-stone-200 dark:bg-stone-800" />
      {back ? <BackToConsultations className="mt-4" /> : null}
      {children}
    </PageColumn>
  );
}

export function BackToConsultations({
  variant = "text",
  className,
}: {
  variant?: "text" | "button";
  className?: string;
}) {
  if (variant === "button") {
    return (
      <Link
        to="/consultations"
        className={cn(buttonVariants({ variant: "outline" }), "w-fit", className)}
      >
        Back to consultations
      </Link>
    );
  }

  return (
    <Link
      to="/consultations"
      className={cn(
        "w-fit text-sm text-stone-500 underline-offset-4 outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 dark:text-stone-400",
        className,
      )}
    >
      Back to consultations
    </Link>
  );
}
