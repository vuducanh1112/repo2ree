import { enforceSourceOriginRules } from "../../domain/artifact/sourceOriginRules";
import type { Ree } from "../../domain/ree/ReeSpec";

export type WorkspaceDraftStateUpdater<T> = T | ((previous: T) => T);

export interface WorkspaceDraftState {
  ree: Ree;
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
  initialWorkspaceShellRee: Ree,
): WorkspaceDraftState {
  return {
    ree: enforceSourceOriginRules(initialWorkspaceShellRee),
    locked: false,
    repoMode: "url",
  };
}
