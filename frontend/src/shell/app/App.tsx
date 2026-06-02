import { QueryClientProvider } from "@tanstack/react-query";
import { useMemo } from "react";
import { ApiClientProvider } from "../data/apiRuntime";
import { AppBootstrap } from "./bootstrap/AppBootstrap";
import { createAppQueryClient } from "./query/queryClient";

export default function App() {
  const queryClient = useMemo(() => createAppQueryClient(), []);
  const baseUrl = useMemo(() => {
    const env =
      (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env || {};
    return env.VITE_API_BASE_URL || "";
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider baseUrl={baseUrl}>
        <AppBootstrap />
      </ApiClientProvider>
    </QueryClientProvider>
  );
}
