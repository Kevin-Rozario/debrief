import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { SessionProvider } from "@/auth/session.tsx";
import { startTheme } from "@/lib/theme.ts";
import App from "./App.tsx";
import "./index.css";

const queryClient = new QueryClient();

startTheme();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <App />
      </SessionProvider>
    </QueryClientProvider>
  </StrictMode>,
);
