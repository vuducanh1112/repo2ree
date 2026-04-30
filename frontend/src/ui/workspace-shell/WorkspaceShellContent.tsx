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
  state: WorkspaceShellController["state"];
  commands: WorkspaceShellController["commands"];
}

export function WorkspaceShellContent({ state, commands }: WorkspaceShellContentProps) {
  return (
    <main style={S_WORKSPACE_EDITOR_MAIN_CONTENT_ROOT}>
      <div style={S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_LAYER}>
        <div style={S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_LEFT} />
        <div style={S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_RIGHT} />
        <div style={S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_CENTER} />
      </div>
      <div style={S_WORKSPACE_EDITOR_MAIN_CONTENT_INNER}>
        <OverviewPageContainer state={state} commands={commands} />
        <SourcePageContainer state={state} commands={commands} />
        <MetadataPageContainer state={state} commands={commands} />
        <HardwareBomPageContainer state={state} commands={commands} />
        <WorkflowPageContainer state={state} commands={commands} />
        <ArchivePageContainer state={state} commands={commands} />
        <FilesPageContainer state={state} commands={commands} />
      </div>
    </main>
  );
}
