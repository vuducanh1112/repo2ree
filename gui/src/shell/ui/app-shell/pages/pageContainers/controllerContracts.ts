import type { AppShellPage } from "@core/app-shell/pages";
import type { ReeFile } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import type { ReeEditorCommands } from "@shell/state/ree-editor/hooks/createReeEditorCommands";
import type { WorkspaceRemoteState } from "@shell/state/ree-editor/hooks/useReeEditor";
import type { ReeIntentState } from "@shell/state/ree-editor/store/reeIntent";
import type { StepRunState } from "@shell/state/ree-editor/store/stepRunState";
import type { UiChromeViewState } from "@shell/state/ree-editor/store/uiChrome";

type MetadataCommands = Pick<ReeEditorCommands, "setReeSpec" | "setPage" | "setFocusedField">;

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
  | "onPersistWorkspaceFile"
>;

type ArchiveCommands = Pick<ReeEditorCommands, "onRunAction" | "setPage">;

export interface MetadataPageContainerProps {
  reeIntent: ReeIntentState;
  stepRuns: StepRunState;
  uiChrome: UiChromeViewState;
  commands: MetadataCommands;
}

export interface ExperimentsPageContainerProps {
  reeIntent: ReeIntentState;
  stepRuns: StepRunState;
  uiChrome: UiChromeViewState;
  workspaceRemote: WorkspaceRemoteState;
  commands: ExperimentCommands;
}

export interface HardwareBomPageContainerProps {
  ree: ReeEditorViewModel;
  stepRuns: StepRunState;
  uiChrome: UiChromeViewState;
  commands: Pick<
    ReeEditorCommands,
    "setReeSpec" | "setPage" | "setFocusedField" | "onRunStep" | "onCancelAction"
  >;
}

export interface StepPageContainerProps {
  /** The page owned by this window, independent of the globally focused page. */
  page: AppShellPage;
  ree: ReeEditorViewModel;
  workspaceRemote: WorkspaceRemoteState;
  stepRuns: StepRunState;
  uiChrome: UiChromeViewState;
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
  /**
   * Which page to render. Several are open at once, each in its own canvas
   * window, so this is not `uiChrome.page` — that one names only the focused
   * window, and every open window renders through here.
   */
  page: AppShellPage;
  ree: ReeEditorViewModel;
  reeIntent: ReeIntentState;
  workspaceRemote: WorkspaceRemoteState;
  stepRuns: StepRunState;
  uiChrome: UiChromeViewState;
  currentReeFiles: ReeFile[];
  commands: ReeEditorCommands;
}
