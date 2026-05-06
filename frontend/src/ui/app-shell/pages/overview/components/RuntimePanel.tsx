import type React from "react";
import type { ReeEditorViewModel } from "../../../../../application/ree-editor/reeEditorViewModel";
import type { AppShellPage } from "../../../../../application/state/pages";
import { PAGE } from "../../../../../application/state/pages";
import type { ArtifactStatus } from "../../../../../core/artifact/ArtifactStatus";
import type { FileTreeNode } from "../../../../../core/workspace/FileTree";
import { findVirtualFileByName } from "../../../../../core/workspace/fileTreeTraversal";
import { Toggle } from "../../../../shared/components/Toggle";
import { fmtBytes } from "../../../../shared/formatting";
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

interface RuntimePanelProps {
  ree: ReeEditorViewModel;
  files: FileTreeNode[];
  runtimeRef: React.RefObject<HTMLDivElement>;
  onGoField: (key: string) => void;
  onNavigate: (key: AppShellPage) => void;
  onArtifactStatusChange: React.Dispatch<React.SetStateAction<ArtifactStatus>>;
}

const panel = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...{
    background: C.surface,
    border: `1px solid ${C.border}`,
    borderRadius: 8,
  },
  ...extra,
});

export function RuntimePanel({
  ree,
  files,
  runtimeRef,
  onGoField,
  onNavigate,
  onArtifactStatusChange,
}: RuntimePanelProps) {
  const runtimeVal = ree?.runtime && ree.runtime !== "__skipped__" ? ree.runtime.trim() : "";
  const runtimeIncluded = !!ree?.runtimeIncluded;
  const canIncludeRuntime = !!runtimeVal;

  const toggleRuntime = () => {
    if (!canIncludeRuntime) return;
    onArtifactStatusChange((current) => ({
      ...current,
      runtimeIncluded: !runtimeIncluded,
    }));
  };

  const runtimeFile = runtimeVal ? findVirtualFileByName(files, runtimeVal) : null;
  const runtimeSizeStr = (() => {
    if (!runtimeFile) return null;
    if (typeof runtimeFile.size === "number" && runtimeFile.size > 0) {
      return fmtBytes(runtimeFile.size);
    }
    const match = (runtimeFile.content || "").match(/Size:\s*(~?[\d.]+ ?[KMGT]?B)/i);
    if (match) return match[1];
    return fmtBytes(new TextEncoder().encode(runtimeFile.content || "").length);
  })();

  return (
    <div ref={runtimeRef} style={panel({ overflow: "hidden" })}>
      <div style={S_OVERVIEW_PANEL_HEADER_ROW}>
        <div
          style={{
            width: 5,
            height: 5,
            borderRadius: "50%",
            background: "#0891b2",
            boxShadow: "0 0 5px #0891b299",
          }}
        />
        <span style={S_PANEL_HEADER_LABEL}>Runtime</span>
        <span
          style={{
            ...S_OVERVIEW_PANEL_BADGE_BASE,
            color: "#164e63",
            background: "#ecfeff",
            border: "1px solid #0891b240",
          }}
        >
          RUN
        </span>
        <div style={{ marginLeft: "auto" }}>
          <div
            style={{
              ...S_OVERVIEW_PANEL_STATUS_ROW_BASE,
              opacity: canIncludeRuntime ? 1 : 0.45,
            }}
          >
            <span
              style={{
                ...S_OVERVIEW_PANEL_INCLUDE_LABEL_BASE,
                color: runtimeIncluded ? "#164e63" : C.textMuted,
              }}
            >
              {runtimeIncluded ? "Included" : "Include"}
            </span>
            <Toggle
              on={runtimeIncluded}
              disabled={!canIncludeRuntime}
              color="#0891b2"
              onChange={toggleRuntime}
            />
          </div>
        </div>
      </div>

      <div style={S_OVERVIEW_PANEL_FIELDS}>
        <PanelFieldRow
          label="Runtime"
          value={runtimeVal || null}
          filled={!!runtimeVal}
          emptyText="not set"
          dotColor="#0891b2"
          dotGlow="#0891b299"
          labelColor="#164e63"
          labelBg="#ecfeff"
          labelBorderColor="#0891b225"
          onClick={() => onNavigate(PAGE.BUILD)}
        />
        {runtimeSizeStr && (
          <PanelFieldRow
            label="Size"
            value={runtimeSizeStr}
            filled={!!runtimeSizeStr}
            dotColor="#0891b2"
            dotGlow="#0891b299"
            labelColor="#164e63"
            labelBg="#ecfeff"
            labelBorderColor="#0891b225"
            onClick={() => onNavigate(PAGE.BUILD)}
          />
        )}
        <PanelFieldRow
          label="Build Script"
          value={ree.build_runtime_script || null}
          filled={!!ree.build_runtime_script}
          emptyText="not set"
          dotColor="#0891b2"
          dotGlow="#0891b299"
          labelColor="#164e63"
          labelBg="#ecfeff"
          labelBorderColor="#0891b225"
          isLast
          onClick={() => onGoField("build_runtime_script")}
        />
      </div>

      <div style={S_OVERVIEW_PANEL_FOOTER}>
        <button
          type="button"
          onClick={() => onNavigate(PAGE.BUILD)}
          style={{
            ...S_OVERVIEW_PANEL_BUTTON_BASE,
            color: "#164e63",
            background: "#ecfeff",
            border: "1px solid #0891b240",
          }}
          {...hoverBrightness(95)}
        >
          → Go to Build Runtime
        </button>
      </div>
    </div>
  );
}
