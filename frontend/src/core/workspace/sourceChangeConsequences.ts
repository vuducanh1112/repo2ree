import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import { type EvaluationState, emptyEvaluationState } from "../evaluate/EvaluationState";
import {
  clearedSourceIdentityReeSpec,
  createEmptyReeActivation,
  type ReeSpec,
} from "../ree/ReeSpec";
import type { ActionStates, Badges, ReeStepParams, Timestamps } from "../ree/ReeTypes";
import type { WorkspaceSourceState } from "./WorkspaceSourceState";

export interface SourceChangeInput {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
  actionStates: ActionStates;
  badges: Badges;
  timestamps: Timestamps;
  stepParams: ReeStepParams;
}

interface SourceChangeOutput {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
  badges: Badges;
  timestamps: Timestamps;
  actionStates: ActionStates;
  stepParams: ReeStepParams;
  sourceSnapshotArchiveName: string;
}

export function computeSourceChangeConsequences(input: SourceChangeInput): SourceChangeOutput {
  return {
    reeSpec: {
      ...input.reeSpec,
      ...clearedSourceIdentityReeSpec(),
      runtime: "",
      activation: createEmptyReeActivation(),
      sbom: "",
      swhid: "",
      zenodo_doi: "",
      dataverse_doi: "",
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
    evaluationState: emptyEvaluationState(),
    badges: {},
    timestamps: {},
    actionStates: {},
    stepParams: input.stepParams,
    sourceSnapshotArchiveName: "",
  };
}
