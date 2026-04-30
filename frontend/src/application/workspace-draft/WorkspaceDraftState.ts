import { enforceSourceOriginRules } from "../../domain/artifact/sourceOriginRules";
import type { ReeDraftViewModel } from "../../domain/ree/ReeSpec";
import { createEmptyRee } from "../../domain/ree/reeLegacyAdapters";

export type WorkspaceDraftStateUpdater<T> = T | ((previous: T) => T);

export interface WorkspaceDraftState {
  ree: ReeDraftViewModel;
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
  return {
    ree: enforceSourceOriginRules(initialRee),
    locked: false,
    repoMode: "url",
  };
}
