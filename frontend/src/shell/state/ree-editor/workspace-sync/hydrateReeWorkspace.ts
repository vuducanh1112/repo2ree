import { isSealed, preserveSeal } from "@core/artifact/ArtifactStatus";
import type { RawReeIntentSlices } from "@core/ree/mapRawReeIntent";
import type { ReeFile } from "@core/ree/ReeTypes";
import type { FileTreeNode } from "@core/workspace/FileTree";
import {
  setArtifactStatus,
  setEvaluationState,
  setLocked,
  setWorkspaceSourceState,
  updateReeSpec,
} from "@shell/ui/app-shell/state/actions";
import type { AppShellAction } from "@shell/ui/app-shell/state/types";
import type React from "react";

export interface HydratedWorkspaceSnapshot {
  workspaceFiles: FileTreeNode[];
  reeArtifactFiles: ReeFile[];
  ree?: RawReeIntentSlices;
}

export function createHydrateReeWorkspace(dispatch: React.Dispatch<AppShellAction>) {
  return (workspace: HydratedWorkspaceSnapshot) => {
    if (!workspace.ree) {
      return;
    }
    const ree = workspace.ree;

    dispatch(updateReeSpec(() => ree.reeSpec));
    dispatch(setWorkspaceSourceState(() => ree.workspaceSourceState));
    dispatch(setArtifactStatus((prev) => preserveSeal(prev, ree.artifactStatus)));
    dispatch(setEvaluationState(() => ree.evaluationState));
    // A sealed session is permanently read-only, so reflect it in the shared
    // lock flag every consumer reads (the overview/source/metadata containers
    // read `uiChrome.locked` directly, not the derived editor view-model). This
    // covers both a fresh load of an already-sealed REE and the post-seal
    // re-hydration. Hydration never unlocks: the reversible "created" lock is
    // owned elsewhere, so we only ever raise the lock here.
    if (isSealed(ree.artifactStatus)) {
      dispatch(setLocked(true));
    }
  };
}
