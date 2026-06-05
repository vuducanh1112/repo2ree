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
  AssemblyPageContainer,
  ExperimentsPageContainer,
  FilesPageContainer,
  HardwareBomPageContainer,
  MetadataPageContainer,
  OverviewPageContainer,
  SourcePageContainer,
  WorkbenchPageContainer,
} from "./pages/AppShellPageSwitch";

type AppShellController = ReturnType<typeof useAppShell>;

interface AppShellContentProps {
  ree: AppShellController["ree"];
  reeIntent: AppShellController["reeIntent"];
  workspaceRemote: AppShellController["workspaceRemote"];
  assemblyRun: AppShellController["assemblyRun"];
  uiChrome: AppShellController["uiChrome"];
  evaluation: AppShellController["evaluation"];
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
        <WorkbenchPageContainer {...props} />
        <OverviewPageContainer {...props} />
        <SourcePageContainer {...props} />
        <MetadataPageContainer {...props} />
        <ExperimentsPageContainer {...props} />
        <HardwareBomPageContainer {...props} />
        <AssemblyPageContainer {...props} />
        <ArchivePageContainer {...props} />
        <FilesPageContainer {...props} />
      </div>
    </main>
  );
}
