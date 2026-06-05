interface WorkspaceHydrationPlanInput {
  forceReeHydration: boolean;
  hasHydratedRemoteRee: boolean;
  latestLocalPatchKey: string;
  lastSyncedPatchKey: string;
  hasSyncTimer: boolean;
  isSyncingRee: boolean;
}

interface ReeIntentSyncPlanInput {
  canUpdateReeIntent: boolean;
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

export function shouldScheduleReeIntentSync(input: ReeIntentSyncPlanInput): boolean {
  if (!input.canUpdateReeIntent) {
    return false;
  }

  return input.patchKey !== input.lastSyncedPatchKey;
}
