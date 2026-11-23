import { auditReceiptRunIds } from "@core/ree/StepEvidence";
import { filesReceipt } from "@core/runs/ReeRun";
import { isTerminalReeRunStatus } from "@core/runs/ReeRunStatus";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useReeRuntime } from "../apiRuntime";
import { resolveReeId } from "../client";
import { queryKeys } from "../queryKeys";
import { useReeRunsQuery } from "../runs/queries";
import { useReeQuery } from "./queries";

const FOLLOW_FOR_MS = 15_000;
const RETRY_DELAYS_MS = [0, 500, 1000, 2000, 4000];

export function useReeDocumentFollowsRuns({
  reeId,
  enabled,
}: {
  reeId?: string;
  enabled: boolean;
}) {
  const runtime = useReeRuntime();
  const resolvedReeId = resolveReeId(runtime, reeId);
  const queryClient = useQueryClient();
  const runs = useReeRunsQuery(reeId).data;
  const document = useReeQuery({ reeId, enabled });
  const seen = useRef<Set<string> | null>(null);
  const awaited = useRef(new Map<string, number>());
  const refetchOwed = useRef(false);
  const attempt = useRef(0);
  const [settled, setSettled] = useState(0);

  useEffect(() => {
    if (!runs) return;
    const terminal = runs.filter((run) => isTerminalReeRunStatus(run.status));
    if (seen.current === null) {
      seen.current = new Set(terminal.map((run) => run.runId));
      return;
    }
    let changed = false;
    for (const run of terminal) {
      if (seen.current.has(run.runId)) continue;
      seen.current.add(run.runId);
      changed = true;
      if (run.status === "succeeded" && filesReceipt(run.operation)) {
        awaited.current.set(run.runId, Date.now() + FOLLOW_FOR_MS);
      }
    }
    if (changed) {
      refetchOwed.current = true;
      attempt.current = 0;
      setSettled((count) => count + 1);
    }
  }, [runs]);

  const audit = document.data?.ree?.audit;
  const { dataUpdatedAt, errorUpdatedAt } = document;
  // biome-ignore lint/correctness/useExhaustiveDependencies: a read or a settled run is what re-checks.
  useEffect(() => {
    const named = auditReceiptRunIds(audit ?? {});
    const now = Date.now();
    for (const [runId, deadline] of awaited.current) {
      if (named.has(runId) || now > deadline) awaited.current.delete(runId);
    }
    const waiting = [...awaited.current.keys()];
    const published =
      queryClient.getQueryData<string[]>(queryKeys.reeAwaitedRuns(resolvedReeId)) ?? [];
    if (waiting.join() !== published.join()) {
      queryClient.setQueryData(queryKeys.reeAwaitedRuns(resolvedReeId), waiting);
    }
    if (!enabled || (!refetchOwed.current && awaited.current.size === 0)) return;
    const delay = RETRY_DELAYS_MS[Math.min(attempt.current, RETRY_DELAYS_MS.length - 1)];
    const timer = setTimeout(() => {
      refetchOwed.current = false;
      attempt.current += 1;
      void queryClient.refetchQueries(
        { queryKey: queryKeys.ree(resolvedReeId), exact: true },
        { cancelRefetch: false },
      );
    }, delay);
    return () => clearTimeout(timer);
  }, [audit, dataUpdatedAt, errorUpdatedAt, settled, enabled, queryClient, resolvedReeId]);
}

export function useRunsAwaitingDocument(reeId?: string): ReadonlySet<string> {
  const runtime = useReeRuntime();
  const resolvedReeId = resolveReeId(runtime, reeId);
  const { data } = useQuery({
    queryKey: queryKeys.reeAwaitedRuns(resolvedReeId),
    queryFn: () => [] as string[],
    enabled: false,
    initialData: [] as string[],
    staleTime: Number.POSITIVE_INFINITY,
  });
  return useMemo(() => new Set(data), [data]);
}
