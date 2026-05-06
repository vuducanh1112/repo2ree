import { useCallback, useEffect, useRef } from "react";
import { toReePatch, toReePatchFromSlices } from "../../../core/ree/reePatch";
import type { ReeEditorViewModel } from "../../../core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "../../../core/workspace/FileTree";
import {
  shouldHydrateRemoteRee,
  shouldScheduleReeDraftSync,
} from "../../../core/workspace/syncReeDraft";
import { useUpdateReeDraftMutation } from "../../../data/ree/mutations";
import { useRefreshReeQuery } from "../../../data/ree/queries";
import type { HydratedWorkspaceSnapshot } from "./hydrateReeWorkspace";

interface UseReeDraftSyncArgs {
  ree: ReeEditorViewModel;
  reeId: string;
  hydrateWorkspace: (workspace: HydratedWorkspaceSnapshot) => void;
}

export function useReeDraftSync({ ree, reeId, hydrateWorkspace }: UseReeDraftSyncArgs) {
  const initialPatchKey = JSON.stringify(toReePatch(ree));
  const lastSyncedReeRef = useRef<string>(initialPatchKey);
  const latestLocalPatchKeyRef = useRef<string>(initialPatchKey);
  const isSyncingReeRef = useRef<boolean>(false);
  const hasHydratedRemoteReeRef = useRef<boolean>(false);
  const syncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fetchWorkspace = useRefreshReeQuery(reeId);
  const { mutateAsync: updateReeDraft } = useUpdateReeDraftMutation(reeId);

  const refreshWorkspace = useCallback(
    async (options: { forceReeHydration?: boolean } = {}): Promise<HydratedWorkspaceSnapshot> => {
      const { forceReeHydration = false } = options;
      const requestStartedPatchKey = latestLocalPatchKeyRef.current;
      const workspace = await fetchWorkspace();
      let reeToHydrate = workspace.ree;

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
          const hydratedPatchKey = JSON.stringify(toReePatchFromSlices(workspace.ree));
          lastSyncedReeRef.current = hydratedPatchKey;
          latestLocalPatchKeyRef.current = hydratedPatchKey;
          hasHydratedRemoteReeRef.current = true;
        } else {
          reeToHydrate = undefined;
        }
      }

      const hydratedWorkspace = {
        workspaceFiles: workspace.files,
        reeArtifactFiles: workspace.reeFiles || [],
        ree: reeToHydrate,
      };
      hydrateWorkspace(hydratedWorkspace);
      return hydratedWorkspace;
    },
    [fetchWorkspace, hydrateWorkspace],
  );

  const refreshWorkspaceFiles = useCallback(
    async (options: { forceReeHydration?: boolean } = {}): Promise<FileTreeNode[]> => {
      const workspace = await refreshWorkspace(options);
      return workspace.workspaceFiles;
    },
    [refreshWorkspace],
  );

  const buildReePatch = useCallback(() => toReePatch(ree), [ree]);

  useEffect(() => {
    latestLocalPatchKeyRef.current = JSON.stringify(buildReePatch());
  }, [buildReePatch]);

  useEffect(() => {
    void refreshWorkspace({ forceReeHydration: true });
  }, [refreshWorkspace]);

  useEffect(() => {
    const patch = buildReePatch();
    const patchKey = JSON.stringify(patch);
    const shouldScheduleSync = shouldScheduleReeDraftSync({
      canUpdateReeDraft: true,
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
          await updateReeDraft(patch);
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
  }, [buildReePatch, refreshWorkspaceFiles, updateReeDraft]);

  return {
    buildReePatch,
    refreshWorkspace,
    refreshWorkspaceFiles,
  };
}
