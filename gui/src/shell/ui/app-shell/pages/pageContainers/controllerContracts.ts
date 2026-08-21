import type { ReeFile } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import type { ReeEditorCommands } from "@shell/state/ree-editor/hooks/createReeEditorCommands";
import type { WorkspaceRemoteState } from "@shell/state/ree-editor/hooks/useReeEditor";
import type { ReeIntentState } from "@shell/state/ree-editor/store/reeIntent";
import type { StepRunState } from "@shell/state/ree-editor/store/stepRunState";
import type { UiChromeState } from "@shell/state/ree-editor/store/uiChrome";

type MetadataCommands = Pick<
  ReeEditorCommands,
  "setReeSpec" | "setLocked" | "setPage" | "setFocusedField"
>;

type ExperimentCommands = Pick<
  ReeEditorCommands,
  "setReeSpec" | "setPage" | "setFocusedField" | "flushReeIntent" | "onPersistWorkspaceFile"
>;

export type StepCommands = Pick<
  ReeEditorCommands,
  | "setStepParams"
  | "setPage"
  | "onRunStep"
  | "onCancelAction"
  | "setReeSpec"
  | "setArtifactStatus"
  | "setWorkspaceSourceState"
  | "setEvaluationState"
  | "onPersistWorkspaceFile"
>;

type ArchiveCommands = Pick<ReeEditorCommands, "onRunAction" | "setPage">;

export interface MetadataPageContainerProps {
  reeIntent: ReeIntentState;
  stepRuns: StepRunState;
  uiChrome: UiChromeState;
  commands: MetadataCommands;
}

export interface ExperimentsPageContainerProps {
  reeIntent: ReeIntentState;
  stepRuns: StepRunState;
  uiChrome: UiChromeState;
  workspaceRemote: WorkspaceRemoteState;
  commands: ExperimentCommands;
}

export interface HardwareBomPageContainerProps {
  ree: ReeEditorViewModel;
  stepRuns: StepRunState;
  uiChrome: UiChromeState;
  commands: Pick<
    ReeEditorCommands,
    "setReeSpec" | "setLocked" | "setPage" | "setFocusedField" | "onRunStep" | "onCancelAction"
  >;
}

export interface StepPageContainerProps {
  ree: ReeEditorViewModel;
  workspaceRemote: WorkspaceRemoteState;
  stepRuns: StepRunState;
  uiChrome: UiChromeState;
  currentReeFiles: ReeFile[];
  commands: StepCommands;
}

export interface ArchivePageContainerProps {
  ree: ReeEditorViewModel;
  workspaceRemote: WorkspaceRemoteState;
  stepRuns: StepRunState;
  commands: ArchiveCommands;
}

export interface AppShellContentProps {
  ree: ReeEditorViewModel;
  reeIntent: ReeIntentState;
  workspaceRemote: WorkspaceRemoteState;
  stepRuns: StepRunState;
  uiChrome: UiChromeState;
  currentReeFiles: ReeFile[];
  commands: ReeEditorCommands;
}
