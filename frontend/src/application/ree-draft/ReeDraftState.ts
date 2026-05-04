import type { ArtifactStatus } from "../../domain/artifact/ArtifactStatus";
import { enforceSourceOriginRules } from "../../domain/artifact/sourceOriginRules";
import type { ReeSpec } from "../../domain/ree/ReeSpec";
import {
  createEmptyReeViewState,
  type ReeViewState,
  splitReeViewState,
} from "../../domain/ree/ReeViewState";
import type { WorkspaceSourceState } from "../../domain/workspace/WorkspaceSourceState";

export interface ReeDraftState {
  reeSpec: ReeSpec;
  locked: boolean;
  repoMode: "url" | "upload";
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  sourceSnapshotArchiveName: string;
}

export function createInitialReeDraftState(
  initialRee: ReeViewState = createEmptyReeViewState(),
): ReeDraftState {
  const { reeSpec, workspaceSourceState, artifactStatus } = splitReeViewState(
    enforceSourceOriginRules(initialRee),
  );
  return {
    reeSpec,
    locked: false,
    repoMode: "url",
    workspaceSourceState,
    artifactStatus,
    sourceSnapshotArchiveName: "",
  };
}
