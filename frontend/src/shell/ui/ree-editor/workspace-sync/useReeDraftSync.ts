import { useCallback, useEffect, useRef } from "react";
import { toReePatch, toReePatchFromSlices } from "../../../../core/ree/reePatch";
import type { ReeEditorViewModel } from "../../../../core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "../../../../core/workspace/FileTree";
import {
  shouldHydrateRemoteRee,
  shouldScheduleReeDraftSync,
} from "../../../../core/workspace/syncReeDraft";
import { useUpdateReeDraftMutation } from "../../../data/ree/mutations";
import { useRefreshReeQuery } from "../../../data/ree/queries";
import type { HydratedWorkspaceSnapshot } from "./hydrateReeWorkspace";

interface UseReeDraftSyncArgs {
  ree: ReeEditorViewModel;
  reeId: string;
  provisioned: boolean;
  hydrateWorkspace: (workspace: HydratedWorkspaceSnapshot) => void;
}

export function useReeDraftSync({
  ree,
  reeId,
  provisioned,
  hydrateWorkspace,
}: UseReeDraftSyncArgs) {
  const initialPatchKey = JSON.stringify(toReePatch(ree));
  const lastSyncedReeRef = useRef<string>(initialPatchKey);
  const latestLocalPatchKeyRef = useRef<string>(initialPatchKey);
  const isSyncingReeRef = useRef<boolean>(false);
  const hasHydratedRemoteReeRef = useRef<boolean>(false);
  const syncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingSyncRef = useRef<Promise<void> | null>(null);
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

  // Single owner of the PATCH + refresh round-trip, shared by the debounced
  // autosave and the explicit flush() below. Publishing the in-flight promise
  // on pendingSyncRef lets a flush() await it instead of racing a concurrent
  // PATCH. Intentionally does NOT swallow errors — callers decide (the
  // autosave retries on next edit; flush() surfaces the failure to its caller).
  const runReeDraftSync = useCallback(
    (patch: ReturnType<typeof buildReePatch>, patchKey: string): Promise<void> => {
      const sync = (async () => {
        isSyncingReeRef.current = true;
        try {
          await updateReeDraft(patch);
          lastSyncedReeRef.current = patchKey;
          await refreshWorkspaceFiles();
        } finally {
          isSyncingReeRef.current = false;
        }
      })();
      pendingSyncRef.current = sync;
      void sync.finally(() => {
        if (pendingSyncRef.current === sync) {
          pendingSyncRef.current = null;
        }
      });
      return sync;
    },
    [updateReeDraft, refreshWorkspaceFiles],
  );

  // Force the latest local edits to the backend now, bypassing the debounce.
  // Callers that depend on a freshly-persisted draft (e.g. running an
  // experiment, which the backend validates against the saved draft) await
  // this first so they never race the 300ms autosave timer below.
  const flush = useCallback(async () => {
    // Drain any in-flight sync(s) before issuing our own so we never run two
    // concurrent PATCHes. A `while` (not `if`) is required: two flush() calls
    // can both await the same pending sync, so after it settles we re-check —
    // by then an earlier flush may have started a fresh sync we must wait on.
    while (pendingSyncRef.current) {
      await pendingSyncRef.current;
    }
    const patch = buildReePatch();
    const patchKey = JSON.stringify(patch);
    const shouldSync = shouldScheduleReeDraftSync({
      canUpdateReeDraft: provisioned,
      patchKey,
      lastSyncedPatchKey: lastSyncedReeRef.current,
    });
    if (!shouldSync) return;
    if (syncTimerRef.current) {
      clearTimeout(syncTimerRef.current);
      syncTimerRef.current = null;
    }
    await runReeDraftSync(patch, patchKey);
  }, [provisioned, buildReePatch, runReeDraftSync]);

  useEffect(() => {
    latestLocalPatchKeyRef.current = JSON.stringify(buildReePatch());
  }, [buildReePatch]);

  useEffect(() => {
    if (!provisioned) return;
    void refreshWorkspace({ forceReeHydration: true });
  }, [provisioned, refreshWorkspace]);

  useEffect(() => {
    if (!provisioned) return;
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
      syncTimerRef.current = null;
      // Keep local metadata editable: swallow the failure here so a transient
      // backend error doesn't surface mid-edit; it retries on the next change.
      void runReeDraftSync(patch, patchKey).catch(() => {});
    }, 300);

    return () => {
      if (syncTimerRef.current) {
        clearTimeout(syncTimerRef.current);
        syncTimerRef.current = null;
      }
    };
  }, [buildReePatch, provisioned, runReeDraftSync]);

  return {
    buildReePatch,
    refreshWorkspace,
    refreshWorkspaceFiles,
    flush,
  };
}
