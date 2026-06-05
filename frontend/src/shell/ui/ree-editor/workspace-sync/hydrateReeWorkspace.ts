import type React from "react";
import type { RawReeIntentSlices } from "../../../../core/ree/mapRawReeIntent";
import type { ReeFile } from "../../../../core/ree/ReeTypes";
import type { FileTreeNode } from "../../../../core/workspace/FileTree";
import {
  setArtifactStatus,
  setEvaluationState,
  setWorkspaceSourceState,
  updateReeSpec,
} from "../../app-shell/state/actions";
import type { AppShellAction } from "../../app-shell/state/types";

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
    dispatch(setArtifactStatus(() => ree.artifactStatus));
    dispatch(setEvaluationState(() => ree.evaluationState));
  };
}
