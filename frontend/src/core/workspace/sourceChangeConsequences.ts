import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { ReeSpec } from "../ree/ReeSpec";
import type { ActionStates, Badges, ReeAssemblyOperationParams, Timestamps } from "../ree/ReeTypes";
import type { EvaluationState } from "../review/EvaluationState";
import type { WorkspaceSourceState } from "./WorkspaceSourceState";

export interface SourceChangeInput {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
  actionStates: ActionStates;
  badges: Badges;
  timestamps: Timestamps;
  assemblyOperationParams: ReeAssemblyOperationParams;
}

interface SourceChangeOutput {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
  badges: Badges;
  timestamps: Timestamps;
  actionStates: ActionStates;
  assemblyOperationParams: ReeAssemblyOperationParams;
  sourceSnapshotArchiveName: string;
}

export function computeSourceChangeConsequences(input: SourceChangeInput): SourceChangeOutput {
  return {
    reeSpec: {
      ...input.reeSpec,
      origin_url: "",
      runtime: "",
      build_runtime_script: "",
      activation_script: "",
      sbom: "",
      swhid: "",
      detected_dependencies: "",
      repro_level: "",
      zenodo_doi: "",
    },
    workspaceSourceState: {
      ...input.workspaceSourceState,
      sourceAvailable: false,
      sourceAcquiredBy: undefined,
      uploadedArchive: "",
      sourceSnapshotArchive: "",
      sourceSnapshotCapturedAt: "",
    },
    artifactStatus: {
      ...input.artifactStatus,
      runtimeIncluded: false,
    },
    evaluationState: {
      ...input.evaluationState,
      evalLevel: 0,
    },
    badges: {},
    timestamps: {},
    actionStates: {},
    assemblyOperationParams: input.assemblyOperationParams,
    sourceSnapshotArchiveName: "",
  };
}
