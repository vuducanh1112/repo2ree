export type InclusionStatus = "unavailable" | "excluded" | "included";

export interface ReeInclusionState {
  source: InclusionStatus;
  runtime: InclusionStatus;
  sbom: InclusionStatus;
  hbom: InclusionStatus;
  activationEvidence: InclusionStatus;
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
    sbom: "unavailable",
    hbom: "unavailable",
    activationEvidence: "unavailable",
  };
}
