import type { ArtifactStatus } from "../../core/artifact/ArtifactStatus";
import { createEmptyReeSpec, type ReeSpec } from "../../core/ree/ReeSpec";
import type { ActionStates, Badges, Timestamps } from "../../core/ree/ReeTypes";
import { type EvaluationState, emptyEvaluationState } from "../../core/review/EvaluationState";
import type { WorkspaceSourceState } from "../../core/workspace/WorkspaceSourceState";

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
  editorUi: ReeEditorUiState;
  assemblyRuns: ReeAssemblyRunsState;
}

interface CreateReeEditorStateInput {
  reeSpec?: ReeSpec;
  workspaceSourceState?: WorkspaceSourceState;
  artifactStatus?: ArtifactStatus;
  evaluationState?: EvaluationState;
  editorUi?: Partial<ReeEditorUiState>;
  assemblyRuns?: Partial<ReeAssemblyRunsState>;
}

export function createReeEditorState(input: CreateReeEditorStateInput = {}): ReeEditorState {
  const reeSpec = input.reeSpec ?? createEmptyReeSpec();
  const workspaceSourceState = input.workspaceSourceState ?? { sourceAvailable: false };
  const artifactStatus = input.artifactStatus ?? { runtimeIncluded: false };

  return {
    reeSpec,
    workspaceSourceState,
    artifactStatus,
    evaluationState: input.evaluationState ?? emptyEvaluationState(),
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

export function createReeEditorStateFromModel(args: {
  reeIntent: { reeSpec: ReeSpec };
  reeSession: { workspaceSourceState: WorkspaceSourceState; artifactStatus: ArtifactStatus };
  uiChrome: { locked: boolean; repoMode: "url" | "upload"; sourceSnapshotArchiveName: string };
  assemblyRun: {
    evaluationState: EvaluationState;
    actionStates: ActionStates;
    badges: Badges;
    timestamps: Timestamps;
    activeRunIds: Record<string, string>;
  };
}): ReeEditorState {
  const { reeIntent, reeSession, uiChrome, assemblyRun } = args;
  return createReeEditorState({
    reeSpec: reeIntent.reeSpec,
    workspaceSourceState: reeSession.workspaceSourceState,
    artifactStatus: reeSession.artifactStatus,
    evaluationState: assemblyRun.evaluationState,
    editorUi: {
      locked: uiChrome.locked,
      repoMode: uiChrome.repoMode,
      sourceSnapshotArchiveName: uiChrome.sourceSnapshotArchiveName,
    },
    assemblyRuns: {
      actionStates: assemblyRun.actionStates,
      badges: assemblyRun.badges,
      timestamps: assemblyRun.timestamps,
      activeRunIds: assemblyRun.activeRunIds,
    },
  });
}
