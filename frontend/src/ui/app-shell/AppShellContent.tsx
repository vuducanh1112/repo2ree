import {
  S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_CENTER,
  S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_LEFT,
  S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_RIGHT,
  S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_LAYER,
  S_WORKSPACE_EDITOR_MAIN_CONTENT_INNER,
  S_WORKSPACE_EDITOR_MAIN_CONTENT_ROOT,
} from "../theme/theme";
import type { useAppShell } from "./hooks/useAppShell";
import {
  ArchivePageContainer,
  FilesPageContainer,
  HardwareBomPageContainer,
  MetadataPageContainer,
  OverviewPageContainer,
  SourcePageContainer,
  WorkflowPageContainer,
} from "./pages/AppShellPageSwitch";

type AppShellController = ReturnType<typeof useAppShell>;

interface AppShellContentProps {
  ree: AppShellController["ree"];
  reeDraft: AppShellController["reeDraft"];
  workspaceRemote: AppShellController["workspaceRemote"];
  workflowRun: AppShellController["workflowRun"];
  uiChrome: AppShellController["uiChrome"];
  level: AppShellController["level"];
  currentReeFiles: AppShellController["currentReeFiles"];
  commands: AppShellController["commands"];
}

export function AppShellContent(props: AppShellContentProps) {
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
