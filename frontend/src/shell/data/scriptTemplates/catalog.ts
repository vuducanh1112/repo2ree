import { useQuery } from "@tanstack/react-query";
import { useApiRuntime } from "../apiRuntime";
import { queryKeys } from "../queryKeys";

// The backend-owned starter templates for the REE-owned scripts (build,
// activation, per-experiment run/verify). They are packaged with the backend
// (core reserved_templates) and static for a session, so cache indefinitely
// and share across every script editor.
export function useScriptTemplates() {
  const { reeApi } = useApiRuntime();
  return useQuery({
    queryKey: queryKeys.scriptTemplates(),
    queryFn: async () => reeApi.listScriptTemplates(),
    staleTime: Number.POSITIVE_INFINITY,
  });
}
