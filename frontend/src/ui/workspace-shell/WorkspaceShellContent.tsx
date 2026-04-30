import {
  S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_CENTER,
  S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_LEFT,
  S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_RIGHT,
  S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_LAYER,
  S_WORKSPACE_EDITOR_MAIN_CONTENT_INNER,
  S_WORKSPACE_EDITOR_MAIN_CONTENT_ROOT,
} from "../theme/theme";
import type { useWorkspaceShell } from "./hooks/useWorkspaceShell";
import {
  ArchivePageContainer,
  FilesPageContainer,
  HardwareBomPageContainer,
  MetadataPageContainer,
  OverviewPageContainer,
  SourcePageContainer,
  WorkflowPageContainer,
} from "./pages/WorkspaceShellPageSwitch";

type WorkspaceShellController = ReturnType<typeof useWorkspaceShell>;

interface WorkspaceShellContentProps {
  workspaceDraft: WorkspaceShellController["workspaceDraft"];
  workspaceRemote: WorkspaceShellController["workspaceRemote"];
  workflowRun: WorkspaceShellController["workflowRun"];
  uiChrome: WorkspaceShellController["uiChrome"];
  reeDraft: WorkspaceShellController["reeDraft"];
  level: WorkspaceShellController["level"];
  currentReeFiles: WorkspaceShellController["currentReeFiles"];
  commands: WorkspaceShellController["commands"];
}

export function WorkspaceShellContent(props: WorkspaceShellContentProps) {
  return (
    <main style={S_WORKSPACE_EDITOR_MAIN_CONTENT_ROOT}>
      <div style={S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_LAYER}>
        <div style={S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_LEFT} />
        <div style={S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_RIGHT} />
        <div style={S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_CENTER} />
      </div>
      <div style={S_WORKSPACE_EDITOR_MAIN_CONTENT_INNER}>
        <OverviewPageContainer {...props} />
        <SourcePageContainer {...props} />
        <MetadataPageContainer {...props} />
        <HardwareBomPageContainer {...props} />
        <WorkflowPageContainer {...props} />
        <ArchivePageContainer {...props} />
        <FilesPageContainer {...props} />
      </div>
    </main>
  );
}
