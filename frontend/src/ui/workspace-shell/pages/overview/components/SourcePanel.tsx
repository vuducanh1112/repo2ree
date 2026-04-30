import React from "react";
import type { WorkspaceShellPage } from "../../../../../application/workspace-shell/WorkspaceShellPages";
import { PAGE } from "../../../../../application/workspace-shell/WorkspaceShellPages";
import type { ReeDraftViewModel } from "../../../../../domain/ree/ReeSpec";
import { Toggle } from "../../../../shared/components/Toggle";
import {
  C,
  hoverBrightness,
  S_OVERVIEW_PANEL_BADGE_BASE,
  S_OVERVIEW_PANEL_BUTTON_BASE,
  S_OVERVIEW_PANEL_FIELDS,
  S_OVERVIEW_PANEL_FOOTER,
  S_OVERVIEW_PANEL_HEADER_ROW,
  S_OVERVIEW_PANEL_INCLUDE_LABEL_BASE,
  S_OVERVIEW_PANEL_STATUS_ROW_BASE,
  S_PANEL_HEADER_LABEL,
} from "../../../../theme/theme";
import { PanelFieldRow } from "./PanelFieldRow";

interface SourcePanelProps {
  ree: ReeDraftViewModel;
  sourceRef: React.RefObject<HTMLDivElement>;
  fileCount: number;
  fileSummary: string;
  onGoField: (key: string) => void;
  onNavigate: (key: WorkspaceShellPage) => void;
  onReeChange: (ree: ReeDraftViewModel) => void;
}

const panel = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...{
    background: C.surface,
    border: `1px solid ${C.border}`,
    borderRadius: 8,
  },
  ...extra,
});

export function SourcePanel({
  ree,
  sourceRef,
  fileCount,
  fileSummary,
  onGoField,
  onNavigate,
  onReeChange,
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
    onReeChange({ ...ree, sourceIncluded: !sourceIncluded });
  };

  React.useEffect(() => {
    if (!sourceInWorkspace && ree.sourceIncluded) {
      onReeChange({ ...ree, sourceIncluded: false });
    }
  }, [sourceInWorkspace, ree, onReeChange]);

  return (
    <div ref={sourceRef} style={panel({ overflow: "hidden" })}>
      <div style={S_OVERVIEW_PANEL_HEADER_ROW}>
        <div
          style={{
            width: 5,
            height: 5,
            borderRadius: "50%",
            background: "#f59e0b",
            boxShadow: "0 0 5px #f59e0b99",
          }}
        />
        <span style={S_PANEL_HEADER_LABEL}>Source</span>
        <span
          style={{
            ...S_OVERVIEW_PANEL_BADGE_BASE,
            color: "#92400e",
            background: "#fffbeb",
            border: "1px solid #f59e0b40",
          }}
        >
          SRC
        </span>
        <div style={{ marginLeft: "auto" }}>
          <div
            style={{
              ...S_OVERVIEW_PANEL_STATUS_ROW_BASE,
              opacity: canIncludeSource ? 1 : 0.45,
            }}
          >
            <span
              style={{
                ...S_OVERVIEW_PANEL_INCLUDE_LABEL_BASE,
                color: sourceIncluded ? "#92400e" : C.textMuted,
              }}
            >
              {sourceIncluded ? "Included" : "Include"}
            </span>
            <Toggle
              on={sourceIncluded}
              disabled={!canIncludeSource}
              color="#f59e0b"
              onChange={toggleSource}
            />
          </div>
        </div>
      </div>

      <div style={S_OVERVIEW_PANEL_FIELDS}>
        <PanelFieldRow
          label="Origin URL"
          value={ree.origin_url || null}
          filled={!!ree.origin_url}
          dotColor="#f59e0b"
          dotGlow="#f59e0b99"
          labelColor="#92400e"
          labelBg="#fffbeb"
          labelBorderColor="#f59e0b25"
          onClick={() => onGoField("origin_url")}
        />
        <PanelFieldRow
          label="Origin Provisioning Status"
          value={sourceProvisionStatus}
          filled={!!ree.sourceAcquiredBy}
          dotColor="#f59e0b"
          dotGlow="#f59e0b99"
          labelColor="#92400e"
          labelBg="#fffbeb"
          labelBorderColor="#f59e0b25"
          onClick={() => onGoField("sourceAcquiredBy")}
        />
        <PanelFieldRow
          label="Origin Type"
          value={ree.source_type || null}
          filled={!!ree.source_type}
          dotColor="#f59e0b"
          dotGlow="#f59e0b99"
          labelColor="#92400e"
          labelBg="#fffbeb"
          labelBorderColor="#f59e0b25"
          onClick={() => onGoField("source_type")}
        />
        <PanelFieldRow
          label="Files"
          value={ree.sourceAvailable ? (fileCount > 0 ? fileSummary : "downloaded") : null}
          filled={!!ree.sourceAvailable}
          emptyText="not downloaded"
          dotColor="#f59e0b"
          dotGlow="#f59e0b99"
          labelColor="#92400e"
          labelBg="#fffbeb"
          labelBorderColor="#f59e0b25"
          isLast
          onClick={() => onNavigate(PAGE.SOURCE)}
        />
      </div>

      <div style={S_OVERVIEW_PANEL_FOOTER}>
        <button
          type="button"
          onClick={() => onNavigate(PAGE.SOURCE)}
          style={{
            ...S_OVERVIEW_PANEL_BUTTON_BASE,
            color: "#92400e",
            background: "#fffbeb",
            border: "1px solid #f59e0b40",
          }}
          {...hoverBrightness(95)}
        >
          → Go to Source
        </button>
      </div>
    </div>
  );
}
