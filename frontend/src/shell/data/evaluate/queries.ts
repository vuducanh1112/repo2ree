import { useQuery } from "@tanstack/react-query";
import {
  parseReproducibilityReport,
  type ReproducibilityReport,
} from "../../../core/evaluate/Threat";
import { useApiRuntime } from "../apiRuntime";
import { ensureReeId, resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";

/**
 * Fetch the reproducibility threat report for an REE. The report is a standalone
 * artifact written by the evaluate run; it 404s until the first run completes, so
 * gate `enabled` on a completed run.
 */
export function useEvaluateReportQuery({
  reeId,
  enabled = true,
}: {
  reeId?: string;
  enabled?: boolean;
}) {
  const runtime = useApiRuntime();
  // Key on the (possibly sentinel) requested id, like useReeQuery; resolve the real
  // workspace id inside the queryFn so we don't hit the literal "active" alias.
  const resolvedReeId = resolveReeId(runtime, reeId);
  return useQuery<ReproducibilityReport | null>({
    queryKey: queryKeys.evaluateReport(resolvedReeId),
    queryFn: async () => {
      const realReeId = await ensureReeId(runtime, reeId);
      const raw = await runtime.reeApi.getEvaluateReport(realReeId);
      return parseReproducibilityReport(raw);
    },
    enabled: enabled && !!resolvedReeId,
    retry: false,
  });
}
