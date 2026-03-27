import type React from "react";
import { PAGE } from "../../../constants/pages";
import {
  C,
  hoverBrightness,
  S_OVERVIEW_PANEL_BADGE_BASE,
  S_OVERVIEW_PANEL_BUTTON_BASE,
  S_OVERVIEW_PANEL_FIELDS,
  S_OVERVIEW_PANEL_FOOTER,
  S_OVERVIEW_PANEL_HEADER_ROW,
  S_PANEL_HEADER_LABEL,
} from "../../../constants/theme";
import type { Badges, ExplorerPage, FileTreeNode, Ree } from "../../../types";
import { findVirtualFileByName } from "../../../utils";
import { PanelFieldRow } from "./PanelFieldRow";

interface SbomPanelProps {
  ree: Ree;
  files: FileTreeNode[];
  badges: Badges;
  sbomRef: React.RefObject<HTMLDivElement | null>;
  onNavigate: (key: ExplorerPage) => void;
}

const panel = (extra: React.CSSProperties = {}): React.CSSProperties => ({
  ...{
    background: C.surface,
    border: `1px solid ${C.border}`,
    borderRadius: 8,
  },
  ...extra,
});

export function SbomPanel({ ree, files, badges, sbomRef, onNavigate }: SbomPanelProps) {
  const earned = !!badges?.sbom;
  const sbomVal = ree?.sbom ? ree.sbom.trim() : "";
  const sbomFile = sbomVal ? findVirtualFileByName(files, sbomVal) : null;

  const sbomMeta = (() => {
    if (!sbomFile) return null;
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
    <div ref={sbomRef} style={panel({ overflow: "hidden" })}>
      <div style={S_OVERVIEW_PANEL_HEADER_ROW}>
        <div
          style={{
            width: 5,
            height: 5,
            borderRadius: "50%",
            background: "#16a34a",
            boxShadow: earned ? "0 0 5px #16a34a99" : "none",
          }}
        />
        <span style={S_PANEL_HEADER_LABEL}>SBOM</span>
        {earned && (
          <span
            style={{
              ...S_OVERVIEW_PANEL_BADGE_BASE,
              color: "#15803d",
              background: "#f0fdf4",
              border: "1px solid #16a34a40",
            }}
          >
            OK
          </span>
        )}
      </div>

      <div style={S_OVERVIEW_PANEL_FIELDS}>
        <PanelFieldRow
          label="SBOM Path"
          value={sbomVal || null}
          filled={!!sbomVal}
          emptyText="not set"
          dotColor="#16a34a"
          dotGlow="#16a34a99"
          labelColor="#15803d"
          labelBg="#f0fdf4"
          labelBorderColor="#16a34a25"
          onClick={() => onNavigate(PAGE.SBOM)}
          isLast={!sbomMeta?.fmt && sbomMeta?.pkgCount == null}
        />
        {sbomMeta?.fmt && (
          <PanelFieldRow
            label="Format"
            value={sbomMeta.fmt}
            filled
            dotColor="#16a34a"
            dotGlow="#16a34a99"
            labelColor="#15803d"
            labelBg="#f0fdf4"
            labelBorderColor="#16a34a25"
            onClick={() => onNavigate(PAGE.SBOM)}
            isLast={sbomMeta?.pkgCount == null}
          />
        )}
        {sbomMeta?.pkgCount != null && (
          <PanelFieldRow
            label="Packages"
            value={`${sbomMeta.pkgCount} pkg${sbomMeta.pkgCount !== 1 ? "s" : ""}`}
            filled
            dotColor="#16a34a"
            dotGlow="#16a34a99"
            labelColor="#15803d"
            labelBg="#f0fdf4"
            labelBorderColor="#16a34a25"
            onClick={() => onNavigate(PAGE.SBOM)}
            isLast
          />
        )}
      </div>

      <div style={S_OVERVIEW_PANEL_FOOTER}>
        <button
          type="button"
          onClick={() => onNavigate(PAGE.SBOM)}
          style={{
            ...S_OVERVIEW_PANEL_BUTTON_BASE,
            color: "#15803d",
            background: "#f0fdf4",
            border: "1px solid #16a34a40",
          }}
          {...hoverBrightness(95)}
        >
          → Generate SBOM
        </button>
      </div>
    </div>
  );
}
