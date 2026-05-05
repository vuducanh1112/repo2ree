import type { ArtifactStatus } from "../../domain/artifact/ArtifactStatus";
import { enforceSourceOriginRules } from "../../domain/artifact/sourceOriginRules";
import { createEmptyReeSpec, type ReeSpec } from "../../domain/ree/ReeSpec";
import type { EvaluationState } from "../../domain/review/EvaluationState";
import type { WorkspaceSourceState } from "../../domain/workspace/WorkspaceSourceState";

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
    evaluationState: input.evaluationState ?? { evalLevel: 0 },
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
