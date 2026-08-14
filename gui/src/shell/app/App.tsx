import { QueryClientProvider } from "@tanstack/react-query";
import { useMemo } from "react";
import { ApiServicesProvider } from "../data/apiRuntime";
import type { UiErrorReporter } from "../ui/errors/ErrorBoundary";
import { AppBootstrap } from "./bootstrap/AppBootstrap";
import { createAppQueryClient } from "./query/queryClient";

interface AppProps {
  reportError: UiErrorReporter;
}

export default function App({ reportError }: AppProps) {
  const queryClient = useMemo(() => createAppQueryClient(), []);
  const baseUrl = useMemo(() => {
    const env =
      (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env || {};
    return env.VITE_API_BASE_URL || "";
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <ApiServicesProvider baseUrl={baseUrl}>
        <AppBootstrap reportError={reportError} />
      </ApiServicesProvider>
    </QueryClientProvider>
  );
}
