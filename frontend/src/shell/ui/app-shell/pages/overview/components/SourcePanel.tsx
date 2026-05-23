import React from "react";
import type { ReeEditorViewModel } from "../../../../../../core/ree-editor/reeEditorViewModel";
import type { WorkspaceSourceState } from "../../../../../../core/workspace/WorkspaceSourceState";
import { Toggle } from "../../../../shared/components/Toggle";
import { lgColors, lgStage, lgStyles } from "../../../../theme/lightGlassTheme";
import { F } from "../../../../theme/theme";
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
  onWorkspaceSourceStateChange: React.Dispatch<React.SetStateAction<WorkspaceSourceState>>;
}

const tint = lgStage.source;

export function SourcePanel({
  ree,
  sourceRef,
  fileCount,
  fileSummary,
  onGoField,
  onNavigate,
  onWorkspaceSourceStateChange,
}: SourcePanelProps) {
  const sourceInWorkspace = !!ree.sourceAvailable;
  const sourceFromUpload = ree.sourceAcquiredBy === "upload" && !!ree.sourceAvailable;
  const sourceFromDownload = ree.sourceAcquiredBy === "download" && !!ree.sourceAvailable;
  const sourceProvisionStatus = sourceFromUpload
    ? "Uploaded archive"
    : sourceFromDownload
      ? "Downloaded from origin"
      : "Not provided yet";

  const sourceIncluded = sourceInWorkspace && !!ree.sourceIncluded;
  const canIncludeSource = sourceInWorkspace;

  const toggleSource = () => {
    if (!canIncludeSource) return;
    onWorkspaceSourceStateChange((current) => ({
      ...current,
      sourceIncluded: !sourceIncluded,
    }));
  };

  React.useEffect(() => {
    if (!sourceInWorkspace && ree.sourceIncluded) {
      onWorkspaceSourceStateChange((current) => ({
        ...current,
        sourceIncluded: false,
      }));
    }
  }, [sourceInWorkspace, ree.sourceIncluded, onWorkspaceSourceStateChange]);

  return (
    <OverviewPanel
      panelRef={sourceRef}
      tint={tint}
      title="Source"
      active={sourceInWorkspace}
      headerRight={
        <div style={{ ...lgStyles.overviewIncludeRow, opacity: canIncludeSource ? 1 : 0.45 }}>
          <span
            style={{
              fontSize: 10,
              fontFamily: F.sans,
              fontWeight: 700,
              color: sourceIncluded ? tint.ink : lgColors.textMuted,
            }}
          >
            {sourceIncluded ? "Included" : "Include"}
          </span>
          <Toggle
            on={sourceIncluded}
            disabled={!canIncludeSource}
            color={tint.line}
            onChange={toggleSource}
          />
        </div>
      }
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
