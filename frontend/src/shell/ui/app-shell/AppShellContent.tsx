import {
  S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_CENTER,
  S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_LEFT,
  S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_RIGHT,
  S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_LAYER,
  S_WORKSPACE_EDITOR_MAIN_CONTENT_INNER,
  S_WORKSPACE_EDITOR_MAIN_CONTENT_ROOT,
} from "../theme/theme";
import {
  ArchivePageContainer,
  AssemblyPageContainer,
  ExperimentsPageContainer,
  HardwareBomPageContainer,
  MetadataPageContainer,
  RuntimeEnvironmentPageContainer,
} from "./pages/AppShellPageSwitch";
import type { AppShellPageContainerProps } from "./pages/pageContainers/shared";

export function AppShellContent(props: AppShellPageContainerProps) {
  return (
    <main style={S_WORKSPACE_EDITOR_MAIN_CONTENT_ROOT}>
      <div style={S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_LAYER}>
        <div style={S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_LEFT} />
        <div style={S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_RIGHT} />
        <div style={S_WORKSPACE_EDITOR_MAIN_CONTENT_BG_BLOB_CENTER} />
      </div>
      <div style={S_WORKSPACE_EDITOR_MAIN_CONTENT_INNER}>
        <MetadataPageContainer {...props} />
        <ExperimentsPageContainer {...props} />
        <HardwareBomPageContainer {...props} />
        <RuntimeEnvironmentPageContainer {...props} />
        <AssemblyPageContainer {...props} />
        <ArchivePageContainer {...props} />
      </div>
    </main>
  );
}
