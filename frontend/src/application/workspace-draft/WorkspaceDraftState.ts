import { enforceSourceOriginRules } from "../../domain/artifact/sourceOriginRules";
import type { ReeDraftViewModel, ReeSpec } from "../../domain/ree/ReeSpec";
import { createEmptyRee, splitLegacyReeModel } from "../../domain/ree/reeLegacyAdapters";

export type WorkspaceDraftStateUpdater<T> = T | ((previous: T) => T);

export interface WorkspaceDraftState {
  reeSpec: ReeSpec;
  locked: boolean;
  repoMode: "url" | "upload";
}

export function resolveWorkspaceDraftUpdater<T>(
  previous: T,
  updater: WorkspaceDraftStateUpdater<T>,
): T {
  if (typeof updater === "function") {
    return (updater as (value: T) => T)(previous);
  }
  return updater;
}

export function createInitialWorkspaceDraftState(
  initialRee: ReeDraftViewModel = createEmptyRee(),
): WorkspaceDraftState {
  const { reeSpec } = splitLegacyReeModel(enforceSourceOriginRules(initialRee));
  return {
    reeSpec,
    locked: false,
    repoMode: "url",
  };
}
