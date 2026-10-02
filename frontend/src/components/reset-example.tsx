import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";
import { ApiError, request } from "@/api/client.ts";
import { peopleKey } from "@/api/queries.ts";
import { useSession } from "@/auth/session.tsx";
import { Button } from "@/components/ui/button";

export function ResetExampleButton() {
  const queryClient = useQueryClient();
  const { signOut } = useSession();
  const navigate = useNavigate();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function reset() {
    if (pending) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      await request<null>("/seed/reset", { method: "POST" });
      signOut();
      await queryClient.invalidateQueries({ queryKey: peopleKey });
      await navigate("/");
    }
    catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The example data could not be restored.");
    }
    finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button variant="ghost" className="text-sm" onClick={() => void reset()}>
        {pending ? "Resetting…" : "Reset example"}
      </Button>
      {error === null
        ? null
        : (
            <p className="max-w-48 text-right text-sm" role="alert">
              {error}
            </p>
          )}
    </div>
  );
}
