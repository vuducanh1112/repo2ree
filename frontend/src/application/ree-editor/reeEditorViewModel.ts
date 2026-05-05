import type { ArtifactStatus } from "../../domain/artifact/ArtifactStatus";
import { createEmptyReeSpec, type ReeSpec } from "../../domain/ree/ReeSpec";
import type { EvaluationState } from "../../domain/review/EvaluationState";
import type { WorkspaceSourceState } from "../../domain/workspace/WorkspaceSourceState";
import type { ReeEditorState } from "./reeEditorState";

export type ReeEditorViewModel = ReeSpec & WorkspaceSourceState & ArtifactStatus & EvaluationState;

export function createEmptyReeEditorViewModel(): ReeEditorViewModel {
  return {
    ...createEmptyReeSpec(),
    sourceAvailable: false,
    sourceIncluded: false,
    runtimeIncluded: false,
    downloadableFiles: [],
    evalLevel: 0,
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
