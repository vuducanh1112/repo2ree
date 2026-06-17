import type { SourceRepoMetadata } from "../../../../../core/workspace/WorkspaceTypes";
import { lgColors, lgStyles } from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/theme";
import { SummaryLine } from "../../components/SummaryLine";

interface Step3Props {
  step3Ready: boolean;
  acquisitionNarrative: string;
  sourceMeta: SourceRepoMetadata | undefined;
}

export function SourceStep3Section(props: Step3Props) {
  const { sourceMeta } = props;
  return (
    <div style={{ borderTop: "1px solid rgba(125, 211, 252, 0.28)", paddingTop: 20 }}>
      <div style={{ ...lgStyles.label, marginBottom: 10 }}>Workspace Snapshot</div>

      {props.step3Ready && sourceMeta ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ fontSize: 13, color: lgColors.textMid, fontFamily: F.sans }}>
            {props.acquisitionNarrative}
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
              gap: "14px 24px",
            }}
          >
            <SummaryLine label="Name" value={sourceMeta.name} />
            <SummaryLine label="Origin" value={sourceMeta.origin || "—"} />
            <SummaryLine label="Type" value={sourceMeta.sourceType || "—"} />
            <SummaryLine label="Size" value={sourceMeta.sizeLabel ?? "—"} />
            <SummaryLine
              label="SWHID"
              value={
                sourceMeta.swhid ? (
                  <span style={{ fontFamily: F.mono, fontSize: 12 }}>{sourceMeta.swhid}</span>
                ) : (
                  "Not computed yet"
                )
              }
            />
          </div>
        </div>
      ) : (
        <div style={lgStyles.helper}>
          Complete the Source Snapshot step above to configure snapshot behavior.
        </div>
      )}
    </div>
  );
}
