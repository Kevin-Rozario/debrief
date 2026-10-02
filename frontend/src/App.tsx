import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { useSession } from "@/auth/session.tsx";
import { TopBar } from "@/components/top-bar.tsx";
import { SignIn } from "@/pages/sign-in.tsx";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={(
            <SignedOutRoute>
              <SignIn />
            </SignedOutRoute>
          )}
        />
        <Route
          path="/consultations"
          element={(
            <SignedInRoute>
              <Placeholder label="Consultations" />
            </SignedInRoute>
          )}
        />
        <Route
          path="/consultations/:id"
          element={(
            <SignedInRoute>
              <Placeholder label="Visit" />
            </SignedInRoute>
          )}
        />
        <Route
          path="/book"
          element={(
            <ClientRoute>
              <Placeholder label="Book" />
            </ClientRoute>
          )}
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

function Placeholder({ label }: { label: string }) {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-160 flex-col px-6 py-8">
      <TopBar />
      <p className="mt-8">{label}</p>
    </main>
  );
}

function SignedOutRoute({ children }: { children: ReactNode }) {
  const { status } = useSession();
  if (status === "loading") {
    return null;
  }
  if (status === "signed-in") {
    return <Navigate to="/consultations" replace />;
  }
  return children;
}

function SignedInRoute({ children }: { children: ReactNode }) {
  const { status } = useSession();
  if (status === "loading") {
    return null;
  }
  if (status === "signed-out") {
    return <Navigate to="/" replace />;
  }
  return children;
}

function ClientRoute({ children }: { children: ReactNode }) {
  const { status, person } = useSession();
  if (status === "loading") {
    return null;
  }
  if (status === "signed-out") {
    return <Navigate to="/" replace />;
  }
  if (person?.role !== "client") {
    return <Navigate to="/consultations" replace />;
  }
  return children;
}
