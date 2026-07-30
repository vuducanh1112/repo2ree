import { type ArtifactStatus, isSealed } from "../../core/artifact/ArtifactStatus";
import { type EvaluationState, emptyEvaluationState } from "../../core/evaluate/EvaluationState";
import { createEmptyReeSpec, type ReeSpec } from "../../core/ree/ReeSpec";
import type { ActionStates, Badges, Timestamps } from "../../core/ree/ReeTypes";
import type { WorkspaceSourceState } from "../../core/workspace/WorkspaceSourceState";

export interface ReeEditorUiState {
  locked: boolean;
  repoMode: "url" | "upload";
  sourceSnapshotArchiveName: string;
}

export interface ReeStepRunsState {
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
  stepRuns: ReeStepRunsState;
}

interface CreateReeEditorStateInput {
  reeSpec?: ReeSpec;
  workspaceSourceState?: WorkspaceSourceState;
  artifactStatus?: ArtifactStatus;
  evaluationState?: EvaluationState;
  editorUi?: Partial<ReeEditorUiState>;
  stepRuns?: Partial<ReeStepRunsState>;
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
    stepRuns: {
      actionStates: {},
      badges: {},
      timestamps: {},
      activeRunIds: {},
      ...input.stepRuns,
    },
  };
}

export function createReeEditorStateFromModel(args: {
  reeIntent: { reeSpec: ReeSpec };
  reeSession: { workspaceSourceState: WorkspaceSourceState; artifactStatus: ArtifactStatus };
  uiChrome: { locked: boolean; repoMode: "url" | "upload"; sourceSnapshotArchiveName: string };
  stepRuns: {
    evaluationState: EvaluationState;
    actionStates: ActionStates;
    badges: Badges;
    timestamps: Timestamps;
    activeRunIds: Record<string, string>;
  };
}): ReeEditorState {
  const { reeIntent, reeSession, uiChrome, stepRuns } = args;
  return createReeEditorState({
    reeSpec: reeIntent.reeSpec,
    workspaceSourceState: reeSession.workspaceSourceState,
    artifactStatus: reeSession.artifactStatus,
    evaluationState: stepRuns.evaluationState,
    editorUi: {
      // A sealed session is read-only regardless of transient UI flags, so the
      // lock derives from the session's seal stamps. `uiChrome.locked` still
      // covers non-seal locking paths (e.g. step-driven locks).
      locked: uiChrome.locked || isSealed(reeSession.artifactStatus),
      repoMode: uiChrome.repoMode,
      sourceSnapshotArchiveName: uiChrome.sourceSnapshotArchiveName,
    },
    stepRuns: {
      actionStates: stepRuns.actionStates,
      badges: stepRuns.badges,
      timestamps: stepRuns.timestamps,
      activeRunIds: stepRuns.activeRunIds,
    },
  });
}
