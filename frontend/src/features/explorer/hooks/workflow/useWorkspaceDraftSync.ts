import { useCallback, useEffect, useRef } from "react";
import {
  shouldHydrateRemoteRee,
  shouldScheduleReeDraftSync,
} from "../../../../application/workspace/syncWorkspaceDraft";
import { toReePatch } from "../../../../domain/ree/reePatch";
import type { FileTreeNode, Ree, ReeFile } from "../../../../types";
import type { WorkspaceGateway } from "../../../../workspace/WorkspaceGateway";

interface HydratedWorkspaceSnapshot {
  virtualFiles: FileTreeNode[];
  workspaceReeFiles: ReeFile[];
  ree?: Ree;
}

interface UseWorkspaceDraftSyncArgs {
  ree: Ree;
  workspaceService: WorkspaceGateway<FileTreeNode>;
  workspaceId: string;
  workspaceServiceMode: "remote" | "mock";
  hydrateWorkspace: (workspace: HydratedWorkspaceSnapshot) => void;
}

export function useWorkspaceDraftSync({
  ree,
  workspaceService,
  workspaceId,
  workspaceServiceMode,
  hydrateWorkspace,
}: UseWorkspaceDraftSyncArgs) {
  const initialPatchKey = JSON.stringify(toReePatch(ree));
  const lastSyncedReeRef = useRef<string>(initialPatchKey);
  const latestLocalPatchKeyRef = useRef<string>(initialPatchKey);
  const isSyncingReeRef = useRef<boolean>(false);
  const hasHydratedRemoteReeRef = useRef<boolean>(false);
  const syncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refreshWorkspace = useCallback(
    async (options: { forceReeHydration?: boolean } = {}): Promise<HydratedWorkspaceSnapshot> => {
      const { forceReeHydration = false } = options;
      const requestStartedPatchKey = latestLocalPatchKeyRef.current;
      const workspace = await workspaceService.getWorkspace(workspaceId);
      let reeToHydrate: Ree | undefined;
      if (workspace.ree) {
        const localPatchChangedDuringRequest =
          latestLocalPatchKeyRef.current !== requestStartedPatchKey;
        const shouldHydrateRee = shouldHydrateRemoteRee({
          forceReeHydration: forceReeHydration && !localPatchChangedDuringRequest,
          hasHydratedRemoteRee: hasHydratedRemoteReeRef.current,
          latestLocalPatchKey: latestLocalPatchKeyRef.current,
          lastSyncedPatchKey: lastSyncedReeRef.current,
          hasSyncTimer: !!syncTimerRef.current,
          isSyncingRee: isSyncingReeRef.current,
        });
        if (shouldHydrateRee) {
          reeToHydrate = workspace.ree;
          const hydratedPatchKey = JSON.stringify(toReePatch(workspace.ree));
          lastSyncedReeRef.current = hydratedPatchKey;
          latestLocalPatchKeyRef.current = hydratedPatchKey;
          hasHydratedRemoteReeRef.current = true;
        }
      }
      const hydratedWorkspace = {
        virtualFiles: workspace.files,
        workspaceReeFiles: workspace.reeFiles || [],
        ree: reeToHydrate,
      };
      hydrateWorkspace(hydratedWorkspace);
      return hydratedWorkspace;
    },
    [hydrateWorkspace, workspaceId, workspaceService],
  );

  const refreshWorkspaceFiles = useCallback(
    async (options: { forceReeHydration?: boolean } = {}): Promise<FileTreeNode[]> => {
      const workspace = await refreshWorkspace(options);
      return workspace.virtualFiles;
    },
    [refreshWorkspace],
  );

  const buildReePatch = useCallback(() => toReePatch(ree), [ree]);

  useEffect(() => {
    latestLocalPatchKeyRef.current = JSON.stringify(buildReePatch());
  }, [buildReePatch]);

  useEffect(() => {
    if (workspaceServiceMode !== "remote") {
      return;
    }
    void refreshWorkspace({ forceReeHydration: true });
  }, [workspaceServiceMode, refreshWorkspace]);

  useEffect(() => {
    const patch = buildReePatch();
    const patchKey = JSON.stringify(patch);
    const shouldScheduleSync = shouldScheduleReeDraftSync({
      workspaceServiceMode,
      canUpdateReeDraft: !!workspaceService.updateReeDraft,
      patchKey,
      lastSyncedPatchKey: lastSyncedReeRef.current,
    });

    if (!shouldScheduleSync) {
      return;
    }
    if (syncTimerRef.current) {
      clearTimeout(syncTimerRef.current);
      syncTimerRef.current = null;
    }
    syncTimerRef.current = setTimeout(() => {
      void (async () => {
        syncTimerRef.current = null;
        isSyncingReeRef.current = true;
        try {
          await workspaceService.updateReeDraft?.(workspaceId, patch);
          lastSyncedReeRef.current = patchKey;
          await refreshWorkspaceFiles();
        } catch {
          // Keep local metadata editable; backend sync can be retried on next change.
        } finally {
          isSyncingReeRef.current = false;
        }
      })();
    }, 300);

    return () => {
      if (syncTimerRef.current) {
        clearTimeout(syncTimerRef.current);
        syncTimerRef.current = null;
      }
    };
  }, [workspaceId, workspaceServiceMode, workspaceService, buildReePatch, refreshWorkspaceFiles]);

  return {
    buildReePatch,
    refreshWorkspace,
    refreshWorkspaceFiles,
  };
}
