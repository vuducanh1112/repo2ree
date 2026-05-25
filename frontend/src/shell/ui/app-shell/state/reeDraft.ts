import type { ArtifactStatus } from "../../../../core/artifact/ArtifactStatus";
import { enforceSourceOriginRules } from "../../../../core/artifact/sourceOriginRules";
import { createEmptyReeSpec, type ReeSpec } from "../../../../core/ree/ReeSpec";
import {
  type EvaluationState,
  emptyEvaluationState,
} from "../../../../core/review/EvaluationState";
import type { WorkspaceSourceState } from "../../../../core/workspace/WorkspaceSourceState";

export interface ReeDraftState {
  reeSpec: ReeSpec;
  locked: boolean;
  repoMode: "url" | "upload";
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  sourceSnapshotArchiveName: string;
}

interface CreateInitialReeDraftStateInput {
  reeSpec?: ReeSpec;
  workspaceSourceState?: WorkspaceSourceState;
  artifactStatus?: ArtifactStatus;
  evaluationState?: EvaluationState;
}

export function createInitialReeDraftState(
  input: CreateInitialReeDraftStateInput = {},
): ReeDraftState {
  const normalized = enforceSourceOriginRules({
    reeSpec: input.reeSpec ?? createEmptyReeSpec(),
    workspaceSourceState: input.workspaceSourceState ?? { sourceAvailable: false },
    artifactStatus: input.artifactStatus ?? { runtimeIncluded: false, downloadableFiles: [] },
    evaluationState: input.evaluationState ?? emptyEvaluationState(),
  });
  return {
    reeSpec: normalized.reeSpec,
    locked: false,
    repoMode: "url",
    workspaceSourceState: normalized.workspaceSourceState,
    artifactStatus: normalized.artifactStatus,
    sourceSnapshotArchiveName: "",
  };
}
