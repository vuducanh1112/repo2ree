import type React from "react";
import type { ReeEditorViewModel } from "../../../../../../core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "../../../../../../core/workspace/FileTree";
import { findFileByWorkspacePath } from "../../../../../../core/workspace/fileTreeTraversal";
import { fmtBytes } from "../../../../shared/formatting";
import { lgStage } from "../../../../theme/lightGlassTheme";
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
}

const tint = lgStage.runtime;

export function RuntimePanel({ ree, files, runtimeRef, onGoField, onNavigate }: RuntimePanelProps) {
  const runtimeVal = ree?.runtime && ree.runtime !== "__skipped__" ? ree.runtime.trim() : "";
  const runtimeFile = runtimeVal ? findFileByWorkspacePath(files, runtimeVal) : null;

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
