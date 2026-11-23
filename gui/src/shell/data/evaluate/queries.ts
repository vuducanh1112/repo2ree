import { parseReproducibilityReport, type ReproducibilityReport } from "@core/evaluate/Threat";
import { useQuery } from "@tanstack/react-query";
import { useReeRuntime } from "../apiRuntime";
import { requireReeId, resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";

export function useEvaluateReportQuery({
  reeId,
  enabled = true,
}: {
  reeId?: string;
  enabled?: boolean;
}) {
  const runtime = useReeRuntime();
  const resolvedReeId = resolveReeId(runtime, reeId);
  return useQuery<ReproducibilityReport | null>({
    queryKey: queryKeys.evaluateReport(resolvedReeId),
    queryFn: async () => {
      const realReeId = requireReeId(runtime, reeId);
      const raw = await runtime.reeApi.getReproducibilityReport(realReeId);
      return parseReproducibilityReport(raw);
    },
    enabled: enabled && !!resolvedReeId,
    retry: false,
  });
}
