import type { InclusionOpts } from "../../../../core/ree/InclusionOpts";
import type { ReeId } from "../../../../core/ree/ReeId";
import { useReeClient } from "../../../data/ree/client";
import { mapReeDetailToReeProject } from "../../../data/ree/reeMapping";
import type { ShowToast } from "../types";
import type { HydratedWorkspaceSnapshot } from "../workspace-sync/hydrateReeWorkspace";

interface UseReeSealArgs {
  reeId: ReeId;
  showToast: ShowToast;
  hydrateWorkspace: (snapshot: HydratedWorkspaceSnapshot) => void;
}

/**
 * Owns the seal operation: ask the backend to build the sealed bundle, then
 * re-hydrate the workspace from the returned session. The session's seal stamps
 * drive the read-only lock (see `isSealed`), so the caller does not need to
 * toggle lock state optimistically. Both success and error feedback live here
 * so every caller gets consistent toasts.
 */
export function useReeSeal({ reeId, showToast, hydrateWorkspace }: UseReeSealArgs) {
  const reeClient = useReeClient();

  const handleSealRee = async (inclusionOpts: InclusionOpts): Promise<void> => {
    try {
      const workspaceDto = await reeClient.sealRee(reeId, {
        includeSource: inclusionOpts.includeSource,
        includeRuntime: inclusionOpts.includeRuntime,
      });
      const project = mapReeDetailToReeProject(workspaceDto);
      hydrateWorkspace({
        workspaceFiles: project.files,
        reeArtifactFiles: project.reeFiles ?? [],
        ree: project.ree,
      });
      showToast("REE sealed — now read-only", "success");
    } catch (error) {
      showToast(error instanceof Error ? `Seal failed: ${error.message}` : "Seal failed", "error");
    }
  };

  return { handleSealRee };
}
