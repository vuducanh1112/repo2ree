import type {
  SourceOutcomePayload,
  WorkflowRunCompletionPayload,
  WorkspaceEditorAction,
  WorkspaceEditorState,
  WorkspaceEditorStateUpdater,
  WorkspaceHydrationPayload,
} from "./WorkspaceEditorState";

export type StateUpdater<T> = WorkspaceEditorStateUpdater<T>;

export interface WorkspaceEditorContextState {
  workspaceEditor: WorkspaceEditorState;
}

export type {
  SourceOutcomePayload,
  WorkflowRunCompletionPayload,
  WorkspaceEditorAction,
  WorkspaceEditorState,
  WorkspaceHydrationPayload,
};
