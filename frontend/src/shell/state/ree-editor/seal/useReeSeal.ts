import type { InclusionOpts } from "@core/ree/InclusionOpts";
import type { ReeId } from "@core/ree/ReeId";
import type { LogEntry } from "@core/ree/ReeTypes";
import { useReeClient } from "@shell/data/ree/client";
import { mapReeDetailToReeProject } from "@shell/data/ree/reeMapping";
import { useState } from "react";
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
  const [sealRunning, setSealRunning] = useState(false);
  const [sealLog, setSealLog] = useState<LogEntry | null>(null);

  const handleSealRee = async (inclusionOpts: InclusionOpts): Promise<void> => {
    const ts = new Date().toISOString();
    setSealRunning(true);
    setSealLog({ ts, lines: [{ type: "info", msg: "Sealing REE…" }] });
    try {
      try {
        await flushReeIntent();
      } catch {
        throw new Error("could not save pending changes");
      }
      const workspaceDto = await reeClient.sealRee(reeId, {
        includeSource: inclusionOpts.includeSource,
        includeRuntime: inclusionOpts.includeRuntime,
        includeResults: inclusionOpts.includeResults,
      });
      const project = mapReeDetailToReeProject(workspaceDto);
      hydrateWorkspace({
        workspaceFiles: project.files,
        reeArtifactFiles: project.reeFiles ?? [],
        ree: project.ree,
      });
      setSealLog({
        ts,
        lines: [
          { type: "info", msg: "Sealing REE…" },
          { type: "ok", msg: "Sealed — workspace updated" },
        ],
      });
      showToast("REE sealed — now read-only", "success");
    } catch (error) {
      const msg = `Seal failed: ${error instanceof Error ? error.message : "unknown error"}`;
      setSealLog({
        ts,
        lines: [
          { type: "info", msg: "Sealing REE…" },
          { type: "err", msg },
        ],
      });
      showToast(msg, "error");
    } finally {
      setSealRunning(false);
    }
  };

  return { handleSealRee, sealRunning, sealLog };
}
