import type React from "react";
import type { Badges } from "../../../../../../core/ree/ReeTypes";
import type { ReeEditorViewModel } from "../../../../../../core/ree-editor/reeEditorViewModel";
import type { FileTreeNode } from "../../../../../../core/workspace/FileTree";
import { findVirtualFileByName } from "../../../../../../core/workspace/fileTreeTraversal";
import { lgStage } from "../../../../theme/lightGlassTheme";
import type { AppShellPage } from "../../../state/pages";
import { PAGE } from "../../../state/pages";
import { OverviewNavButton, OverviewPanel } from "./OverviewPanel";
import { PanelFieldRow } from "./PanelFieldRow";

const SBOM_PANEL_PARSE_CHAR_LIMIT = 200_000;

interface SbomPanelProps {
  ree: ReeEditorViewModel;
  files: FileTreeNode[];
  badges: Badges;
  sbomRef: React.RefObject<HTMLDivElement>;
  onNavigate: (key: AppShellPage) => void;
}

const tint = lgStage.sbom;

export function SbomPanel({ ree, files, badges, sbomRef, onNavigate }: SbomPanelProps) {
  const earned = !!badges?.sbom;
  const sbomVal = ree?.sbom ? ree.sbom.trim() : "";
  const sbomFile = sbomVal ? findVirtualFileByName(files, sbomVal) : null;

  const sbomMeta = (() => {
    if (!sbomFile) return null;
    if (!sbomFile.content || sbomFile.content.length > SBOM_PANEL_PARSE_CHAR_LIMIT) {
      return null;
    }
    try {
      const parsed = JSON.parse(sbomFile.content || "{}");
      const pkgCount = Array.isArray(parsed.packages)
        ? parsed.packages.length
        : Array.isArray(parsed.components)
          ? parsed.components.length
          : null;
      const fmt = parsed.spdxVersion
        ? `SPDX ${parsed.spdxVersion.replace("SPDX-", "")}`
        : parsed.bomFormat === "CycloneDX"
          ? `CycloneDX ${parsed.specVersion || ""}`
          : parsed.descriptor?.name === "syft"
            ? "Syft JSON"
            : "JSON";
      return { pkgCount, fmt };
    } catch {
      return null;
    }
  })();

  return (
    <OverviewPanel
      panelRef={sbomRef}
      tint={tint}
      title="SBOM"
      active={earned}
      footer={
        <OverviewNavButton
          tint={tint}
          label="Generate SBOM"
          onClick={() => onNavigate(PAGE.SBOM)}
        />
      }
    >
      <PanelFieldRow
        label="SBOM Path"
        value={sbomVal || null}
        filled={!!sbomVal}
        emptyText="not set"
        tint={tint}
        onClick={() => onNavigate(PAGE.SBOM)}
        isLast={!sbomMeta?.fmt && sbomMeta?.pkgCount == null}
      />
      {sbomMeta?.fmt && (
        <PanelFieldRow
          label="Format"
          value={sbomMeta.fmt}
          filled
          tint={tint}
          onClick={() => onNavigate(PAGE.SBOM)}
          isLast={sbomMeta?.pkgCount == null}
        />
      )}
      {sbomMeta?.pkgCount != null && (
        <PanelFieldRow
          label="Packages"
          value={`${sbomMeta.pkgCount} pkg${sbomMeta.pkgCount !== 1 ? "s" : ""}`}
          filled
          tint={tint}
          onClick={() => onNavigate(PAGE.SBOM)}
          isLast
        />
      )}
    </OverviewPanel>
  );
}
