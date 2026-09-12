import { useQuery } from "@tanstack/react-query";
import { useReeRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";

export function useOperationHistoryQuery(enabled: boolean) {
  const runtime = useReeRuntime();
  const reeId = resolveReeId(runtime);
  return useQuery({
    queryKey: queryKeys.history(reeId),
    queryFn: () => runtime.reeApi.listOperationHistory(reeId),
    enabled: enabled && !!runtime.reeId,
    refetchInterval: enabled ? 5000 : false,
  });
}
