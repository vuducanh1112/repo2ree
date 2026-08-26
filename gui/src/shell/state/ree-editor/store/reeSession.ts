import type { ArtifactStatus } from "@core/artifact/ArtifactStatus";
import { createEmptyStepEvidence, type StepEvidence } from "@core/ree/StepEvidence";
import type { WorkspaceSourceState } from "@core/workspace/WorkspaceSourceState";

export interface ReeSessionState {
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  /** The REE's own standing per executed step, restored on every hydration. */
  stepEvidence: StepEvidence;
}

export function createInitialReeSessionState(
  input: {
    workspaceSourceState?: WorkspaceSourceState;
    artifactStatus?: ArtifactStatus;
    stepEvidence?: StepEvidence;
  } = {},
): ReeSessionState {
  return {
    workspaceSourceState: input.workspaceSourceState ?? { sourceAvailable: false },
    artifactStatus: input.artifactStatus ?? { runtimeIncluded: false },
    stepEvidence: input.stepEvidence ?? createEmptyStepEvidence(),
  };
}
