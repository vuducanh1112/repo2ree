interface WorkspaceHydrationPlanInput {
  forceReeHydration: boolean;
  hasHydratedRemoteRee: boolean;
  latestLocalPatchKey: string;
  lastSyncedPatchKey: string;
  hasSyncTimer: boolean;
  isSyncingRee: boolean;
}

interface ReeDraftSyncPlanInput {
  workspaceServiceMode: "remote" | "mock";
  canUpdateReeDraft: boolean;
  patchKey: string;
  lastSyncedPatchKey: string;
}

export function shouldHydrateRemoteRee(input: WorkspaceHydrationPlanInput): boolean {
  const hasUnsyncedLocalChanges = input.latestLocalPatchKey !== input.lastSyncedPatchKey;
  const hasPendingLocalSync = hasUnsyncedLocalChanges || input.hasSyncTimer || input.isSyncingRee;

  if (input.forceReeHydration) {
    return !hasPendingLocalSync;
  }

  if (hasPendingLocalSync) {
    return false;
  }

  return true;
}

export function shouldScheduleReeDraftSync(input: ReeDraftSyncPlanInput): boolean {
  if (input.workspaceServiceMode !== "remote" || !input.canUpdateReeDraft) {
    return false;
  }

  return input.patchKey !== input.lastSyncedPatchKey;
}
