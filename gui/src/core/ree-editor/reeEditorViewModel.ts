import type { ArtifactStatus } from "../../core/artifact/ArtifactStatus";
import type { EvaluationState } from "../../core/evaluate/EvaluationState";
import { createEmptyReeSpec, type ReeSpec } from "../../core/ree/ReeSpec";
import type { ReeAudit } from "../../core/ree/StepEvidence";
import type { WorkspaceSourceState } from "../../core/workspace/WorkspaceSourceState";
import type { ReeEditorState } from "./reeEditorState";

export interface ReeEditorViewModel {
  spec: ReeSpec;
  source: WorkspaceSourceState;
  artifact: ArtifactStatus;
  evaluation: EvaluationState;
  /**
   * Whether each executed step's receipt still speaks for this REE. Named for
   * the backend's `ReeAudit` rather than "evidence" so it cannot be misread as
   * a sibling of `evaluation`, which carries the readiness axes.
   */
  audit: ReeAudit;
}

export interface ReeEditorViewModelPatch {
  spec?: Partial<ReeSpec>;
  source?: Partial<WorkspaceSourceState>;
  artifact?: Partial<ArtifactStatus>;
  evaluation?: Partial<EvaluationState>;
  audit?: Partial<ReeAudit>;
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
    audit: { ...current.audit, ...patch.audit },
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
    audit: { experiments: [] },
  };
}

export function createReeEditorViewModel(
  editorState: Pick<
    ReeEditorState,
    "reeSpec" | "workspaceSourceState" | "artifactStatus" | "evaluationState" | "stepEvidence"
  > & { audit?: ReeAudit },
): ReeEditorViewModel {
  return {
    spec: editorState.reeSpec,
    source: editorState.workspaceSourceState,
    artifact: editorState.artifactStatus,
    evaluation: editorState.evaluationState,
    audit: editorState.audit ?? {
      ...Object.fromEntries(
        Object.entries(editorState.stepEvidence).map(([key, evidence]) => [
          key,
          { evidence, payload: "missing", reasons: [] },
        ]),
      ),
      experiments: [],
    },
  };
}
