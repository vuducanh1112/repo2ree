import { useQuery } from "@tanstack/react-query";
import { useApiServices } from "../apiRuntime";
import { queryKeys } from "../queryKeys";

// UI components take template lists as props; surface the entry type here so
// they don't have to reach into the infra layer for it.
export type { ScriptTemplateEntry } from "@shell/infra/api/apiTypes";

// The backend-owned starter templates for the REE-owned scripts (build,
// activation, per-experiment run/verify). They are packaged with the backend
// (core reserved_templates) and static for a session, so cache indefinitely
// and share across every script editor.
export function useScriptTemplates() {
  const { reeApi } = useApiServices();
  return useQuery({
    queryKey: queryKeys.scriptTemplates(),
    queryFn: async () => reeApi.listScriptTemplates(),
    staleTime: Number.POSITIVE_INFINITY,
  });
}
