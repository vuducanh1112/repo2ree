import type { ArtifactStatus } from "../../core/artifact/ArtifactStatus";
import type { EvaluationState } from "../../core/evaluate/EvaluationState";
import { createEmptyReeSpec, type ReeSpec } from "../../core/ree/ReeSpec";
import type { WorkspaceSourceState } from "../../core/workspace/WorkspaceSourceState";
import type { ReeEditorState } from "./reeEditorState";

export interface ReeEditorViewModel {
  spec: ReeSpec;
  source: WorkspaceSourceState;
  artifact: ArtifactStatus;
  evaluation: EvaluationState;
}

export interface ReeEditorViewModelPatch {
  spec?: Partial<ReeSpec>;
  source?: Partial<WorkspaceSourceState>;
  artifact?: Partial<ArtifactStatus>;
  evaluation?: Partial<EvaluationState>;
}

export function patchReeEditorViewModel(
  current: ReeEditorViewModel,
  patch: ReeEditorViewModelPatch,
): ReeEditorViewModel {
  return {
    spec: { ...current.spec, ...patch.spec },
    source: { ...current.source, ...patch.source },
    artifact: { ...current.artifact, ...patch.artifact },
    evaluation: { ...current.evaluation, ...patch.evaluation },
  };
}

export function createEmptyReeEditorViewModel(): ReeEditorViewModel {
  return {
    spec: createEmptyReeSpec(),
    source: { sourceAvailable: false, sourceIncluded: false },
    artifact: { runtimeIncluded: false },
    evaluation: {
      dependencyLevel: 0,
      environmentLevel: 0,
      machineLevel: 0,
    },
  };
}

export function createReeEditorViewModel(
  editorState: Pick<
    ReeEditorState,
    "reeSpec" | "workspaceSourceState" | "artifactStatus" | "evaluationState"
  >,
): ReeEditorViewModel {
  return {
    spec: editorState.reeSpec,
    source: editorState.workspaceSourceState,
    artifact: editorState.artifactStatus,
    evaluation: editorState.evaluationState,
  };
}
