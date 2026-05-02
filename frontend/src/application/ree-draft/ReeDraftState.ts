import { enforceSourceOriginRules } from "../../domain/artifact/sourceOriginRules";
import type { ReeDraftViewModel, ReeSpec } from "../../domain/ree/ReeSpec";
import {
  createEmptyReeDraftViewModel,
  splitReeDraftViewModel,
} from "../../domain/ree/reeDraftViewModel";

export type ReeDraftStateUpdater<T> = T | ((previous: T) => T);

export interface ReeDraftState {
  reeSpec: ReeSpec;
  locked: boolean;
  repoMode: "url" | "upload";
}

export function resolveReeDraftUpdater<T>(previous: T, updater: ReeDraftStateUpdater<T>): T {
  if (typeof updater === "function") {
    return (updater as (value: T) => T)(previous);
  }
  return updater;
}

export function createInitialReeDraftState(
  initialRee: ReeDraftViewModel = createEmptyReeDraftViewModel(),
): ReeDraftState {
  const { reeSpec } = splitReeDraftViewModel(enforceSourceOriginRules(initialRee));
  return {
    reeSpec,
    locked: false,
    repoMode: "url",
  };
}
