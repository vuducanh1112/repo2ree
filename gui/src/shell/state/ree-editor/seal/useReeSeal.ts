import type { InclusionOpts } from "@core/ree/InclusionOpts";
import type { ReeId } from "@core/ree/ReeId";
import type { LogEntry } from "@core/ree/ReeTypes";
import { queryKeys } from "@shell/data/queryKeys";
import { useReeClient } from "@shell/data/ree/client";
import { useReeRunsClient } from "@shell/data/runs/client";
import { observeReeRun } from "@shell/data/runs/queries";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import type { ShowToast } from "../types";
import type { HydratedWorkspaceSnapshot } from "../workspace-sync/hydrateReeWorkspace";

interface UseReeSealArgs {
  reeId: ReeId;
  showToast: ShowToast;
  hydrateWorkspace: (snapshot: HydratedWorkspaceSnapshot) => void;
  flushReeIntent: () => Promise<void>;
}

/**
 * Owns the seal operation: flush pending intent edits, ask the backend to
 * build the sealed bundle, then re-hydrate the workspace from the returned
 * session. The session's seal stamps drive the read-only lock (see `isSealed`),
 * so the caller does not need to toggle lock state optimistically. Both success
 * and error feedback live here so every caller gets consistent toasts.
 * sealRunning is set before the flush so the UI disables for the full operation.
 */
export function useReeSeal({ reeId, showToast, hydrateWorkspace, flushReeIntent }: UseReeSealArgs) {
  const reeClient = useReeClient();
  const reeRunsClient = useReeRunsClient();
  const queryClient = useQueryClient();
  const [sealRunning, setSealRunning] = useState(false);
  const [sealLog, setSealLog] = useState<LogEntry | null>(null);

  const handleSealRee = useCallback(
    async (inclusionOpts: InclusionOpts): Promise<void> => {
      const ts = new Date().toISOString();
      let latestLines: LogEntry["lines"] = [{ type: "info", msg: "Sealing REE…" }];
      setSealRunning(true);
      setSealLog({ ts, lines: latestLines });
      try {
        try {
          await flushReeIntent();
        } catch {
          throw new Error("could not save pending changes");
        }
        const run = await reeClient.sealRee(reeId, {
          includeSource: inclusionOpts.includeSource,
          includeRuntime: inclusionOpts.includeRuntime,
          includeResults: inclusionOpts.includeResults,
        });
        const terminal = await observeReeRun(queryClient, reeRunsClient, {
          reeId: String(reeId),
          runId: run.run_id,
          onUpdate: (update) => {
            latestLines = update.lines.length > 0 ? update.lines : latestLines;
            setSealLog({
              ts: update.ts,
              lines: latestLines,
            });
          },
        });
        if (terminal.status !== "succeeded") {
          throw new Error(
            terminal.failure?.message ??
              (terminal.status === "canceled" ? "sealing was canceled" : "sealing did not succeed"),
          );
        }

        const project = await reeClient.getRee(reeId);
        queryClient.setQueryData(queryKeys.ree(String(reeId)), project);
        hydrateWorkspace({
          workspaceFiles: project.files,
          reeArtifactFiles: project.reeFiles ?? [],
          ree: project.ree,
        });
        setSealLog({
          ts: terminal.ts,
          lines: [...terminal.lines, { type: "ok", msg: "Sealed — workspace updated" }],
        });
        showToast("REE sealed — now read-only", "success");
      } catch (error) {
        const msg = `Seal failed: ${error instanceof Error ? error.message : "unknown error"}`;
        setSealLog({
          ts,
          lines: [...latestLines, { type: "err", msg }],
        });
        showToast(msg, "error");
      } finally {
        setSealRunning(false);
      }
    },
    [flushReeIntent, hydrateWorkspace, queryClient, reeClient, reeId, reeRunsClient, showToast],
  );

  return { handleSealRee, sealRunning, sealLog };
}
