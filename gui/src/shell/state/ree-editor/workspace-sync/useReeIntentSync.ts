import { toReePatchFromSlices } from "@core/ree/reePatch";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "@core/workspace/FileTree";
import { shouldHydrateRemoteRee, shouldScheduleReeIntentSync } from "@core/workspace/syncReeIntent";
import { useUpdateReeIntentMutation } from "@shell/data/ree/mutations";
import { useRefreshReeQuery } from "@shell/data/ree/queries";
import { useCallback, useEffect, useRef, useState } from "react";
import type { HydratedWorkspaceSnapshot } from "./hydrateReeWorkspace";

type WorkspaceHydrationState =
  | { status: "loading"; error: null }
  | { status: "ready"; error: null }
  | { status: "error"; error: Error };

export type ReeIntentSyncState =
  | { phase: "clean" }
  | { phase: "dirty" }
  | { phase: "saving" }
  | { phase: "error"; error: Error };

interface RefreshWorkspaceOptions {
  forceReeHydration?: boolean;
  requireReeHydration?: boolean;
}

function normalizeError(error: unknown): Error {
  return error instanceof Error ? error : new Error("The workspace could not be loaded");
}

interface UseReeIntentSyncArgs {
  ree: ReeEditorViewModel;
  reeId: string;
  provisioned: boolean;
  hydrateWorkspace: (workspace: HydratedWorkspaceSnapshot) => void;
}

