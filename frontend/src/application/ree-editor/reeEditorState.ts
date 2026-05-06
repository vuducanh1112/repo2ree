import type { ArtifactStatus } from "../../domain/artifact/ArtifactStatus";
import {
  deriveReeInclusionState,
  type ReeInclusionState,
} from "../../domain/ree/ReeInclusionState";
import { createEmptyReeSpec, type ReeSpec } from "../../domain/ree/ReeSpec";
import type { ActionStates, Badges, Timestamps } from "../../domain/ree/ReeTypes";
import type { EvaluationState } from "../../domain/review/EvaluationState";
import type { WorkspaceSourceState } from "../../domain/workspace/WorkspaceSourceState";

export interface ReeEditorUiState {
  locked: boolean;
  repoMode: "url" | "upload";
  sourceSnapshotArchiveName: string;
}

export interface ReeAssemblyRunsState {
  actionStates: ActionStates;
  badges: Badges;
  timestamps: Timestamps;
  activeRunIds: Record<string, string>;
}

export interface ReeEditorState {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
  inclusionState: ReeInclusionState;
  editorUi: ReeEditorUiState;
  assemblyRuns: ReeAssemblyRunsState;
}

interface CreateReeEditorStateInput {
  reeSpec?: ReeSpec;
  workspaceSourceState?: WorkspaceSourceState;
  artifactStatus?: ArtifactStatus;
  evaluationState?: EvaluationState;
  inclusionState?: ReeInclusionState;
  editorUi?: Partial<ReeEditorUiState>;
  assemblyRuns?: Partial<ReeAssemblyRunsState>;
}

export function createReeEditorState(input: CreateReeEditorStateInput = {}): ReeEditorState {
  const reeSpec = input.reeSpec ?? createEmptyReeSpec();
  const workspaceSourceState = input.workspaceSourceState ?? { sourceAvailable: false };
  const artifactStatus = input.artifactStatus ?? {
    runtimeIncluded: false,
    downloadableFiles: [],
  };

  return {
    reeSpec,
    workspaceSourceState,
    artifactStatus,
    evaluationState: input.evaluationState ?? { evalLevel: 0 },
    inclusionState:
      input.inclusionState ??
      deriveReeInclusionState({
        workspaceSourceState,
        artifactStatus,
        reeSpec,
      }),
    editorUi: {
      locked: false,
      repoMode: "url",
      sourceSnapshotArchiveName: "",
      ...input.editorUi,
    },
    assemblyRuns: {
      actionStates: {},
      badges: {},
      timestamps: {},
      activeRunIds: {},
      ...input.assemblyRuns,
    },
  };
}

export function createReeEditorStateFromAppShell(args: {
  reeDraft: {
    reeSpec: ReeSpec;
    workspaceSourceState: WorkspaceSourceState;
    artifactStatus: ArtifactStatus;
    locked: boolean;
    repoMode: "url" | "upload";
    sourceSnapshotArchiveName: string;
  };
  assemblyRun: {
    evaluationState: EvaluationState;
    actionStates: ActionStates;
    badges: Badges;
    timestamps: Timestamps;
    activeRunIds: Record<string, string>;
  };
}): ReeEditorState {
  const { reeDraft, assemblyRun } = args;
  return createReeEditorState({
    reeSpec: reeDraft.reeSpec,
    workspaceSourceState: reeDraft.workspaceSourceState,
    artifactStatus: reeDraft.artifactStatus,
    evaluationState: assemblyRun.evaluationState,
    editorUi: {
      locked: reeDraft.locked,
      repoMode: reeDraft.repoMode,
      sourceSnapshotArchiveName: reeDraft.sourceSnapshotArchiveName,
    },
    assemblyRuns: {
      actionStates: assemblyRun.actionStates,
      badges: assemblyRun.badges,
      timestamps: assemblyRun.timestamps,
      activeRunIds: assemblyRun.activeRunIds,
    },
  });
}
