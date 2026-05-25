import type { ArtifactStatus } from "../../core/artifact/ArtifactStatus";
import { createEmptyReeSpec, type ReeSpec } from "../../core/ree/ReeSpec";
import type { EvaluationState } from "../../core/review/EvaluationState";
import type { WorkspaceSourceState } from "../../core/workspace/WorkspaceSourceState";
import type { ReeEditorState } from "./reeEditorState";

export type ReeEditorViewModel = ReeSpec & WorkspaceSourceState & ArtifactStatus & EvaluationState;

export function createEmptyReeEditorViewModel(): ReeEditorViewModel {
  return {
    ...createEmptyReeSpec(),
    sourceAvailable: false,
    sourceIncluded: false,
    runtimeIncluded: false,
    downloadableFiles: [],
    dependencyLevel: 0,
    environmentLevel: 0,
    machineLevel: 0,
  };
}

export function createReeEditorViewModel(
  editorState: Pick<
    ReeEditorState,
    "reeSpec" | "workspaceSourceState" | "artifactStatus" | "evaluationState"
  >,
): ReeEditorViewModel {
  return {
    ...editorState.reeSpec,
    ...editorState.workspaceSourceState,
    ...editorState.artifactStatus,
    ...editorState.evaluationState,
  };
}
