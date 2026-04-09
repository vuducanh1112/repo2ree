import {
  S_EXPLORER_MAIN_CONTENT_BG_BLOB_CENTER,
  S_EXPLORER_MAIN_CONTENT_BG_BLOB_LEFT,
  S_EXPLORER_MAIN_CONTENT_BG_BLOB_RIGHT,
  S_EXPLORER_MAIN_CONTENT_BG_LAYER,
  S_EXPLORER_MAIN_CONTENT_INNER,
  S_EXPLORER_MAIN_CONTENT_ROOT,
} from "../../constants/theme";
import {
  ArchivePageContainer,
  FilesPageContainer,
  MetadataPageContainer,
  OverviewPageContainer,
  ServicePageContainer,
  SourcePageContainer,
} from "./containers/ExplorerPageContainers";
import type { useExplorerController } from "./hooks/useExplorerController";

type ExplorerController = ReturnType<typeof useExplorerController>;

interface ExplorerMainContentProps {
  state: ExplorerController["state"];
  commands: ExplorerController["commands"];
}

export function ExplorerMainContent({ state, commands }: ExplorerMainContentProps) {
  return (
    <main style={S_EXPLORER_MAIN_CONTENT_ROOT}>
      <div style={S_EXPLORER_MAIN_CONTENT_BG_LAYER}>
        <div style={S_EXPLORER_MAIN_CONTENT_BG_BLOB_LEFT} />
        <div style={S_EXPLORER_MAIN_CONTENT_BG_BLOB_RIGHT} />
        <div style={S_EXPLORER_MAIN_CONTENT_BG_BLOB_CENTER} />
      </div>
      <div style={S_EXPLORER_MAIN_CONTENT_INNER}>
        <OverviewPageContainer state={state} commands={commands} />
        <SourcePageContainer state={state} commands={commands} />
        <MetadataPageContainer state={state} commands={commands} />
        <ServicePageContainer state={state} commands={commands} />
        <ArchivePageContainer state={state} commands={commands} />
        <FilesPageContainer state={state} commands={commands} />
      </div>
    </main>
  );
}
