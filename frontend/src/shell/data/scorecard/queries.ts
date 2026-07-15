import { isTerminalReeRunStatus } from "@core/runs/ReeRunStatus";
import {
  parseReproducibilityScoreCard,
  type ReproducibilityScoreCard,
} from "@core/scorecard/ReproducibilityScoreCard";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useApiRuntime } from "../apiRuntime";
import { ensureReeId, resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";
import { useReeRunsQuery } from "../runs/queries";

/**
 * Fetch the reproducibility scorecard for the active REE. The backend
 * recomputes it from the persisted record (intent + session + run receipts)
 * on every read; the query is keyed on the REE alone and refetched by
 * invalidation whenever the record changes — run completions via
 * useScorecardRunSync, seals and intent patches at their mutation sites.
 * Multiple subscribers share one request via the common key.
 */
export function useReproducibilityScoreCard({ enabled = true }: { enabled?: boolean } = {}) {
  const runtime = useApiRuntime();
  const { reeId } = runtime;
  // Key on the (possibly sentinel) requested id, like useReeQuery; resolve the real
  // workspace id inside the queryFn so we don't hit the literal "active" alias.
  const resolvedReeId = resolveReeId(runtime, reeId);
  return useQuery<ReproducibilityScoreCard | null>({
    queryKey: queryKeys.scorecard(resolvedReeId),
    queryFn: async () => {
      const realReeId = await ensureReeId(runtime, reeId);
      const raw = await runtime.reeApi.getScorecard(realReeId);
      return parseReproducibilityScoreCard(raw);
    },
    enabled: enabled && !!resolvedReeId,
    retry: false,
    // The superseded card keeps showing while the fresh one loads.
    placeholderData: (previous) => previous,
  });
}

/**
 * Invalidate the scorecard whenever a run reaches a terminal status — the
 * client-side moment a receipt lands (or a failure supersedes one). Piggybacks
 * on the always-polled runs listing, so runs started outside this tab (e.g.
 * by an agent) are covered too. Mount exactly once, in the app shell.
 */
export function useScorecardRunSync() {
  const runtime = useApiRuntime();
  const queryClient = useQueryClient();
  const resolvedReeId = resolveReeId(runtime, runtime.reeId);
  const runsQuery = useReeRunsQuery();
  const terminalRunIds = (runsQuery.data ?? [])
    .filter((run) => isTerminalReeRunStatus(run.status))
    .map((run) => run.runId)
    .sort()
    .join(",");

  const previousRef = useRef<string | null>(null);
  useEffect(() => {
    const previous = previousRef.current;
    previousRef.current = terminalRunIds;
    // The first listing is history, not news — the query's own initial fetch
    // already reflects it.
    if (previous === null || previous === terminalRunIds) return;
    void queryClient.invalidateQueries({ queryKey: queryKeys.scorecard(resolvedReeId) });
    // The evaluate report is also run-derived: the cross-check step rewrites
    // the artifact in place, so it refreshes on the same signal.
    void queryClient.invalidateQueries({ queryKey: queryKeys.evaluateReport(resolvedReeId) });
  }, [terminalRunIds, queryClient, resolvedReeId]);
}
