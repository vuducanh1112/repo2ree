import type React from "react";
import {
  setArtifactStatus,
  setEvaluationState,
  setWorkspaceSourceState,
  updateReeSpec,
} from "../../../application/state/actions";
import type { AppShellAction } from "../../../application/state/types";
import type { RawReeDraftSlices } from "../../../core/ree/mapRawReeDraft";
import type { ReeFile } from "../../../core/ree/ReeTypes";
import type { FileTreeNode } from "../../../core/workspace/FileTree";

export interface HydratedWorkspaceSnapshot {
  workspaceFiles: FileTreeNode[];
  reeArtifactFiles: ReeFile[];
  ree?: RawReeDraftSlices;
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
