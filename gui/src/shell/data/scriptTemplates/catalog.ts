import { DEFAULT_REE_ID } from "@core/ree/ReeId";
import { useQuery } from "@tanstack/react-query";
import { useReeRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";

export type { ScriptTemplateEntry } from "@shell/infra/api/apiTypes";

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
