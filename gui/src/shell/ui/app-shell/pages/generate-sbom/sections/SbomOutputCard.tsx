import { Ic } from "@shell/ui/shared/components/Icon";
import { translucent } from "@shell/ui/theme/appearance";
import {
  lgColors,
  lgInfoBanner,
  lgPillChip,
  lgStatusBadge,
  lgStyles,
} from "@shell/ui/theme/lightGlassTheme";
import { F } from "@shell/ui/theme/theme";

interface SbomOutputCardProps {
  color: string;
  sbomPath: string;
  sbomFilePresent: boolean;
  pkgCount: number | null;
  sbomFormat: string | null;
}

export function SbomOutputCard({
  color,
  sbomPath,
  sbomFilePresent,
  pkgCount,
  sbomFormat,
}: SbomOutputCardProps) {
  if (!sbomPath) {
    return (
      <div style={{ ...lgStyles.summaryBox, alignItems: "flex-start" }}>
        <span style={lgStatusBadge(false)}>Not generated</span>
        <div style={{ color: lgColors.textMuted, fontSize: 13 }}>
          No SBOM has been attached yet. Generate one from the selected runtime.
        </div>
      </div>
    );
  }

  if (!sbomFilePresent) {
    return (
      <div style={lgInfoBanner("danger")}>
        <span style={{ color: lgColors.danger, display: "flex" }}>{Ic.info(13)}</span>
        <span style={{ color: lgColors.danger, fontSize: 12 }}>
          SBOM is set to <code>{sbomPath}</code>, but that file is not present in the REE.
        </span>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "10px 14px",
        background: translucent(color, 6),
        border: `1px solid ${translucent(color, 14)}`,
        borderRadius: 10,
        flexWrap: "wrap",
      }}
    >
      <span style={{ color, display: "flex" }}>{Ic.file(13)}</span>
      <span
        style={{
          fontSize: 13,
          fontFamily: F.mono,
          fontWeight: 700,
          color,
          flex: 1,
          minWidth: 140,
          overflowWrap: "anywhere",
        }}
      >
        {sbomPath}
      </span>
      {sbomFormat && <span style={lgPillChip(true)}>{sbomFormat}</span>}
      {pkgCount !== null && (
        <span style={lgPillChip(true)}>
          {pkgCount} package{pkgCount !== 1 ? "s" : ""}
        </span>
      )}
    </div>
  );
}
