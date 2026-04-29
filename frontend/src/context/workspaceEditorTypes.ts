import type {
  SourceOutcomePayload,
  WorkflowRunCompletionPayload,
  WorkspaceEditorAction,
  WorkspaceEditorState,
  WorkspaceEditorStateUpdater,
  WorkspaceHydrationPayload,
} from "../application/workspace/workspaceEditorState";

export type StateUpdater<T> = WorkspaceEditorStateUpdater<T>;

export interface WorkspaceEditorContextState {
  explorer: WorkspaceEditorState;
}

export type {
  SourceOutcomePayload,
  WorkflowRunCompletionPayload,
  WorkspaceEditorAction,
  WorkspaceEditorState,
  WorkspaceHydrationPayload,
};