export function useReeIntentSync({
  ree,
  reeId,
  provisioned,
  hydrateWorkspace,
}: UseReeIntentSyncArgs) {
  const initialPatchKey = JSON.stringify(toReePatchFromSlices(toPatchSlices(ree)));
  const lastSyncedReeRef = useRef<string>(initialPatchKey);
  const latestLocalPatchKeyRef = useRef<string>(initialPatchKey);
  const observedLocalPatchKeyRef = useRef<string>(initialPatchKey);
  const isSyncingReeRef = useRef<boolean>(false);
  const hasHydratedRemoteReeRef = useRef<boolean>(false);
  const syncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingSyncRef = useRef<Promise<void> | null>(null);
  const mountedRef = useRef(false);
  const hydrationRequestRef = useRef(0);
  const [hydration, setHydration] = useState<WorkspaceHydrationState>(
    provisioned ? { status: "loading", error: null } : { status: "ready", error: null },
  );
  const [syncState, setSyncState] = useState<ReeIntentSyncState>({ phase: "clean" });
  const fetchWorkspace = useRefreshReeQuery(reeId);
  const { mutateAsync: updateReeIntent } = useUpdateReeIntentMutation(reeId);

  const refreshWorkspace = useCallback(
    async (options: RefreshWorkspaceOptions = {}): Promise<HydratedWorkspaceSnapshot> => {
      const { forceReeHydration = false, requireReeHydration = false } = options;
      const requestStartedPatchKey = latestLocalPatchKeyRef.current;
      const workspace = await fetchWorkspace();

      if (requireReeHydration && !workspace.ree) {
        throw new Error("The workspace response did not contain its REE definition");
      }

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

      if (requireReeHydration && !reeToHydrate) {
        throw new Error("The remote REE could not be safely applied");
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
    async (options: RefreshWorkspaceOptions = {}): Promise<FileTreeNode[]> => {
      const workspace = await refreshWorkspace(options);
      return workspace.workspaceFiles;
    },
    [refreshWorkspace],
  );

  const buildReePatch = useCallback(() => toReePatchFromSlices(toPatchSlices(ree)), [ree]);

  // Single owner of the PATCH + refresh round-trip, shared by the debounced
  // autosave and the explicit flush() below. Publishing the in-flight promise
  // on pendingSyncRef lets a flush() await it instead of racing a concurrent
  // PATCH. Intentionally does NOT swallow errors — callers decide (the
  // autosave retries on next edit; flush() surfaces the failure to its caller).
  const runReeIntentSync = useCallback(
    (patch: ReturnType<typeof buildReePatch>, patchKey: string): Promise<void> => {
      const sync = (async () => {
        isSyncingReeRef.current = true;
        setSyncState({ phase: "saving" });
        try {
          await updateReeIntent(patch);
          lastSyncedReeRef.current = patchKey;
          await refreshWorkspaceFiles();
          setSyncState(
            latestLocalPatchKeyRef.current === patchKey ? { phase: "clean" } : { phase: "dirty" },
          );
        } catch (error) {
          const normalized = normalizeError(error);
          setSyncState({ phase: "error", error: normalized });
          throw normalized;
        } finally {
          isSyncingReeRef.current = false;
        }
      })();
      pendingSyncRef.current = sync;
      // `finally()` creates a second promise. Consume rejection on that cleanup
      // branch while leaving `sync` itself rejected for flush/autosave callers;
      // otherwise a failed PATCH produces an unrelated unhandled rejection.
      void sync
        .finally(() => {
          if (pendingSyncRef.current === sync) {
            pendingSyncRef.current = null;
          }
        })
        .catch(() => {});
      return sync;
    },
    [updateReeIntent, refreshWorkspaceFiles],
  );

  // Force the latest local edits to the backend now, bypassing the debounce.
  // Callers that depend on a freshly-persisted draft (e.g. running an
  // experiment, which the backend validates against the saved draft) await
  // this first so they never race the 300ms autosave timer below.
  const flush = useCallback(async () => {
    if (provisioned && hydration.status !== "ready") {
      throw hydration.status === "error"
        ? hydration.error
        : new Error("The workspace is still loading");
    }

    // Drain any in-flight sync(s) before issuing our own so we never run two
    // concurrent PATCHes. A `while` (not `if`) is required: two flush() calls
    // can both await the same pending sync, so after it settles we re-check —
    // by then an earlier flush may have started a fresh sync we must wait on.
    while (pendingSyncRef.current) {
      await pendingSyncRef.current;
    }
    const patch = buildReePatch();
    const patchKey = JSON.stringify(patch);
    const shouldSync = shouldScheduleReeIntentSync({
      canUpdateReeIntent: provisioned,
      patchKey,
      lastSyncedPatchKey: lastSyncedReeRef.current,
    });
    if (!shouldSync) return;
    if (syncTimerRef.current) {
      clearTimeout(syncTimerRef.current);
      syncTimerRef.current = null;
    }
    await runReeIntentSync(patch, patchKey);
  }, [provisioned, hydration, buildReePatch, runReeIntentSync]);

  useEffect(() => {
    const patchKey = JSON.stringify(buildReePatch());
    const changed = observedLocalPatchKeyRef.current !== patchKey;
    observedLocalPatchKeyRef.current = patchKey;
    latestLocalPatchKeyRef.current = patchKey;
    if (
      changed &&
      provisioned &&
      hydration.status === "ready" &&
      patchKey !== lastSyncedReeRef.current
    ) {
      setSyncState((current) =>
        current.phase === "saving" || current.phase === "error" ? current : { phase: "dirty" },
      );
    }
  }, [buildReePatch, hydration.status, provisioned]);

  const loadInitialWorkspace = useCallback(async () => {
    if (!provisioned) {
      setHydration({ status: "ready", error: null });
      return;
    }

    const request = hydrationRequestRef.current + 1;
    hydrationRequestRef.current = request;
    setHydration({ status: "loading", error: null });
    try {
      await refreshWorkspace({ forceReeHydration: true, requireReeHydration: true });
      if (mountedRef.current && hydrationRequestRef.current === request) {
        setHydration({ status: "ready", error: null });
      }
    } catch (error) {
      if (mountedRef.current && hydrationRequestRef.current === request) {
        setHydration({ status: "error", error: normalizeError(error) });
      }
    }
  }, [provisioned, refreshWorkspace]);

  useEffect(() => {
    mountedRef.current = true;
    void loadInitialWorkspace();
    return () => {
      mountedRef.current = false;
    };
  }, [loadInitialWorkspace]);

  useEffect(() => {
    const patch = buildReePatch();
    const patchKey = JSON.stringify(patch);
    const shouldScheduleSync = shouldScheduleReeIntentSync({
      canUpdateReeIntent: provisioned && hydration.status === "ready",
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
      // `flush` serializes behind an in-flight PATCH and publishes failures in
      // `syncState`; consuming the rejection here only prevents an unrelated
      // unhandled-promise report from the background branch.
      void flush().catch(() => {});
    }, 300);

    return () => {
      if (syncTimerRef.current) {
        clearTimeout(syncTimerRef.current);
        syncTimerRef.current = null;
      }
    };
  }, [buildReePatch, provisioned, hydration.status, flush]);

  const retryHydration = useCallback(() => {
    void loadInitialWorkspace();
  }, [loadInitialWorkspace]);

  return {
    hydration,
    retryHydration,
    buildReePatch,
    refreshWorkspace,
    refreshWorkspaceFiles,
    flush,
    syncState,
    isDirty: syncState.phase !== "clean",
    retrySync: flush,
  };
}

function toPatchSlices(ree: ReeEditorViewModel) {
  return {
    reeSpec: ree.spec,
    workspaceSourceState: ree.source,
    artifactStatus: ree.artifact,
    evaluationState: ree.evaluation,
  };
}
