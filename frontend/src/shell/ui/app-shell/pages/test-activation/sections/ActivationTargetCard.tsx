import { Ic } from "../../../../shared/components/Icon";
import {
  lgColors,
  lgInfoBanner,
  lgPageColors,
  lgPillChip,
  lgStatusBadge,
  lgStyles,
} from "../../../../theme/lightGlassTheme";
import { F } from "../../../../theme/theme";

interface ActivationTargetCardProps {
  runtimePath: string;
  runtimePathExists: boolean;
  sbomPath: string;
  sbomPathExists: boolean;
}

export function ActivationTargetCard({
  runtimePath,
  runtimePathExists,
  sbomPath,
  sbomPathExists,
}: ActivationTargetCardProps) {
  const runtimeReady = !!runtimePath && runtimePathExists;

  return (
    <div style={{ ...lgStyles.summaryBox, gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
        <div
          style={{ ...lgStyles.sectionIcon, color: lgPageColors.runtimeEnv, width: 42, height: 42 }}
        >
          {Ic.archive(20)}
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
        <span style={lgStatusBadge(runtimeReady)}>{runtimeReady ? "Ready" : "Needs runtime"}</span>
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
        <span style={lgPillChip(runtimeReady)}>
          {runtimeReady ? "Runtime file present" : "Runtime pending"}
        </span>
        <span style={lgPillChip(!!sbomPath && sbomPathExists)}>
          {sbomPath && sbomPathExists ? "SBOM attached" : "SBOM pending"}
        </span>
      </div>
    </div>
  );
}
