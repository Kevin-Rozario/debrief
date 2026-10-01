import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { useSession } from "@/auth/session.tsx";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={<SignedOutRoute>Choose a person</SignedOutRoute>}
        />
        <Route
          path="/consultations"
          element={<SignedInRoute>Consultations</SignedInRoute>}
        />
        <Route
          path="/consultations/:id"
          element={<SignedInRoute>Visit</SignedInRoute>}
        />
        <Route path="/book" element={<ClientRoute>Book</ClientRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
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
