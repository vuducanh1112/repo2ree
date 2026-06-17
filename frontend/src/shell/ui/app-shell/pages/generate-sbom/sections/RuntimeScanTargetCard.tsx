import { Ic } from "../../../../shared/components/Icon";
import {
  lgColors,
  lgInfoBanner,
  lgPillChip,
  lgStatusBadge,
  lgStyles,
} from "../../../../theme/lightGlassTheme";
import { F } from "../../../../theme/theme";

interface RuntimeScanTargetCardProps {
  runtimePath: string;
  runtimePathExists: boolean;
  runtimeIsTarball: boolean;
  color: string;
}

export function RuntimeScanTargetCard({
  runtimePath,
  runtimePathExists,
  runtimeIsTarball,
  color,
}: RuntimeScanTargetCardProps) {
  const ready = !!runtimePath && runtimePathExists;
  return (
    <div style={{ ...lgStyles.summaryBox, gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
        <div style={{ ...lgStyles.sectionIcon, color, width: 42, height: 42 }}>
          {runtimeIsTarball ? Ic.archive(20) : Ic.cpu(20)}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 11, color: lgColors.overview, fontWeight: 800 }}>ree.runtime</div>
          <div
            style={{
              marginTop: 3,
              color: runtimePath ? lgColors.text : lgColors.textMuted,
              fontFamily: runtimePath ? F.mono : F.sans,
              fontSize: 13,
              overflowWrap: "anywhere",
            }}
          >
            {runtimePath || "No runtime selected yet"}
          </div>
        </div>
        <span style={lgStatusBadge(ready)}>{ready ? "Ready" : "Needs runtime"}</span>
      </div>

      {runtimePath && !runtimePathExists && (
        <div style={lgInfoBanner("danger")}>
          <span style={{ color: lgColors.danger, display: "flex" }}>{Ic.info(13)}</span>
          <span style={{ fontSize: 12, color: lgColors.danger }}>
            Selected runtime is not present in the current workspace files.
          </span>
        </div>
      )}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <span style={lgPillChip(!!runtimePath)}>{runtimeIsTarball ? "Tarball" : "Runtime"}</span>
      </div>
    </div>
  );
}
