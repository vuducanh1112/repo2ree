import type { ArtifactStatus } from "../../../../core/artifact/ArtifactStatus";
import type { WorkspaceSourceState } from "../../../../core/workspace/WorkspaceSourceState";

export interface ReeSessionState {
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
}

export function createInitialReeSessionState(
  input: { workspaceSourceState?: WorkspaceSourceState; artifactStatus?: ArtifactStatus } = {},
): ReeSessionState {
  return {
    workspaceSourceState: input.workspaceSourceState ?? { sourceAvailable: false },
    artifactStatus: input.artifactStatus ?? { runtimeIncluded: false },
  };
}
