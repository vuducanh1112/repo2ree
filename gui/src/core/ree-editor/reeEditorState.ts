import type { ArtifactStatus } from "../../core/artifact/ArtifactStatus";
import { type EvaluationState, emptyEvaluationState } from "../../core/evaluate/EvaluationState";
import { createEmptyReeSpec, type ReeSpec } from "../../core/ree/ReeSpec";
import type { WorkspaceSourceState } from "../../core/workspace/WorkspaceSourceState";

export interface ReeEditorState {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
}

interface CreateReeEditorStateInput {
  reeSpec?: ReeSpec;
  workspaceSourceState?: WorkspaceSourceState;
  artifactStatus?: ArtifactStatus;
  evaluationState?: EvaluationState;
}

export function createReeEditorState(input: CreateReeEditorStateInput = {}): ReeEditorState {
  const reeSpec = input.reeSpec ?? createEmptyReeSpec();
  const workspaceSourceState = input.workspaceSourceState ?? { sourceAvailable: false };
  const artifactStatus = input.artifactStatus ?? { runtimeIncluded: false };

  return {
    reeSpec,
    workspaceSourceState,
    artifactStatus,
    evaluationState: input.evaluationState ?? emptyEvaluationState(),
  };
}
