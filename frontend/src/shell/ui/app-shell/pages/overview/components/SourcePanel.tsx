import type React from "react";
import type { ReeEditorViewModel } from "../../../../../../core/ree-editor/reeEditorViewModel";
import { lgStage } from "../../../../theme/lightGlassTheme";
import type { AppShellPage } from "../../../state/pages";
import { PAGE } from "../../../state/pages";
import { OverviewNavButton, OverviewPanel } from "./OverviewPanel";
import { PanelFieldRow } from "./PanelFieldRow";

interface SourcePanelProps {
  ree: ReeEditorViewModel;
  sourceRef: React.RefObject<HTMLDivElement>;
  fileCount: number;
  fileSummary: string;
  onGoField: (key: string) => void;
  onNavigate: (key: AppShellPage) => void;
}

const tint = lgStage.source;

export function SourcePanel({
  ree,
  sourceRef,
  fileCount,
  fileSummary,
  onGoField,
  onNavigate,
}: SourcePanelProps) {
  const sourceInWorkspace = !!ree.sourceAvailable;
  const sourceFromUpload = ree.sourceAcquiredBy === "upload" && !!ree.sourceAvailable;
  const sourceFromDownload = ree.sourceAcquiredBy === "download" && !!ree.sourceAvailable;
  const sourceProvisionStatus = sourceFromUpload
    ? "Uploaded archive"
    : sourceFromDownload
      ? "Downloaded from origin"
      : "Not provided yet";

  return (
    <OverviewPanel
      panelRef={sourceRef}
      tint={tint}
      title="Source"
      active={sourceInWorkspace}
      footer={
        <OverviewNavButton
          tint={tint}
          label="Go to Source"
          onClick={() => onNavigate(PAGE.SOURCE)}
        />
      }
    >
      <PanelFieldRow
        label="Origin URL"
        value={ree.origin_url || null}
        filled={!!ree.origin_url}
        tint={tint}
        onClick={() => onGoField("origin_url")}
      />
      <PanelFieldRow
        label="Provisioning"
        value={sourceProvisionStatus}
        filled={!!ree.sourceAcquiredBy}
        tint={tint}
        onClick={() => onGoField("sourceAcquiredBy")}
      />
      <PanelFieldRow
        label="Origin Type"
        value={ree.source_type || null}
        filled={!!ree.source_type}
        tint={tint}
        onClick={() => onGoField("source_type")}
      />
      <PanelFieldRow
        label="Files"
        value={ree.sourceAvailable ? (fileCount > 0 ? fileSummary : "downloaded") : null}
        filled={!!ree.sourceAvailable}
        emptyText="not downloaded"
        tint={tint}
        isLast
        onClick={() => onNavigate(PAGE.SOURCE)}
      />
    </OverviewPanel>
  );
}
