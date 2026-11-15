import { DEFAULT_REE_ID } from "@core/ree/ReeId";
import { useQuery } from "@tanstack/react-query";
import { useReeRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";

// UI components take template lists as props; surface the entry type here so
// they don't have to reach into the infra layer for it.
export type { ScriptTemplateEntry } from "@shell/infra/api/apiTypes";

// The starter templates for the REE-owned scripts (build, activation,
// per-experiment run/verify), as the command line on the REE's workbench
// prints them. Static for that command line, so cache indefinitely and share
// across every script editor of the REE.
export function useScriptTemplates() {
  const runtime = useReeRuntime();
  const reeId = resolveReeId(runtime);
  return useQuery({
    queryKey: queryKeys.scriptTemplates(reeId),
    queryFn: async () => runtime.reeApi.listScriptTemplates(reeId),
    enabled: reeId !== DEFAULT_REE_ID,
    staleTime: Number.POSITIVE_INFINITY,
  });
}
