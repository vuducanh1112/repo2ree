import { QueryClientProvider } from "@tanstack/react-query";
import { useMemo } from "react";
import { AppBootstrap } from "./app/bootstrap/AppBootstrap";
import { DEFAULT_REE_ID } from "./app/config/ReeConstants";
import { createAppQueryClient } from "./app/query/queryClient";
import { ApiClientProvider } from "./data/apiRuntime";
import { AppShellProvider } from "./ui/app-shell/providers/AppShellProvider";

export default function App() {
  const queryClient = useMemo(() => createAppQueryClient(), []);
  const runtimeConfig = useMemo(() => {
    const env =
      (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env || {};
    const reeIdFromQuery =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("reeId") || undefined
        : undefined;
    return {
      baseUrl: env.VITE_API_BASE_URL || "",
      initialReeId: reeIdFromQuery,
    };
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider
        baseUrl={runtimeConfig.baseUrl}
        initialReeId={runtimeConfig.initialReeId}
        reeId={DEFAULT_REE_ID}
      >
        <AppShellProvider>
          <AppBootstrap />
        </AppShellProvider>
      </ApiClientProvider>
    </QueryClientProvider>
  );
}
