import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import type { ReeSpec } from "./ReeSpec";

export type InclusionStatus = "unavailable" | "excluded" | "included";

export interface ReeInclusionState {
  source: InclusionStatus;
  runtime: InclusionStatus;
}

interface LegacyInclusionInputs {
  sourceAvailable: boolean;
  sourceIncluded: boolean;
  runtimeIncluded: boolean;
}

function toInclusionStatus(available: boolean, included: boolean): InclusionStatus {
  if (!available) {
    return "unavailable";
  }
  return included ? "included" : "excluded";
}

export function mapLegacyInclusionState(inputs: LegacyInclusionInputs): ReeInclusionState {
  return {
    source: toInclusionStatus(inputs.sourceAvailable, inputs.sourceIncluded),
    runtime: toInclusionStatus(inputs.sourceAvailable, inputs.runtimeIncluded),
  };
}

function hasText(value: string | undefined): boolean {
  return Boolean(value?.trim());
}

export function deriveReeInclusionState(input: {
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  reeSpec: ReeSpec;
}): ReeInclusionState {
  const sourceAvailable = !!input.workspaceSourceState.sourceAvailable;
  const runtimeAvailable = hasText(input.reeSpec.runtime);

  return {
    source: toInclusionStatus(sourceAvailable, !!input.workspaceSourceState.sourceIncluded),
    runtime: toInclusionStatus(runtimeAvailable, !!input.artifactStatus.runtimeIncluded),
  };
}
