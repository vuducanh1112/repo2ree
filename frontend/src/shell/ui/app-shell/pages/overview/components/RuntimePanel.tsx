import type React from "react";
import type { ArtifactStatus } from "../../../../../../core/artifact/ArtifactStatus";
import type { ReeEditorViewModel } from "../../../../../../core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "../../../../../../core/workspace/FileTree";
import { findFileByWorkspacePath } from "../../../../../../core/workspace/fileTreeTraversal";
import { Toggle } from "../../../../shared/components/Toggle";
import { fmtBytes } from "../../../../shared/formatting";
import { lgColors, lgStage, lgStyles } from "../../../../theme/lightGlassTheme";
import { F } from "../../../../theme/theme";
import type { AppShellPage } from "../../../state/pages";
import { PAGE } from "../../../state/pages";
import { OverviewNavButton, OverviewPanel } from "./OverviewPanel";
import { PanelFieldRow } from "./PanelFieldRow";

interface RuntimePanelProps {
  ree: ReeEditorViewModel;
  files: FileTreeNode[];
  runtimeRef: React.RefObject<HTMLDivElement>;
  onGoField: (key: string) => void;
  onNavigate: (key: AppShellPage) => void;
  onArtifactStatusChange: React.Dispatch<React.SetStateAction<ArtifactStatus>>;
}

const tint = lgStage.runtime;

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
  const runtimeFile = runtimeVal ? findFileByWorkspacePath(files, runtimeVal) : null;
  const canIncludeRuntime = !!runtimeVal && !!runtimeFile;

  const toggleRuntime = () => {
    if (!canIncludeRuntime) return;
    onArtifactStatusChange((current) => ({
      ...current,
      runtimeIncluded: !runtimeIncluded,
    }));
  };

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
    <OverviewPanel
      panelRef={runtimeRef}
      tint={tint}
      title="Runtime"
      active={!!runtimeVal}
      headerRight={
        <div style={{ ...lgStyles.overviewIncludeRow, opacity: canIncludeRuntime ? 1 : 0.45 }}>
          <span
            style={{
              fontSize: 10,
              fontFamily: F.sans,
              fontWeight: 700,
              color: runtimeIncluded ? tint.ink : lgColors.textMuted,
            }}
          >
            {runtimeIncluded ? "Included" : "Include"}
          </span>
          <Toggle
            on={runtimeIncluded}
            disabled={!canIncludeRuntime}
            color={tint.line}
            onChange={toggleRuntime}
          />
        </div>
      }
      footer={
        <OverviewNavButton
          tint={tint}
          label="Go to Runtime"
          onClick={() => onNavigate(PAGE.BUILD)}
        />
      }
    >
      <PanelFieldRow
        label="Runtime"
        value={runtimeVal || null}
        filled={!!runtimeVal}
        emptyText="not set"
        tint={tint}
        onClick={() => onNavigate(PAGE.BUILD)}
      />
      {runtimeVal && !runtimeFile && (
        <PanelFieldRow
          label="Status"
          value="missing from workspace"
          filled={false}
          tint={lgStage.danger}
          onClick={() => onNavigate(PAGE.BUILD)}
        />
      )}
      {runtimeSizeStr && (
        <PanelFieldRow
          label="Size"
          value={runtimeSizeStr}
          filled={!!runtimeSizeStr}
          tint={tint}
          onClick={() => onNavigate(PAGE.BUILD)}
        />
      )}
      <PanelFieldRow
        label="Build Script"
        value={ree.build_runtime_script || null}
        filled={!!ree.build_runtime_script}
        emptyText="not set"
        tint={tint}
        isLast
        onClick={() => onGoField("build_runtime_script")}
      />
    </OverviewPanel>
  );
}
