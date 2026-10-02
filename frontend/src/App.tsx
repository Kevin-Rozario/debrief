import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { useSession } from "@/auth/session.tsx";
import { BookConsultation } from "@/pages/book-consultation.tsx";
import { ConsultationDetail } from "@/pages/consultation-detail.tsx";
import { ConsultationList } from "@/pages/consultation-list.tsx";
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
              <ConsultationList />
            </SignedInRoute>
          )}
        />
        <Route
          path="/consultations/:id"
          element={(
            <SignedInRoute>
              <ConsultationDetail />
            </SignedInRoute>
          )}
        />
        <Route
          path="/book"
          element={(
            <ClientRoute>
              <BookConsultation />
            </ClientRoute>
          )}
        />
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
